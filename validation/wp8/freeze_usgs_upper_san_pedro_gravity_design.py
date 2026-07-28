#!/usr/bin/env python
"""Freeze a response-blind spatial design for USGS OFR 00-138 Appendix 4."""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-upper-san-pedro-gravity-v1"
RAW = DATA / "appendix-4.html"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-upper-san-pedro-gravity-design.json"
BLOCK_KM = 5.0
REFERENCE_LATITUDE = 32.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-upper-san-pedro-gravity-v1|{block}".encode()).hexdigest()[:8],
        16,
    ) % 100
    if bucket < 20:
        return "train"
    if bucket < 30:
        return "buffer"
    if bucket < 40:
        return "calibration"
    return "test"


def geometry_records() -> list[dict[str, object]]:
    source = RAW.read_text(encoding="windows-1252")
    paragraphs = re.findall(r"<p>(.*?)</p>", source, flags=re.I | re.S)
    records = []
    for ordinal, paragraph in enumerate(paragraphs):
        text = html.unescape(re.sub(r"<[^>]+>", " ", paragraph))
        tokens = text.split()
        id_length = None
        for length in range(1, min(6, len(tokens))):
            if len(tokens) == 14 + 2 * length and tokens[:length] == tokens[-length:]:
                id_length = length
                break
        if id_length is None:
            continue
        middle = tokens[id_length:-id_length]
        try:
            latitude = float(middle[0]) + float(middle[1]) / 60.0
            longitude = -(abs(float(middle[2])) + float(middle[3]) / 60.0)
        except (ValueError, IndexError):
            continue
        x = longitude * 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
        y = latitude * 111.32
        block = f"{math.floor(x / BLOCK_KM)}:{math.floor(y / BLOCK_KM)}"
        records.append(
            {
                "record_key": f"{ordinal}:{' '.join(tokens[:id_length])}",
                "latitude": latitude,
                "longitude": longitude,
                "block": block,
                "role": role(block),
            }
        )
    return records


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    member = next(item for item in manifest["members"] if item["path"] == RAW.name)
    if member["sha256"] != sha(RAW):
        raise RuntimeError("Upper San Pedro raw freeze drift")
    records = geometry_records()
    block_roles = {record["block"]: record["role"] for record in records}
    roles = ("train", "buffer", "calibration", "test")
    partition_blocks = {
        assigned: sum(value == assigned for value in block_roles.values())
        for assigned in roles
    }
    partition_rows = {
        assigned: sum(record["role"] == assigned for record in records)
        for assigned in roles
    }
    result = {
        "schema_version": "wp8-upper-san-pedro-gravity-design-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "raw_html_sha256": sha(RAW),
        "selection_fields": ["record ordinal", "station id", "latitude", "longitude"],
        "response_fields_interpreted": 0,
        "malformed_source_records_excluded": 1,
        "spatial_design": {
            "block_size_km": BLOCK_KM,
            "reference_latitude": REFERENCE_LATITUDE,
            "role_assignment": (
                "SHA-256 wp8-upper-san-pedro-gravity-v1|block; "
                "20% train, 10% buffer, 10% calibration, 60% test"
            ),
            "success_condition": (
                "training-only residual correlation range strictly below 5 km "
                "and at least 223 correlation-adjusted sealed test clusters"
            ),
        },
        "station_records": len(records),
        "unique_spatial_blocks": len(block_roles),
        "partition_block_counts": partition_blocks,
        "partition_station_counts": partition_rows,
        "coverage_required_test_clusters": 223,
        "design_test_cluster_upper_bound": partition_blocks["test"],
        "design_power_gate_possible": partition_blocks["test"] >= 223,
        "design_impossibility_reason": (
            None
            if partition_blocks["test"] >= 223
            else "Even the finest defensible 5-km geometry-only blocks yield fewer "
            "than 223 sealed test blocks before correlation adjustment."
        ),
        "records": records,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "records": len(records),
                "blocks": len(block_roles),
                "partitions": partition_blocks,
                "design_power_gate_possible": result["design_power_gate_possible"],
            }
        )
    )


if __name__ == "__main__":
    main()
