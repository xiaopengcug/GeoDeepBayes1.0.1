#!/usr/bin/env python
"""Freeze a response-blind national spatial design from the GA AEM catalogue."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-aem-catalog-v1"
CATALOGUE = DATA / "aem-catalog.geojson"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-aem-design.json"
LATITUDE_STEP_DEG = 0.5
PRIOR_CORRELATION_RANGE_KM = 21.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def ring_contains(ring: list, x: float, y: float) -> bool:
    inside = False
    for index in range(len(ring)):
        x1, y1 = ring[index - 1][:2]
        x2, y2 = ring[index][:2]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def geometry_contains(geometry: dict, x: float, y: float) -> bool:
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    return any(
        ring_contains(polygon[0], x, y)
        and not any(ring_contains(hole, x, y) for hole in polygon[1:])
        for polygon in polygons
    )


def role(cell: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-ga-aem-v1|{cell}".encode()).hexdigest()[:8], 16
    ) % 100
    if bucket < 45:
        return "train"
    if bucket < 60:
        return "buffer"
    if bucket < 75:
        return "calibration"
    return "test"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    member = next(item for item in manifest["members"] if item["path"] == CATALOGUE.name)
    if (
        manifest["catalogue_is_design_metadata_only"] is not True
        or manifest["aem_response_values_interpreted"] != 0
        or member["sha256"] != sha(CATALOGUE)
    ):
        raise RuntimeError("GA AEM catalogue freeze drift")
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    products = [
        feature
        for feature in catalogue["features"]
        if feature.get("geometry")
        and feature["properties"].get("SURVEY_TYPE") == "air"
        and feature["properties"].get("MEASURE_TYPE") == "electromagnetic"
        and feature["properties"].get("LICENCE")
        and feature["properties"].get("LICENCE") != "None"
    ]
    cells = []
    latitude = -44.0
    while latitude <= -9.0:
        longitude_step = LATITUDE_STEP_DEG / max(
            0.2, math.cos(math.radians(latitude))
        )
        longitude = 112.0
        while longitude <= 154.5:
            covering = []
            for feature in products:
                properties = feature["properties"]
                if not (
                    float(properties["MIN_LONG_WGS84"])
                    <= longitude
                    <= float(properties["MAX_LONG_WGS84"])
                    and float(properties["MIN_LAT_WGS84"])
                    <= latitude
                    <= float(properties["MAX_LAT_WGS84"])
                ):
                    continue
                if geometry_contains(feature["geometry"], longitude, latitude):
                    covering.append(int(properties["DATASET_NO"]))
            if covering:
                cell = f"{latitude:.6f}:{longitude:.6f}"
                cells.append(
                    {
                        "cell": cell,
                        "latitude": latitude,
                        "longitude": longitude,
                        "role": role(cell),
                        "covering_dataset_numbers": sorted(covering),
                    }
                )
            longitude += longitude_step
        latitude += LATITUDE_STEP_DEG
    counts = {
        assigned: sum(cell["role"] == assigned for cell in cells)
        for assigned in ("train", "buffer", "calibration", "test")
    }
    metadata_fields = (
        "DATASET_NO",
        "SURVEY_ID",
        "SURVEY_NAME",
        "STATE",
        "SURVEY_START_DATE",
        "SURVEY_END_DATE",
        "DATASET_TYPE",
        "ARCHIVE_FILE_DESC",
        "ARCHIVE_FILE_FORMAT",
        "AEM_SYSTEM",
        "AREA_KM2",
        "AIRCRAFT_FLIGHT_HEIGHT_AGL",
        "TRANSMITTER_NOMINAL_TERRAIN_CLEARANCE_M",
        "RECEIVER_NOMINAL_TERRAIN_CLEARANCE_M",
        "MIN_LINE_SPACING_M",
        "MAX_LINE_SPACING_M",
        "LINE_KM",
        "LICENCE",
        "FILE_SIZE",
        "FILE_DOWNLOAD",
        "ECAT_PID",
    )
    product_metadata = [
        {name: feature["properties"].get(name) for name in metadata_fields}
        for feature in products
    ]
    product_metadata.sort(key=lambda item: int(item["DATASET_NO"]))
    unique_surveys = {
        str(feature["properties"]["SURVEY_ID"]) for feature in products
    }
    result = {
        "schema_version": "wp8-geoscience-australia-aem-design-v1",
        "catalogue_manifest_sha256": sha(MANIFEST),
        "catalogue_sha256": sha(CATALOGUE),
        "selection_is_design_metadata_only": True,
        "aem_response_values_interpreted": 0,
        "catalogue_product_count": len(catalogue["features"]),
        "eligible_open_license_product_count": len(products),
        "unique_survey_count": len(unique_surveys),
        "selection_contract": {
            "method": "airborne electromagnetics",
            "survey_type": "air",
            "measure_type": "electromagnetic",
            "explicit_nonempty_product_license": True,
            "all_selected_licenses_are_cc_by_4_0": all(
                str(feature["properties"]["LICENCE"]).startswith("CC BY 4.0")
                for feature in products
            ),
        },
        "spatial_design": {
            "latitude_step_deg": LATITUDE_STEP_DEG,
            "longitude_step_rule": "0.5 degrees divided by cosine(latitude)",
            "minimum_nominal_center_spacing_km": 55.0,
            "external_training_prior_correlation_range_km": PRIOR_CORRELATION_RANGE_KM,
            "centers_are_farther_apart_than_prior_range": True,
            "coverage_rule": "cell center lies in at least one official survey polygon",
        },
        "partition_counts": counts,
        "coverage_required_test_clusters": 223,
        "design_test_cluster_upper_bound": counts["test"],
        "design_power_gate_possible": counts["test"] >= 223,
        "survey_independence_upper_bound": len(unique_surveys),
        "products": product_metadata,
        "cells": cells,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "warning": (
            "This is a polygon-catalogue upper bound. Product bytes, located-line "
            "support, waveform/source-receiver geometry, uncertainty fields and a "
            "training-only AEM correlation audit remain required."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "products": len(products),
                "surveys": len(unique_surveys),
                "cells": len(cells),
                "partitions": counts,
            }
        )
    )


if __name__ == "__main__":
    main()
