#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["netCDF4==1.7.2", "numpy==2.4.1"]
# ///
"""Training-only GA national gravity response/correlation audit."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
POOL_MANIFEST = DATA / "pool-manifest.json"
GEOMETRY = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-geometry.json"
UNCERTAINTY = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-uncertainty.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-training.json"
REFERENCE_LATITUDE = -25.0
SUBCELL_KM = 5.0
LAG_KM = 5.0
MAX_LAG_KM = 200.0
ELEVATION_COEFFICIENT_UM_S2_PER_M = 1.967


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def values(variable) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=float)


def eligible_arrays(dataset: Dataset, include_response: bool) -> dict[str, np.ndarray]:
    names = ["latitude", "longitude", "gravacc", "gndelevacc", "tcerr"]
    if include_response:
        names.extend(["bouguer", "tc"])
    arrays = {name: values(dataset.variables[name]) for name in names}
    common = min(map(len, arrays.values()))
    arrays = {name: value[:common] for name, value in arrays.items()}
    sigma = np.sqrt(
        arrays["gravacc"] ** 2
        + (ELEVATION_COEFFICIENT_UM_S2_PER_M * arrays["gndelevacc"]) ** 2
        + arrays["tcerr"] ** 2
    )
    mask = (
        np.isfinite(arrays["latitude"])
        & np.isfinite(arrays["longitude"])
        & np.isfinite(arrays["gravacc"])
        & np.isfinite(arrays["gndelevacc"])
        & np.isfinite(arrays["tcerr"])
        & np.isfinite(sigma)
        & (arrays["gravacc"] >= 0.0)
        & (arrays["gndelevacc"] >= 0.0)
        & (arrays["tcerr"] >= 0.0)
        & (sigma > 0.0)
    )
    if include_response:
        mask &= np.isfinite(arrays["bouguer"]) & np.isfinite(arrays["tc"])
    arrays["mask"] = mask
    arrays["sigma_um_s2"] = sigma
    return arrays


def main() -> None:
    pool = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    uncertainty = json.loads(UNCERTAINTY.read_text(encoding="utf-8"))
    members = {
        member["survey_id"]: DATA / member["path"] for member in pool["members"]
    }
    roles = {
        survey["survey_id"]: survey["retained_role"]
        for survey in geometry["surveys"]
        if survey["status"] == "retained"
    }
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    cell_values = defaultdict(list)
    cell_geometry = {}
    cell_surveys = defaultdict(Counter)
    train_rows = 0
    train_eligible = 0
    for survey_id, assigned in roles.items():
        if assigned != "train":
            continue
        with Dataset(members[survey_id], "r") as dataset:
            arrays = eligible_arrays(dataset, include_response=True)
        train_rows += len(arrays["mask"])
        mask = arrays["mask"]
        train_eligible += int(np.count_nonzero(mask))
        # GA documentation defines the point Bouguer field as spherical-cap
        # Bouguer; adding Bullard-C terrain correction yields complete Bouguer.
        complete_bouguer_mgal = (arrays["bouguer"] + arrays["tc"]) / 10.0
        for latitude, longitude, response in zip(
            arrays["latitude"][mask],
            arrays["longitude"][mask],
            complete_bouguer_mgal[mask],
        ):
            x = longitude * lon_scale
            y = latitude * 111.32
            cell = (math.floor(x / SUBCELL_KM), math.floor(y / SUBCELL_KM))
            cell_values[cell].append(float(response))
            cell_geometry[cell] = (x, y)
            cell_surveys[cell][survey_id] += 1
    cells = sorted(cell_values)
    x = np.asarray([cell_geometry[cell][0] for cell in cells])
    y = np.asarray([cell_geometry[cell][1] for cell in cells])
    response = np.asarray([np.median(cell_values[cell]) for cell in cells])
    dominant = [cell_surveys[cell].most_common(1)[0][0] for cell in cells]
    survey_levels = sorted(set(dominant))
    x_centered = x - np.mean(x)
    y_centered = y - np.mean(y)
    columns = [
        np.ones(len(cells)),
        x_centered,
        y_centered,
        x_centered * x_centered,
        x_centered * y_centered,
        y_centered * y_centered,
    ]
    columns.extend(
        np.asarray([value == survey for value in dominant], dtype=float)
        for survey in survey_levels[1:]
    )
    matrix = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(matrix, response, rcond=None)
    residual = response - matrix @ coefficients
    sill = float(np.var(residual, ddof=1))
    bin_count = int(MAX_LAG_KM / LAG_KM)
    sums = np.zeros(bin_count)
    counts = np.zeros(bin_count, dtype=np.int64)
    for index in range(len(cells) - 1):
        distance = np.sqrt(
            (x[index + 1 :] - x[index]) ** 2
            + (y[index + 1 :] - y[index]) ** 2
        )
        semivariance = 0.5 * (residual[index + 1 :] - residual[index]) ** 2
        bins = np.floor(distance / LAG_KM).astype(int)
        valid = (bins >= 0) & (bins < bin_count)
        np.add.at(sums, bins[valid], semivariance[valid])
        np.add.at(counts, bins[valid], 1)
    variogram, reached = [], []
    for index in range(bin_count):
        value = float(sums[index] / counts[index]) if counts[index] else None
        variogram.append(
            {
                "lag_center_km": (index + 0.5) * LAG_KM,
                "pairs": int(counts[index]),
                "semivariance_mgal2": value,
            }
        )
        reached.append(
            counts[index] >= 20 and value is not None and value >= 0.95 * sill
        )
    correlation_range = MAX_LAG_KM
    censored = True
    for index in range(len(reached) - 1):
        if reached[index] and reached[index + 1]:
            correlation_range = max(LAG_KM, variogram[index]["lag_center_km"])
            censored = False
            break
    test_cells = set()
    test_quality_rows = 0
    for survey_id, assigned in roles.items():
        if assigned != "test":
            continue
        with Dataset(members[survey_id], "r") as dataset:
            arrays = eligible_arrays(dataset, include_response=False)
        mask = arrays["mask"]
        test_quality_rows += int(np.count_nonzero(mask))
        if censored:
            continue
        for latitude, longitude in zip(
            arrays["latitude"][mask], arrays["longitude"][mask]
        ):
            x_value = longitude * lon_scale
            y_value = latitude * 111.32
            test_cells.add(
                (
                    math.floor(x_value / correlation_range),
                    math.floor(y_value / correlation_range),
                )
            )
    adjusted = len(test_cells) if not censored else 0
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-training-v1",
        "pool_manifest_sha256": sha(POOL_MANIFEST),
        "geometry_sha256": sha(GEOMETRY),
        "uncertainty_sha256": sha(UNCERTAINTY),
        "response_policy": {
            "train_rows_interpreted": train_rows,
            "train_contract_eligible_rows": train_eligible,
            "buffer_rows_interpreted": 0,
            "calibration_rows_interpreted": 0,
            "test_rows_interpreted": 0,
            "test_quality_rows_examined_without_response": test_quality_rows,
        },
        "response_definition": (
            "complete_bouguer_mgal = (bouguer + tc) / 10; GA point bouguer is "
            "spherical-cap Bouguer and tc is Bullard-C terrain correction."
        ),
        "training_subcell_size_km": SUBCELL_KM,
        "training_subcells": len(cells),
        "dominant_training_surveys": len(survey_levels),
        "residual_sill_mgal2": sill,
        "correlation_range_km": correlation_range,
        "range_censored_at_200km": censored,
        "variogram": variogram,
        "uncertainty_qualified_test_cluster_upper_bound": uncertainty[
            "uncertainty_qualified_test_cluster_upper_bound"
        ],
        "correlation_adjusted_test_cluster_upper_bound": adjusted,
        "cluster_power_gate_passes": (
            not censored and correlation_range <= 55.0 and adjusted >= 223
        ),
        "complete_bouguer_contract": True,
        "per_observation_uncertainty_contract": True,
        "paired_crps_effect_available": False,
        "formal_confirmatory_contribution": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "training_rows": train_rows,
            "eligible_training_rows": train_eligible,
            "training_subcells": len(cells),
            "range_km": correlation_range,
            "censored": censored,
            "adjusted_test_upper_bound": adjusted,
            "cluster_gate": result["cluster_power_gate_passes"],
        }
    )


if __name__ == "__main__":
    main()
