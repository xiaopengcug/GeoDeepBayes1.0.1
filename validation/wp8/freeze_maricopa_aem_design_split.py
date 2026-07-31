#!/usr/bin/env python
"""Freeze Maricopa AEM roles from coordinates and line identifiers only."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/maricopa-aem-v1"
MANIFEST = RAW / "raw-manifest.json"
SOURCE = RAW / "MaricopaCA2018.nc"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/maricopa-aem-design-split.json"
ROLE_NAMES = ("train", "buffer", "calibration", "test")


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def role(easting: float) -> str:
    stripe = math.floor(easting / 1000.0) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["observation_response_interpreted"] is not False:
        raise RuntimeError("Maricopa response was interpreted before split")
    lines: dict[str, set[int]] = defaultdict(set)
    cells: dict[str, set[tuple[int, int]]] = defaultdict(set)
    coordinate_hash = hashlib.sha256()
    with Dataset(SOURCE) as dataset:
        table = dataset.groups["survey"].groups["tabular"].groups["1"]
        required = {"X", "Y", "LINE"}
        if not required <= table.variables.keys():
            raise RuntimeError("Maricopa design schema drift")
        eastings = table.variables["X"]
        northings = table.variables["Y"]
        line_ids = table.variables["LINE"]
        rows = len(eastings)
        if rows != 24_103:
            raise RuntimeError(f"Maricopa design row drift: {rows}")
        for start in range(0, rows, 8192):
            stop = min(rows, start + 8192)
            for east, north, line_id in zip(
                eastings[start:stop], northings[start:stop], line_ids[start:stop]
            ):
                east_value = float(east)
                north_value = float(north)
                line_value = int(line_id)
                assigned = role(east_value)
                lines[assigned].add(line_value)
                cells[assigned].add(
                    (math.floor(east_value / 500), math.floor(north_value / 500))
                )
                coordinate_hash.update(
                    f"{line_value}|{east_value:.6f}|{north_value:.6f}\n".encode()
                )
    result = {
        "schema_version": "wp8-maricopa-aem-design-split-v1",
        "candidate_status": "design_split_frozen_before_response_interpretation",
        "raw_manifest_sha256": sha(MANIFEST),
        "source_sha256": sha(SOURCE),
        "design_rows": rows,
        "assignment": {
            "cell_m": 500,
            "period_m": 12000,
            "stripe_width_m": 1000,
            "stripe_roles": {
                "buffer": [0, 6, 9],
                "train": [1, 2, 3, 4, 5],
                "calibration": [7, 8],
                "test": [10, 11],
            },
            "boundary_statement": "held-out stripes are separated from training by 1-km buffers",
        },
        "design_line_counts": {name: len(lines[name]) for name in ROLE_NAMES},
        "candidate_500m_cell_counts": {name: len(cells[name]) for name in ROLE_NAMES},
        "design_coordinate_stream_sha256": coordinate_hash.hexdigest(),
        "observation_response_values_parsed": False,
        "formal_cluster_gate_passed": False,
        "formal_power_gate_passed": False,
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
