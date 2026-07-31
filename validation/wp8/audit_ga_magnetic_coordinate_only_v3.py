#!/usr/bin/env python
# /// script
# dependencies = ["netCDF4==1.7.2", "numpy==2.4.1"]
# ///
"""Extract exact GA test representatives by requesting coordinates only."""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "combined-magnetic-provider-survey-design-v3.json"
)
DATA = ROOT / "validation/wp8/data/ga-magnetic-coordinate-only-v3"
CHECKPOINTS = DATA / "representatives"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "ga-magnetic-coordinate-only-v3.json"
)
WORKERS = 4
ATTEMPTS = 4
ROUNDS = 6
CHUNK_ROWS = 1_000_000
RECORD_TIMEOUT_SECONDS = 600
MAX_RECORD_TIMEOUT_SECONDS = 3600
# GA stores some coordinate actual_range attributes as float32 while the
# coordinate arrays are float64.  Permit only the resulting sub-metre
# quantisation difference; retain both declared and observed ranges in evidence.
ACTUAL_RANGE_ATOL_DEGREES = 2e-5
# These endpoints repeatedly stalled or failed in earlier runs. Process them
# only after all other candidates so they cannot delay useful checkpoints.
DEFERRED_DATASETS = {19132, 19137}
# Dataset 17858 was read coordinate-only in round 1. Its latitude/longitude
# variables contain no valid coordinate pair, so it cannot contribute a
# spatial representative. Retain the exclusion explicitly instead of
# repeatedly downloading the same unusable coordinate arrays.
NO_VALID_COORDINATE_DATASETS = {17858}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def dap_url(download: str) -> str:
    return download.replace("/thredds/fileServer/", "/thredds/dodsC/")


def extract(record: dict) -> dict:
    dataset_no = record["dataset_no"]
    url = dap_url(record["file_download"])
    target_latitude = float(record["centroid_latitude"])
    target_longitude = float(record["centroid_longitude"])
    error: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            with Dataset(url) as dataset:
                names = {name.lower(): name for name in dataset.variables}
                if not {"latitude", "longitude"} <= names.keys():
                    raise RuntimeError(f"coordinate schema drift: {dataset_no}")
                latitude_variable = dataset.variables[names["latitude"]]
                longitude_variable = dataset.variables[names["longitude"]]
                declared_latitude_range = np.asarray(
                    latitude_variable.getncattr("actual_range"), dtype=float
                )
                declared_longitude_range = np.asarray(
                    longitude_variable.getncattr("actual_range"), dtype=float
                )
                if (
                    latitude_variable.shape != longitude_variable.shape
                    or len(latitude_variable.shape) != 1
                ):
                    raise RuntimeError(f"coordinate shape drift: {dataset_no}")
                row_count = int(latitude_variable.shape[0])
                digest = hashlib.sha256()
                valid_count = 0
                observed_latitude_range = np.asarray([np.inf, -np.inf])
                observed_longitude_range = np.asarray([np.inf, -np.inf])
                best_distance2 = np.inf
                best_source_index = -1
                best_latitude = np.nan
                best_longitude = np.nan
                lon_scale = math.cos(math.radians(target_latitude))
                # These are the only remote arrays whose values are requested.
                # Chunking prevents multi-gigabyte coordinate variables from
                # exhausting a worker and makes every OPeNDAP request bounded.
                for start in range(0, row_count, CHUNK_ROWS):
                    stop = min(row_count, start + CHUNK_ROWS)
                    latitude = np.asarray(
                        np.ma.filled(
                            latitude_variable[start:stop], np.nan
                        ),
                        dtype=np.float64,
                    )
                    longitude = np.asarray(
                        np.ma.filled(
                            longitude_variable[start:stop], np.nan
                        ),
                        dtype=np.float64,
                    )
                    if latitude.shape != longitude.shape:
                        raise RuntimeError(
                            f"coordinate chunk shape drift: {dataset_no}"
                        )
                    digest.update(
                        np.ascontiguousarray(latitude).view(np.uint8)
                    )
                    digest.update(
                        np.ascontiguousarray(longitude).view(np.uint8)
                    )
                    valid = (
                        np.isfinite(latitude)
                        & np.isfinite(longitude)
                        & (latitude >= -90.0)
                        & (latitude <= 90.0)
                        & (longitude >= -180.0)
                        & (longitude <= 180.0)
                    )
                    if not np.any(valid):
                        continue
                    valid_count += int(valid.sum())
                    lat = latitude[valid]
                    lon = longitude[valid]
                    observed_latitude_range[0] = min(
                        observed_latitude_range[0], float(np.min(lat))
                    )
                    observed_latitude_range[1] = max(
                        observed_latitude_range[1], float(np.max(lat))
                    )
                    observed_longitude_range[0] = min(
                        observed_longitude_range[0], float(np.min(lon))
                    )
                    observed_longitude_range[1] = max(
                        observed_longitude_range[1], float(np.max(lon))
                    )
                    distance2 = (lat - target_latitude) ** 2 + (
                        (lon - target_longitude) * lon_scale
                    ) ** 2
                    local_index = int(np.argmin(distance2))
                    local_distance2 = float(distance2[local_index])
                    if local_distance2 < best_distance2:
                        source_indices = np.flatnonzero(valid)
                        best_distance2 = local_distance2
                        best_source_index = int(
                            start + source_indices[local_index]
                        )
                        best_latitude = float(lat[local_index])
                        best_longitude = float(lon[local_index])
            if valid_count == 0:
                raise RuntimeError(f"no valid coordinates: {dataset_no}")
            if (
                declared_latitude_range.shape != (2,)
                or declared_longitude_range.shape != (2,)
                or not np.allclose(
                    observed_latitude_range,
                    declared_latitude_range,
                    rtol=0.0,
                    atol=ACTUAL_RANGE_ATOL_DEGREES,
                )
                or not np.allclose(
                    observed_longitude_range,
                    declared_longitude_range,
                    rtol=0.0,
                    atol=ACTUAL_RANGE_ATOL_DEGREES,
                )
            ):
                raise RuntimeError(
                    f"coordinate actual_range mismatch: {dataset_no}"
                )
            return {
                "dataset_no": dataset_no,
                "survey_id": record["survey_id"],
                "source_url": url,
                "requested_value_variables": ["latitude", "longitude"],
                "response_variables_requested": 0,
                "coordinate_rows_requested": row_count,
                "coordinate_chunk_rows": CHUNK_ROWS,
                "valid_coordinate_rows": valid_count,
                "declared_latitude_range": declared_latitude_range.tolist(),
                "declared_longitude_range": declared_longitude_range.tolist(),
                "observed_latitude_range": observed_latitude_range.tolist(),
                "observed_longitude_range": observed_longitude_range.tolist(),
                "actual_range_tolerance_degrees": ACTUAL_RANGE_ATOL_DEGREES,
                "actual_range_max_abs_error_degrees": float(
                    max(
                        np.max(
                            np.abs(
                                observed_latitude_range
                                - declared_latitude_range
                            )
                        ),
                        np.max(
                            np.abs(
                                observed_longitude_range
                                - declared_longitude_range
                            )
                        ),
                    )
                ),
                "coordinate_stream_sha256": digest.hexdigest(),
                "centroid_latitude": target_latitude,
                "centroid_longitude": target_longitude,
                "representative_source_index": best_source_index,
                "representative_latitude": best_latitude,
                "representative_longitude": best_longitude,
                "centroid_to_representative_km": float(
                    math.sqrt(best_distance2) * 111.32
                ),
                "test_unseal_count": 0,
            }
        except Exception as caught:
            error = caught
            if attempt + 1 < ATTEMPTS:
                time.sleep(2**attempt)
    raise RuntimeError(
        f"coordinate-only extraction failed: {dataset_no}"
    ) from error


