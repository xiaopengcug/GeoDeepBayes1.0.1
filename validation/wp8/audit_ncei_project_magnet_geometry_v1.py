#!/usr/bin/env python3
"""Audit frozen NCEI Project Magnet geometry without interpreting test responses."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import urllib.request
import zipfile
from pathlib import Path


DESIGN = Path("validation/wp8/evidence/feasibility-v1/ncei-project-magnet-design-v1.json")
DATA = Path("validation/wp8/data/ncei-project-magnet-v1")
OUT = Path("validation/wp8/evidence/feasibility-v1/ncei-project-magnet-geometry-v1.json")
TRAINING_ID = "PM-HI-ALT-WORLD-C32-051"
TEST_ID = "PM-HI-ALT-WORLD-C32-052"
MIN_DISTANCE_KM = 120.0
ORDER_SALT = "wp8-ncei-project-magnet-geometry-v1-2026-07-25"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "WP8-public-data-audit/1.0"})
    with urllib.request.urlopen(request, timeout=120) as source, path.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)


def geometry(zip_path: Path) -> tuple[set[tuple[float, float]], dict]:
    occupied: set[tuple[float, float]] = set()
    rows = 0
    altitude_rows = 0
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".m88t")]
        if len(members) != 1:
            raise RuntimeError(f"Expected one MAG88T member, found {members}")
        # Only LAT, LON, and altitude columns are selected. Magnetic response
        # columns are neither converted, summarized, compared, nor emitted.
        with archive.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            header = next(csv.reader(text, delimiter="\t"))
            index = {name: header.index(name) for name in ("LAT", "LON", "ALT_BAROM", "ALT_GPS", "ALT_RADAR")}
            for values in csv.reader(text, delimiter="\t"):
                try:
                    lat = float(values[index["LAT"]])
                    lon = float(values[index["LON"]])
                except (ValueError, IndexError):
                    continue
                rows += 1
                if any(
                    index[name] < len(values) and values[index[name]].strip()
                    for name in ("ALT_BAROM", "ALT_GPS", "ALT_RADAR")
                ):
                    altitude_rows += 1
                occupied.add((math.floor(lat) + 0.5, math.floor(lon) + 0.5))
    return occupied, {
        "geometry_rows": rows,
        "rows_with_at_least_one_altitude": altitude_rows,
        "occupied_one_degree_cells": len(occupied),
    }


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    q = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 12742.0 * math.asin(min(1.0, math.sqrt(q)))


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    records = {record["survey_id"]: record for record in design["records"]}
    if records[TRAINING_ID]["role"] != "training_exposed":
        raise RuntimeError("Training survey role is not frozen")
    if records[TEST_ID]["role"] != "sealed_test_candidate":
        raise RuntimeError("Test survey role is not frozen")

    paths = {}
    for survey_id in (TRAINING_ID, TEST_ID):
        path = DATA / f"{survey_id.lower()}.zip"
        download(records[survey_id]["survey_zip_url"], path)
        paths[survey_id] = path

    training_cells, training_summary = geometry(paths[TRAINING_ID])
    test_cells, test_summary = geometry(paths[TEST_ID])
    buffered = [
        cell
        for cell in test_cells
        if all(haversine_km(cell, training) >= MIN_DISTANCE_KM for training in training_cells)
    ]
    ordered = sorted(
        buffered,
        key=lambda cell: hashlib.sha256(f"{ORDER_SALT}|{cell[0]}|{cell[1]}".encode()).hexdigest(),
    )
    selected: list[tuple[float, float]] = []
    for cell in ordered:
        if all(haversine_km(cell, other) >= MIN_DISTANCE_KM for other in selected):
            selected.append(cell)

    artifact = {
        "schema_version": "wp8-ncei-project-magnet-geometry-v1",
        "design_sha256": sha256(DESIGN),
        "licence": design["licence_basis"],
        "selection_algorithm": "one-degree occupied-cell centres; deterministic salted greedy packing",
        "order_salt": ORDER_SALT,
        "minimum_training_test_and_test_test_distance_km": MIN_DISTANCE_KM,
        "training": {
            "survey_id": TRAINING_ID,
            "zip_sha256": sha256(paths[TRAINING_ID]),
            **training_summary,
        },
        "sealed_test": {
            "survey_id": TEST_ID,
            "zip_sha256": sha256(paths[TEST_ID]),
            **test_summary,
            "cells_after_training_buffer": len(buffered),
            "independent_selected_cells": len(selected),
            "required_independent_cells": 223,
            "cluster_gate_pass": len(selected) >= 223,
            "selected_cell_centres": [
                {"latitude": latitude, "longitude": longitude} for latitude, longitude in selected
            ],
        },
        "response_columns_selected": [],
        "response_values_interpreted": 0,
        "response_values_output": 0,
        "test_unseal_count": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "sealed_test_geometry_rows": test_summary["geometry_rows"],
                "sealed_test_independent_cells": len(selected),
                "cluster_gate_pass": len(selected) >= 223,
                "test_unseal_count": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
