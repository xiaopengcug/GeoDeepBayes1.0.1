#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["netCDF4==1.7.2", "numpy==2.4.1", "scipy==1.17.0"]
# ///
"""Training-block paired-CRPS dispersion and WP8-0 power audit for GA gravity."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from netCDF4 import Dataset
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
POOL_MANIFEST = DATA / "pool-manifest.json"
GEOMETRY = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-geometry.json"
TRAINING = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-training.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-power.json"
REFERENCE_LATITUDE = -25.0
SUBCELL_KM = 5.0
POWER_BLOCK_KM = 55.0
GP_RANGE_KM = 12.5
ELEVATION_COEFFICIENT_UM_S2_PER_M = 1.967
FOLDS = 5
TARGET_RELATIVE_IMPROVEMENT = 0.10


def required_paired_clusters(
    standardized_effect: float,
    alpha_one_sided: float = 0.05,
    power: float = 0.8,
) -> int:
    def achieved(count: int) -> float:
        critical = stats.t.ppf(1 - alpha_one_sided, count - 1)
        return float(
            stats.nct.sf(
                critical, count - 1, standardized_effect * math.sqrt(count)
            )
        )

    low, high = 2, 2
    while achieved(high) < power:
        low, high = high + 1, high * 2
    while low < high:
        middle = (low + high) // 2
        if achieved(middle) >= power:
            high = middle
        else:
            low = middle + 1
    return low


def required_coverage_clusters(
    nominal: float,
    equivalence_margin: float = 0.05,
    alpha_two_sided: float = 0.05,
    power: float = 0.8,
) -> int:
    z_alpha = stats.norm.ppf(1 - alpha_two_sided)
    z_power = stats.norm.ppf(power)
    return int(
        np.ceil(
            nominal
            * (1 - nominal)
            * ((z_alpha + z_power) / equivalence_margin) ** 2
        )
    )


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def values(variable) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=float)


def fold(block: tuple[int, int]) -> int:
    token = f"wp8-ga-gravity-power-v1|{block[0]}:{block[1]}"
    return int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % FOLDS


def gaussian_crps(mean: np.ndarray, sigma: np.ndarray, observed: np.ndarray) -> np.ndarray:
    sigma = np.maximum(sigma, 1e-9)
    z = (observed - mean) / sigma
    return sigma * (
        z * (2.0 * stats.norm.cdf(z) - 1.0)
        + 2.0 * stats.norm.pdf(z)
        - 1.0 / math.sqrt(math.pi)
    )


def design_matrix(x: np.ndarray, y: np.ndarray, center: tuple[float, float]) -> np.ndarray:
    x0, y0 = x - center[0], y - center[1]
    return np.column_stack([np.ones(len(x)), x0, y0, x0 * x0, x0 * y0, y0 * y0])


def main() -> None:
    pool = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    training = json.loads(TRAINING.read_text(encoding="utf-8"))
    members = {
        member["survey_id"]: DATA / member["path"] for member in pool["members"]
    }
    train_surveys = {
        survey["survey_id"]
        for survey in geometry["surveys"]
        if survey["status"] == "retained" and survey["retained_role"] == "train"
    }
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    cell_response = defaultdict(list)
    cell_sigma = defaultdict(list)
    cell_geometry = {}
    for survey_id in sorted(train_surveys):
        with Dataset(members[survey_id], "r") as dataset:
            arrays = {
                name: values(dataset.variables[name])
                for name in (
                    "latitude",
                    "longitude",
                    "bouguer",
                    "tc",
                    "gravacc",
                    "gndelevacc",
                    "tcerr",
                )
            }
        common = min(map(len, arrays.values()))
        arrays = {name: value[:common] for name, value in arrays.items()}
        sigma_um_s2 = np.sqrt(
            arrays["gravacc"] ** 2
            + (ELEVATION_COEFFICIENT_UM_S2_PER_M * arrays["gndelevacc"]) ** 2
            + arrays["tcerr"] ** 2
        )
        mask = np.ones(common, dtype=bool)
        for value in arrays.values():
            mask &= np.isfinite(value)
        mask &= (
            np.isfinite(sigma_um_s2)
            & (arrays["gravacc"] >= 0)
            & (arrays["gndelevacc"] >= 0)
            & (arrays["tcerr"] >= 0)
            & (sigma_um_s2 > 0)
        )
        complete_bouguer = (arrays["bouguer"] + arrays["tc"]) / 10.0
        sigma_mgal = sigma_um_s2 / 10.0
        for latitude, longitude, response, sigma in zip(
            arrays["latitude"][mask],
            arrays["longitude"][mask],
            complete_bouguer[mask],
            sigma_mgal[mask],
        ):
            x = longitude * lon_scale
            y = latitude * 111.32
            cell = (math.floor(x / SUBCELL_KM), math.floor(y / SUBCELL_KM))
            cell_response[cell].append(float(response))
            cell_sigma[cell].append(float(sigma))
            cell_geometry[cell] = (x, y)
    cells = sorted(cell_response)
    x = np.asarray([cell_geometry[cell][0] for cell in cells])
    y = np.asarray([cell_geometry[cell][1] for cell in cells])
    observed = np.asarray([np.median(cell_response[cell]) for cell in cells])
    sigma_obs = np.asarray([np.median(cell_sigma[cell]) for cell in cells])
    power_blocks = [
        (math.floor(x_value / POWER_BLOCK_KM), math.floor(y_value / POWER_BLOCK_KM))
        for x_value, y_value in zip(x, y)
    ]
    fold_ids = np.asarray([fold(block) for block in power_blocks])
    candidate_scores = np.full(len(cells), np.nan)
    baseline_scores = np.full(len(cells), np.nan)
    fold_diagnostics = []
    for held_out in range(FOLDS):
        train = fold_ids != held_out
        validate = fold_ids == held_out
        center = (float(np.mean(x[train])), float(np.mean(y[train])))
        train_matrix = design_matrix(x[train], y[train], center)
        validate_matrix = design_matrix(x[validate], y[validate], center)
        weights = 1.0 / np.maximum(sigma_obs[train] ** 2, 1e-6)
        weighted_matrix = train_matrix * np.sqrt(weights)[:, None]
        weighted_response = observed[train] * np.sqrt(weights)
        coefficients, *_ = np.linalg.lstsq(
            weighted_matrix, weighted_response, rcond=None
        )
        trend_train = train_matrix @ coefficients
        trend_validate = validate_matrix @ coefficients
        residual = observed[train] - trend_train
        residual_variance = max(float(np.var(residual, ddof=1)), 1e-6)
        baseline_sd = np.sqrt(residual_variance + sigma_obs[validate] ** 2)
        baseline_scores[validate] = gaussian_crps(
            trend_validate, baseline_sd, observed[validate]
        )
        train_xy = np.column_stack([x[train], y[train]])
        validate_xy = np.column_stack([x[validate], y[validate]])
        train_distance2 = np.sum(
            (train_xy[:, None, :] - train_xy[None, :, :]) ** 2, axis=2
        )
        cross_distance2 = np.sum(
            (validate_xy[:, None, :] - train_xy[None, :, :]) ** 2, axis=2
        )
        kernel = residual_variance * np.exp(
            -0.5 * train_distance2 / GP_RANGE_KM**2
        )
        kernel.flat[:: len(kernel) + 1] += sigma_obs[train] ** 2 + 1e-6
        cross = residual_variance * np.exp(
            -0.5 * cross_distance2 / GP_RANGE_KM**2
        )
        cholesky = np.linalg.cholesky(kernel)
        alpha = np.linalg.solve(cholesky.T, np.linalg.solve(cholesky, residual))
        candidate_mean = trend_validate + cross @ alpha
        projected = np.linalg.solve(cholesky, cross.T)
        latent_variance = np.maximum(
            residual_variance - np.sum(projected * projected, axis=0), 1e-9
        )
        candidate_sd = np.sqrt(latent_variance + sigma_obs[validate] ** 2)
        candidate_scores[validate] = gaussian_crps(
            candidate_mean, candidate_sd, observed[validate]
        )
        fold_diagnostics.append(
            {
                "fold": held_out,
                "training_subcells": int(np.count_nonzero(train)),
                "validation_subcells": int(np.count_nonzero(validate)),
                "validation_blocks": len(
                    {power_blocks[index] for index in np.flatnonzero(validate)}
                ),
            }
        )
    if not np.all(np.isfinite(candidate_scores)) or not np.all(
        np.isfinite(baseline_scores)
    ):
        raise RuntimeError("cross-validation did not score every training subcell")
    block_candidate = defaultdict(list)
    block_baseline = defaultdict(list)
    for block, candidate, baseline in zip(
        power_blocks, candidate_scores, baseline_scores
    ):
        block_candidate[block].append(float(candidate))
        block_baseline[block].append(float(baseline))
    paired = []
    for block in sorted(block_candidate):
        candidate = float(np.mean(block_candidate[block]))
        baseline = float(np.mean(block_baseline[block]))
        paired.append(
            {
                "block": f"{block[0]}:{block[1]}",
                "candidate_crps": candidate,
                "baseline_crps": baseline,
                "relative_improvement": (baseline - candidate) / baseline,
            }
        )
    relative = np.asarray([item["relative_improvement"] for item in paired])
    dispersion = float(np.std(relative, ddof=1))
    standardized_target = TARGET_RELATIVE_IMPROVEMENT / max(dispersion, 1e-12)
    required_crps = required_paired_clusters(standardized_target)
    required_coverage_90 = required_coverage_clusters(nominal=0.90)
    required_coverage_95 = required_coverage_clusters(nominal=0.95)
    required_all = max(required_crps, required_coverage_90, required_coverage_95)
    available = training["correlation_adjusted_test_cluster_upper_bound"]
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-power-v1",
        "pool_manifest_sha256": sha(POOL_MANIFEST),
        "geometry_sha256": sha(GEOMETRY),
        "training_sha256": sha(TRAINING),
        "training_only": True,
        "comparison": {
            "information_parity": (
                "Both models use identical training subcell complete-Bouguer values "
                "and propagated observation sigmas."
            ),
            "baseline": "weighted quadratic regional-trend Gaussian prediction",
            "candidate": (
                "same weighted trend plus fixed 12.5-km Gaussian-process residual"
            ),
            "validation": "five deterministic folds of 55-km training blocks",
        },
        "folds": fold_diagnostics,
        "paired_training_blocks": len(paired),
        "paired_block_scores": paired,
        "exploratory_mean_relative_improvement": float(np.mean(relative)),
        "paired_relative_improvement_sd": dispersion,
        "power_target_relative_improvement": TARGET_RELATIVE_IMPROVEMENT,
        "standardized_target_effect": standardized_target,
        "required_paired_crps_clusters": required_crps,
        "required_coverage_clusters": {
            "0.90": required_coverage_90,
            "0.95": required_coverage_95,
        },
        "required_clusters_all_metrics": required_all,
        "available_correlation_adjusted_test_clusters": available,
        "alpha_one_sided": 0.05,
        "target_power": 0.80,
        "wp8_0_power_gate_passes": available >= required_all,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "formal_test_result": None,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "paired_training_blocks": len(paired),
            "mean_exploratory_improvement": result[
                "exploratory_mean_relative_improvement"
            ],
            "relative_sd": dispersion,
            "required_crps": required_crps,
            "required_all": required_all,
            "available": available,
            "power_gate": result["wp8_0_power_gate_passes"],
        }
    )


if __name__ == "__main__":
    main()
