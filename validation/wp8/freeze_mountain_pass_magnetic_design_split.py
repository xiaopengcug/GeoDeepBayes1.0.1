#!/usr/bin/env python
"""Freeze an outcome-blind Mountain Pass magnetic spatial split.

Only acquisition/design columns are parsed. Magnetic response columns are
never converted or inspected by this program.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = (
    ROOT
    / "_bmad-output/planning-artifacts/research/open-data/magnetic"
    / "USGS_MountainPass_airborne_magnetic_2020/Magnetic_Data.csv"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "mountain-pass-magnetic-design-split.json"
)
DESIGN_FIELDS = (
    "ALT_RADAR",
    "Bearing",
    "Date",
    "Easting",
    "FID",
    "Flight",
    "GPSZ",
    "Line",
    "Latitude",
    "Longitude",
    "Northing",
)
CELL_M = 1000.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def role(easting: float) -> str:
    """Periodic 1-km stripes with explicit buffer stripes."""
    stripe = math.floor(easting / CELL_M) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def main() -> None:
    row_counts: Counter[str] = Counter()
    line_sets: dict[str, set[str]] = defaultdict(set)
    cell_sets: dict[str, set[tuple[int, int]]] = defaultdict(set)
    coordinate_hash = hashlib.sha256()
    design_minmax: dict[str, list[float | None]] = {
        name: [None, None]
        for name in ("ALT_RADAR", "Bearing", "Easting", "GPSZ", "Latitude", "Longitude", "Northing")
    }

    with RAW.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or any(name not in reader.fieldnames for name in DESIGN_FIELDS):
            raise RuntimeError(f"design-column drift: {reader.fieldnames}")
        response_fields = [name for name in reader.fieldnames if name not in DESIGN_FIELDS]
        for row in reader:
            east = float(row["Easting"])
            north = float(row["Northing"])
            assigned = role(east)
            row_counts[assigned] += 1
            line_sets[assigned].add(row["Line"])
            cell_sets[assigned].add((math.floor(east / CELL_M), math.floor(north / CELL_M)))
            coordinate_hash.update(
                ("|".join(row[name] for name in DESIGN_FIELDS) + "\n").encode("utf-8")
            )
            for name, bounds in design_minmax.items():
                value = float(row[name])
                bounds[0] = value if bounds[0] is None else min(bounds[0], value)
                bounds[1] = value if bounds[1] is None else max(bounds[1], value)

    overlaps = {
        f"{a}:{b}": len(cell_sets[a] & cell_sets[b])
        for a in ("train", "buffer", "calibration", "test")
        for b in ("train", "buffer", "calibration", "test")
        if a < b
    }
    if any(overlaps.values()):
        raise RuntimeError(f"spatial cell leakage: {overlaps}")

    result = {
        "schema_version": "wp8-mountain-pass-magnetic-design-split-v1",
        "created_before_response_interpretation": True,
        "source": {
            "path": str(RAW.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(RAW),
            "bytes": RAW.stat().st_size,
        },
        "design_contract": {
            "parsed_fields": list(DESIGN_FIELDS),
            "response_fields_values_parsed": False,
            "response_field_names_recorded_only": response_fields,
            "coordinate_design_sha256": coordinate_hash.hexdigest(),
            "design_minmax": design_minmax,
        },
        "split_rule": {
            "cell_size_m": CELL_M,
            "axis": "UTM NAD83 Zone 11 easting",
            "period_km": 12,
            "train_stripes": [1, 2, 3, 4, 5],
            "buffer_stripes": [0, 6, 9],
            "calibration_stripes": [7, 8],
            "test_stripes": [10, 11],
            "heldout_separation": "at least one explicit 1-km buffer stripe from training",
        },
        "counts": {
            name: {
                "rows": row_counts[name],
                "lines_touched": len(line_sets[name]),
                "spatial_cells_1km": len(cell_sets[name]),
            }
            for name in ("train", "buffer", "calibration", "test")
        },
        "cell_overlap_counts": overlaps,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
