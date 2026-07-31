#!/usr/bin/env python
# /// script
# dependencies = ["numpy==2.4.1", "scipy==1.16.3"]
# ///
"""Estimate TDIP paired-CRPS power using only contaminated-ledger training data."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm

from audit_ntgs_tdip_coordinate_design_v1 import (
    EVIDENCE as DESIGN,
    TRAINING_ARCHIVE,
    greedy_pack,
    sha256,
    training_centres_and_chargeability,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = (
    ROOT
    / "validation"
    / "wp8"
    / "evidence"
    / "feasibility-v1"
    / "ntgs-pine-creek-tdip-training-power-v1.json"
)
TARGET_IMPROVEMENT = 0.10
ALPHA_ONE_SIDED = 0.05
TARGET_POWER = 0.80
CORRELATION_RANGE_M = 250


def normal_crps(value: float, mean: float, sigma: float) -> float:
    sigma = max(float(sigma), 1e-6)
    z_score = (value - mean) / sigma
    return float(
        sigma
        * (
            z_score * (2 * norm.cdf(z_score) - 1)
            + 2 * norm.pdf(z_score)
            - 1 / math.sqrt(math.pi)
        )
    )


def design_matrix(coordinates: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    centre = np.mean(coordinates, axis=0)
    scale = np.std(coordinates, axis=0)
    if np.any(scale <= 0):
        raise RuntimeError("degenerate training coordinates")
    normalized = (coordinates - centre) / scale
    return (
        np.column_stack(
            [np.ones(len(normalized)), normalized[:, 0], normalized[:, 1]]
        ),
        centre,
        scale,
    )


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if not (
        design["selection_frozen_before_sealed_response_interpretation"]
        and design["training_only_correlation"]["frozen_range_m"]
        == CORRELATION_RANGE_M
        and design["role_assignment"]["test_count"] == 223
        and design["sealed_response_values_interpreted"] == 0
        and design["test_unseal_count"] == 0
    ):
        raise RuntimeError("NTGS TDIP design seal drift")

    training = training_centres_and_chargeability()
    coordinates = training[:, :2]
    response = training[:, 2]
    coordinate_set = {(float(row[0]), float(row[1])) for row in coordinates}
    packed_coordinates = greedy_pack(coordinate_set, CORRELATION_RANGE_M)
    coordinate_to_index = {
        (float(row[0]), float(row[1])): index
        for index, row in enumerate(coordinates)
    }
    held_indices = [coordinate_to_index[item] for item in packed_coordinates]
    if len(held_indices) != 17:
        raise RuntimeError("expected 17 correlation-separated training centres")

    paired_scores = []
    for held_index in held_indices:
        distances = np.linalg.norm(
            coordinates - coordinates[held_index], axis=1
        )
        retained = distances > CORRELATION_RANGE_M
        retained_response = response[retained]
        retained_coordinates = coordinates[retained]

        baseline_mean = float(np.mean(retained_response))
        baseline_sigma = float(np.std(retained_response, ddof=1))
        baseline_crps = normal_crps(
            float(response[held_index]), baseline_mean, baseline_sigma
        )

        matrix, centre, scale = design_matrix(retained_coordinates)
        coefficients = np.linalg.lstsq(
            matrix, retained_response, rcond=None
        )[0]
        held_normalized = (coordinates[held_index] - centre) / scale
        candidate_mean = float(
            np.asarray([1.0, held_normalized[0], held_normalized[1]])
            @ coefficients
        )
        residuals = retained_response - matrix @ coefficients
        candidate_sigma = float(
            np.std(residuals, ddof=matrix.shape[1])
        )
        candidate_crps = normal_crps(
            float(response[held_index]), candidate_mean, candidate_sigma
        )
        paired_scores.append(
            {
                "easting_m": float(coordinates[held_index, 0]),
                "northing_m": float(coordinates[held_index, 1]),
                "training_centres_after_buffer": int(np.sum(retained)),
                "baseline_crps": baseline_crps,
                "candidate_crps": candidate_crps,
                "relative_improvement": (
                    baseline_crps - candidate_crps
                )
                / baseline_crps,
            }
        )

    improvements = np.asarray(
        [item["relative_improvement"] for item in paired_scores]
    )
    observed_sd = float(np.std(improvements, ddof=1))
    sigma_upper_95 = observed_sd * math.sqrt(
        (len(improvements) - 1)
        / chi2.ppf(0.05, len(improvements) - 1)
    )
    z_sum = norm.ppf(1 - ALPHA_ONE_SIDED) + norm.ppf(TARGET_POWER)
    required_crps = math.ceil(
        (z_sum * sigma_upper_95 / TARGET_IMPROVEMENT) ** 2
    )
    required_coverage = {"0.90": 223, "0.95": 118}
    required_all = max(required_crps, *required_coverage.values())
    available_test = design["role_assignment"]["test_count"]

    payload = {
        "schema_version": "wp8-ntgs-pine-creek-tdip-training-power-v1",
        "design_sha256": sha256(DESIGN),
        "training_archive_sha256": sha256(TRAINING_ARCHIVE),
        "training_only": True,
        "observation_contract": {
            "unique_receiver_centres": len(training),
            "correlation_separated_paired_centres": len(held_indices),
            "transmitter_receiver_geometry_present": True,
            "potential_present": True,
            "current_present": True,
            "chargeability_present": True,
            "chargeability_error_present": True,
            "decay_window_count": 20,
        },
        "comparison": {
            "information_parity": "Both models use the same Jindari training-only receiver coordinates and chargeability observations.",
            "baseline": "global Gaussian predictive distribution",
            "candidate": "first-order planar spatial Gaussian predictive distribution",
            "validation": "leave-one-250-m-separated-centre-out with every training observation within 250 m removed",
            "test_information_used": False,
        },
        "paired_training_clusters": len(paired_scores),
        "paired_cluster_scores": paired_scores,
        "exploratory_mean_relative_improvement": float(np.mean(improvements)),
        "paired_relative_improvement_sd": observed_sd,
        "paired_relative_improvement_sd_upper_95": sigma_upper_95,
        "power_target_relative_improvement": TARGET_IMPROVEMENT,
        "required_paired_crps_clusters_conservative": required_crps,
        "required_coverage_clusters": required_coverage,
        "required_clusters_all_metrics": required_all,
        "available_correlation_adjusted_test_clusters": available_test,
        "alpha_one_sided": ALPHA_ONE_SIDED,
        "target_power": TARGET_POWER,
        "wp8_0_power_gate_passes": available_test >= required_all,
        "sealed_response_values_interpreted": 0,
        "test_unseal_count": 0,
        "formal_test_result": None,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "paired_training_clusters": len(paired_scores),
                "mean_relative_improvement": payload[
                    "exploratory_mean_relative_improvement"
                ],
                "sd_upper_95": sigma_upper_95,
                "required_crps_clusters": required_crps,
                "required_all_metrics": required_all,
                "available_test_clusters": available_test,
                "power_gate": payload["wp8_0_power_gate_passes"],
            }
        )
    )


if __name__ == "__main__":
    main()
