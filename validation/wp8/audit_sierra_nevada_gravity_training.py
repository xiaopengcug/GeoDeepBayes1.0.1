#!/usr/bin/env python
"""Training-only Sierra Nevada gravity correlation and uncertainty audit."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/sierra-nevada-gravity-v1"
RAW = DATA / "sierra_nevada_gravity.csv"
MANIFEST = DATA / "raw-manifest.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/sierra-nevada-gravity-design.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/sierra-nevada-gravity-train-diagnostics.json"
LAG_BIN_KM = 5.0
MAX_LAG_KM = 200.0


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        design["raw_manifest_sha256"] != sha(MANIFEST)
        or design["raw_csv_sha256"] != sha(RAW)
        or design["response_fields_interpreted"] != 0
        or design["test_unseal_count"] != 0
    ):
        raise RuntimeError("Sierra Nevada gravity design drift")
    roles = {record["id"]: record for record in design["records"]}
    selected = []
    geometry_rows = defaultdict(int)
    response_rows = defaultdict(int)
    with RAW.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        index = {name: position for position, name in enumerate(header)}
        for row in reader:
            station_id = row[index["id"]]
            record = roles.get(station_id)
            if record is None:
                continue
            assigned = record["role"]
            geometry_rows[assigned] += 1
            if assigned != "train":
                continue
            value = float(row[index["cba"]])
            if math.isfinite(value):
                selected.append(
                    (
                        record["block"],
                        record["latitude"],
                        record["longitude"],
                        record["source"],
                        value,
                    )
                )
                response_rows["train"] += 1

    block_values = defaultdict(list)
    block_coordinates = {}
    block_sources = defaultdict(lambda: defaultdict(int))
    for block, latitude, longitude, source, value in selected:
        block_values[block].append(value)
        block_coordinates[block] = (latitude, longitude)
        block_sources[block][source] += 1
    blocks = sorted(block_values)
    latitude = np.asarray([block_coordinates[block][0] for block in blocks])
    longitude = np.asarray([block_coordinates[block][1] for block in blocks])
    response = np.asarray(
        [float(np.median(block_values[block])) for block in blocks]
    )
    sources = sorted({source for _, _, _, source, _ in selected})
    dominant_source = [
        max(block_sources[block], key=block_sources[block].get) for block in blocks
    ]
    x = (longitude - np.mean(longitude)) * 111.32 * math.cos(math.radians(38.0))
    y = (latitude - np.mean(latitude)) * 111.32
    columns = [
        np.ones(len(blocks)),
        x,
        y,
        x * x,
        x * y,
        y * y,
    ]
    for source in sources[1:]:
        columns.append(
            np.asarray([value == source for value in dominant_source], dtype=float)
        )
    matrix = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(matrix, response, rcond=None)
    residual = response - matrix @ coefficients
    sill = float(np.var(residual, ddof=1))
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    distance = np.sqrt(dx * dx + dy * dy)
    difference = residual[:, None] - residual[None, :]
    upper = np.triu(np.ones(distance.shape, dtype=bool), 1)
    distance = distance[upper]
    semivariance = 0.5 * difference[upper] ** 2
    variogram = []
    reached = []
    edges = np.arange(0.0, MAX_LAG_KM + LAG_BIN_KM, LAG_BIN_KM)
    for start, end in zip(edges[:-1], edges[1:]):
        mask = (distance >= start) & (distance < end)
        count = int(np.count_nonzero(mask))
        value = float(np.mean(semivariance[mask])) if count else None
        variogram.append(
            {
                "lag_center_km": float((start + end) / 2.0),
                "pairs": count,
                "semivariance_mgal2": value,
            }
        )
        reached.append(count >= 20 and value is not None and value >= 0.95 * sill)
    correlation_range_km = MAX_LAG_KM
    censored = True
    for position in range(len(reached) - 1):
        if reached[position] and reached[position + 1]:
            correlation_range_km = max(
                LAG_BIN_KM, variogram[position]["lag_center_km"]
            )
            censored = False
            break

    close_differences = []
    raw_lat = np.asarray([item[1] for item in selected])
    raw_lon = np.asarray([item[2] for item in selected])
    raw_response = np.asarray([item[4] for item in selected])
    micro_x = raw_lon * 111.32 * math.cos(math.radians(38.0))
    micro_y = raw_lat * 111.32
    micro_cell = defaultdict(list)
    for px, py, value in zip(micro_x, micro_y, raw_response):
        micro_cell[(round(px, 2), round(py, 2))].append(float(value))
    for values in micro_cell.values():
        if len(values) > 1:
            center = float(np.median(values))
            close_differences.extend(value - center for value in values)
    colocated_sigma = (
        float(1.4826 * np.median(np.abs(close_differences)))
        if close_differences
        else None
    )
    test_effective_cells = set()
    if not censored:
        for record in design["records"]:
            if record["role"] != "test":
                continue
            px = (
                record["longitude"]
                * 111.32
                * math.cos(math.radians(38.0))
            )
            py = record["latitude"] * 111.32
            test_effective_cells.add(
                (
                    math.floor(px / correlation_range_km),
                    math.floor(py / correlation_range_km),
                )
            )
    correlation_adjusted_test_cluster_upper_bound = (
        len(test_effective_cells) if not censored else 0
    )
    result = {
        "schema_version": "wp8-sierra-nevada-gravity-train-diagnostics-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "design_sha256": sha(DESIGN),
        "training_response_rows_interpreted": response_rows["train"],
        "geometry_rows_by_role": dict(geometry_rows),
        "response_rows_interpreted": {
            "train": response_rows["train"],
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "training_spatial_blocks": len(blocks),
        "regional_model": (
            "quadratic x/y trend plus dominant-source fixed effects, fitted on "
            "training block medians only"
        ),
        "residual_sill_mgal2": sill,
        "correlation_range_km": correlation_range_km,
        "range_censored_at_200km": censored,
        "variogram": variogram,
        "design_block_size_km": design["spatial_design"]["block_size_km"],
        "range_is_below_design_spacing": (
            not censored
            and correlation_range_km
            < design["spatial_design"]["block_size_km"]
        ),
        "design_test_cluster_upper_bound": design[
            "design_test_cluster_upper_bound"
        ],
        "correlation_adjusted_test_cluster_upper_bound": (
            correlation_adjusted_test_cluster_upper_bound
        ),
        "cluster_power_gate_passes": (
            correlation_adjusted_test_cluster_upper_bound >= 223
            and not censored
            and correlation_range_km
            < design["spatial_design"]["block_size_km"]
        ),
        "training_colocated_residual_count": len(close_differences),
        "training_colocated_robust_sigma_mgal": colocated_sigma,
        "per_observation_uncertainty_contract_ready": False,
        "uncertainty_reason": (
            "the release has no gravity/Bouguer sigma field; colocated training "
            "residuals provide a population noise floor but not a validated "
            "per-observation uncertainty for heterogeneous legacy sources"
        ),
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": result["training_response_rows_interpreted"],
                "training_blocks": len(blocks),
                "range_km": correlation_range_km,
                "censored": censored,
                "test_upper_bound": result["design_test_cluster_upper_bound"],
                "correlation_adjusted_test_upper_bound": (
                    correlation_adjusted_test_cluster_upper_bound
                ),
                "cluster_power": result["cluster_power_gate_passes"],
                "colocated_sigma_mgal": colocated_sigma,
            }
        )
    )


if __name__ == "__main__":
    main()
