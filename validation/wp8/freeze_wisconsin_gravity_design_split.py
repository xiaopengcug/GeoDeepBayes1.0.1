#!/usr/bin/env python
"""Freeze the Wisconsin gravity split using station design fields only."""
from __future__ import annotations

import hashlib
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/wp8/data/wisconsin-gravity-v1/wi_gravity_state.zip"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "wisconsin-gravity-design-split.json"
)
MEMBER = "wi_gravity_state.asc"
CELL_KM = 5.0
REFERENCE_LATITUDE_DEG = 44.5


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
    ids: dict[str, set[str]] = defaultdict(set)
    design_hash = hashlib.sha256()
    bounds = {"longitude": [None, None], "latitude": [None, None], "elevation_m": [None, None]}
    cos_lat = math.cos(math.radians(REFERENCE_LATITUDE_DEG))

    with zipfile.ZipFile(ARCHIVE) as archive, archive.open(MEMBER) as raw:
        for byte_line in raw:
            line = byte_line.decode("ascii").rstrip("\r\n")
            if not line.strip():
                continue
            station_id = line[:8].rstrip()
            # USGS format: A8, 8X, then eight E16.8 fields. Only the first
            # three numeric fields (longitude, latitude, elevation) are design.
            longitude = float(line[16:32])
            latitude = float(line[32:48])
            elevation_m = float(line[48:64])
            x_km = longitude * 111.32 * cos_lat
            y_km = latitude * 110.57
            assigned = role(x_km)
            counts[assigned] += 1
            cells[assigned].add((math.floor(x_km / CELL_KM), math.floor(y_km / CELL_KM)))
            ids[assigned].add(station_id)
            design_hash.update(
                f"{station_id}|{longitude:.8f}|{latitude:.8f}|{elevation_m:.8f}\n".encode()
            )
            for name, value in (
                ("longitude", longitude),
                ("latitude", latitude),
                ("elevation_m", elevation_m),
            ):
                lo, hi = bounds[name]
                bounds[name] = [
                    value if lo is None else min(lo, value),
                    value if hi is None else max(hi, value),
                ]

    roles = ("train", "buffer", "calibration", "test")
    overlaps = {
        f"{a}:{b}": len(cells[a] & cells[b])
        for index, a in enumerate(roles)
        for b in roles[index + 1 :]
    }
    if any(overlaps.values()):
        raise RuntimeError(f"spatial cell leakage: {overlaps}")

    result = {
        "schema_version": "wp8-wisconsin-gravity-design-split-v1",
        "created_before_response_interpretation": True,
        "source": {
            "archive_path": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
            "archive_sha256": sha256(ARCHIVE),
            "member": MEMBER,
        },
        "format_contract": {
            "fortran": "(A8,8X,8E16.8)",
            "parsed_design_fields": ["station_id", "longitude", "latitude", "elevation_m"],
            "response_fields_values_parsed": False,
            "unparsed_response_fields": [
                "observed_gravity",
                "inner_terrain_correction",
                "outer_terrain_correction",
                "free_air_anomaly",
                "complete_bouguer_anomaly",
            ],
        },
        "projection_for_split_only": {
            "x_km": f"longitude * 111.32 * cos({REFERENCE_LATITUDE_DEG} degrees)",
            "y_km": "latitude * 110.57",
        },
        "split_rule": {
            "cell_size_km": CELL_KM,
            "period_cells": 12,
            "train_stripes": [1, 2, 3, 4, 5],
            "buffer_stripes": [0, 6, 9],
            "calibration_stripes": [7, 8],
            "test_stripes": [10, 11],
            "heldout_separation": "at least one explicit 5-km buffer stripe from training",
        },
        "design_bounds": bounds,
        "design_sha256": design_hash.hexdigest(),
        "counts": {
            name: {
                "stations": counts[name],
                "unique_station_ids": len(ids[name]),
                "spatial_cells_5km": len(cells[name]),
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
