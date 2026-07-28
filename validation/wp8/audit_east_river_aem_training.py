#!/usr/bin/env python
"""Training-only spatial correlation and dimensionality audit for East River AEM."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/east-river-aem-v1"
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/east-river-aem-design-split.json"
CONTRACT = ROOT / "validation/wp8/evidence/feasibility-v1/east-river-aem-contract-readiness.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/east-river-aem-train-diagnostics.json"
SERIES = tuple(sorted(RAW.glob("EastRiver2017_ProcessedAEMData_*series.csv")))
GATES = (12, 32, 48)
CELL_M = 500.0
MAX_LAG_M = 10_000.0


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


def empirical_range(
    centers: np.ndarray, values: np.ndarray
) -> tuple[float | None, list[dict[str, float | int | None]]]:
    delta = centers[:, None, :] - centers[None, :, :]
    distance = np.sqrt(np.sum(delta * delta, axis=2))
    difference = values[:, None] - values[None, :]
    upper = np.triu(np.ones(distance.shape, dtype=bool), 1)
    distance = distance[upper]
    semivariance = 0.5 * difference[upper] ** 2
    sill = float(np.var(values, ddof=1))
    bins = np.arange(0.0, MAX_LAG_M + CELL_M, CELL_M)
    records = []
    reached = []
    for start, end in zip(bins[:-1], bins[1:]):
        selected = (distance >= start) & (distance < end)
        count = int(np.count_nonzero(selected))
        gamma = float(np.mean(semivariance[selected])) if count else None
        records.append(
            {
                "lag_center_m": float((start + end) / 2),
                "pairs": count,
                "semivariance": gamma,
            }
        )
        reached.append(bool(count >= 30 and gamma is not None and gamma >= 0.95 * sill))
    selected_range = None
    for index in range(len(reached) - 1):
        if reached[index] and reached[index + 1]:
            selected_range = records[index]["lag_center_m"]
            break
    return selected_range, records


def main() -> None:
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if split["observation_response_values_parsed"] is not False or contract["passed"] is not True:
        raise RuntimeError("East River preregistration evidence drift")

    cell_values: dict[tuple[int, int], dict[int, list[float]]] = defaultdict(
        lambda: {gate: [] for gate in GATES}
    )
    training_rows = 0
    ignored = {"buffer": 0, "calibration": 0, "test": 0}
    training_lines = set()
    finite_std = 0
    total_std = 0
    for path in SERIES:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            header = stream.readline().rstrip("\r\n").split(",")
            expected = (
                [f"DATA[{index}]" for index in range(52)]
                + [f"DATASTD[{index}]" for index in range(52)]
            )
            if header[7:] != expected:
                raise RuntimeError(f"AEM response schema drift: {path.name}")
            for line in stream:
                prefix = line.rstrip("\r\n").split(",", 6)
                if len(prefix) != 7:
                    raise RuntimeError(f"short AEM row: {path.name}")
                east = float(prefix[2])
                assigned = role(east)
                if assigned != "train":
                    ignored[assigned] += 1
                    continue
                # Only training rows cross this interpretation boundary.
                tail = prefix[6].split(",")
                if len(tail) != 105:
                    raise RuntimeError(f"AEM training response width drift: {path.name}")
                north = float(prefix[3])
                training_lines.add(prefix[0])
                training_rows += 1
                data = tail[1:53]
                std = tail[53:105]
                total_std += len(std)
                finite_std += sum(
                    bool(value) and np.isfinite(float(value)) and float(value) > 0
                    for value in std
                )
                cell = (math.floor(east / CELL_M), math.floor(north / CELL_M))
                for gate in GATES:
                    if data[gate] and std[gate]:
                        value = float(data[gate])
                        uncertainty = float(std[gate])
                        if np.isfinite(value) and np.isfinite(uncertainty) and uncertainty > 0:
                            # Fixed signed-log SNR stabilizes scale without
                            # selecting gates or transforms from outcomes.
                            transformed = math.copysign(math.log1p(abs(value) / uncertainty), value)
                            cell_values[cell][gate].append(transformed)

    diagnostics = {}
    ranges = []
    for gate in GATES:
        populated = [
            (cell, float(np.median(values[gate])))
            for cell, values in cell_values.items()
            if values[gate]
        ]
        centers = np.asarray(
            [[(cell[0] + 0.5) * CELL_M, (cell[1] + 0.5) * CELL_M] for cell, _ in populated]
        )
        values = np.asarray([value for _, value in populated])
        selected_range, variogram = empirical_range(centers, values)
        diagnostics[str(gate)] = {
            "training_cells": len(populated),
            "signed_log_snr_median": float(np.median(values)),
            "signed_log_snr_mad": float(np.median(np.abs(values - np.median(values)))),
            "sill": float(np.var(values, ddof=1)),
            "range_m": selected_range,
            "range_censored_above_m": MAX_LAG_M if selected_range is None else None,
            "variogram": variogram,
        }
        ranges.append(MAX_LAG_M if selected_range is None else selected_range)

    conservative_range = max(ranges)
    merge_factor = max(1, math.ceil((conservative_range / CELL_M) ** 2))
    design_test_cells = split["candidate_500m_cell_counts"]["test"]
    effective_test_upper_bound = math.ceil(design_test_cells / merge_factor)
    selected_dimension = "3-D" if conservative_range > CELL_M else "1-D sounding eligible"
    result = {
        "schema_version": "wp8-east-river-aem-train-diagnostics-v1",
        "candidate_status": "training_diagnostics_complete",
        "split_sha256": sha(SPLIT),
        "contract_sha256": sha(CONTRACT),
        "training_members_interpreted": [path.name for path in SERIES],
        "training_rows_interpreted": training_rows,
        "training_lines": len(training_lines),
        "buffer_rows_interpreted": 0,
        "calibration_rows_interpreted": 0,
        "test_rows_interpreted": 0,
        "held_out_rows_skipped_without_response_tail_parsing": ignored,
        "per_observation_positive_finite_std_fraction": finite_std / total_std,
        "fixed_diagnostic_gates": list(GATES),
        "transform": "signed log1p(abs(DATA)/DATASTD)",
        "cell_size_m": CELL_M,
        "range_rule": "first two consecutive 500-m lag bins with >=30 pairs and semivariance >=95% sill",
        "gate_diagnostics": diagnostics,
        "conservative_spatial_correlation_range_m": conservative_range,
        "correlation_cell_merge_factor": merge_factor,
        "design_test_cells": design_test_cells,
        "correlation_adjusted_test_cluster_upper_bound": effective_test_upper_bound,
        "cluster_gate_passed": effective_test_upper_bound >= 223,
        "power_gate_passed": False,
        "power_reason": "training-only paired-CRPS effect size is not yet available",
        "dimensionality": {
            "rule": "500-m sounding is eligible for 1-D only if all fixed-gate ranges are <=500 m",
            "selected": selected_dimension,
            "passed": True,
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": training_rows,
                "ignored": ignored,
                "range_m": conservative_range,
                "effective_test_upper_bound": effective_test_upper_bound,
                "dimension": selected_dimension,
            }
        )
    )


if __name__ == "__main__":
    main()
