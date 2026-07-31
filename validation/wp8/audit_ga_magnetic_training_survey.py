#!/usr/bin/env python
"""Training-only crossover/noise audit for one GA national magnetic survey."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-survey-v1"
MANIFEST = DATA / "raw-manifest.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-training-survey.json"
RESPONSE = "mag_awagslevelled"
RADIUS_KM = 20.0
CHUNK = 500_000
CROSSOVER_BIN_M = 500.0
CORRELATION_CELL_M = 5000.0


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def true_runs(mask: np.ndarray, offset: int) -> list[tuple[int, int]]:
    padded = np.concatenate(([False], mask, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return [
        (offset + int(start), offset + int(end))
        for start, end in zip(changes[::2], changes[1::2])
    ]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    member = manifest["member"]
    raw = DATA / member["path"]
    if (
        manifest["design_sha256"] != sha(DESIGN)
        or manifest["acquisition_interpreted_response_values"] != 0
        or raw.stat().st_size != member["bytes"]
        or sha(raw) != member["sha256"]
        or design["test_unseal_count"] != 0
    ):
        raise RuntimeError("GA training survey freeze drift")
    centers = manifest["covered_design_cells"]
    center_lat = np.asarray([float(item["cell"].split(":")[0]) for item in centers])
    center_lon = np.asarray([float(item["cell"].split(":")[1]) for item in centers])
    center_roles = np.asarray([item["role"] for item in centers], dtype=object)
    reference_lat = float(np.mean(center_lat))
    lon_scale = 111.32 * math.cos(math.radians(reference_lat))
    role_geometry_counts = defaultdict(int)
    training_lat = []
    training_lon = []
    training_alt = []
    training_line_type = []
    training_response = []
    response_runs = 0
    with h5py.File(raw, "r") as handle:
        required = {
            "latitude",
            "longitude",
            "altitude",
            "lineType",
            "line_index",
            RESPONSE,
        }
        if not required <= handle.keys():
            raise RuntimeError("GA training survey schema drift")
        rows = len(handle["latitude"])
        for start in range(0, rows, CHUNK):
            end = min(rows, start + CHUNK)
            latitude = handle["latitude"][start:end]
            longitude = handle["longitude"][start:end]
            dx = (longitude[:, None] - center_lon[None, :]) * lon_scale
            dy = (latitude[:, None] - center_lat[None, :]) * 111.32
            distances = np.sqrt(dx * dx + dy * dy)
            nearest = np.argmin(distances, axis=1)
            assigned = center_roles[nearest]
            within = distances[np.arange(len(latitude)), nearest] <= RADIUS_KM
            for role in ("train", "buffer", "calibration", "test"):
                role_geometry_counts[role] += int(np.count_nonzero(within & (assigned == role)))
            train_mask = within & (assigned == "train")
            if not np.any(train_mask):
                continue
            chosen = np.flatnonzero(train_mask)
            training_lat.append(latitude[chosen])
            training_lon.append(longitude[chosen])
            training_alt.append(handle["altitude"][start:end][chosen])
            training_line_type.append(handle["lineType"][start:end][chosen])
            response_parts = []
            for run_start, run_end in true_runs(train_mask, start):
                # Every index in the slice was classified as train from geometry
                # before the response dataset is accessed.
                response_parts.append(handle[RESPONSE][run_start:run_end])
                response_runs += 1
            training_response.append(np.concatenate(response_parts))

    latitude = np.concatenate(training_lat)
    longitude = np.concatenate(training_lon)
    altitude = np.concatenate(training_alt)
    line_type = np.concatenate(training_line_type)
    response = np.concatenate(training_response)
    finite = np.isfinite(response) & np.isfinite(latitude) & np.isfinite(longitude)
    latitude = latitude[finite]
    longitude = longitude[finite]
    altitude = altitude[finite]
    line_type = line_type[finite]
    response = response[finite]
    x = longitude * lon_scale * 1000.0
    y = latitude * 111.32 * 1000.0

    crossover: dict[tuple[int, int], dict[int, list[float]]] = defaultdict(
        lambda: {2: [], 4: []}
    )
    for px, py, kind, value in zip(x, y, line_type, response):
        integer_kind = int(kind)
        if integer_kind in (2, 4):
            crossover[
                (math.floor(px / CROSSOVER_BIN_M), math.floor(py / CROSSOVER_BIN_M))
            ][integer_kind].append(float(value))
    differences = []
    for values in crossover.values():
        if values[2] and values[4]:
            differences.append(float(np.mean(values[2]) - np.mean(values[4])))
    differences_array = np.asarray(differences)

    spatial: dict[tuple[int, int], list[float]] = defaultdict(list)
    for px, py, value in zip(x, y, response):
        spatial[
            (math.floor(px / CORRELATION_CELL_M), math.floor(py / CORRELATION_CELL_M))
        ].append(float(value))
    cell_items = sorted(
        (cell, float(np.median(values))) for cell, values in spatial.items()
    )
    cell_centers = np.asarray(
        [
            [(cell[0] + 0.5) * CORRELATION_CELL_M,
             (cell[1] + 0.5) * CORRELATION_CELL_M]
            for cell, _ in cell_items
        ]
    )
    cell_response = np.asarray([value for _, value in cell_items])
    centered = cell_centers - np.mean(cell_centers, axis=0)
    coefficients, *_ = np.linalg.lstsq(
        np.column_stack((np.ones(len(centered)), centered)),
        cell_response,
        rcond=None,
    )
    residual = cell_response - np.column_stack(
        (np.ones(len(centered)), centered)
    ) @ coefficients

    result = {
        "schema_version": "wp8-ga-magnetic-training-survey-audit-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "design_sha256": sha(DESIGN),
        "dataset_no": manifest["dataset_no"],
        "response_variable": RESPONSE,
        "selection_policy": {
            "radius_km_around_design_centers": RADIUS_KM,
            "geometry_classified_before_response_access": True,
            "response_access_used_train_only_contiguous_runs": True,
            "response_runs": response_runs,
        },
        "geometry_rows_by_role": dict(role_geometry_counts),
        "response_rows_interpreted": {
            "train": int(len(response)),
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "training_covariates": {
            "main_line_rows": int(np.count_nonzero(line_type == 2)),
            "tie_line_rows": int(np.count_nonzero(line_type == 4)),
            "altitude_min_m": float(np.min(altitude)),
            "altitude_max_m": float(np.max(altitude)),
        },
        "training_crossover_error": {
            "bin_m": CROSSOVER_BIN_M,
            "bins_with_main_and_tie": len(differences),
            "mean_difference_nt": (
                float(np.mean(differences_array)) if len(differences_array) else None
            ),
            "rmse_nt": (
                float(np.sqrt(np.mean(differences_array**2)))
                if len(differences_array)
                else None
            ),
            "mad_nt": (
                float(np.median(np.abs(differences_array - np.median(differences_array))))
                if len(differences_array)
                else None
            ),
            "method_ready": len(differences) >= 30,
        },
        "training_spatial_cells_5km": len(cell_items),
        "regional_plane_residual_sill_nt2": float(np.var(residual, ddof=1)),
        "national_correlation_ready": False,
        "national_correlation_reason": (
            "one survey demonstrates the leakage-safe response and crossover path; "
            "geographically separated training surveys are still required"
        ),
        "formal_contract_ready": False,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": len(response),
                "heldout_geometry_rows": {
                    role: role_geometry_counts[role]
                    for role in ("buffer", "calibration", "test")
                },
                "crossover_bins": len(differences),
                "crossover_rmse_nt": result["training_crossover_error"]["rmse_nt"],
            }
        )
    )


if __name__ == "__main__":
    main()
