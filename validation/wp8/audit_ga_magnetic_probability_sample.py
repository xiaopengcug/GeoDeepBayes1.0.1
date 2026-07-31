#!/usr/bin/env python
"""Audit the preregistered GA magnetic probability sample on training data only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit_ga_magnetic_training_consortium import audit_member

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-probability-sample-v1"
MANIFEST = DATA / "raw-manifest.json"
SAMPLE = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-probability-sample.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DDS = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-dds-contract.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-probability-audit.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    dds = json.loads(DDS.read_text(encoding="utf-8"))
    if (
        manifest["sample_sha256"] != sha(SAMPLE)
        or manifest["design_sha256"] != sha(DESIGN)
        or manifest["dds_contract_sha256"] != sha(DDS)
        or manifest["dataset_numbers"] != sample["selected_dataset_numbers"]
        or manifest["acquisition_interpreted_response_values"] != 0
        or manifest["calibration_responses_interpreted"] != 0
        or manifest["test_responses_interpreted"] != 0
        or manifest["test_unseal_count"] != 0
        or design["test_unseal_count"] != 0
        or dds["test_unseal_count"] != 0
    ):
        raise RuntimeError("GA probability-sample evidence drift")

    audits = {}
    for member in manifest["members"]:
        raw = DATA / member["path"]
        if raw.stat().st_size != member["bytes"] or sha(raw) != member["sha256"]:
            raise RuntimeError(f"probability member drift: {member['dataset_no']}")
        audit = audit_member(member, DATA)
        audits[int(member["dataset_no"])] = audit
        print(
            json.dumps(
                {
                    "dataset_no": member["dataset_no"],
                    "training_rows": audit["training_rows_interpreted"],
                    "range_m": audit["correlation_range_m"],
                    "censored": audit["range_censored_at_100km"],
                }
            ),
            flush=True,
        )

    spacing_m = (
        float(design["spatial_design"]["minimum_nominal_center_spacing_km"])
        * 1000.0
    )
    cell_results = []
    for sampled_cell in sample["sampled_cells"]:
        dataset_no = int(sampled_cell["assigned_dataset_no"])
        audit = audits[dataset_no]
        success = (
            audit["training_rows_interpreted"] > 0
            and audit["training_cells_5km"] > 1
            and audit["range_censored_at_100km"] is False
            and audit["correlation_range_m"] < spacing_m
        )
        cell_results.append(
            {
                "cell": sampled_cell["cell"],
                "assigned_dataset_no": dataset_no,
                "success": success,
                "correlation_range_m": audit["correlation_range_m"],
                "range_censored_at_100km": audit["range_censored_at_100km"],
                "training_rows_interpreted": audit[
                    "training_rows_interpreted"
                ],
                "training_cells_5km": audit["training_cells_5km"],
            }
        )
    all_success = all(item["success"] for item in cell_results)
    inference = sample["preregistered_inference"]
    formal_gate = (
        all_success
        and inference["test_count_condition_passes"] is True
        and inference["binomial_tail_probability_at_lower_bound"]
        >= 1.0 - inference["test_count_alpha"]
    )
    result = {
        "schema_version": "wp8-ga-magnetic-probability-audit-v1",
        "sample_sha256": sha(SAMPLE),
        "raw_manifest_sha256": sha(MANIFEST),
        "design_sha256": sha(DESIGN),
        "dds_contract_sha256": sha(DDS),
        "members": [audits[number] for number in sorted(audits)],
        "sampled_cell_results": cell_results,
        "sampled_cells": len(cell_results),
        "successful_sampled_cells": sum(item["success"] for item in cell_results),
        "all_sampled_cells_succeed": all_success,
        "total_training_rows_interpreted": sum(
            audit["training_rows_interpreted"] for audit in audits.values()
        ),
        "total_crossover_bins": sum(
            audit["crossover_bins"] for audit in audits.values()
        ),
        "maximum_observed_correlation_range_m": max(
            audit["correlation_range_m"] for audit in audits.values()
        ),
        "censored_product_count": sum(
            audit["range_censored_at_100km"] for audit in audits.values()
        ),
        "response_rows_interpreted": {
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "preregistered_inference": inference,
        "formal_correlation_power_gate_passes": formal_gate,
        "formal_gate_reason": (
            "all preregistered sampled cells passed and the family-wise "
            "95% lower-bound test-count criterion passed"
            if formal_gate
            else "one or more preregistered sampled cells or inference criteria failed"
        ),
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "sampled_cells": result["sampled_cells"],
                "successful_cells": result["successful_sampled_cells"],
                "maximum_range_m": result[
                    "maximum_observed_correlation_range_m"
                ],
                "censored_products": result["censored_product_count"],
                "formal_gate": formal_gate,
            }
        )
    )


if __name__ == "__main__":
    main()
