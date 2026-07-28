#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["netCDF4==1.7.2"]
# ///
"""Station-geometry-only leakage audit for the frozen GA national gravity pool."""
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
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-design.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-geometry.json"
BLOCK_KM = 55.0
REFERENCE_LATITUDE = -25.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def role(block: str) -> str:
    bucket = int(
        hashlib.sha256(
            f"wp8-ga-national-ground-gravity-v1|{block}".encode()
        ).hexdigest()[:8],
        16,
    ) % 100
    if bucket < 20:
        return "train"
    if bucket < 30:
        return "buffer"
    if bucket < 40:
        return "calibration"
    return "test"


def main() -> None:
    pool = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    declared = {
        record["survey_id"]: int(record["declared_stations"])
        for record in design["records"]
    }
    lon_scale = 111.32 * math.cos(math.radians(REFERENCE_LATITUDE))
    surveys = []
    global_retained_blocks = {value: set() for value in ("train", "buffer", "calibration", "test")}
    coordinate_rows = 0
    for index, member in enumerate(pool["members"], 1):
        path = DATA / member["path"]
        with Dataset(path, "r") as dataset:
            if "latitude" not in dataset.variables or "longitude" not in dataset.variables:
                surveys.append(
                    {
                        "survey_id": member["survey_id"],
                        "status": "excluded_missing_coordinate_schema",
                    }
                )
                continue
            # No response, anomaly, correction, accuracy or reliability array is read.
            latitude = np.ma.filled(dataset.variables["latitude"][:], np.nan)
            longitude = np.ma.filled(dataset.variables["longitude"][:], np.nan)
        valid = np.isfinite(latitude) & np.isfinite(longitude)
        latitude = np.asarray(latitude[valid], dtype=float)
        longitude = np.asarray(longitude[valid], dtype=float)
        coordinate_rows += len(latitude)
        blocks = {
            (
                f"{math.floor(lon * lon_scale / BLOCK_KM)}:"
                f"{math.floor(lat * 111.32 / BLOCK_KM)}"
            )
            for lat, lon in zip(latitude, longitude)
        }
        roles = {role(block) for block in blocks}
        if not blocks:
            status = "excluded_no_valid_coordinates"
            retained_role = None
        elif len(roles) != 1:
            status = "excluded_cross_role_footprint"
            retained_role = None
        else:
            status = "retained"
            retained_role = next(iter(roles))
            global_retained_blocks[retained_role].update(blocks)
        surveys.append(
            {
                "survey_id": member["survey_id"],
                "declared_stations": declared[member["survey_id"]],
                "coordinate_rows": len(latitude),
                "declared_count_matches": len(latitude) == declared[member["survey_id"]],
                "occupied_blocks": len(blocks),
                "roles_touched": sorted(roles),
                "status": status,
                "retained_role": retained_role,
            }
        )
        if index % 200 == 0:
            print(f"geometry {index}/{len(pool['members'])}")
    statuses = Counter(survey["status"] for survey in surveys)
    retained_surveys = Counter(
        survey["retained_role"]
        for survey in surveys
        if survey.get("status") == "retained"
    )
    retained_blocks = {
        assigned: len(blocks) for assigned, blocks in global_retained_blocks.items()
    }
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-geometry-v1",
        "pool_manifest_sha256": sha(POOL_MANIFEST),
        "design_sha256": sha(DESIGN),
        "coordinate_fields_read": ["latitude", "longitude"],
        "response_fields_read": [],
        "uncertainty_fields_read": [],
        "coordinate_rows_read": coordinate_rows,
        "survey_status_counts": dict(statuses),
        "retained_survey_role_counts": dict(retained_surveys),
        "retained_unique_block_counts": retained_blocks,
        "leakage_policy": (
            "Exclude an entire provider survey if its station coordinates occupy "
            "55-km blocks assigned to more than one role."
        ),
        "station_level_test_cluster_upper_bound": retained_blocks["test"],
        "station_level_power_gate_possible": retained_blocks["test"] >= 223,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "surveys": surveys,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "coordinate_rows": coordinate_rows,
            "status": dict(statuses),
            "retained_surveys": dict(retained_surveys),
            "retained_blocks": retained_blocks,
            "power_possible": result["station_level_power_gate_possible"],
        }
    )


if __name__ == "__main__":
    main()
