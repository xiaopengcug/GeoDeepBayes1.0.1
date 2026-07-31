# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf==6.6.2"]
# ///
"""Freeze a response-blind 20-km spatial design from OFR 85-254 geometry."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-saudi-regional-gravity-v1"
PDF = DATA / "report.pdf"
MANIFEST = DATA / "raw-manifest.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-saudi-regional-gravity-design.json"
BLOCK_KM = 20.0
REFERENCE_LATITUDE = 21.0
GEOMETRY = re.compile(
    r"^\s*(\d+)\s+(.+?)\s+(1[7-9]|2[0-4])\s+"
    r"([0-9]+(?:[.,]\s*[0-9]+)?)\s+(3[9]|4[0-7])\s+"
    r"([0-9]+(?:[.,]\s*[0-9]+)?)\s+"
)


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-saudi-gravity-v1|{block}".encode()).hexdigest()[:8], 16
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
    report = next(item for item in manifest["members"] if item["path"] == "report.pdf")
    if report["sha256"] != sha(PDF):
        raise RuntimeError("Saudi gravity PDF drift")
    candidates: dict[int, dict[str, object]] = {}
    conflicts: set[int] = set()
    reader = PdfReader(PDF)
    for page in reader.pages[66:]:
        for line in (page.extract_text(extraction_mode="layout") or "").splitlines():
            match = GEOMETRY.match(line)
            if not match:
                continue
            sequence = int(match.group(1))
            latitude = float(match.group(3)) + float(
                match.group(4).replace(",", ".").replace(" ", "")
            ) / 60.0
            longitude = float(match.group(5)) + float(
                match.group(6).replace(",", ".").replace(" ", "")
            ) / 60.0
            current = {"sequence": sequence, "latitude": latitude, "longitude": longitude}
            prior = candidates.get(sequence)
            if prior is None:
                candidates[sequence] = current
            elif prior != current:
                conflicts.add(sequence)
    for sequence in conflicts:
        candidates.pop(sequence, None)
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    records = []
    for sequence in sorted(candidates):
        record = candidates[sequence]
        block = (
            f"{math.floor(float(record['longitude']) * lon_scale / BLOCK_KM)}:"
            f"{math.floor(float(record['latitude']) * 111.32 / BLOCK_KM)}"
        )
        records.append({**record, "block": block, "role": role(block)})
    block_roles = {record["block"]: record["role"] for record in records}
    roles = ("train", "buffer", "calibration", "test")
    partitions = {
        assigned: sum(value == assigned for value in block_roles.values())
        for assigned in roles
    }
    result = {
        "schema_version": "wp8-saudi-regional-gravity-design-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "raw_pdf_sha256": sha(PDF),
        "extractor": "pypdf==6.6.2 layout mode",
        "selection_fields": ["sequence", "station id", "latitude", "longitude"],
        "response_fields_interpreted": 0,
        "geometry_records": len(records),
        "conflicting_geometry_sequences_excluded": sorted(conflicts),
        "spatial_design": {
            "block_size_km": BLOCK_KM,
            "reference_latitude": REFERENCE_LATITUDE,
            "role_assignment": (
                "SHA-256 wp8-saudi-gravity-v1|block; "
                "20% train, 10% buffer, 10% calibration, 60% test"
            ),
            "success_condition": (
                "training-only residual correlation range strictly below 20 km and "
                "at least 223 strict, correlation-adjusted sealed test clusters"
            ),
        },
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
            "geometry_records": len(records),
            "blocks": len(block_roles),
            "partitions": partitions,
            "design_power_gate_possible": result["design_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
