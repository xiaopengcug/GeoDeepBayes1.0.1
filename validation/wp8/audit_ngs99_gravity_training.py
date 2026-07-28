#!/usr/bin/env python
"""Training-only quality and spatial-dependence audit for NOAA NGS99 gravity."""
from __future__ import annotations

import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/wp8/data/ngs99-gravity-v1/ngs99_ascii.zip"
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/ngs99-gravity-design-split.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/ngs99-gravity-train-diagnostics.json"
MEMBER = "ngs99.asc"
CELL_KM = 100.0
REFERENCE_LATITUDE_DEG = 38.0
LAG_BIN_KM = 100.0
MAX_LAG_KM = 2000.0
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


def scaled(text: str, factor: float) -> float | None:
    value = text.strip()
    if not value:
        return None
    try:
        return int(value) * factor
    except ValueError:
        return None


def main() -> None:
    frozen = json.loads(SPLIT.read_text(encoding="utf-8"))
    cells: dict[tuple[int, int], list[float]] = defaultdict(list)
    sd_counts: Counter[str] = Counter()
    training_rows = 0
    ignored = 0
    cos_lat = math.cos(math.radians(REFERENCE_LATITUDE_DEG))

    with zipfile.ZipFile(ARCHIVE) as archive, archive.open(MEMBER) as raw:
        for byte_line in raw:
            line = byte_line.decode("ascii").rstrip("\r\n")
            latitude = scaled(line[0:8], 1e-5)
            longitude = scaled(line[8:17], 1e-5)
            if latitude is None or longitude is None:
                ignored += 1
                continue
            x_km = longitude * 111.32 * cos_lat
            y_km = latitude * 110.57
            if role(x_km) != "train":
                ignored += 1
                continue
            bouguer = scaled(line[50:56], 0.1)
            bouguer_sd = scaled(line[56:59], 0.1)
            if bouguer is None:
                sd_counts["missing_response"] += 1
                continue
            if bouguer_sd is None:
                sd_counts["missing_sd"] += 1
            elif bouguer_sd == 0:
                sd_counts["zero_or_unspecified_sd"] += 1
            else:
                sd_counts["positive_sd"] += 1
            cell = (math.floor(x_km / CELL_KM), math.floor(y_km / CELL_KM))
            cells[cell].append(bouguer)
            training_rows += 1

    coordinates = np.asarray(
        [[(key[0] + 0.5) * CELL_KM, (key[1] + 0.5) * CELL_KM] for key in cells],
        dtype=float,
    )
    values = np.asarray([np.mean(cells[key]) for key in cells], dtype=float)
    design = np.column_stack([np.ones(len(values)), coordinates])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    residuals = values - design @ coefficients
    sill = float(np.var(residuals, ddof=1))
    bins = math.ceil(MAX_LAG_KM / LAG_BIN_KM)
    lag_sum = np.zeros(bins)
    lag_count = np.zeros(bins, dtype=np.int64)
    for index in range(len(values) - 1):
        delta = coordinates[index + 1 :] - coordinates[index]
        distances = np.sqrt(np.sum(delta * delta, axis=1))
        keep = (distances > 0) & (distances <= MAX_LAG_KM)
        indices = np.minimum((distances[keep] // LAG_BIN_KM).astype(int), bins - 1)
        semivariance = 0.5 * (residuals[index + 1 :][keep] - residuals[index]) ** 2
        np.add.at(lag_sum, indices, semivariance)
        np.add.at(lag_count, indices, 1)
    variogram = [
        {
            "lag_center_km": (index + 0.5) * LAG_BIN_KM,
            "pairs": int(count),
            "semivariance_mgal2": float(lag_sum[index] / count) if count else None,
        }
        for index, count in enumerate(lag_count)
    ]
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
    test_cells = frozen["counts"]["test"]["spatial_cells_100km"]
    effective_upper = test_cells // merge_factor
    result = {
        "schema_version": "wp8-ngs99-gravity-training-diagnostics-v1",
        "response_policy": {
            "training_rows_interpreted": training_rows,
            "heldout_or_invalid_rows_skipped_without_response_parsing": ignored,
            "buffer_rows_interpreted": 0,
            "calibration_rows_interpreted": 0,
            "test_rows_interpreted": 0,
        },
        "quality_metadata": {
            "bouguer_anomaly_sd_counts_training_only": dict(sd_counts),
            "positive_sd_fraction": sd_counts["positive_sd"] / training_rows,
        },
        "aggregation": "mean Bouguer anomaly per occupied 100-km training cell",
        "regional_field": {
            "model": "fixed OLS plane fitted to training cells only",
            "coefficients": coefficients.tolist(),
        },
        "residual_sill_mgal2": sill,
        "variogram": {
            "range_rule": "first two consecutive 100-km bins at or above 95% residual sill",
            "bins": variogram,
        },
        "conservative_spatial_correlation_range_km": range_km,
        "range_censored_at_maximum_lag": censored,
        "correlation_cell_merge_factor_2d": merge_factor,
        "design_test_cells": test_cells,
        "correlation_adjusted_test_cluster_upper_bound": effective_upper,
        "cluster_gate_passed": effective_upper >= 223,
        "power_gate_passed": False,
        "power_reason": "training-only paired-CRPS effect size is not yet available",
        "dimensionality": {
            "selected": "3D",
            "passed": True,
            "reason": "continental station coverage spans heterogeneous lateral structure",
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": training_rows,
                "positive_sd_fraction": result["quality_metadata"]["positive_sd_fraction"],
                "range_km": range_km,
                "effective_test_upper_bound": effective_upper,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
