#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["netCDF4==1.7.2", "numpy==2.4.1", "scipy==1.17.0"]
# ///
"""Conservative provider-survey and spatial-separation audit for GA gravity."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from netCDF4 import Dataset
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
POOL_MANIFEST = DATA / "pool-manifest.json"
GEOMETRY = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-geometry.json"
TRAINING = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-training.json"
POWER = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-power.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-separation.json"
REFERENCE_LATITUDE = -25.0
ELEVATION_COEFFICIENT_UM_S2_PER_M = 1.967


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def values(variable) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=float)


def eligible_coordinates(path: Path, lon_scale: float) -> np.ndarray:
    with Dataset(path, "r") as dataset:
        arrays = {
            name: values(dataset.variables[name])
            for name in ("latitude", "longitude", "gravacc", "gndelevacc", "tcerr")
        }
    common = min(map(len, arrays.values()))
    arrays = {name: value[:common] for name, value in arrays.items()}
    sigma = np.sqrt(
        arrays["gravacc"] ** 2
        + (ELEVATION_COEFFICIENT_UM_S2_PER_M * arrays["gndelevacc"]) ** 2
        + arrays["tcerr"] ** 2
    )
    mask = np.ones(common, dtype=bool)
    for value in arrays.values():
        mask &= np.isfinite(value)
    mask &= (
        np.isfinite(sigma)
        & (arrays["gravacc"] >= 0)
        & (arrays["gndelevacc"] >= 0)
        & (arrays["tcerr"] >= 0)
        & (sigma > 0)
    )
    return np.column_stack(
        [
            arrays["longitude"][mask] * lon_scale,
            arrays["latitude"][mask] * 111.32,
        ]
    )


def main() -> None:
    pool = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    training = json.loads(TRAINING.read_text(encoding="utf-8"))
    power = json.loads(POWER.read_text(encoding="utf-8"))
    range_km = float(training["correlation_range_km"])
    members = {
        member["survey_id"]: DATA / member["path"] for member in pool["members"]
    }
    retained = [
        survey for survey in geometry["surveys"] if survey["status"] == "retained"
    ]
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    protected_parts = []
    candidates = []
    quality_empty = []
    for survey in retained:
        role = survey["retained_role"]
        coordinates = eligible_coordinates(members[survey["survey_id"]], lon_scale)
        if not len(coordinates):
            quality_empty.append(survey["survey_id"])
            continue
        if role in {"train", "calibration"}:
            protected_parts.append(coordinates)
        elif role == "test":
            center = np.median(coordinates, axis=0)
            representative = coordinates[
                np.argmin(np.sum((coordinates - center) ** 2, axis=1))
            ]
            candidates.append(
                {
                    "survey_id": survey["survey_id"],
                    "x_km": float(representative[0]),
                    "y_km": float(representative[1]),
                }
            )
    protected = np.vstack(protected_parts)
    protected_tree = cKDTree(protected)
    separated = []
    excluded_near_training = []
    for candidate in candidates:
        point = np.asarray([candidate["x_km"], candidate["y_km"]])
        distance, _ = protected_tree.query(point, k=1)
        candidate["nearest_train_or_calibration_km"] = float(distance)
        if distance < range_km:
            excluded_near_training.append(candidate)
        else:
            separated.append(candidate)
    # Deterministic hash order prevents outcome-dependent packing.
    separated.sort(
        key=lambda item: hashlib.sha256(
            f"wp8-ga-gravity-pack-v1|{item['survey_id']}".encode()
        ).hexdigest()
    )
    accepted = []
    for candidate in separated:
        point = np.asarray([candidate["x_km"], candidate["y_km"]])
        if all(
            np.linalg.norm(
                point - np.asarray([other["x_km"], other["y_km"]])
            )
            >= range_km
            for other in accepted
        ):
            accepted.append(candidate)
    available = len(accepted)
    required = int(power["required_clusters_all_metrics"])
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-separation-v1",
        "pool_manifest_sha256": sha(POOL_MANIFEST),
        "geometry_sha256": sha(GEOMETRY),
        "training_sha256": sha(TRAINING),
        "power_sha256": sha(POWER),
        "fields_read": [
            "latitude",
            "longitude",
            "gravacc",
            "gndelevacc",
            "tcerr",
        ],
        "response_fields_read": [],
        "policy": {
            "provider_cap": "at most one representative per retained provider survey",
            "representative": (
                "observed station nearest the componentwise median of eligible "
                "station coordinates"
            ),
            "protected_roles": ["train", "calibration"],
            "minimum_train_calibration_distance_km": range_km,
            "minimum_test_pair_distance_km": range_km,
            "packing_order": "SHA-256 wp8-ga-gravity-pack-v1|survey_id",
        },
        "test_provider_survey_candidates": len(candidates),
        "quality_empty_surveys": quality_empty,
        "excluded_near_train_or_calibration": len(excluded_near_training),
        "candidates_after_protected_distance": len(separated),
        "accepted_independent_test_surveys": available,
        "required_clusters_all_metrics": required,
        "provider_spatial_power_gate_passes": available >= required,
        "accepted": accepted,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "candidates": len(candidates),
            "near_protected": len(excluded_near_training),
            "after_distance": len(separated),
            "accepted": available,
            "required": required,
            "passes": result["provider_spatial_power_gate_passes"],
        }
    )


if __name__ == "__main__":
    main()
