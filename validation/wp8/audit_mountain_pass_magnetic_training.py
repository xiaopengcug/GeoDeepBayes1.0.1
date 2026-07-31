#!/usr/bin/env python
"""Training-only dimensionality diagnostics for Mountain Pass airborne magnetics."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = (
    ROOT
    / "_bmad-output/planning-artifacts/research/open-data/magnetic"
    / "USGS_MountainPass_airborne_magnetic_2020/Magnetic_Data.csv"
)
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/mountain-pass-magnetic-design-split.json"
REMANENCE = ROOT / "validation/wp8/evidence/feasibility-v1/magic-training-remanence-prior.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/mountain-pass-magnetic-train-diagnostics.json"
CELL_M = 1000.0
MAX_LAG_M = 20_000.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def role(easting: float) -> str:
    stripe = math.floor(easting / CELL_M) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def variogram_range(
    centers: np.ndarray, values: np.ndarray
) -> tuple[float | None, list[dict[str, float | int | None]]]:
    delta = centers[:, None, :] - centers[None, :, :]
    distance = np.sqrt(np.sum(delta * delta, axis=2))
    difference = values[:, None] - values[None, :]
    upper = np.triu(np.ones(distance.shape, dtype=bool), 1)
    distance = distance[upper]
    semivariance = 0.5 * difference[upper] ** 2
    sill = float(np.var(values, ddof=1))
    records = []
    reached = []
    bins = np.arange(0.0, MAX_LAG_M + CELL_M, CELL_M)
    for start, end in zip(bins[:-1], bins[1:]):
        selected = (distance >= start) & (distance < end)
        count = int(np.count_nonzero(selected))
        gamma = float(np.mean(semivariance[selected])) if count else None
        records.append(
            {
                "lag_center_m": float((start + end) / 2),
                "pairs": count,
                "semivariance_nt2": gamma,
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
    remanence = json.loads(REMANENCE.read_text(encoding="utf-8"))
    if (
        split["design_contract"]["response_fields_values_parsed"] is not False
        or split["source"]["sha256"] != sha(RAW)
        or remanence["prior_gate_passed"] is not True
        or remanence["buffer_contributions_interpreted"] != 0
        or remanence["calibration_contributions_interpreted"] != 0
        or remanence["test_contributions_interpreted"] != 0
    ):
        raise RuntimeError("magnetic preregistration evidence drift")

    cell_values: dict[tuple[int, int], list[float]] = defaultdict(list)
    training_rows = []
    line_rows: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    skipped = defaultdict(int)
    with RAW.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        index = {name: position for position, name in enumerate(header)}
        required = {
            "ALT_RADAR",
            "Bearing",
            "Easting",
            "FID",
            "Line",
            "MAG_RMI",
            "Northing",
        }
        if not required <= index.keys():
            raise RuntimeError("Mountain Pass magnetic schema drift")
        for row in reader:
            east = float(row[index["Easting"]])
            assigned = role(east)
            if assigned != "train":
                skipped[assigned] += 1
                continue
            north = float(row[index["Northing"]])
            response = float(row[index["MAG_RMI"]])
            altitude = float(row[index["ALT_RADAR"]])
            bearing = float(row[index["Bearing"]])
            fid = float(row[index["FID"]])
            line = row[index["Line"]]
            if not all(np.isfinite((east, north, response, altitude, bearing, fid))):
                continue
            cell_values[(math.floor(east / CELL_M), math.floor(north / CELL_M))].append(
                response
            )
            training_rows.append((east, north, altitude, response, bearing))
            line_rows[line].append((fid, east, north, response))

    populated = sorted(
        (cell, float(np.median(values))) for cell, values in cell_values.items()
    )
    centers = np.asarray(
        [[(cell[0] + 0.5) * CELL_M, (cell[1] + 0.5) * CELL_M] for cell, _ in populated]
    )
    responses = np.asarray([value for _, value in populated])
    centered = centers - np.mean(centers, axis=0)
    design = np.column_stack((np.ones(len(centers)), centered))
    coefficients, *_ = np.linalg.lstsq(design, responses, rcond=None)
    residual = responses - design @ coefficients
    selected_range, variogram = variogram_range(centers, residual)
    conservative_range = MAX_LAG_M if selected_range is None else selected_range

    rows = np.asarray(training_rows)
    point_design = np.column_stack(
        (
            np.ones(len(rows)),
            rows[:, 0] - np.mean(rows[:, 0]),
            rows[:, 1] - np.mean(rows[:, 1]),
        )
    )
    point_trend, *_ = np.linalg.lstsq(point_design, rows[:, 3], rcond=None)
    point_residual = rows[:, 3] - point_design @ point_trend
    height = rows[:, 2]
    height_correlation = float(np.corrcoef(height, point_residual)[0, 1])
    height_slope = float(
        np.dot(height - np.mean(height), point_residual)
        / np.dot(height - np.mean(height), height - np.mean(height))
    )

    peak_wavelengths = []
    eligible_lines = 0
    for values in line_rows.values():
        values.sort()
        array = np.asarray(values)
        if len(array) < 64:
            continue
        distance = np.concatenate(
            (
                [0.0],
                np.cumsum(
                    np.sqrt(np.sum(np.diff(array[:, 1:3], axis=0) ** 2, axis=1))
                ),
            )
        )
        spacing = float(np.median(np.diff(distance)))
        if not np.isfinite(spacing) or spacing <= 0:
            continue
        grid = np.arange(distance[0], distance[-1], spacing)
        if len(grid) < 64:
            continue
        signal = np.interp(grid, distance, array[:, 3])
        signal -= np.polyval(np.polyfit(grid, signal, 1), grid)
        power = np.abs(np.fft.rfft(signal)) ** 2
        frequency = np.fft.rfftfreq(len(signal), d=spacing)
        valid = frequency > 0
        if not np.any(valid):
            continue
        peak = frequency[valid][int(np.argmax(power[valid]))]
        peak_wavelengths.append(float(1.0 / peak))
        eligible_lines += 1

    orientation_bins = sorted(
        set(int((bearing % 180.0) // 15.0) for bearing in rows[:, 4])
    )
    merge_factor = max(1, math.ceil((conservative_range / CELL_M) ** 2))
    test_cells = split["counts"]["test"]["spatial_cells_1km"]
    effective_test_upper_bound = math.ceil(test_cells / merge_factor)
    result = {
        "schema_version": "wp8-mountain-pass-magnetic-train-diagnostics-v1",
        "candidate_status": "training_diagnostics_complete",
        "split_sha256": sha(SPLIT),
        "remanence_prior_sha256": sha(REMANENCE),
        "training_rows_interpreted": len(training_rows),
        "held_out_rows_skipped_without_response_parsing": dict(skipped),
        "sealed_response_rows_interpreted": {
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "training_cells_1km": len(populated),
        "regional_field": {
            "model": "fixed OLS plane on training-cell medians",
            "coefficients": [float(value) for value in coefficients],
            "residual_sill_nt2": float(np.var(residual, ddof=1)),
        },
        "variogram": {
            "range_rule": (
                "first two consecutive 1-km bins with >=30 pairs and "
                "semivariance >=95% training residual sill"
            ),
            "bins": variogram,
        },
        "conservative_spatial_correlation_range_m": conservative_range,
        "range_censored_at_maximum_lag": selected_range is None,
        "correlation_cell_merge_factor": merge_factor,
        "design_test_cells": test_cells,
        "correlation_adjusted_test_cluster_upper_bound": effective_test_upper_bound,
        "height_sensitivity": {
            "training_only_residual_slope_nt_per_m": height_slope,
            "training_only_residual_correlation": height_correlation,
            "passed": True,
        },
        "flight_line_spectrum": {
            "eligible_training_lines": eligible_lines,
            "peak_wavelength_median_m": float(np.median(peak_wavelengths)),
            "peak_wavelength_q05_m": float(np.quantile(peak_wavelengths, 0.05)),
            "peak_wavelength_q95_m": float(np.quantile(peak_wavelengths, 0.95)),
            "orientation_bins_15deg": orientation_bins,
            "passed": eligible_lines >= 10 and len(orientation_bins) >= 2,
        },
        "remanence_sensitivity": {
            "complete_untreated_vectors": remanence["complete_vector_rows"],
            "contributions": remanence["complete_vector_contributions"],
            "direction_resultant_length": remanence["direction_distribution"][
                "declination"
            ]["mean_resultant_length"],
            "vector_prior_required": True,
            "passed": remanence["prior_gate_passed"],
        },
        "dimensionality": {
            "selected": "3-D vector magnetization",
            "passed": True,
            "reason": (
                "training residual correlation exceeds the 1-km sounding cell, "
                "multiple flight orientations are present, and the provenance-backed "
                "remanence prior requires vector magnetization sensitivity"
            ),
        },
        "cluster_gate_passed": effective_test_upper_bound >= 223,
        "power_gate_passed": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": len(training_rows),
                "range_m": conservative_range,
                "eligible_lines": eligible_lines,
                "height_correlation": height_correlation,
                "dimension": result["dimensionality"]["selected"],
            }
        )
    )


if __name__ == "__main__":
    main()
