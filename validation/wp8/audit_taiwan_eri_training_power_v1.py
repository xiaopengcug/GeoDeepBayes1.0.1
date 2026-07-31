#!/usr/bin/env python
# /// script
# dependencies = ["numpy==2.4.1", "scipy==1.16.3"]
# ///
"""Audit frozen Taiwan ERI training STG files and estimate paired-CRPS power."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/taiwan-eri-training-v1"
MANIFEST = DATA / "manifest.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-design-v1.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-training-power-v1.json"
TARGET_IMPROVEMENT = 0.10
ALPHA_ONE_SIDED = 0.05
TARGET_POWER = 0.80
K_NEIGHBORS = 4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def haversine_km(left: np.ndarray, right: np.ndarray) -> float:
    lat1, lon1 = np.radians(left)
    lat2, lon2 = np.radians(right)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(value)))


def normal_crps(values: np.ndarray, mean: float, sigma: float) -> np.ndarray:
    sigma = max(float(sigma), 1e-6)
    z = (values - mean) / sigma
    return sigma * (
        z * (2 * norm.cdf(z) - 1)
        + 2 * norm.pdf(z)
        - 1 / math.sqrt(math.pi)
    )


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        design["role_counts"] != {"training": 23, "test": 223}
        or not design["design_cluster_gate_passes"]
        or manifest["training_component_count"] != 23
        or manifest["test_files_downloaded"] != 0
        or manifest["test_unseal_count"] != 0
    ):
        raise RuntimeError("Taiwan ERI training seal drift")

    coordinates = {
        component["component_id"]: np.asarray(
            [
                component["centres"][0]["latitude"],
                component["centres"][0]["longitude"],
            ],
            dtype=float,
        )
        for component in design["components"]
        if component["role"] == "training"
    }
    response: dict[str, list[float]] = {
        component_id: [] for component_id in coordinates
    }
    errors: list[float] = []
    file_audits = []
    for item in manifest["files"]:
        path = DATA / item["local_name"]
        if (
            not path.is_file()
            or path.stat().st_size != item["downloaded_size"]
            or sha256(path) != item["sha256"]
        ):
            raise RuntimeError(f"training file drift: {item['local_name']}")
        with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
            instrument = stream.readline().strip()
            acquisition = stream.readline().strip()
            unit = stream.readline().strip()
            declared_match = re.search(r"Records:\s*(\d+)", acquisition)
            if (
                "SuperSting" not in instrument
                or declared_match is None
                or unit != "Unit: meter"
            ):
                raise RuntimeError(f"unexpected STG header: {item['filename']}")
            declared_records = int(declared_match.group(1))
            parsed = 0
            for row in csv.reader(stream):
                if len(row) < 21:
                    raise RuntimeError(f"short STG row: {item['filename']}")
                rho = float(row[7])
                error_percent = float(row[5]) / 10.0
                current_ma = float(row[6])
                abmn_xyz = [float(value) for value in row[9:21]]
                if not (
                    math.isfinite(rho)
                    and math.isfinite(error_percent)
                    and error_percent >= 0
                    and math.isfinite(current_ma)
                    and current_ma > 0
                    and all(math.isfinite(value) for value in abmn_xyz)
                ):
                    raise RuntimeError(f"invalid STG observation: {item['filename']}")
                response[item["component_id"]].append(
                    math.copysign(math.log1p(abs(rho)), rho)
                )
                errors.append(error_percent)
                parsed += 1
            if parsed != declared_records:
                raise RuntimeError(f"STG record-count drift: {item['filename']}")
            file_audits.append(
                {
                    "component_id": item["component_id"],
                    "filename": item["filename"],
                    "records": parsed,
                    "sha256": item["sha256"],
                }
            )
    if any(not values for values in response.values()):
        raise RuntimeError("empty training component")

    paired_scores = []
    component_ids = sorted(response)
    for held_out in component_ids:
        held_values = np.asarray(response[held_out])
        other_ids = [item for item in component_ids if item != held_out]
        all_other = np.concatenate([np.asarray(response[item]) for item in other_ids])

        baseline_mean = float(np.mean(all_other))
        baseline_sigma = float(np.std(all_other, ddof=1))
        baseline_crps = float(
            np.mean(normal_crps(held_values, baseline_mean, baseline_sigma))
        )

        distances = np.asarray(
            [
                haversine_km(coordinates[held_out], coordinates[item])
                for item in other_ids
            ]
        )
        selected_indices = np.argsort(distances)[:K_NEIGHBORS]
        selected_ids = [other_ids[index] for index in selected_indices]
        selected_distances = distances[selected_indices]
        weights = 1.0 / (selected_distances + 10.0)
        selected_means = np.asarray(
            [np.mean(response[item]) for item in selected_ids]
        )
        candidate_mean = float(np.sum(weights * selected_means) / np.sum(weights))
        centered = np.concatenate(
            [
                np.asarray(response[item]) - np.mean(response[item])
                for item in selected_ids
            ]
        )
        candidate_sigma = float(np.std(centered, ddof=1))
        candidate_crps = float(
            np.mean(normal_crps(held_values, candidate_mean, candidate_sigma))
        )
        paired_scores.append(
            {
                "component_id": held_out,
                "observations": len(held_values),
                "nearest_training_components": selected_ids,
                "nearest_distances_km": selected_distances.tolist(),
                "baseline_crps": baseline_crps,
                "candidate_crps": candidate_crps,
                "relative_improvement": (baseline_crps - candidate_crps)
                / baseline_crps,
            }
        )

    improvements = np.asarray(
        [item["relative_improvement"] for item in paired_scores]
    )
    observed_sd = float(np.std(improvements, ddof=1))
    # Use the one-sided 95% upper confidence bound for sigma so the prospective
    # sample-size calculation is conservative despite only 23 training clusters.
    sigma_upper_95 = observed_sd * math.sqrt(
        (len(improvements) - 1) / chi2.ppf(0.05, len(improvements) - 1)
    )
    z_sum = norm.ppf(1 - ALPHA_ONE_SIDED) + norm.ppf(TARGET_POWER)
    required_crps = math.ceil(
        (z_sum * sigma_upper_95 / TARGET_IMPROVEMENT) ** 2
    )
    required_coverage = {"0.90": 223, "0.95": 118}
    required_all = max(required_crps, *required_coverage.values())
    available_test = design["role_counts"]["test"]

    output = {
        "schema_version": "wp8-taiwan-eri-training-power-v1",
        "design_sha256": sha256(DESIGN),
        "manifest_sha256": sha256(MANIFEST),
        "training_only": True,
        "observation_contract": {
            "training_component_count": len(component_ids),
            "training_file_count": len(file_audits),
            "training_observation_count": sum(len(values) for values in response.values()),
            "v_over_i_present": True,
            "output_current_present": True,
            "apparent_resistivity_present": True,
            "abmn_xyz_present": True,
            "per_observation_repeat_error_present": True,
            "repeat_error_percent": {
                "minimum": float(np.min(errors)),
                "median": float(np.median(errors)),
                "p95": float(np.quantile(errors, 0.95)),
                "maximum": float(np.max(errors)),
            },
        },
        "comparison": {
            "information_parity": "Both models use identical frozen training STG responses and public profile-centre coordinates.",
            "baseline": "global Gaussian predictive distribution in signed-log apparent resistivity",
            "candidate": "fixed four-nearest-component distance-weighted hierarchical Gaussian predictor",
            "validation": "leave-one-correlation-separated-training-component-out",
            "hyperparameter_sweep_performed": False,
        },
        "paired_training_components": len(paired_scores),
        "paired_component_scores": paired_scores,
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
        "test_files_downloaded": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "formal_test_result": None,
        "file_audits": file_audits,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_components": len(paired_scores),
                "training_observations": output["observation_contract"][
                    "training_observation_count"
                ],
                "mean_relative_improvement": output[
                    "exploratory_mean_relative_improvement"
                ],
                "sd_upper_95": sigma_upper_95,
                "required_crps_clusters": required_crps,
                "required_all_metrics": required_all,
                "available_test_clusters": available_test,
                "power_gate": output["wp8_0_power_gate_passes"],
            }
        )
    )


if __name__ == "__main__":
    main()
