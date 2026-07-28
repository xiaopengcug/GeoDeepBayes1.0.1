#!/usr/bin/env python
"""Freeze a response-blind 5-km design for MRT Tasmania gravity."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/mrt-tasmania-gravity-v1"
RAW = DATA / "Gravity_Data_Geopackage.gpkg"
ARCHIVE = DATA / "Gravity_Data_Geopackage.zip"
MANIFEST = DATA / "raw-manifest.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/mrt-tasmania-gravity-design.json"
BLOCK_M = 5_000.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-mrt-tasmania-gravity-v1|{block}".encode()).hexdigest()[:8],
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
    if manifest["archive"]["sha256"] != sha(ARCHIVE):
        raise RuntimeError("MRT Tasmania gravity archive freeze drift")
    connection = sqlite3.connect(f"file:{RAW}?mode=ro", uri=True)
    # Deliberately exclude gravity/anomaly/correction response columns.
    rows = connection.execute(
        """
        SELECT READING_ID, STATION_NUMBER, DATA_SET_NAME, EASTING, NORTHING
        FROM GRAVITY_POINTS
        WHERE EASTING IS NOT NULL AND NORTHING IS NOT NULL
        """
    )
    records = []
    for reading_id, station, source, easting, northing in rows:
        block = f"{int(easting // BLOCK_M)}:{int(northing // BLOCK_M)}"
        records.append(
            {
                "reading_id": reading_id,
                "station_number": station,
                "source": source,
                "easting": easting,
                "northing": northing,
                "block": block,
                "role": role(block),
            }
        )
    connection.close()
    block_roles = {record["block"]: record["role"] for record in records}
    roles = ("train", "buffer", "calibration", "test")
    partitions = {
        assigned: sum(value == assigned for value in block_roles.values())
        for assigned in roles
    }
    result = {
        "schema_version": "wp8-mrt-tasmania-gravity-design-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "raw_archive_sha256": sha(ARCHIVE),
        "raw_geopackage_sha256": sha(RAW),
        "selection_fields": [
            "READING_ID",
            "STATION_NUMBER",
            "DATA_SET_NAME",
            "EASTING",
            "NORTHING",
        ],
        "excluded_response_fields": [
            "OBSERV_GRAVITY",
            "THEOR_GRAVITY",
            "BOUGUER_ANOMALY",
            "TERRAIN_CORR",
        ],
        "response_fields_interpreted": 0,
        "spatial_design": {
            "block_size_m": BLOCK_M,
            "role_assignment": (
                "SHA-256 wp8-mrt-tasmania-gravity-v1|block; "
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
            "sources": result["source_count"],
            "blocks": len(block_roles),
            "partitions": partitions,
            "design_power_gate_possible": result["design_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
