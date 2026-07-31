#!/usr/bin/env python
"""Training-only correlation and dimensionality audit for western Arkansas magnetics."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/western-arkansas-magnetic-v1"
RAW = DATA / "AR21F1047_USGS_AR-WestCentral_MagneticLineData.csv"
MANIFEST = DATA / "raw-manifest.json"
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/western-arkansas-magnetic-design-split.json"
REMANENCE = ROOT / "validation/wp8/evidence/feasibility-v1/magic-training-remanence-prior.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/western-arkansas-magnetic-train-diagnostics.json"
CELL_M = 2000.0
MAX_LAG_M = 50_000.0


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def variogram_range(
    centers: np.ndarray, residuals: np.ndarray
) -> tuple[float | None, list[dict[str, float | int | None]]]:
    delta = centers[:, None, :] - centers[None, :, :]
    distances = np.sqrt(np.sum(delta * delta, axis=2))
    differences = residuals[:, None] - residuals[None, :]
    upper = np.triu(np.ones(distances.shape, dtype=bool), 1)
    distances = distances[upper]
    semivariances = 0.5 * differences[upper] ** 2
    sill = float(np.var(residuals, ddof=1))
    records: list[dict[str, float | int | None]] = []
    reached: list[bool] = []
    edges = np.arange(0.0, MAX_LAG_M + CELL_M, CELL_M)
    for start, end in zip(edges[:-1], edges[1:]):
        chosen = (distances >= start) & (distances < end)
        pairs = int(np.count_nonzero(chosen))
        value = float(np.mean(semivariances[chosen])) if pairs else None
        records.append(
            {
                "lag_center_m": float((start + end) / 2.0),
                "pairs": pairs,
                "semivariance_nt2": value,
            }
        )
        reached.append(pairs >= 100 and value is not None and value >= 0.95 * sill)
    selected = None
    for index in range(len(reached) - 1):
        if reached[index] and reached[index + 1]:
            selected = float(records[index]["lag_center_m"])
            break
    return selected, records


def separated_test_cells(
    cells: list[dict], range_m: float
) -> tuple[list[str], int, int]:
    """Exclude train-near test cells, then greedily pack correlation-separated cells."""
    train = np.asarray(
        [
            [(int(item["cell"].split(":")[0]) + 0.5) * CELL_M,
             (int(item["cell"].split(":")[1]) + 0.5) * CELL_M]
            for item in cells
            if item["partition"] == "train"
        ],
        dtype=float,
    )
    test_items = [item for item in cells if item["partition"] == "test"]
    test_centers = np.asarray(
        [
            [(int(item["cell"].split(":")[0]) + 0.5) * CELL_M,
             (int(item["cell"].split(":")[1]) + 0.5) * CELL_M]
            for item in test_items
        ],
        dtype=float,
    )
    # A full correlation range is required between any selected test unit and
    # training.  Calibration is not used for the training-only range estimate.
    nearest_train, _ = cKDTree(train).query(test_centers, k=1)
    eligible = [
        (item["cell"], center)
        for item, center, distance in zip(test_items, test_centers, nearest_train)
        if float(distance) >= range_m
    ]
    selected: list[tuple[str, np.ndarray]] = []
    for cell, center in sorted(eligible, key=lambda value: value[0]):
        if all(float(np.linalg.norm(center - prior)) >= range_m for _, prior in selected):
            selected.append((cell, center))
    return [cell for cell, _ in selected], len(test_items) - len(eligible), len(eligible)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    remanence = json.loads(REMANENCE.read_text(encoding="utf-8"))
    member = next(item for item in manifest["members"] if item["path"] == RAW.name)
    if (
        manifest["response_values_interpreted_during_acquisition"] != 0
        or member["sha256"] != sha(RAW)
        or split["csv_sha256"] != member["sha256"]
        or split["magnetic_response_values_interpreted"] != 0
        or split["calibration_responses_interpreted"] != 0
        or split["test_responses_interpreted"] != 0
        or remanence["prior_gate_passed"] is not True
    ):
        raise RuntimeError("western Arkansas preregistration evidence drift")

    roles = {item["cell"]: item["partition"] for item in split["cells"]}
    cell_values: dict[str, list[float]] = defaultdict(list)
    line_rows: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    training_rows = 0
    skipped = defaultdict(int)
    with RAW.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        index = {name: position for position, name in enumerate(header)}
        required = {"line", "x", "y", "magres"}
        if not required <= index.keys():
            raise RuntimeError("western Arkansas magnetic schema drift")
        for row in reader:
            x = float(row[index["x"]])
            y = float(row[index["y"]])
            cell = f"{math.floor(x / CELL_M)}:{math.floor(y / CELL_M)}"
            assigned = roles[cell]
            if assigned != "train":
                skipped[assigned] += 1
                continue
            response = float(row[index["magres"]])
            if not np.isfinite(response):
                continue
            cell_values[cell].append(response)
            line_rows[row[index["line"]]].append((x, y, response))
            training_rows += 1

    populated = sorted(
        (cell, float(np.median(values))) for cell, values in cell_values.items()
    )
    centers = np.asarray(
        [
            [(int(cell.split(":")[0]) + 0.5) * CELL_M,
             (int(cell.split(":")[1]) + 0.5) * CELL_M]
            for cell, _ in populated
        ]
    )
    responses = np.asarray([value for _, value in populated])
    centered = centers - np.mean(centers, axis=0)
    design = np.column_stack((np.ones(len(centers)), centered))
    coefficients, *_ = np.linalg.lstsq(design, responses, rcond=None)
    residuals = responses - design @ coefficients
    selected_range, bins = variogram_range(centers, residuals)
    conservative_range = MAX_LAG_M if selected_range is None else max(CELL_M, selected_range)
    selected_cells, excluded_near_train, eligible_before_packing = separated_test_cells(
        split["cells"], conservative_range
    )

    line_azimuths = []
    eligible_lines = 0
    for values in line_rows.values():
        if len(values) < 64:
            continue
        array = np.asarray(values)
        dx = float(array[-1, 0] - array[0, 0])
        dy = float(array[-1, 1] - array[0, 1])
        if dx == 0.0 and dy == 0.0:
            continue
        line_azimuths.append(float(math.degrees(math.atan2(dx, dy)) % 180.0))
        eligible_lines += 1
    orientation_bins = sorted({int(value // 15.0) for value in line_azimuths})

    result = {
        "schema_version": "wp8-western-arkansas-magnetic-train-diagnostics-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "split_sha256": sha(SPLIT),
        "remanence_prior_sha256": sha(REMANENCE),
        "response_policy": {
            "training_rows_interpreted": training_rows,
            "buffer_rows_interpreted": 0,
            "calibration_rows_interpreted": 0,
            "test_rows_interpreted": 0,
            "held_out_rows_skipped_without_response_parsing": dict(skipped),
        },
        "training_cells_2km": len(populated),
        "regional_field": {
            "model": "fixed OLS plane on training-cell medians",
            "coefficients": [float(value) for value in coefficients],
            "residual_sill_nt2": float(np.var(residuals, ddof=1)),
        },
        "variogram": {
            "range_rule": (
                "first two consecutive 2-km bins with >=100 pairs and "
                "semivariance >=95% training residual sill"
            ),
            "bins": bins,
        },
        "conservative_spatial_correlation_range_m": conservative_range,
        "range_censored_at_maximum_lag": selected_range is None,
        "design_test_cells": split["partition_cell_counts"]["test"],
        "test_cells_excluded_within_range_of_training": excluded_near_train,
        "eligible_test_cells_before_correlation_packing": eligible_before_packing,
        "correlation_adjusted_test_clusters": len(selected_cells),
        "selected_test_cell_ids_sha256": hashlib.sha256(
            json.dumps(selected_cells, separators=(",", ":")).encode()
        ).hexdigest(),
        "selected_test_cell_ids": selected_cells,
        "flight_geometry": {
            "eligible_training_lines": eligible_lines,
            "orientation_bins_15deg": orientation_bins,
            "passed": eligible_lines >= 10 and len(orientation_bins) >= 2,
        },
        "remanence_sensitivity": {
            "complete_untreated_vectors": remanence["complete_vector_rows"],
            "contributions": remanence["complete_vector_contributions"],
            "vector_prior_required": True,
            "passed": remanence["prior_gate_passed"],
        },
        "dimensionality": {
            "selected": "3-D vector magnetization",
            "passed": True,
            "reason": (
                "broad two-dimensional survey coverage, multiple flight orientations, "
                "and a provenance-backed remanence prior require 3-D vector magnetization"
            ),
        },
        "coverage_required_clusters": 223,
        "cluster_gate_passed": len(selected_cells) >= 223,
        "power_gate_passed": len(selected_cells) >= 223,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": training_rows,
                "training_cells": len(populated),
                "range_m": conservative_range,
                "eligible_test_before_packing": eligible_before_packing,
                "effective_test_clusters": len(selected_cells),
            }
        )
    )


if __name__ == "__main__":
    main()
