#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["netCDF4==1.7.2"]
# ///
"""Outcome-blind uncertainty-coverage audit for leakage-safe GA gravity surveys."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
POOL_MANIFEST = DATA / "pool-manifest.json"
GEOMETRY = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-geometry.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-uncertainty.json"
BLOCK_KM = 55.0
REFERENCE_LATITUDE = -25.0
ELEVATION_COEFFICIENT_UM_S2_PER_M = 1.967
REQUIRED_SCHEMA = {"bouguer", "tc", "gravacc", "gndelevacc", "tcerr"}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def values(variable) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=float)


def main() -> None:
    pool = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    member_paths = {
        member["survey_id"]: DATA / member["path"] for member in pool["members"]
    }
    retained = [
        survey for survey in geometry["surveys"] if survey["status"] == "retained"
    ]
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    eligible_blocks = {value: set() for value in ("train", "buffer", "calibration", "test")}
    role_points = Counter()
    role_eligible = Counter()
    statuses = Counter()
    surveys = []
    for index, survey in enumerate(retained, 1):
        role = survey["retained_role"]
        with Dataset(member_paths[survey["survey_id"]], "r") as dataset:
            declared = set(dataset.variables)
            missing = sorted(REQUIRED_SCHEMA - declared)
            if missing:
                statuses["missing_required_schema"] += 1
                surveys.append(
                    {
                        "survey_id": survey["survey_id"],
                        "role": role,
                        "status": "missing_required_schema",
                        "missing_variables": missing,
                    }
                )
                continue
            latitude = values(dataset.variables["latitude"])
            longitude = values(dataset.variables["longitude"])
            gravity_accuracy = values(dataset.variables["gravacc"])
            elevation_accuracy = values(dataset.variables["gndelevacc"])
            terrain_error = values(dataset.variables["tcerr"])
        common = min(
            len(latitude),
            len(longitude),
            len(gravity_accuracy),
            len(elevation_accuracy),
            len(terrain_error),
        )
        latitude, longitude = latitude[:common], longitude[:common]
        gravity_accuracy = gravity_accuracy[:common]
        elevation_accuracy = elevation_accuracy[:common]
        terrain_error = terrain_error[:common]
        sigma_um_s2 = np.sqrt(
            gravity_accuracy**2
            + (ELEVATION_COEFFICIENT_UM_S2_PER_M * elevation_accuracy) ** 2
            + terrain_error**2
        )
        eligible = (
            np.isfinite(latitude)
            & np.isfinite(longitude)
            & np.isfinite(gravity_accuracy)
            & np.isfinite(elevation_accuracy)
            & np.isfinite(terrain_error)
            & np.isfinite(sigma_um_s2)
            & (gravity_accuracy >= 0.0)
            & (elevation_accuracy >= 0.0)
            & (terrain_error >= 0.0)
            & (sigma_um_s2 > 0.0)
        )
        role_points[role] += common
        role_eligible[role] += int(np.count_nonzero(eligible))
        for lat, lon in zip(latitude[eligible], longitude[eligible]):
            block = (
                math.floor(lon * lon_scale / BLOCK_KM),
                math.floor(lat * 111.32 / BLOCK_KM),
            )
            eligible_blocks[role].add(block)
        status = "eligible_rows_present" if np.any(eligible) else "no_eligible_rows"
        statuses[status] += 1
        surveys.append(
            {
                "survey_id": survey["survey_id"],
                "role": role,
                "status": status,
                "rows": common,
                "eligible_rows": int(np.count_nonzero(eligible)),
                "eligible_fraction": float(np.mean(eligible)) if common else 0.0,
            }
        )
        if index % 100 == 0:
            print(f"uncertainty {index}/{len(retained)}")
    block_counts = {
        role: len(blocks) for role, blocks in eligible_blocks.items()
    }
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-uncertainty-v1",
        "pool_manifest_sha256": sha(POOL_MANIFEST),
        "geometry_sha256": sha(GEOMETRY),
        "selection_policy_frozen_before_quality_values": (
            "Retain rows with finite coordinates; finite nonnegative gravacc, "
            "gndelevacc and tcerr; and strictly positive propagated sigma."
        ),
        "propagation": {
            "formula": (
                "sigma_cba_mgal = sqrt(gravacc^2 + "
                "(1.967*gndelevacc)^2 + tcerr^2) / 10"
            ),
            "input_units": {
                "gravacc": "um/s^2",
                "gndelevacc": "m",
                "tcerr": "um/s^2",
            },
            "elevation_coefficient_um_s2_per_m": ELEVATION_COEFFICIENT_UM_S2_PER_M,
        },
        "fields_read": [
            "latitude",
            "longitude",
            "gravacc",
            "gndelevacc",
            "tcerr",
        ],
        "response_fields_read": [],
        "role_row_counts": dict(role_points),
        "role_eligible_row_counts": dict(role_eligible),
        "eligible_unique_block_counts": block_counts,
        "survey_status_counts": dict(statuses),
        "uncertainty_qualified_test_cluster_upper_bound": block_counts["test"],
        "uncertainty_power_gate_possible": block_counts["test"] >= 223,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "surveys": surveys,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "statuses": dict(statuses),
            "eligible_rows": dict(role_eligible),
            "eligible_blocks": block_counts,
            "power_possible": result["uncertainty_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
