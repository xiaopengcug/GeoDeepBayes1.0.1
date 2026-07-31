#!/usr/bin/env python
"""Estimate Maricopa AEM spatial correlation using training responses only."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from audit_east_river_aem_training import empirical_range

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/maricopa-aem-v1"
SOURCE = RAW / "MaricopaCA2018.nc"
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/maricopa-aem-design-split.json"
CONTRACT = ROOT / "validation/wp8/evidence/feasibility-v1/maricopa-aem-contract-readiness.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/maricopa-aem-train-diagnostics.json"
CELL_M = 500.0
CHANNELS = {
    "LM10": ("LM_DATA_dBdt", "LM_DATA_STD", 10),
    "LM18": ("LM_DATA_dBdt", "LM_DATA_STD", 18),
    "LM26": ("LM_DATA_dBdt", "LM_DATA_STD", 26),
    "HM12": ("HM_DATA_dBdt", "HM_DATA_STD", 12),
    "HM24": ("HM_DATA_dBdt", "HM_DATA_STD", 24),
    "HM34": ("HM_DATA_dBdt", "HM_DATA_STD", 34),
}


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
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        split["observation_response_values_parsed"] is not False
        or contract["observation_response_values_parsed"] is not False
        or contract["passed"] is not True
        or split["source_sha256"] != sha(SOURCE)
    ):
        raise RuntimeError("Maricopa preregistration evidence drift")

    cell_values: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(
        lambda: {name: [] for name in CHANNELS}
    )
    skipped = defaultdict(int)
    with Dataset(SOURCE) as dataset:
        table = dataset.groups["survey"].groups["tabular"].groups["1"]
        eastings = np.asarray(table.variables["X"][:], dtype=float)
        northings = np.asarray(table.variables["Y"][:], dtype=float)
        line_ids = np.asarray(table.variables["LINE"][:])
        assigned = np.asarray([role(value) for value in eastings])
        training_indices = np.flatnonzero(assigned == "train")
        for name in ("buffer", "calibration", "test"):
            skipped[name] = int(np.count_nonzero(assigned == name))
        training_cells = [
            (math.floor(eastings[index] / CELL_M), math.floor(northings[index] / CELL_M))
            for index in training_indices
        ]
        finite_std = 0
        total_std = 0
        for label, (data_name, std_name, gate) in CHANNELS.items():
            # The fixed role indices are applied inside the netCDF read. No
            # held-out response array is materialized.
            data_variable = table.variables[data_name]
            standard_variable = table.variables[std_name]
            # The published response variables carry an erroneous [0, 0]
            # valid_range attribute. Disable automatic valid-range masking and
            # enforce the documented -9999/null and finite-value rules here.
            data_variable.set_auto_mask(False)
            standard_variable.set_auto_mask(False)
            data = np.asarray(data_variable[training_indices, gate], dtype=float)
            standard = np.asarray(
                standard_variable[training_indices, gate], dtype=float
            )
            valid = (
                np.isfinite(data)
                & np.isfinite(standard)
                & (data != -9999)
                & (standard != -9999)
                & (standard > 0)
            )
            total_std += len(standard)
            finite_std += int(np.count_nonzero(valid))
            for position in np.flatnonzero(valid):
                value = float(data[position])
                uncertainty = float(standard[position])
                cell_values[training_cells[position]][label].append(
                    math.copysign(math.log1p(abs(value) / uncertainty), value)
                )

    channel_diagnostics = {}
    ranges = []
    for channel in CHANNELS:
        populated = [
            (cell, float(np.median(values[channel])))
            for cell, values in cell_values.items()
            if values[channel]
        ]
        centers = np.asarray(
            [[(cell[0] + 0.5) * CELL_M, (cell[1] + 0.5) * CELL_M] for cell, _ in populated]
        )
        values = np.asarray([value for _, value in populated])
        selected_range, variogram = empirical_range(centers, values)
        conservative = 10_000.0 if selected_range is None else selected_range
        ranges.append(conservative)
        channel_diagnostics[channel] = {
            "training_cells": len(populated),
            "signed_log_snr_median": float(np.median(values)),
            "signed_log_snr_mad": float(np.median(np.abs(values - np.median(values)))),
            "sill": float(np.var(values, ddof=1)),
            "range_m": selected_range,
            "range_censored_above_m": 10_000.0 if selected_range is None else None,
            "variogram": variogram,
        }
    conservative_range = max(ranges)
    merge_factor = max(1, math.ceil((conservative_range / CELL_M) ** 2))
    design_test_cells = split["candidate_500m_cell_counts"]["test"]
    effective_test_upper_bound = math.ceil(design_test_cells / merge_factor)
    result = {
        "schema_version": "wp8-maricopa-aem-train-diagnostics-v1",
        "candidate_status": "training_diagnostics_complete",
        "split_sha256": sha(SPLIT),
        "contract_sha256": sha(CONTRACT),
        "training_rows_interpreted": len(training_indices),
        "training_lines": len(set(int(line_ids[index]) for index in training_indices)),
        "held_out_rows_skipped_without_response_parsing": dict(skipped),
        "sealed_response_rows_interpreted": {
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "fixed_diagnostic_channels": list(CHANNELS),
        "transform": "signed log1p(abs(DATA)/DATA_STD)",
        "per_observation_positive_finite_std_fraction": finite_std / total_std,
        "cell_size_m": CELL_M,
        "range_rule": (
            "first two consecutive 500-m lag bins with >=30 pairs and "
            "semivariance >=95% sill"
        ),
        "channel_diagnostics": channel_diagnostics,
        "conservative_spatial_correlation_range_m": conservative_range,
        "correlation_cell_merge_factor": merge_factor,
        "design_test_cells": design_test_cells,
        "correlation_adjusted_test_cluster_upper_bound": effective_test_upper_bound,
        "cluster_gate_passed": effective_test_upper_bound >= 223,
        "power_gate_passed": False,
        "power_reason": "training-only paired-CRPS effect size is not yet available",
        "dimensionality": {
            "rule": "500-m sounding is eligible for 1-D only if all fixed-channel ranges are <=500 m",
            "selected": (
                "1-D sounding eligible" if conservative_range <= CELL_M else "3-D"
            ),
            "passed": True,
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": len(training_indices),
                "skipped": dict(skipped),
                "range_m": conservative_range,
                "effective_test_upper_bound": effective_test_upper_bound,
            }
        )
    )


if __name__ == "__main__":
    main()
