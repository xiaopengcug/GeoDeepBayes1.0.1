#!/usr/bin/env python
"""Freeze the GA + USGS magnetic provider-survey v3 candidate design."""
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
GA_DESIGN = EVIDENCE / "geoscience-australia-magnetic-survey-design-v2.json"
GA_TRAIN = EVIDENCE / "geoscience-australia-magnetic-survey-training-v2.json"
USGS_AUDIT = EVIDENCE / "usgs-sciencebase-magnetic-catalogue-audit-v1.json"
OUT = EVIDENCE / "combined-magnetic-provider-survey-design-v3.json"
RANGE_KM = 75.0


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


def independent_set(records: list[dict]) -> tuple[list[dict], int, float]:
    edges = []
    for index in range(len(records)):
        point = (
            records[index]["centroid_latitude"],
            records[index]["centroid_longitude"],
        )
        for other in range(index):
            other_point = (
                records[other]["centroid_latitude"],
                records[other]["centroid_longitude"],
            )
            if distance_km(point, other_point) < RANGE_KM:
                edges.append((index, other))
    rows = [row for row in range(len(edges)) for _ in (0, 1)]
    columns = [node for edge in edges for node in edge]
    matrix = coo_matrix(
        (np.ones(2 * len(edges)), (rows, columns)),
        shape=(len(edges), len(records)),
    ).tocsr()
    # The sub-unit hash term resolves alternate optima without ever changing
    # the integer cardinality objective.
    tie = np.asarray(
        [
            int(
                hashlib.sha256(
                    f"wp8-combined-mag-v3|{record['survey_id']}".encode()
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
        raise RuntimeError(f"GA independent-set failure: {result.message}")
    selected = [
        record for record, value in zip(records, result.x) if value > 0.5
    ]
    return selected, len(edges), float(result.mip_gap)


def main() -> None:
    ga_design = json.loads(GA_DESIGN.read_text(encoding="utf-8"))
    ga_train = json.loads(GA_TRAIN.read_text(encoding="utf-8"))
    usgs = json.loads(USGS_AUDIT.read_text(encoding="utf-8"))
    if (
        ga_design["test_unseal_count"] != 0
        or ga_train["test_unseal_count"] != 0
        or usgs["test_unseal_count"] != 0
        or usgs["selection_interpreted_response_values"] != 0
    ):
        raise RuntimeError("sealed-response invariant violated")
    if (
        ga_train["cross_survey_representative_range_km"] != RANGE_KM
        or ga_train["cross_survey_range_censored_at_2000km"]
    ):
        raise RuntimeError("training correlation-range drift")

    train_ids = {
        str(record["survey_id"]) for record in ga_train["audits"]
    }
    train_points = [
        (
            record["representative"]["latitude"],
            record["representative"]["longitude"],
        )
        for record in ga_train["audits"]
    ]
    remaining = [
        record
        for record in ga_design["records"]
        if str(record["survey_id"]) not in train_ids
    ]
    ga_eligible = []
    ga_near_training = []
    for record in remaining:
        point = (
            record["centroid_latitude"],
            record["centroid_longitude"],
        )
        minimum = min(distance_km(point, anchor) for anchor in train_points)
        prepared = dict(record)
        prepared["minimum_training_representative_distance_km"] = minimum
        if minimum >= RANGE_KM:
            ga_eligible.append(prepared)
        else:
            ga_near_training.append(prepared)
    ga_selected, ga_edges, ga_gap = independent_set(ga_eligible)

    usgs_by_id = {
        record["sciencebase_id"]: record
        for record in usgs["eligible_records"]
    }
    usgs_selected = [
        usgs_by_id[item_id]
        for item_id in usgs["maximum_independent_set_sciencebase_ids"]
    ]
    combined_count = len(ga_selected) + len(usgs_selected)
    result = {
        "schema_version": "wp8-combined-magnetic-provider-design-v3",
        "ga_design_v2_sha256": sha(GA_DESIGN),
        "ga_training_v2_sha256": sha(GA_TRAIN),
        "usgs_catalogue_audit_v1_sha256": sha(USGS_AUDIT),
        "correlation_range_km": RANGE_KM,
        "correlation_range_source": (
            "77 GA training provider-survey representatives; uncensored"
        ),
        "provider_cap": "one unit per GA SURVEY_ID or USGS direct parent release",
        "ga_training_provider_count": len(train_ids),
        "ga_remaining_unexposed_provider_count": len(remaining),
        "ga_excluded_near_training_count": len(ga_near_training),
        "ga_centroid_eligible_count": len(ga_eligible),
        "ga_centroid_conflict_edge_count": ga_edges,
        "ga_centroid_maximum_independent_set_count": len(ga_selected),
        "ga_centroid_mip_gap": ga_gap,
        "ga_coordinate_only_pool_count": len(ga_eligible),
        "usgs_bbox_maximum_independent_set_count": len(usgs_selected),
        "usgs_bbox_mip_gap": usgs["maximum_independent_set_mip_gap"],
        "combined_candidate_test_count": combined_count,
        "required_independent_test_count": 223,
        "provisional_margin": combined_count - 223,
        "ga_training_records": ga_train["audits"],
        "ga_coordinate_only_pool_records": ga_eligible,
        "ga_candidate_test_records": ga_selected,
        "usgs_external_candidate_test_records": usgs_selected,
        "ga_geometry_status": (
            "provisional: replace centroids with coordinate-only observed "
            "representatives before any response unseal"
        ),
        "usgs_geometry_status": (
            "sealed and conservative: provider bounding-box minimum distance "
            "is at least 75 km"
        ),
        "calibration_policy": (
            "no response-exposed field calibration role; all model selection "
            "and uncertainty calibration remain nested within the 77 GA "
            "training surveys"
        ),
        "response_values_interpreted_during_selection": 0,
        "usgs_candidate_files_downloaded": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    if combined_count < 223:
        raise RuntimeError("combined metadata-only power gate is impossible")
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "ga_candidate_test": len(ga_selected),
            "usgs_external_test": len(usgs_selected),
            "combined": combined_count,
            "margin": combined_count - 223,
        }
    )


if __name__ == "__main__":
    main()
