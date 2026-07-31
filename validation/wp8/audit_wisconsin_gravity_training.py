#!/usr/bin/env python
"""Training-only correlation audit for Wisconsin complete Bouguer gravity."""
from __future__ import annotations

import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/wp8/data/wisconsin-gravity-v1/wi_gravity_state.zip"
SPLIT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "wisconsin-gravity-design-split.json"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "wisconsin-gravity-train-diagnostics.json"
)
MEMBER = "wi_gravity_state.asc"
CELL_KM = 5.0
REFERENCE_LATITUDE_DEG = 44.5
LAG_BIN_KM = 5.0
MAX_LAG_KM = 150.0
MIN_PAIRS = 100


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
    frozen = json.loads(SPLIT.read_text(encoding="utf-8"))
    cell_values: dict[tuple[int, int], list[float]] = defaultdict(list)
    rows = 0
    ignored = 0
    cos_lat = math.cos(math.radians(REFERENCE_LATITUDE_DEG))

    with zipfile.ZipFile(ARCHIVE) as archive, archive.open(MEMBER) as raw:
        for byte_line in raw:
            line = byte_line.decode("ascii").rstrip("\r\n")
            if not line.strip():
                continue
            longitude = float(line[16:32])
            latitude = float(line[32:48])
            x_km = longitude * 111.32 * cos_lat
            y_km = latitude * 110.57
            if role(x_km) != "train":
                ignored += 1
                # Crucially, do not slice or convert any held-out response field.
                continue
            complete_bouguer_mgal = float(line[128:144])
            cell = (math.floor(x_km / CELL_KM), math.floor(y_km / CELL_KM))
            cell_values[cell].append(complete_bouguer_mgal)
            rows += 1

    coordinates = np.asarray(
        [[(cell[0] + 0.5) * CELL_KM, (cell[1] + 0.5) * CELL_KM] for cell in cell_values],
        dtype=float,
    )
    values = np.asarray([np.mean(cell_values[cell]) for cell in cell_values], dtype=float)
    # A fixed linear regional-field removal prevents continental-scale trend
    # from being mislabeled as short-scale residual dependence.
    design = np.column_stack([np.ones(len(values)), coordinates])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    residuals = values - design @ coefficients
    sill = float(np.var(residuals, ddof=1))

    lag_sum = np.zeros(math.ceil(MAX_LAG_KM / LAG_BIN_KM), dtype=float)
    lag_count = np.zeros_like(lag_sum, dtype=np.int64)
    for index in range(len(values) - 1):
        delta = coordinates[index + 1 :] - coordinates[index]
        distance = np.sqrt(np.sum(delta * delta, axis=1))
        keep = (distance > 0) & (distance <= MAX_LAG_KM)
        bins = np.floor(distance[keep] / LAG_BIN_KM).astype(int)
        bins = np.minimum(bins, len(lag_sum) - 1)
        semivariance = 0.5 * (residuals[index + 1 :][keep] - residuals[index]) ** 2
        np.add.at(lag_sum, bins, semivariance)
        np.add.at(lag_count, bins, 1)

    variogram = []
    for index, (total, count) in enumerate(zip(lag_sum, lag_count, strict=True)):
        variogram.append(
            {
                "lag_center_km": (index + 0.5) * LAG_BIN_KM,
                "pairs": int(count),
                "semivariance_mgal2": float(total / count) if count else None,
            }
        )

    threshold = 0.95 * sill
    eligible = [
        item["pairs"] >= MIN_PAIRS
        and item["semivariance_mgal2"] is not None
        and item["semivariance_mgal2"] >= threshold
        for item in variogram
    ]
    range_km = MAX_LAG_KM
    censored = True
    for index in range(len(eligible) - 1):
        if eligible[index] and eligible[index + 1]:
            range_km = variogram[index]["lag_center_km"]
            censored = False
            break

    merge_factor = max(1, math.ceil(range_km / CELL_KM) ** 2)
    test_cells = frozen["counts"]["test"]["spatial_cells_5km"]
    effective_test_upper_bound = test_cells // merge_factor
    result = {
        "schema_version": "wp8-wisconsin-gravity-training-diagnostics-v1",
        "split_sha256": frozen["design_sha256"],
        "response_policy": {
            "training_rows_interpreted": rows,
            "heldout_rows_skipped_without_response_tail_parsing": ignored,
            "buffer_rows_interpreted": 0,
            "calibration_rows_interpreted": 0,
            "test_rows_interpreted": 0,
        },
        "response": "complete Bouguer anomaly at 2.67 g/cm3",
        "aggregation": "mean response per occupied 5-km training cell",
        "regional_field": {
            "model": "fixed ordinary least-squares plane fitted on training cells only",
            "coefficients": coefficients.tolist(),
        },
        "residual_sill_mgal2": sill,
        "variogram": {
            "lag_bin_km": LAG_BIN_KM,
            "maximum_lag_km": MAX_LAG_KM,
            "minimum_pairs": MIN_PAIRS,
            "range_rule": "first two consecutive eligible bins at or above 95% residual sill",
            "bins": variogram,
        },
        "conservative_spatial_correlation_range_km": range_km,
        "range_censored_at_maximum_lag": censored,
        "correlation_cell_merge_factor_2d": merge_factor,
        "design_test_cells": test_cells,
        "correlation_adjusted_test_cluster_upper_bound": effective_test_upper_bound,
        "cluster_gate_passed": effective_test_upper_bound >= 223,
        "power_gate_passed": False,
        "power_reason": "training-only paired-CRPS effect size is not yet available",
        "dimensionality": {
            "selected": "3D",
            "reason": "statewide irregular station coverage and regional lateral variation",
            "passed": True,
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": rows,
                "range_km": range_km,
                "censored": censored,
                "effective_test_upper_bound": effective_test_upper_bound,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