def extract_isolated(record: dict) -> dict:
    """Run one remote endpoint in a killable process with a hard timeout."""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-dataset",
        str(record["dataset_no"]),
    ]
    size_match = re.search(
        r"([0-9.]+)\s*(KB|MB|GB)",
        str(record.get("catalogue_file_size", "")),
        flags=re.IGNORECASE,
    )
    size_kb = 0.0
    if size_match:
        scale = {"KB": 1.0, "MB": 1024.0, "GB": 1024.0**2}
        size_kb = float(size_match.group(1)) * scale[size_match.group(2).upper()]
    timeout_seconds = min(
        MAX_RECORD_TIMEOUT_SECONDS,
        max(RECORD_TIMEOUT_SECONDS, int(RECORD_TIMEOUT_SECONDS + size_kb / 500.0)),
    )
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as caught:
        raise RuntimeError(
            f"coordinate worker timeout after {timeout_seconds}s: "
            f"{record['dataset_no']}"
        ) from caught
    except subprocess.CalledProcessError as caught:
        raise RuntimeError(
            f"coordinate worker failed: {record['dataset_no']}: "
            f"{caught.stderr[-1000:]}"
        ) from caught
    return json.loads(completed.stdout)


def worker(dataset_no: int) -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    record = next(
        item
        for item in design["ga_coordinate_only_pool_records"]
        if int(item["dataset_no"]) == dataset_no
    )
    print(json.dumps(extract(record)))


