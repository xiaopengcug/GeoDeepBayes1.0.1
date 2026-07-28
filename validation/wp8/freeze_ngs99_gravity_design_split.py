#!/usr/bin/env python
"""Freeze an outcome-blind continental split for NOAA NGS99 gravity."""
from __future__ import annotations

import hashlib
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/wp8/data/ngs99-gravity-v1/ngs99_ascii.zip"
FORMAT = ROOT / "validation/wp8/data/ngs99-gravity-v1/ngs99.fmt"
OUTPUT = (
    ROOT / "validation/wp8/evidence/feasibility-v1/ngs99-gravity-design-split.json"
)
MEMBER = "ngs99.asc"
CELL_KM = 100.0
REFERENCE_LATITUDE_DEG = 38.0


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


def parse_scaled(text: str, scale: float) -> float | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return int(stripped) * scale
    except ValueError:
        return None


def main() -> None:
    counts: Counter[str] = Counter()
    cells: dict[str, set[tuple[int, int]]] = defaultdict(set)
    sources: dict[str, set[str]] = defaultdict(set)
    invalid = 0
    design_hash = hashlib.sha256()
    cos_lat = math.cos(math.radians(REFERENCE_LATITUDE_DEG))

    with zipfile.ZipFile(ARCHIVE) as archive, archive.open(MEMBER) as raw:
        for byte_line in raw:
            line = byte_line.decode("ascii").rstrip("\r\n")
            latitude = parse_scaled(line[0:8], 1e-5)
            longitude = parse_scaled(line[8:17], 1e-5)
            elevation_m = parse_scaled(line[17:23], 0.1)
            source_id = line[67:72].strip()
            if (
                latitude is None
                or longitude is None
                or elevation_m is None
                or not (-90 <= latitude <= 90)
                or not (-180 <= longitude <= 180)
            ):
                invalid += 1
                continue
            x_km = longitude * 111.32 * cos_lat
            y_km = latitude * 110.57
            assigned = role(x_km)
            counts[assigned] += 1
            cells[assigned].add((math.floor(x_km / CELL_KM), math.floor(y_km / CELL_KM)))
            sources[assigned].add(source_id)
            design_hash.update(
                f"{latitude:.5f}|{longitude:.5f}|{elevation_m:.1f}|{source_id}\n".encode()
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
        "schema_version": "wp8-ngs99-gravity-design-split-v1",
        "created_before_response_interpretation": True,
        "source": {
            "archive_path": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
            "archive_sha256": sha256(ARCHIVE),
            "format_path": str(FORMAT.relative_to(ROOT)).replace("\\", "/"),
            "format_sha256": sha256(FORMAT),
            "member": MEMBER,
        },
        "format_contract": {
            "parsed_design_fields": [
                "latitude",
                "longitude",
                "sea_level_elevation_m",
                "source_id",
            ],
            "response_fields_values_parsed": False,
            "quality_fields_reserved_for_training_only": [
                "observed_gravity_sd",
                "free_air_anomaly_sd",
                "bouguer_anomaly_sd",
                "terrain_correction_sd",
            ],
        },
        "split_rule": {
            "cell_size_km": CELL_KM,
            "projection_for_split_only": {
                "x_km": f"longitude * 111.32 * cos({REFERENCE_LATITUDE_DEG} degrees)",
                "y_km": "latitude * 110.57",
            },
            "period_cells": 12,
            "train_stripes": [1, 2, 3, 4, 5],
            "buffer_stripes": [0, 6, 9],
            "calibration_stripes": [7, 8],
            "test_stripes": [10, 11],
            "heldout_separation": "at least one explicit 100-km buffer stripe from training",
        },
        "design_sha256": design_hash.hexdigest(),
        "invalid_design_rows_excluded": invalid,
        "counts": {
            name: {
                "stations": counts[name],
                "spatial_cells_100km": len(cells[name]),
                "source_ids": len(sources[name]),
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
