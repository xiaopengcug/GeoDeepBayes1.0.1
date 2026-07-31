#!/usr/bin/env python
"""Final sealed geometry audit for the combined GA + USGS magnetic v3 design."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "combined-magnetic-provider-survey-design-v3.json"
COORDINATES = EVIDENCE / "ga-magnetic-coordinate-only-v3.json"
OUT = EVIDENCE / "combined-magnetic-provider-separation-v3.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    latitude = (a[0] + b[0]) / 2.0
    return math.hypot(
        (a[0] - b[0]) * 111.32,
        (a[1] - b[1])
        * 111.32
        * math.cos(math.radians(latitude)),
    )


def maximum_independent(
    records: list[dict], range_km: float
) -> tuple[list[dict], int, float]:
    edges = []
    for index in range(len(records)):
        point = (
            records[index]["representative_latitude"],
            records[index]["representative_longitude"],
        )
        for other in range(index):
            other_point = (
                records[other]["representative_latitude"],
                records[other]["representative_longitude"],
            )
            if distance_km(point, other_point) < range_km:
                edges.append((index, other))
    if not edges:
        return records, 0, 0.0
    rows = [row for row in range(len(edges)) for _ in (0, 1)]
    columns = [node for edge in edges for node in edge]
    matrix = coo_matrix(
        (np.ones(2 * len(edges)), (rows, columns)),
        shape=(len(edges), len(records)),
    ).tocsr()
    tie = np.asarray(
        [
            int(
                hashlib.sha256(
                    f"wp8-combined-mag-final-v3|{record['survey_id']}".encode()
                ).hexdigest()[:12],
                16,
            )
            / float(16**12)
            for record in records
        ]
    )
    result = milp(
        c=-(np.ones(len(records)) + tie / (10.0 * len(records))),
        integrality=np.ones(len(records)),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(
            matrix, -np.inf, np.ones(len(edges))
        ),
        options={"mip_rel_gap": 0.0},
    )
    if result.status != 0 or result.x is None:
        raise RuntimeError(f"final separation MILP failed: {result.message}")
    selected = [
        record for record, value in zip(records, result.x) if value > 0.5
    ]
    return selected, len(edges), float(result.mip_gap)


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    coordinates = json.loads(COORDINATES.read_text(encoding="utf-8"))
    range_km = float(design["correlation_range_km"])
    if (
        design["test_unseal_count"] != 0
        or coordinates["test_unseal_count"] != 0
        or coordinates["response_variables_requested"] != 0
        or coordinates.get("coordinate_pool_count")
        != design["ga_coordinate_only_pool_count"]
        or coordinates["candidate_count"]
        + len(coordinates.get("excluded_coordinate_datasets", []))
        != design["ga_coordinate_only_pool_count"]
        or coordinates.get("excluded_coordinate_datasets")
        != [
            {
                "dataset_no": 17858,
                "reason": "latitude/longitude variables contain no valid coordinate pair",
                "response_variables_requested": 0,
                "test_unseal_count": 0,
            }
        ]
    ):
        raise RuntimeError("sealed geometry chain drift")
    train = [
        (
            record["representative"]["latitude"],
            record["representative"]["longitude"],
        )
        for record in design["ga_training_records"]
    ]
    candidates = []
    excluded_near_training = []
    for record in coordinates["representatives"]:
        point = (
            record["representative_latitude"],
            record["representative_longitude"],
        )
        minimum = min(distance_km(point, anchor) for anchor in train)
        prepared = dict(record)
        prepared["minimum_training_distance_km"] = minimum
        if minimum >= range_km:
            candidates.append(prepared)
        else:
            excluded_near_training.append(prepared)
    ga_selected, conflict_edges, mip_gap = maximum_independent(
        candidates, range_km
    )
    usgs_count = design["usgs_bbox_maximum_independent_set_count"]
    combined = len(ga_selected) + usgs_count
    result = {
        "schema_version": "wp8-combined-magnetic-provider-separation-v3",
        "combined_design_sha256": sha(DESIGN),
        "ga_coordinate_only_sha256": sha(COORDINATES),
        "correlation_range_km": range_km,
        "ga_input_candidate_count": coordinates["candidate_count"],
        "ga_excluded_near_training_count": len(excluded_near_training),
        "ga_post_training_distance_candidate_count": len(candidates),
        "ga_actual_representative_conflict_edge_count": conflict_edges,
        "ga_actual_representative_independent_count": len(ga_selected),
        "ga_final_mip_gap": mip_gap,
        "usgs_conservative_bbox_independent_count": usgs_count,
        "combined_independent_test_count": combined,
        "required_independent_test_count": 223,
        "cluster_count_gate_passed": combined >= 223,
        "ga_selected_records": ga_selected,
        "ga_excluded_near_training_records": excluded_near_training,
        "usgs_selected_records": design[
            "usgs_external_candidate_test_records"
        ],
        "response_variables_requested_for_geometry": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "ga_actual_independent": len(ga_selected),
            "usgs_bbox_independent": usgs_count,
            "combined": combined,
            "required": 223,
            "passed": combined >= 223,
        }
    )


if __name__ == "__main__":
    main()
