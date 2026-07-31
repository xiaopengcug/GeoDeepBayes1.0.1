#!/usr/bin/env python
"""Freeze the USGS rock-property spatial split before property interpretation."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-rock-properties-v1/rock_property_data.csv"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-rock-properties-design-split.json"
)
DESIGN_FIELDS = (
    "Sample_ID",
    "LAT_nad27",
    "LONG_nad27",
    "ELEV_m_navd29",
    "DEPTH_m",
    "ROCK_MODIFIER",
    "ROCK_TYPE",
    "AGE_yr_sym",
)
CELL_KM = 100.0
REFERENCE_LATITUDE_DEG = 45.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def role(x_km: float) -> str:
    stripe = math.floor(x_km / CELL_KM) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def main() -> None:
    counts: Counter[str] = Counter()
    cells: dict[str, set[tuple[int, int]]] = defaultdict(set)
    rock_types: dict[str, set[str]] = defaultdict(set)
    design_hash = hashlib.sha256()
    invalid = 0
    cos_lat = math.cos(math.radians(REFERENCE_LATITUDE_DEG))
    with RAW.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or any(name not in reader.fieldnames for name in DESIGN_FIELDS):
            raise RuntimeError(f"design-column drift: {reader.fieldnames}")
        property_names = [name for name in reader.fieldnames if name not in DESIGN_FIELDS]
        for row in reader:
            try:
                latitude = float(row["LAT_nad27"])
                longitude = float(row["LONG_nad27"])
            except (TypeError, ValueError):
                invalid += 1
                continue
            x_km = longitude * 111.32 * cos_lat
            y_km = latitude * 110.57
            assigned = role(x_km)
            counts[assigned] += 1
            cells[assigned].add((math.floor(x_km / CELL_KM), math.floor(y_km / CELL_KM)))
            rock_types[assigned].add(row["ROCK_TYPE"])
            design_hash.update(
                ("|".join(row[name] for name in DESIGN_FIELDS) + "\n").encode("utf-8")
            )
    roles = ("train", "buffer", "calibration", "test")
    overlaps = {
        f"{a}:{b}": len(cells[a] & cells[b])
        for index, a in enumerate(roles)
        for b in roles[index + 1 :]
    }
    if any(overlaps.values()):
        raise RuntimeError(f"spatial cell leakage: {overlaps}")
    result = {
        "schema_version": "wp8-usgs-rock-properties-design-split-v1",
        "created_before_property_interpretation": True,
        "source": {
            "path": str(RAW.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(RAW),
            "bytes": RAW.stat().st_size,
        },
        "design_contract": {
            "parsed_fields": list(DESIGN_FIELDS),
            "property_values_converted_or_interpreted": False,
            "property_field_names_recorded_only": property_names,
        },
        "split_rule": {
            "cell_size_km": CELL_KM,
            "period_cells": 12,
            "train_stripes": [1, 2, 3, 4, 5],
            "buffer_stripes": [0, 6, 9],
            "calibration_stripes": [7, 8],
            "test_stripes": [10, 11],
        },
        "design_sha256": design_hash.hexdigest(),
        "invalid_design_rows_excluded": invalid,
        "counts": {
            name: {
                "samples": counts[name],
                "spatial_cells_100km": len(cells[name]),
                "rock_types": len(rock_types[name]),
            }
            for name in roles
        },
        "cell_overlap_counts": overlaps,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
