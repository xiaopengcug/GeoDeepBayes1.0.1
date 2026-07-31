#!/usr/bin/env python
"""Fit the preregistered training-only TDIP error and dimensionality evidence."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from geodeepbayes.data.tdip_reykjanes import GATE_COLUMNS, paired_discrepancies, read_training_dates

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "_bmad-output/planning-artifacts/research/open-data/dc_ip/Zenodo_Reykjanes_ERT_IP_monitoring_2025/ERT_IP_Reykjanes.zip"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
SPLIT = EVIDENCE / "tdip-date-split.json"
OUTPUT = EVIDENCE / "tdip-train-diagnostics.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def robust_scale(values: np.ndarray) -> float:
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)) / np.sqrt(2.0))


def temporal_blocks(dates: list[str], correlation_days: int) -> list[list[str]]:
    blocks: list[list[str]] = []
    for value in dates:
        date = datetime.strptime(value, "%Y%m%d")
        if not blocks:
            blocks.append([value])
            continue
        start = datetime.strptime(blocks[-1][0], "%Y%m%d")
        if (date - start).days < correlation_days:
            blocks[-1].append(value)
        else:
            blocks.append([value])
    return blocks


def main() -> None:
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    train_dates = split["partitions"]["train"]
    days = read_training_dates(ARCHIVE, dates=train_dates, members=split["members"])
    daily = []
    pooled: dict[str, list[np.ndarray]] = {}
    for day in days:
        differences = paired_discrepancies(day)
        for column, values in differences.items():
            pooled.setdefault(column, []).append(values)
        daily.append(float(np.median(np.abs(differences["M (mV/V)"]))))
    daily_values = np.asarray(daily)
    correlations = []
    centered = daily_values - np.mean(daily_values)
    for lag in range(1, min(30, len(centered) - 1)):
        denominator = float(np.dot(centered, centered))
        correlations.append(float(np.dot(centered[:-lag], centered[lag:]) / denominator) if denominator else 0.0)
    correlation_days = next((i + 1 for i, value in enumerate(correlations) if value <= np.exp(-1)), len(correlations))
    block_map = {
        name: temporal_blocks(dates, correlation_days)
        for name, dates in split["partitions"].items()
        if name != "buffer"
    }
    scales = {column: robust_scale(np.concatenate(values)) for column, values in pooled.items()}
    all_gate = np.concatenate([np.concatenate(pooled[column]) for column in GATE_COLUMNS])
    tail_ratio = float(np.quantile(np.abs(all_gate), 0.99) / max(np.quantile(np.abs(all_gate), 0.5), 1e-12))
    payload = {
        "schema_version": "wp8-tdip-training-diagnostics-v1",
        "split_sha256": sha(SPLIT),
        "archive_sha256": sha(ARCHIVE),
        "training_dates_interpreted": len(days),
        "buffer_dates_interpreted": 0,
        "calibration_dates_interpreted": 0,
        "test_dates_interpreted": 0,
        "observation_unit": "acquisition_date",
        "power_cluster_unit": f"non-overlapping {correlation_days}-day temporal block",
        "normal_reciprocal_role": "paired repeats used for error estimation; never counted as clusters",
        "time_window_role": "20 correlated response channels; never counted as samples",
        "contract": {
            "abmn": True,
            "normal_reciprocal": True,
            "chargeability_windows": 20,
            "time_delay": True,
            "window_durations": 20,
            "potential_and_current": True,
        },
        "error_model": {
            "family": "Student-t",
            "heteroscedastic": True,
            "scale_estimator": "MAD of normal-reciprocal discrepancy divided by sqrt(2), independently by response channel",
            "tail_diagnostic_q99_over_q50": tail_ratio,
            "degrees_of_freedom_policy": "estimate from training paired discrepancies, constrained to [3,30]",
            "channel_scales": scales,
            "method_basis": [
                "10.1190/GEO2017-0024.1 normal-reciprocal discrepancy",
                "full-waveform TDIP gate variability/drift QC",
            ],
        },
        "temporal_correlation_length_days": correlation_days,
        "derived_temporal_cluster_map": block_map,
        "effective_cluster_counts": {name: len(blocks) for name, blocks in block_map.items()},
        "dimensionality": {
            "selected": "2d",
            "reason": "electrodes are positions along a repeated profile; temporal monitoring does not create a third spatial dimension",
            "upgrade_required": False,
        },
        "coverage_power": {
            "sealed_test_date_observations": split["counts"]["test"],
            "sealed_test_effective_temporal_clusters": len(block_map["test"]),
            "required_0.90_coverage_clusters": 223,
            "passed": len(block_map["test"]) >= 223,
            "status": "blocked",
            "reason": "daily observations are correlated; power uses non-overlapping temporal blocks",
        },
        "crps_power": {
            "status": "blocked",
            "reason": "training-only paired CRPS effect size requires competing inference methods and is not inferred from N/R repeats",
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"train": len(days), "test": split["counts"]["test"], "crps": "blocked"}))


if __name__ == "__main__":
    main()
