#!/usr/bin/env python
"""Leakage-safe multi-state GA magnetic training correlation/crossover pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-consortium-v1"
MANIFEST = DATA / "raw-manifest.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
CONTRACT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-dds-contract.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-training-consortium.json"
RADIUS_KM = 20.0
CELL_M = 5000.0
MAX_LAG_M = 100_000.0
CHUNK = 500_000


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runs(mask: np.ndarray, offset: int) -> list[tuple[int, int]]:
    changes = np.flatnonzero(
        np.concatenate(([False], mask, [False]))[1:]
        != np.concatenate(([False], mask, [False]))[:-1]
    )
    return [
        (offset + int(start), offset + int(end))
        for start, end in zip(changes[::2], changes[1::2])
    ]


def range_from_cells(
    centers: np.ndarray, responses: np.ndarray
) -> tuple[float, bool, list[dict]]:
    centered = centers - np.mean(centers, axis=0)
    design = np.column_stack((np.ones(len(centers)), centered))
    coefficients, *_ = np.linalg.lstsq(design, responses, rcond=None)
    residual = responses - design @ coefficients
    sill = float(np.var(residual, ddof=1))
    delta = centers[:, None, :] - centers[None, :, :]
    distance = np.sqrt(np.sum(delta * delta, axis=2))
    difference = residual[:, None] - residual[None, :]
    upper = np.triu(np.ones(distance.shape, dtype=bool), 1)
    distance = distance[upper]
    semivariance = 0.5 * difference[upper] ** 2
    records = []
    reached = []
    edges = np.arange(0.0, MAX_LAG_M + CELL_M, CELL_M)
    for start, end in zip(edges[:-1], edges[1:]):
        selected = (distance >= start) & (distance < end)
        count = int(np.count_nonzero(selected))
        value = float(np.mean(semivariance[selected])) if count else None
        records.append(
            {
                "lag_center_m": float((start + end) / 2),
                "pairs": count,
                "semivariance_nt2": value,
            }
        )
        reached.append(count >= 30 and value is not None and value >= 0.95 * sill)
    for index in range(len(reached) - 1):
        if reached[index] and reached[index + 1]:
            return max(CELL_M, float(records[index]["lag_center_m"])), False, records
    return MAX_LAG_M, True, records


def audit_member(member: dict, data_dir: Path = DATA) -> dict:
    raw = data_dir / member["path"]
    centers = member["covered_design_cells"]
    center_lat = np.asarray([float(item["cell"].split(":")[0]) for item in centers])
    center_lon = np.asarray([float(item["cell"].split(":")[1]) for item in centers])
    center_roles = np.asarray([item["role"] for item in centers], dtype=object)
    reference_lat = float(np.mean(center_lat))
    lon_scale_km = 111.32 * math.cos(math.radians(reference_lat))
    role_counts = defaultdict(int)
    selected_lat = []
    selected_lon = []
    selected_kind = []
    selected_response = []
    with h5py.File(raw, "r") as handle:
        names = {name.lower(): name for name in handle.keys()}
        required = {"latitude", "longitude", "altitude", "linetype", "line_index"}
        if not required <= names.keys():
            raise RuntimeError(f"training schema drift: {member['dataset_no']}")
        response_key = names.get("mag_awagslevelled")
        if response_key is None:
            raise RuntimeError(f"AWAGS response absent: {member['dataset_no']}")
        rows = len(handle[names["latitude"]])
        line_type_dataset = handle[names["linetype"]]
        line_type_by_line = (
            np.asarray(line_type_dataset[:])
            if len(line_type_dataset) != rows
            else None
        )
        for start in range(0, rows, CHUNK):
            end = min(rows, start + CHUNK)
            latitude = handle[names["latitude"]][start:end]
            longitude = handle[names["longitude"]][start:end]
            dx = (longitude[:, None] - center_lon[None, :]) * lon_scale_km
            dy = (latitude[:, None] - center_lat[None, :]) * 111.32
            distance = np.sqrt(dx * dx + dy * dy)
            nearest = np.argmin(distance, axis=1)
            assigned = center_roles[nearest]
            within = distance[np.arange(len(latitude)), nearest] <= RADIUS_KM
            for role in ("train", "buffer", "calibration", "test"):
                role_counts[role] += int(np.count_nonzero(within & (assigned == role)))
            train = within & (assigned == "train")
            if not np.any(train):
                continue
            chosen = np.flatnonzero(train)
            selected_lat.append(latitude[chosen])
            selected_lon.append(longitude[chosen])
            if line_type_by_line is None:
                selected_kind.append(line_type_dataset[start:end][chosen])
            else:
                line_indices = handle[names["line_index"]][start:end][chosen]
                selected_kind.append(line_type_by_line[line_indices])
            response_parts = [
                handle[response_key][run_start:run_end]
                for run_start, run_end in runs(train, start)
            ]
            selected_response.append(np.concatenate(response_parts))
    latitude = np.concatenate(selected_lat)
    longitude = np.concatenate(selected_lon)
    kind = np.concatenate(selected_kind)
    response = np.concatenate(selected_response)
    finite = np.isfinite(latitude) & np.isfinite(longitude) & np.isfinite(response)
    latitude, longitude, kind, response = (
        latitude[finite],
        longitude[finite],
        kind[finite],
        response[finite],
    )
    x = longitude * lon_scale_km * 1000.0
    y = latitude * 111.32 * 1000.0
    cell_values: dict[tuple[int, int], list[float]] = defaultdict(list)
    crossover: dict[tuple[int, int], dict[int, list[float]]] = defaultdict(
        lambda: {2: [], 4: []}
    )
    for px, py, line_type, value in zip(x, y, kind, response):
        cell_values[(math.floor(px / CELL_M), math.floor(py / CELL_M))].append(
            float(value)
        )
        integer_kind = int(line_type)
        if integer_kind in (2, 4):
            crossover[(math.floor(px / 500.0), math.floor(py / 500.0))][
                integer_kind
            ].append(float(value))
    differences = [
        float(np.mean(values[2]) - np.mean(values[4]))
        for values in crossover.values()
        if values[2] and values[4]
    ]
    cells = sorted(
        (cell, float(np.median(values))) for cell, values in cell_values.items()
    )
    spatial_centers = np.asarray(
        [[(cell[0] + 0.5) * CELL_M, (cell[1] + 0.5) * CELL_M] for cell, _ in cells]
    )
    spatial_response = np.asarray([value for _, value in cells])
    selected_range, censored, variogram = range_from_cells(
        spatial_centers, spatial_response
    )
    return {
        "dataset_no": member["dataset_no"],
        "state": member["state"],
        "training_rows_interpreted": int(len(response)),
        "geometry_rows_by_role": dict(role_counts),
        "heldout_response_rows_interpreted": {
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "training_cells_5km": len(cells),
        "correlation_range_m": selected_range,
        "range_censored_at_100km": censored,
        "variogram": variogram,
        "crossover_bins": len(differences),
        "crossover_rmse_nt": (
            float(np.sqrt(np.mean(np.asarray(differences) ** 2)))
            if differences
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        manifest["design_sha256"] != sha(DESIGN)
        or manifest["acquisition_interpreted_response_values"] != 0
        or design["test_unseal_count"] != 0
        or contract["test_unseal_count"] != 0
    ):
        raise RuntimeError("GA consortium evidence drift")
    members = []
    for member in manifest["members"]:
        raw = args.data / member["path"]
        if raw.stat().st_size != member["bytes"] or sha(raw) != member["sha256"]:
            raise RuntimeError(f"training member drift: {member['dataset_no']}")
        members.append(audit_member(member, args.data))
        print(
            json.dumps(
                {
                    "dataset_no": member["dataset_no"],
                    "training_rows": members[-1]["training_rows_interpreted"],
                    "range_m": members[-1]["correlation_range_m"],
                }
            ),
            flush=True,
        )
    ranges = [member["correlation_range_m"] for member in members]
    result = {
        "schema_version": "wp8-ga-magnetic-training-consortium-audit-v1",
        "raw_manifest_sha256": sha(args.manifest),
        "design_sha256": sha(DESIGN),
        "dds_contract_sha256": sha(CONTRACT),
        "states": manifest["states"],
        "members": members,
        "total_training_rows_interpreted": sum(
            member["training_rows_interpreted"] for member in members
        ),
        "response_rows_interpreted": {
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "conservative_pilot_correlation_range_m": max(ranges),
        "censored_member_count": sum(
            member["range_censored_at_100km"] for member in members
        ),
        "total_crossover_bins": sum(member["crossover_bins"] for member in members),
        "products_sampled": len(members),
        "eligible_catalogue_products": design["eligible_product_count"],
        "catalogue_product_fraction": len(members) / design["eligible_product_count"],
        "pilot_geometry_response_test_clusters": contract["coverage"][
            "geometry_response"
        ]["partition_cell_counts"]["test"],
        "design_center_minimum_spacing_km": design["spatial_design"][
            "minimum_nominal_center_spacing_km"
        ],
        "pilot_range_is_below_design_spacing": (
            max(ranges) / 1000.0
            < design["spatial_design"]["minimum_nominal_center_spacing_km"]
        ),
        "pilot_power_count_possible": (
            contract["coverage"]["geometry_response"]["partition_cell_counts"][
                "test"
            ]
            >= 223
            and max(ranges) / 1000.0
            < design["spatial_design"]["minimum_nominal_center_spacing_km"]
        ),
        "national_correlation_ready": False,
        "national_correlation_reason": (
            f"{len(members)} stratified products are "
            f"{100 * len(members) / design['eligible_product_count']:.2f}% of the "
            f"{design['eligible_product_count']}-product catalogue and cannot yet "
            "establish an upper tolerance bound for unsampled survey heterogeneity"
        ),
        "formal_contract_ready": False,
        "test_unseal_count": 0,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "states": result["states"],
                "training_rows": result["total_training_rows_interpreted"],
                "pilot_range_m": result["conservative_pilot_correlation_range_m"],
                "crossover_bins": result["total_crossover_bins"],
            }
        )
    )


if __name__ == "__main__":
    main()
