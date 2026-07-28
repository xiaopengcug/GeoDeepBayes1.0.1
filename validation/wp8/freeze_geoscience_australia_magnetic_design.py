#!/usr/bin/env python
"""Freeze a response-blind national design from the GA magnetic WFS catalogue."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-catalog-v1"
CATALOGUE = DATA / "magnetic-catalog.geojson"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
LATITUDE_STEP_DEG = 0.5
MAX_LINE_SPACING_M = 10_000.0
PRIOR_CORRELATION_RANGE_KM = 21.0
FORMAL_EXCLUDED_DATASET_NUMBERS = {17638}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        hashlib.sha256(f"wp8-ga-national-magnetic-v1|{cell}".encode()).hexdigest()[:8],
        16,
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
    member = next(
        item for item in manifest["members"] if item["path"] == CATALOGUE.name
    )
    if (
        manifest["catalogue_is_design_metadata_only"] is not True
        or manifest["magnetic_response_values_interpreted"] != 0
        or member["sha256"] != sha(CATALOGUE)
    ):
        raise RuntimeError("GA catalogue freeze drift")
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    required = {
        "AREA_KM2",
        "FILE_DOWNLOAD",
        "FLIGHT_HEIGHT_AGL",
        "LICENCE",
        "LINE_AZIMUTH",
        "LINE_KM",
        "MAX_LAT_WGS84",
        "MAX_LINE_SPACING_M",
        "MAX_LONG_WGS84",
        "MIN_LAT_WGS84",
        "MIN_LINE_SPACING_M",
        "MIN_LONG_WGS84",
    }
    products = []
    for feature in catalogue["features"]:
        properties = feature["properties"]
        if (
            properties.get("DATASET_TYPE") == "line"
            and properties.get("MEASURE_SUB_TYPE") == "magnetic line data"
            and properties.get("SURVEY_TYPE") == "air"
            and all(properties.get(name) is not None for name in required)
            and float(properties["MAX_LINE_SPACING_M"]) <= MAX_LINE_SPACING_M
            and feature.get("geometry") is not None
            and int(properties["DATASET_NO"]) not in FORMAL_EXCLUDED_DATASET_NUMBERS
        ):
            products.append(feature)

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
    product_metadata = []
    for feature in products:
        properties = feature["properties"]
        product_metadata.append(
            {
                name: properties.get(name)
                for name in (
                    "DATASET_NO",
                    "SURVEY_ID",
                    "SURVEY_NAME",
                    "STATE",
                    "SURVEY_START_DATE",
                    "SURVEY_END_DATE",
                    "AREA_KM2",
                    "FLIGHT_HEIGHT_AGL",
                    "MIN_LINE_SPACING_M",
                    "MAX_LINE_SPACING_M",
                    "LINE_KM",
                    "LINE_AZIMUTH",
                    "LICENCE",
                    "FILE_SIZE",
                    "FILE_DOWNLOAD",
                    "DOI",
                )
            }
        )
    product_metadata.sort(key=lambda item: int(item["DATASET_NO"]))
    result = {
        "schema_version": "wp8-geoscience-australia-magnetic-design-v1",
        "catalogue_manifest_sha256": sha(MANIFEST),
        "catalogue_sha256": sha(CATALOGUE),
        "selection_is_design_metadata_only": True,
        "magnetic_response_values_interpreted": 0,
        "eligible_product_count": len(products),
        "formal_excluded_dataset_numbers": sorted(FORMAL_EXCLUDED_DATASET_NUMBERS),
        "formal_exclusion_reason": (
            "dataset 17638 NetCDF response actual_range metadata was exposed during "
            "the training schema probe; it remains training/development-only"
        ),
        "unique_survey_count": len(
            {feature["properties"]["SURVEY_ID"] for feature in products}
        ),
        "selection_contract": {
            "method": "magnetic",
            "dataset_type": "line",
            "survey_type": "air",
            "required_fields": sorted(required),
            "maximum_line_spacing_m": MAX_LINE_SPACING_M,
            "all_licenses_explicit": all(
                bool(feature["properties"]["LICENCE"]) for feature in products
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
        "products": product_metadata,
        "cells": cells,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "warning": (
            "This is a catalogue-only upper bound. Located-line NetCDF schemas, "
            "actual observation support, uncertainty fields, training-only national "
            "correlation and byte integrity must pass before formal qualification."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "products": len(products),
                "surveys": result["unique_survey_count"],
                "cells": len(cells),
                "partitions": counts,
            }
        )
    )


if __name__ == "__main__":
    main()
