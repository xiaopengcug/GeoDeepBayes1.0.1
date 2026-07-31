#!/usr/bin/env python
"""Training-only diagnostics for the clean GA magnetic provider-survey v2 pool."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-survey-design-v2.json"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-survey-training-v2"
MANIFEST = DATA / "raw-manifest.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-survey-training-v2.json"
CHUNK = 500_000
LOCAL_CELL_KM = 10.0
LOCAL_MAX_LAG_KM = 200.0
LOCAL_MAX_CELLS = 2_000
REPRESENTATIVE_MAX_LAG_KM = 2_000.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def response_name(names: dict[str, str]) -> str:
    for candidate in (
        "mag_awagslevelled",
        "mag_microlevelled",
        "mag_tielevelled",
        "magnetics_final_microlevelled",
        "magnetics_final_tielevelled",
        "mag",
        "tmi",
    ):
        if candidate in names:
            return names[candidate]
    raise RuntimeError("no declared magnetic response variable")


def empirical_range(
    xy: np.ndarray,
    response: np.ndarray,
    *,
    lag_km: float,
    max_lag_km: float,
    minimum_pairs: int,
) -> tuple[float, bool, list[dict]]:
    center = np.mean(xy, axis=0)
    x, y = xy[:, 0] - center[0], xy[:, 1] - center[1]
    matrix = np.column_stack([np.ones(len(x)), x, y, x * x, x * y, y * y])
    coefficients, *_ = np.linalg.lstsq(matrix, response, rcond=None)
    residual = response - matrix @ coefficients
    sill = float(np.var(residual, ddof=1))
    bins = int(max_lag_km / lag_km)
    sums = np.zeros(bins)
    counts = np.zeros(bins, dtype=np.int64)
    for index in range(len(xy) - 1):
        distance = np.sqrt(
            np.sum((xy[index + 1 :] - xy[index]) ** 2, axis=1)
        )
        semivariance = 0.5 * (residual[index + 1 :] - residual[index]) ** 2
        indices = np.floor(distance / lag_km).astype(int)
        valid = (indices >= 0) & (indices < bins)
        np.add.at(sums, indices[valid], semivariance[valid])
        np.add.at(counts, indices[valid], 1)
    records, reached = [], []
    for index in range(bins):
        value = float(sums[index] / counts[index]) if counts[index] else None
        records.append(
            {
                "lag_center_km": (index + 0.5) * lag_km,
                "pairs": int(counts[index]),
                "semivariance_nt2": value,
            }
        )
        reached.append(
            counts[index] >= minimum_pairs
            and value is not None
            and value >= 0.95 * sill
        )
    for index in range(len(reached) - 1):
        if reached[index] and reached[index + 1]:
            return max(lag_km, records[index]["lag_center_km"]), False, records
    return max_lag_km, True, records


def audit_member(member: dict, design_record: dict) -> dict:
    path = DATA / member["path"]
    target_latitude = float(design_record["centroid_latitude"])
    target_longitude = float(design_record["centroid_longitude"])
    reference_latitude = target_latitude
    lon_scale = 111.32 * math.cos(math.radians(reference_latitude))
    nearest = None
    cell_sum: dict[tuple[int, int], float] = defaultdict(float)
    cell_count: dict[tuple[int, int], int] = defaultdict(int)
    crossover_sum: dict[tuple[int, int, int], float] = defaultdict(float)
    crossover_count: dict[tuple[int, int, int], int] = defaultdict(int)
    interpreted = 0
    with h5py.File(path, "r") as handle:
        names = {name.lower(): name for name in handle.keys()}
        if not {"latitude", "longitude", "line_index"} <= names.keys():
            raise RuntimeError(f"schema drift: {member['dataset_no']}")
        response_key = response_name(names)
        rows = len(handle[names["latitude"]])
        line_types = handle[names["linetype"]] if "linetype" in names else None
        response_fill = handle[response_key].attrs.get("_FillValue")
        line_type_by_line = (
            np.asarray(line_types[:])
            if line_types is not None and len(line_types) != rows
            else None
        )
        for start in range(0, rows, CHUNK):
            end = min(rows, start + CHUNK)
            latitude = np.asarray(handle[names["latitude"]][start:end], dtype=float)
            longitude = np.asarray(handle[names["longitude"]][start:end], dtype=float)
            response = np.asarray(handle[response_key][start:end], dtype=float)
            if line_types is None:
                kind = np.full(end - start, -1, dtype=int)
            elif line_type_by_line is None:
                kind = np.asarray(line_types[start:end], dtype=int)
            else:
                indices = np.asarray(
                    handle[names["line_index"]][start:end], dtype=int
                )
                valid_indices = (indices >= 0) & (indices < len(line_type_by_line))
                kind = np.full(len(indices), -1, dtype=int)
                kind[valid_indices] = line_type_by_line[
                    indices[valid_indices]
                ].astype(int)
            finite = (
                np.isfinite(latitude)
                & np.isfinite(longitude)
                & np.isfinite(response)
                & (latitude >= -90.0)
                & (latitude <= 90.0)
                & (longitude >= -180.0)
                & (longitude <= 180.0)
            )
            if response_fill is not None:
                finite &= response != float(np.asarray(response_fill).reshape(-1)[0])
            latitude, longitude, response, kind = (
                latitude[finite],
                longitude[finite],
                response[finite],
                kind[finite],
            )
            interpreted += len(response)
            x = longitude * lon_scale
            y = latitude * 111.32
            distance2 = (
                (longitude - target_longitude) * lon_scale
            ) ** 2 + ((latitude - target_latitude) * 111.32) ** 2
            chosen = int(np.argmin(distance2))
            candidate = (
                float(distance2[chosen]),
                float(latitude[chosen]),
                float(longitude[chosen]),
                float(response[chosen]),
            )
            if nearest is None or candidate[0] < nearest[0]:
                nearest = candidate
            local_x = np.floor(x / LOCAL_CELL_KM).astype(np.int64)
            local_y = np.floor(y / LOCAL_CELL_KM).astype(np.int64)
            keys = np.column_stack([local_x, local_y])
            unique, inverse = np.unique(keys, axis=0, return_inverse=True)
            sums = np.bincount(inverse, weights=response)
            counts = np.bincount(inverse)
            for key, total, count in zip(unique, sums, counts):
                cell = (int(key[0]), int(key[1]))
                cell_sum[cell] += float(total)
                cell_count[cell] += int(count)
            crossover_valid = np.isin(kind, (2, 4))
            cross_x = np.floor(x[crossover_valid]).astype(np.int64)
            cross_y = np.floor(y[crossover_valid]).astype(np.int64)
            cross_kind = kind[crossover_valid].astype(np.int64)
            cross_response = response[crossover_valid]
            if len(cross_response):
                cross_keys = np.column_stack([cross_x, cross_y, cross_kind])
                unique, inverse = np.unique(
                    cross_keys, axis=0, return_inverse=True
                )
                sums = np.bincount(inverse, weights=cross_response)
                counts = np.bincount(inverse)
                for key, total, count in zip(unique, sums, counts):
                    item = (int(key[0]), int(key[1]), int(key[2]))
                    crossover_sum[item] += float(total)
                    crossover_count[item] += int(count)
    if nearest is None:
        raise RuntimeError(f"no finite training response: {member['dataset_no']}")
    cells = sorted(cell_sum)
    if len(cells) > LOCAL_MAX_CELLS:
        cells = sorted(
            cells,
            key=lambda cell: hashlib.sha256(
                (
                    f"wp8-ga-mag-local-cells-v2|{member['dataset_no']}|"
                    f"{cell[0]}:{cell[1]}"
                ).encode()
            ).hexdigest(),
        )[:LOCAL_MAX_CELLS]
    local_xy = np.asarray(
        [[(cell[0] + 0.5) * LOCAL_CELL_KM, (cell[1] + 0.5) * LOCAL_CELL_KM] for cell in cells]
    )
    local_response = np.asarray(
        [cell_sum[cell] / cell_count[cell] for cell in cells]
    )
    if len(cells) >= 10:
        local_range, local_censored, variogram = empirical_range(
            local_xy,
            local_response,
            lag_km=LOCAL_CELL_KM,
            max_lag_km=LOCAL_MAX_LAG_KM,
            minimum_pairs=20,
        )
    else:
        local_range, local_censored, variogram = (
            LOCAL_MAX_LAG_KM,
            True,
            [],
        )
    crossover = {}
    for x_cell, y_cell, line_type in crossover_sum:
        key = (x_cell, y_cell)
        crossover.setdefault(key, {})[line_type] = (
            crossover_sum[(x_cell, y_cell, line_type)]
            / crossover_count[(x_cell, y_cell, line_type)]
        )
    differences = [
        values[2] - values[4]
        for values in crossover.values()
        if 2 in values and 4 in values
    ]
    return {
        "dataset_no": member["dataset_no"],
        "survey_id": member["survey_id"],
        "training_response_rows_interpreted": interpreted,
        "representative": {
            "latitude": nearest[1],
            "longitude": nearest[2],
            "magnetic_response_nt": nearest[3],
            "distance_from_catalogue_centroid_km": math.sqrt(nearest[0]),
        },
        "training_cells_10km": len(cell_sum),
        "local_variogram_cells_used": len(cells),
        "local_correlation_range_km": local_range,
        "local_range_censored_at_200km": local_censored,
        "local_variogram": variogram,
        "crossover_bins_1km": len(differences),
        "crossover_rmse_nt": (
            float(np.sqrt(np.mean(np.asarray(differences) ** 2)))
            if differences
            else None
        ),
    }


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["design_sha256"] != sha(DESIGN)
        or manifest["member_count"] != 77
        or manifest["acquisition_interpreted_response_values"] != 0
        or manifest["test_files_downloaded"] != 0
    ):
        raise RuntimeError("GA magnetic v2 raw freeze drift")
    records = {record["dataset_no"]: record for record in design["records"]}
    audits = []
    for index, member in enumerate(manifest["members"], 1):
        path = DATA / member["path"]
        if path.stat().st_size != member["bytes"] or sha(path) != member["sha256"]:
            raise RuntimeError(f"raw drift: {member['dataset_no']}")
        audit = audit_member(member, records[member["dataset_no"]])
        audits.append(audit)
        print(
            {
                "audited": index,
                "dataset_no": member["dataset_no"],
                "rows": audit["training_response_rows_interpreted"],
                "range_km": audit["local_correlation_range_km"],
                "crossover_bins": audit["crossover_bins_1km"],
            },
            flush=True,
        )
    representative_xy = np.asarray(
        [
            [
                audit["representative"]["longitude"]
                * 111.32
                * math.cos(
                    math.radians(audit["representative"]["latitude"])
                ),
                audit["representative"]["latitude"] * 111.32,
            ]
            for audit in audits
        ]
    )
    representative_response = np.asarray(
        [audit["representative"]["magnetic_response_nt"] for audit in audits]
    )
    representative_range, representative_censored, representative_variogram = (
        empirical_range(
            representative_xy,
            representative_response,
            lag_km=50.0,
            max_lag_km=REPRESENTATIVE_MAX_LAG_KM,
            minimum_pairs=10,
        )
    )
    crossover_rmse = [
        audit["crossover_rmse_nt"]
        for audit in audits
        if audit["crossover_rmse_nt"] is not None
    ]
    result = {
        "schema_version": "wp8-ga-magnetic-survey-training-audit-v2",
        "design_sha256": sha(DESIGN),
        "raw_manifest_sha256": sha(MANIFEST),
        "training_surveys": len(audits),
        "training_response_rows_interpreted": sum(
            audit["training_response_rows_interpreted"] for audit in audits
        ),
        "response_rows_interpreted": {
            "train": sum(
                audit["training_response_rows_interpreted"] for audit in audits
            ),
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "audits": audits,
        "local_range_summary_km": {
            "maximum": max(audit["local_correlation_range_km"] for audit in audits),
            "median": float(
                np.median(
                    [audit["local_correlation_range_km"] for audit in audits]
                )
            ),
            "censored_surveys": sum(
                audit["local_range_censored_at_200km"] for audit in audits
            ),
        },
        "cross_survey_representative_range_km": representative_range,
        "cross_survey_range_censored_at_2000km": representative_censored,
        "cross_survey_variogram": representative_variogram,
        "training_crossover_noise_floor_nt": (
            float(np.quantile(crossover_rmse, 0.95)) if crossover_rmse else None
        ),
        "training_surveys_with_crossover_noise": len(crossover_rmse),
        "observation_contract_potential": bool(crossover_rmse),
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "training_surveys": len(audits),
            "rows": result["training_response_rows_interpreted"],
            "local_range": result["local_range_summary_km"],
            "cross_survey_range_km": representative_range,
            "cross_survey_censored": representative_censored,
            "noise_floor_nt": result["training_crossover_noise_floor_nt"],
        }
    )


if __name__ == "__main__":
    main()
