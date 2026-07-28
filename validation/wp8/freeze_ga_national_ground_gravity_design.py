#!/usr/bin/env python
"""Freeze a response-blind catalogue-level GA national gravity design."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
CATALOGUE = DATA / "geophysical-datasets-gravity-point.json"
MANIFEST = DATA / "raw-manifest.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-design.json"
BLOCK_KM = 55.0
REFERENCE_LATITUDE = -25.0
FORMAL_EXCLUDED_SURVEYS = ["P199964"]


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(
            f"wp8-ga-national-ground-gravity-v1|{block}".encode()
        ).hexdigest()[:8],
        16,
    ) % 100
    if bucket < 20:
        return "train"
    if bucket < 30:
        return "buffer"
    if bucket < 40:
        return "calibration"
    return "test"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["catalogue"]["sha256"] != sha(CATALOGUE):
        raise RuntimeError("GA national gravity catalogue freeze drift")
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    records = []
    for feature in catalogue["features"]:
        properties = feature["properties"]
        survey_id = f"P{properties['SURVEY_ID']}"
        if survey_id in FORMAL_EXCLUDED_SURVEYS:
            continue
        west, south, east, north = feature["bbox"]
        longitude = (west + east) / 2.0
        latitude = (south + north) / 2.0
        block = (
            f"{math.floor(longitude * lon_scale / BLOCK_KM)}:"
            f"{math.floor(latitude * 111.32 / BLOCK_KM)}"
        )
        records.append(
            {
                "dataset_no": properties["DATASET_NO"],
                "survey_id": survey_id,
                "survey_name": properties["SURVEY_NAME"],
                "declared_stations": properties["GRAVITY_STATIONS"],
                "gravity_reliability": properties["GRAVITY_RELIABILITY"],
                "license": properties["LICENCE"],
                "file_download": properties["FILE_DOWNLOAD"],
                "bbox": feature["bbox"],
                "centroid_longitude": longitude,
                "centroid_latitude": latitude,
                "block": block,
                "role": role(block),
            }
        )
    block_roles = {record["block"]: record["role"] for record in records}
    roles = ("train", "buffer", "calibration", "test")
    partitions = {
        assigned: sum(value == assigned for value in block_roles.values())
        for assigned in roles
    }
    survey_partitions = {
        assigned: sum(record["role"] == assigned for record in records)
        for assigned in roles
    }
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-design-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "catalogue_sha256": sha(CATALOGUE),
        "selection_fields": [
            "DATASET_NO",
            "SURVEY_ID",
            "SURVEY_NAME",
            "GRAVITY_STATIONS",
            "GRAVITY_RELIABILITY",
            "LICENCE",
            "FILE_DOWNLOAD",
            "bbox",
        ],
        "response_fields_interpreted": 0,
        "formal_excluded_surveys": FORMAL_EXCLUDED_SURVEYS,
        "exclusion_reason": (
            "P199964 NetCDF actual_range response metadata was displayed during "
            "schema recoverability probing before this design was frozen."
        ),
        "spatial_design": {
            "block_size_km": BLOCK_KM,
            "reference_latitude": REFERENCE_LATITUDE,
            "unit": "provider survey assigned by catalogue-footprint centroid",
            "role_assignment": (
                "SHA-256 wp8-ga-national-ground-gravity-v1|block; "
                "20% train, 10% buffer, 10% calibration, 60% test"
            ),
            "limitation": (
                "Catalogue-centroid design is a nominal upper bound. A station-level "
                "geometry audit must exclude cross-role footprint leakage before any "
                "formal response unseal."
            ),
        },
        "survey_count": len(records),
        "declared_station_total": sum(
            int(record["declared_stations"]) for record in records
        ),
        "unique_spatial_blocks": len(block_roles),
        "partition_block_counts": partitions,
        "partition_survey_counts": survey_partitions,
        "design_test_cluster_upper_bound": partitions["test"],
        "design_power_gate_possible": partitions["test"] >= 223,
        "records": records,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "surveys": len(records),
            "stations": result["declared_station_total"],
            "blocks": len(block_roles),
            "partitions": partitions,
            "design_power_gate_possible": result["design_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
