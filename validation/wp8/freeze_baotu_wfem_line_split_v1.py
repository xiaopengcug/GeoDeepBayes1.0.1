#!/usr/bin/env python
"""Freeze Baotu Spring WFEM whole-line roles before response interpretation."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = (
    ROOT
    / "_bmad-output/planning-artifacts/research/open-data/wfem"
    / "Zenodo_BaotuSpring_WFEM_2025"
)
SOURCE = DATA / "source_record.zenodo.json"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "baotu-wfem-line-split-v1.json"
)
SALT = "GeoDeepBayes-WP8-Baotu-WFEM-line-v1"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def role(name: str) -> str:
    bucket = int(
        hashlib.sha256(f"{SALT}|{name}".encode()).hexdigest()[:12], 16
    ) % 10
    if bucket < 3:
        return "train"
    if bucket == 3:
        return "buffer"
    if bucket == 4:
        return "calibration"
    return "test"


def main() -> None:
    record = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected = {item["key"]: item["size"] for item in record["files"]}
    files = sorted(DATA.glob("*.dat"))
    if len(files) != 27 or {path.name for path in files} != set(expected):
        raise RuntimeError("Baotu WFEM file population drift")
    lines = []
    for path in files:
        if path.stat().st_size != expected[path.name]:
            raise RuntimeError(f"Baotu WFEM size drift: {path.name}")
        lines.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "role": role(path.name),
            }
        )
    counts = Counter(item["role"] for item in lines)
    result = {
        "schema_version": "wp8-baotu-wfem-line-split-v1",
        "source_record_sha256": sha(SOURCE),
        "doi": record["metadata"]["doi"],
        "license": record["metadata"]["license"]["id"],
        "selection_unit": "whole named WFEM line file",
        "selection_inputs": "filename, byte size and checksum only",
        "selection_frozen_before_response_interpretation": True,
        "role_rule": (
            "SHA256(salt|filename) modulo 10: 30% train, 10% buffer, "
            "10% calibration, 50% test"
        ),
        "salt_sha256": hashlib.sha256(SALT.encode()).hexdigest(),
        "line_count": len(lines),
        "partition_line_counts": dict(counts),
        "lines": lines,
        "required_test_clusters": 223,
        "line_level_test_cluster_upper_bound": counts["test"],
        "design_cluster_gate_possible": counts["test"] >= 223,
        "response_values_interpreted_during_selection": 0,
        "calibration_response_values_interpreted": 0,
        "test_response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "partition_line_counts": dict(counts),
                "line_level_test_cluster_upper_bound": counts["test"],
                "design_cluster_gate_possible": False,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
