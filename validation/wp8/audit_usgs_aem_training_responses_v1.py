#!/usr/bin/env python
# /// script
# dependencies = ["netCDF4==1.7.2", "numpy==2.4.1"]
# ///
"""Training-only response diagnostics for preregistered USGS AEM NetCDF files."""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-aem-training-expansion-design-v1.json"
)
DATA = ROOT / "validation/wp8/data/usgs-aem-training-expansion-v1/files"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-aem-training-response-diagnostics-v1.json"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def values(variable) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=np.float64)


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        design["test_unseal_count"] != 0
        or design["test_responses_interpreted"] != 0
    ):
        raise RuntimeError("USGS AEM training design is not sealed")
    records = []
    for survey in design["training_surveys"]:
        payload = survey["payload"]
        path = DATA / f"{survey['sciencebase_id']}__{payload['name']}"
        if (
            not path.exists()
            or path.stat().st_size != payload["size"]
            or path.suffix.lower() != ".nc"
        ):
            continue
        with Dataset(path) as dataset:
            if "survey" not in dataset.groups:
                continue
            survey_group = dataset.groups["survey"]
            if "processed_data" in survey_group.groups:
                group = survey_group.groups["processed_data"]
                group_path = "/survey/processed_data"
            elif (
                "tabular" in survey_group.groups
                and "1" in survey_group.groups["tabular"].groups
            ):
                group = survey_group.groups["tabular"].groups["1"]
                group_path = "/survey/tabular/1"
            else:
                continue
            names = {name.lower(): name for name in group.variables}
            aliases = {
                "low": ("dbdtlm", "lm_data"),
                "high": ("dbdthm", "hm_data"),
                "low_std": ("dbdtlm_std", "lm_datastd"),
                "high_std": ("dbdthm_std", "hm_datastd"),
                "low_times": ("lm_gate_times", "lm_gate_times_centers"),
                "high_times": ("hm_gate_times", "hm_gate_times_centers"),
            }
            selected_names = {
                key: next((names[name] for name in options if name in names), None)
                for key, options in aliases.items()
            }
            if any(name is None for name in selected_names.values()):
                continue
            low = values(group.variables[selected_names["low"]])
            high = values(group.variables[selected_names["high"]])
            low_std = values(group.variables[selected_names["low_std"]])
            high_std = values(group.variables[selected_names["high_std"]])
            low_times = values(group.variables[selected_names["low_times"]])
            high_times = values(group.variables[selected_names["high_times"]])
            if {"lon", "lat"} <= names.keys():
                coordinate_mode = "geographic_degrees"
                coordinate_x = values(group.variables[names["lon"]])
                coordinate_y = values(group.variables[names["lat"]])
                adjacent_distance_km = 111.32 * np.sqrt(
                    np.diff(coordinate_y) ** 2
                    + (
                        np.diff(coordinate_x)
                        * np.cos(
                            np.deg2rad(
                                (coordinate_y[:-1] + coordinate_y[1:]) / 2.0
                            )
                        )
                    )
                    ** 2
                )
            elif {"e_n83wtm", "n_n83wtm"} <= names.keys():
                coordinate_mode = "projected_meters"
                coordinate_x = values(group.variables[names["e_n83wtm"]])
                coordinate_y = values(group.variables[names["n_n83wtm"]])
                adjacent_distance_km = (
                    np.sqrt(
                        np.diff(coordinate_x) ** 2
                        + np.diff(coordinate_y) ** 2
                    )
                    / 1000.0
                )
            else:
                continue
            line_name = next(
                (
                    name
                    for name, variable in group.variables.items()
                    if "line" in name.lower()
                    or "line" in str(
                        getattr(variable, "standard_name", "")
                    ).lower()
                ),
                None,
            )
            declared_lines = (
                values(group.variables[line_name])
                if line_name
                else None
            )
            # Processed_data has no line variable in the Delaware release.
            # Split only at conservative >1-km trajectory jumps rather than
            # falsely treating the full concatenated survey as one line.
            trajectory_segments = np.zeros(len(coordinate_x), dtype=np.int64)
            trajectory_segments[1:] = np.cumsum(
                ~np.isfinite(adjacent_distance_km)
                | (adjacent_distance_km > 1.0)
            )
            lines = (
                declared_lines
                if declared_lines is not None
                else trajectory_segments
            )
        valid_low = np.isfinite(low) & np.isfinite(low_std) & (low_std > 0)
        valid_high = (
            np.isfinite(high) & np.isfinite(high_std) & (high_std > 0)
        )
        scale_ratio = float(
            np.nanmedian(np.concatenate([low_std.ravel(), high_std.ravel()]))
            / np.nanmedian(
                np.abs(np.concatenate([low.ravel(), high.ravel()]))
            )
        )
        uncertainty_semantics = (
            "relative_standard_deviation_factor"
            if scale_ratio > 1e6
            else "absolute_standard_deviation"
        )
        absolute_low_sigma = (
            np.abs(low) * low_std
            if uncertainty_semantics == "relative_standard_deviation_factor"
            else low_std
        )
        absolute_high_sigma = (
            np.abs(high) * high_std
            if uncertainty_semantics == "relative_standard_deviation_factor"
            else high_std
        )
        standardized = np.concatenate(
            [
                np.where(valid_low & (absolute_low_sigma > 0), low / absolute_low_sigma, np.nan),
                np.where(valid_high & (absolute_high_sigma > 0), high / absolute_high_sigma, np.nan),
            ],
            axis=1,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="All-NaN slice encountered", category=RuntimeWarning
            )
            scalar = np.nanmedian(
                np.sign(standardized) * np.log1p(np.abs(standardized)), axis=1
            )
        correlations = []
        for lag in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
            if lag >= len(scalar):
                break
            selected = (
                np.isfinite(scalar[:-lag])
                & np.isfinite(scalar[lag:])
                & (lines[:-lag] == lines[lag:])
            )
            if int(selected.sum()) < 100:
                continue
            left = scalar[:-lag][selected]
            right = scalar[lag:][selected]
            correlation = float(np.corrcoef(left, right)[0, 1])
            if coordinate_mode == "geographic_degrees":
                distance_km = 111.32 * np.sqrt(
                    (coordinate_y[:-lag][selected] - coordinate_y[lag:][selected])
                    ** 2
                    + (
                        (
                            coordinate_x[:-lag][selected]
                            - coordinate_x[lag:][selected]
                        )
                        * np.cos(
                            np.deg2rad(
                                (
                                    coordinate_y[:-lag][selected]
                                    + coordinate_y[lag:][selected]
                                )
                                / 2.0
                            )
                        )
                    )
                    ** 2
                )
            else:
                distance_km = (
                    np.sqrt(
                        (
                            coordinate_x[:-lag][selected]
                            - coordinate_x[lag:][selected]
                        )
                        ** 2
                        + (
                            coordinate_y[:-lag][selected]
                            - coordinate_y[lag:][selected]
                        )
                        ** 2
                    )
                    / 1000.0
                )
            correlations.append(
                {
                    "index_lag": lag,
                    "pair_count": int(selected.sum()),
                    "median_distance_km": float(np.median(distance_km)),
                    "correlation": correlation,
                }
            )
        range_candidates = [
            item["median_distance_km"]
            for item in correlations
            if item["correlation"] <= 0.05
        ]
        records.append(
            {
                "sciencebase_id": survey["sciencebase_id"],
                "systems": survey["systems"],
                "response_group": group_path,
                "coordinate_mode": coordinate_mode,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "processed_rows": int(len(scalar)),
                "processed_line_variable_present": line_name is not None,
                "declared_unique_lines": (
                    int(len(np.unique(declared_lines[np.isfinite(declared_lines)])))
                    if declared_lines is not None
                    else None
                ),
                "trajectory_segments_at_1km_jump": int(
                    len(np.unique(trajectory_segments))
                ),
                "low_moment_gate_count": int(len(low_times)),
                "high_moment_gate_count": int(len(high_times)),
                "low_moment_gate_range_seconds": [
                    float(np.min(low_times)),
                    float(np.max(low_times)),
                ],
                "high_moment_gate_range_seconds": [
                    float(np.min(high_times)),
                    float(np.max(high_times)),
                ],
                "valid_low_moment_response_uncertainty_pairs": int(
                    valid_low.sum()
                ),
                "valid_high_moment_response_uncertainty_pairs": int(
                    valid_high.sum()
                ),
                "uncertainty_semantics": uncertainty_semantics,
                "uncertainty_to_response_median_scale_ratio": scale_ratio,
                "stored_uncertainty_value_p50": float(
                    np.nanmedian(
                        np.concatenate(
                            [
                                np.where(valid_low, low_std, np.nan).ravel(),
                                np.where(valid_high, high_std, np.nan).ravel(),
                            ]
                        )
                    )
                ),
                "stored_uncertainty_value_p95": float(
                    np.nanquantile(
                        np.concatenate(
                            [
                                np.where(valid_low, low_std, np.nan).ravel(),
                                np.where(valid_high, high_std, np.nan).ravel(),
                            ]
                        ),
                        0.95,
                    )
                ),
                "standardized_response_absolute_p95_after_relative_sigma_conversion": float(
                    np.nanquantile(np.abs(standardized), 0.95)
                ),
                "training_along_line_correlations": correlations,
                "training_correlation_range_km": (
                    float(range_candidates[0])
                    if range_candidates
                    else None
                ),
            }
        )
    output = {
        "schema_version": "wp8-usgs-aem-training-response-diagnostics-v1",
        "design_sha256": sha(DESIGN),
        "completed_netcdf_training_survey_count": len(records),
        "records": records,
        "training_response_values_interpreted": sum(
            record["valid_low_moment_response_uncertainty_pairs"]
            + record["valid_high_moment_response_uncertainty_pairs"]
            for record in records
        ),
        "paired_crps_effect_size_available": False,
        "power_gate_passed": False,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_surveys": len(records),
                "response_uncertainty_pairs": output[
                    "training_response_values_interpreted"
                ],
                "test_responses_interpreted": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
