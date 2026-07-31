#!/usr/bin/env python
"""Freeze an outcome-blind East River AEM split using design columns only."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/east-river-aem-v1"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/east-river-aem-design-split.json"
SERIES = tuple(sorted(RAW.glob("EastRiver2017_ProcessedAEMData_*series.csv")))
PREFIX = ("LINE", "TIMESTAMP", "E_UTM13N", "N_UTM13N", "ELEVATION", "ALT")


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def role(easting: float) -> str:
    """Periodic 1-km stripes with explicit buffers between held-out roles."""
    stripe = math.floor(easting / 1000.0) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def main() -> None:
    if len(SERIES) != 4:
        raise RuntimeError("expected four immutable processed-AEM series files")
    rows = 0
    lines: dict[str, set[str]] = {name: set() for name in ("train", "buffer", "calibration", "test")}
    cells: dict[str, set[tuple[int, int]]] = {
        name: set() for name in ("train", "buffer", "calibration", "test")
    }
    coordinate_hash = hashlib.sha256()
    for path in SERIES:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            header = stream.readline().rstrip("\r\n").split(",")
            if tuple(header[:6]) != PREFIX:
                raise RuntimeError(f"design-column drift: {path.name}: {header[:6]}")
            for line in stream:
                # The seventh field and the entire response tail remain one
                # unparsed string and are immediately discarded.
                fields = line.rstrip("\r\n").split(",", 6)
                if len(fields) != 7:
                    raise RuntimeError(f"short row in {path.name}")
                line_id, timestamp, east_text, north_text, elevation, altitude, _unparsed = fields
                east = float(east_text)
                north = float(north_text)
                assigned = role(east)
                lines[assigned].add(line_id)
                cells[assigned].add((math.floor(east / 500.0), math.floor(north / 500.0)))
                coordinate_hash.update(
                    f"{path.name}|{line_id}|{timestamp}|{east_text}|{north_text}|{elevation}|{altitude}\n".encode()
                )
                rows += 1
    result = {
        "schema_version": "wp8-east-river-aem-design-split-v1",
        "candidate_status": "design_split_frozen_before_response_interpretation",
        "doi": "10.5066/P949ZCZ8",
        "cluster_candidate_definition": "occupied 500 m x 500 m spatial cell",
        "assignment": {
            "axis": "WGS84 UTM zone 13N easting",
            "period_m": 12000,
            "stripe_width_m": 1000,
            "stripe_roles": {
                "buffer": [0, 6, 9],
                "train": [1, 2, 3, 4, 5],
                "calibration": [7, 8],
                "test": [10, 11],
            },
            "boundary_statement": "every held-out stripe is separated from training stripes by a 1-km buffer",
        },
        "source_members": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}
            for path in SERIES
        ],
        "design_rows": rows,
        "design_line_counts": {name: len(value) for name, value in lines.items()},
        "candidate_500m_cell_counts": {name: len(value) for name, value in cells.items()},
        "design_coordinate_stream_sha256": coordinate_hash.hexdigest(),
        "columns_parsed": list(PREFIX),
        "numdata_parsed": False,
        "observation_response_values_parsed": False,
        "formal_cluster_gate_passed": False,
        "formal_power_gate_passed": False,
        "next_required_evidence": (
            "interpret training response only; estimate spatial correlation length and paired-CRPS effect "
            "without calibration/test access; merge candidate cells if correlation exceeds 500 m"
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": rows,
                "lines": result["design_line_counts"],
                "cells": result["candidate_500m_cell_counts"],
            }
        )
    )


if __name__ == "__main__":
    main()
