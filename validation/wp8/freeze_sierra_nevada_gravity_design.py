#!/usr/bin/env python
"""Freeze a response-blind Sierra Nevada gravity spatial design."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/sierra-nevada-gravity-v1"
RAW = DATA / "sierra_nevada_gravity.csv"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/sierra-nevada-gravity-design.json"
BLOCK_KM = 15.0
REFERENCE_LATITUDE = 38.0
EXCLUDED_IDS = {"CH75"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-sierra-gravity-v1|{block}".encode()).hexdigest()[:8],
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
    if (
        manifest["response_values_interpreted_during_acquisition"] != 0
        or member["sha256"] != sha(RAW)
    ):
        raise RuntimeError("Sierra Nevada gravity raw freeze drift")
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    records = []
    source_counts = Counter()
    with RAW.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        index = {name: position for position, name in enumerate(header)}
        required = {"id", "latitude", "longitude", "Source"}
        if not required <= index.keys():
            raise RuntimeError("Sierra Nevada design schema drift")
        for row in reader:
            station_id = row[index["id"]]
            if station_id in EXCLUDED_IDS:
                continue
            latitude = float(row[index["latitude"]])
            longitude = float(row[index["longitude"]])
            x = longitude * lon_scale
            y = latitude * 111.32
            block_x = math.floor(x / BLOCK_KM)
            block_y = math.floor(y / BLOCK_KM)
            block = f"{block_x}:{block_y}"
            source = row[index["Source"]]
            records.append(
                {
                    "id": station_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "source": source,
                    "block": block,
                    "role": role(block),
                }
            )
            source_counts[source] += 1
    block_roles = {}
    for record in records:
        block_roles[record["block"]] = record["role"]
    partition_blocks = {
        assigned: sum(value == assigned for value in block_roles.values())
        for assigned in ("train", "buffer", "calibration", "test")
    }
    partition_rows = {
        assigned: sum(record["role"] == assigned for record in records)
        for assigned in ("train", "buffer", "calibration", "test")
    }
    result = {
        "schema_version": "wp8-sierra-nevada-gravity-design-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "raw_csv_sha256": sha(RAW),
        "selection_fields": ["id", "latitude", "longitude", "Source"],
        "response_fields_interpreted": 0,
        "formal_excluded_ids": sorted(EXCLUDED_IDS),
        "formal_exclusion_reason": (
            "CH75 response values were exposed during an initial schema inspection "
            "before this design was frozen"
        ),
        "spatial_design": {
            "block_size_km": BLOCK_KM,
            "reference_latitude": REFERENCE_LATITUDE,
            "projection": (
                "x=longitude*111.32*cos(38deg), y=latitude*111.32 kilometres"
            ),
            "role_assignment": (
                "SHA-256 wp8-sierra-gravity-v1|block; "
                "20% train, 10% buffer, 10% calibration, 60% test"
            ),
            "success_condition": (
                "training-only residual correlation range strictly below 15 km"
            ),
        },
        "station_count": len(records),
        "source_count": len(source_counts),
        "source_counts": dict(sorted(source_counts.items())),
        "unique_spatial_blocks": len(block_roles),
        "partition_block_counts": partition_blocks,
        "partition_station_counts": partition_rows,
        "coverage_required_test_clusters": 223,
        "design_test_cluster_upper_bound": partition_blocks["test"],
        "design_power_gate_possible": partition_blocks["test"] >= 223,
        "records": records,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "stations": len(records),
                "sources": len(source_counts),
                "blocks": len(block_roles),
                "partitions": partition_blocks,
                "design_power_gate_possible": result[
                    "design_power_gate_possible"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