def normalize_range_evidence(result: dict) -> dict:
    """Backfill explicit tolerance evidence for resumable pre-change checkpoints."""
    result = dict(result)
    latitude_error = np.max(
        np.abs(
            np.asarray(result["observed_latitude_range"], dtype=float)
            - np.asarray(result["declared_latitude_range"], dtype=float)
        )
    )
    longitude_error = np.max(
        np.abs(
            np.asarray(result["observed_longitude_range"], dtype=float)
            - np.asarray(result["declared_longitude_range"], dtype=float)
        )
    )
    maximum_error = float(max(latitude_error, longitude_error))
    if maximum_error > ACTUAL_RANGE_ATOL_DEGREES:
        raise RuntimeError(
            f"checkpoint coordinate actual_range mismatch: "
            f"{result['dataset_no']} ({maximum_error})"
        )
    result["actual_range_tolerance_degrees"] = ACTUAL_RANGE_ATOL_DEGREES
    result["actual_range_max_abs_error_degrees"] = maximum_error
    return result


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        design["test_unseal_count"] != 0
        or design["test_responses_interpreted"] != 0
        or design["response_values_interpreted_during_selection"] != 0
    ):
        raise RuntimeError("combined design is not sealed")
    records = design["ga_coordinate_only_pool_records"]
    if len(records) != design["ga_coordinate_only_pool_count"]:
        raise RuntimeError("GA v3 coordinate-pool count drift")
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    completed: dict[int, dict] = {}
    excluded = []
    pending = []
    for record in records:
        if record["dataset_no"] in NO_VALID_COORDINATE_DATASETS:
            excluded.append(
                {
                    "dataset_no": record["dataset_no"],
                    "reason": "latitude/longitude variables contain no valid coordinate pair",
                    "response_variables_requested": 0,
                    "test_unseal_count": 0,
                }
            )
            continue
        path = CHECKPOINTS / f"{record['dataset_no']}.json"
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))
            if (
                result.get("dataset_no") == record["dataset_no"]
                and result.get("response_variables_requested") == 0
                and result.get("test_unseal_count") == 0
            ):
                completed[record["dataset_no"]] = normalize_range_evidence(
                    result
                )
                continue
        pending.append(record)
    pending.sort(
        key=lambda record: (
            record["dataset_no"] in DEFERRED_DATASETS,
            record["dataset_no"],
        )
    )
    print(
        json.dumps(
            {
                "resumed": len(completed),
                "pending": len(pending),
                "total": len(records),
            }
        ),
        flush=True,
    )
    failures: dict[int, str] = {}
    for round_index in range(1, ROUNDS + 1):
        if not pending:
            break
        retry = []
        # Threads only supervise isolated Python subprocesses. Each remote
        # OPeNDAP endpoint is therefore forcibly killable on timeout.
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {
                executor.submit(extract_isolated, record): record
                for record in pending
            }
            for future in as_completed(futures):
                record = futures[future]
                try:
                    result = future.result()
                except Exception as caught:
                    retry.append(record)
                    failures[record["dataset_no"]] = repr(caught)
                    print(
                        json.dumps(
                            {
                                "round": round_index,
                                "retry": record["dataset_no"],
                                "error": repr(caught),
                            }
                        ),
                        flush=True,
                    )
                    continue
                path = CHECKPOINTS / f"{result['dataset_no']}.json"
                path.write_text(
                    json.dumps(result, indent=2) + "\n", encoding="utf-8"
                )
                completed[result["dataset_no"]] = normalize_range_evidence(
                    result
                )
                failures.pop(result["dataset_no"], None)
                print(
                    json.dumps(
                        {
                            "completed": len(completed),
                            "total": len(records),
                            "dataset_no": result["dataset_no"],
                            "rows": result["coordinate_rows_requested"],
                        }
                    ),
                    flush=True,
                )
        pending = retry
        if pending and round_index < ROUNDS:
            time.sleep(min(30, 5 * round_index))
    if pending:
        raise RuntimeError(
            "coordinate-only extraction incomplete after "
            f"{ROUNDS} rounds: "
            + json.dumps(
                {
                    record["dataset_no"]: failures[record["dataset_no"]]
                    for record in pending
                },
                sort_keys=True,
            )
        )
    results = [
        completed[record["dataset_no"]]
        for record in records
        if record["dataset_no"] not in NO_VALID_COORDINATE_DATASETS
    ]
    output = {
        "schema_version": "wp8-ga-magnetic-coordinate-only-v3",
        "combined_design_sha256": sha(DESIGN),
        "coordinate_pool_count": len(records),
        "candidate_count": len(results),
        "excluded_coordinate_datasets": excluded,
        "requested_value_variables": ["latitude", "longitude"],
        "response_variables_requested": 0,
        "coordinate_rows_requested": sum(
            result["coordinate_rows_requested"] for result in results
        ),
        "representatives": results,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidates": len(results),
                "coordinate_rows": output["coordinate_rows_requested"],
                "response_variables_requested": 0,
            }
        )
    )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker-dataset":
        worker(int(sys.argv[2]))
    else:
        main()
