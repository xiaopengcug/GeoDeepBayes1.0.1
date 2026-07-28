#!/usr/bin/env python
"""Freeze a response-blind 5-km Ridgecrest gravity spatial design."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-ridgecrest-gravity-v1"
RAW = DATA / "250130_gravity_data_final.csv"
MANIFEST = DATA / "raw-manifest.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-ridgecrest-gravity-design.json"
BLOCK_KM = 5.0
REFERENCE_LATITUDE = 35.5


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-ridgecrest-gravity-v1|{block}".encode()).hexdigest()[:8],
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
    member = next(item for item in manifest["members"] if item["path"] == RAW.name)
    if member["sha256"] != sha(RAW):
        raise RuntimeError("Ridgecrest raw freeze drift")
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    records = []
    with RAW.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            latitude = float(row["lat"])
            longitude = float(row["long"])
            block = (
                f"{math.floor(longitude * lon_scale / BLOCK_KM)}:"
                f"{math.floor(latitude * 111.32 / BLOCK_KM)}"
            )
            records.append(
                {
                    "id": row["id"],
                    "latitude": latitude,
                    "longitude": longitude,
                    "source": row["source"],
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
    result = {
        "schema_version": "wp8-ridgecrest-gravity-design-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "raw_csv_sha256": sha(RAW),
        "selection_fields": ["id", "lat", "long", "source"],
        "response_fields_interpreted": 0,
        "spatial_design": {
            "block_size_km": BLOCK_KM,
            "reference_latitude": REFERENCE_LATITUDE,
            "role_assignment": (
                "SHA-256 wp8-ridgecrest-gravity-v1|block; "
                "20% train, 10% buffer, 10% calibration, 60% test"
            ),
            "success_condition": (
                "training-only residual correlation range strictly below 5 km and "
                "at least 223 correlation-adjusted sealed test clusters"
            ),
        },
        "station_count": len(records),
        "source_count": len({record["source"] for record in records}),
        "unique_spatial_blocks": len(block_roles),
        "partition_block_counts": partitions,
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
            "stations": len(records),
            "blocks": len(block_roles),
            "partitions": partitions,
            "design_power_gate_possible": result["design_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
