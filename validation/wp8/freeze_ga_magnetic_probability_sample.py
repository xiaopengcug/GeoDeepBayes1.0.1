#!/usr/bin/env python
"""Freeze a response-blind, cell-weighted GA magnetic probability sample."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DDS = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-dds-contract.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-probability-sample.json"
SAMPLE_SIZE = 20
TARGET_TEST_CELLS = 223
ALPHA_PREVALENCE = 0.025
ALPHA_TEST_COUNT = 0.025
CELL_SALT = "wp8-ga-probability-cell-sample-v1"
ASSIGNMENT_SALT = "wp8-ga-cell-product-v1"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binomial_tail_at_least(n: int, k: int, p: float) -> float:
    return sum(
        math.comb(n, value) * p**value * (1.0 - p) ** (n - value)
        for value in range(k, n + 1)
    )


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    dds = json.loads(DDS.read_text(encoding="utf-8"))
    if (
        dds["design_sha256"] != sha(DESIGN)
        or design["magnetic_response_values_interpreted"] != 0
        or dds["magnetic_response_values_interpreted"] != 0
        or design["test_unseal_count"] != 0
        or dds["test_unseal_count"] != 0
    ):
        raise RuntimeError("response-blind GA design or DDS contract drift")

    required_flags = (
        "latitude",
        "longitude",
        "point_altitude_or_height",
        "line_identity",
        "magnetic_response",
    )
    compatible = {
        int(dataset_no)
        for dataset_no, contract in dds["products"].items()
        if all(contract["flags"][flag] for flag in required_flags)
    }
    products = {
        int(product["DATASET_NO"]): product for product in design["products"]
    }
    frame = []
    for cell in design["cells"]:
        if cell["role"] != "train":
            continue
        candidates = sorted(
            compatible & set(cell["covering_dataset_numbers"])
        )
        if not candidates:
            continue
        assigned = min(
            candidates,
            key=lambda dataset_no: hashlib.sha256(
                f"{ASSIGNMENT_SALT}|{cell['cell']}|{dataset_no}".encode()
            ).hexdigest(),
        )
        frame.append(
            {
                "cell": cell["cell"],
                "latitude": cell["latitude"],
                "longitude": cell["longitude"],
                "candidate_dataset_count": len(candidates),
                "assigned_dataset_no": assigned,
                "sample_rank_sha256": hashlib.sha256(
                    f"{CELL_SALT}|{cell['cell']}".encode()
                ).hexdigest(),
            }
        )
    frame.sort(key=lambda item: item["sample_rank_sha256"])
    sample = frame[:SAMPLE_SIZE]
    selected_dataset_numbers = sorted(
        {item["assigned_dataset_no"] for item in sample}
    )
    product_sample = []
    for dataset_no in selected_dataset_numbers:
        product = products[dataset_no]
        product_sample.append(
            {
                "dataset_no": dataset_no,
                "survey_id": product["SURVEY_ID"],
                "survey_name": product["SURVEY_NAME"],
                "state": product["STATE"],
                "survey_start_date": product["SURVEY_START_DATE"],
                "catalogue_file_size": product["FILE_SIZE"],
                "provider_url": product["FILE_DOWNLOAD"],
                "sampled_cells": [
                    item["cell"]
                    for item in sample
                    if item["assigned_dataset_no"] == dataset_no
                ],
            }
        )

    test_cells = dds["coverage"]["geometry_response"][
        "partition_cell_counts"
    ]["test"]
    all_successes_prevalence_lower_bound = ALPHA_PREVALENCE ** (
        1.0 / SAMPLE_SIZE
    )
    test_count_tail_probability = binomial_tail_at_least(
        test_cells,
        TARGET_TEST_CELLS,
        all_successes_prevalence_lower_bound,
    )
    result = {
        "schema_version": "wp8-ga-magnetic-cell-weighted-probability-sample-v1",
        "design_sha256": sha(DESIGN),
        "dds_contract_sha256": sha(DDS),
        "selection_is_design_metadata_only": True,
        "magnetic_response_values_interpreted": 0,
        "sampling_frame": {
            "inference_unit": "eligible design cell",
            "eligible_training_cells": len(frame),
            "eligible_test_cells": test_cells,
            "eligibility": (
                "train/test design cell covered by at least one DDS product "
                "declaring latitude, longitude, point height, line identity, "
                "and magnetic response"
            ),
            "cell_order": f"ascending SHA-256 of {CELL_SALT}|cell",
            "product_assignment": (
                "minimum SHA-256 of "
                f"{ASSIGNMENT_SALT}|cell|dataset_no among compatible covering products"
            ),
            "file size and response values do not enter selection": True,
        },
        "sample_size": SAMPLE_SIZE,
        "sampled_cells": sample,
        "selected_product_count": len(product_sample),
        "selected_dataset_numbers": selected_dataset_numbers,
        "products": product_sample,
        "success_definition": {
            "cell_success": (
                "the assigned product's training-only spatial diagnostic has an "
                "uncensored correlation-range upper bound strictly below the "
                "55 km minimum design-center spacing"
            ),
            "all_sampled_cells_must_succeed": True,
            "failure_includes": [
                "range estimate at or above 55 km",
                "range estimate censored before 55 km",
                "insufficient training-only geometry or response support",
                "integrity or schema failure",
            ],
        },
        "preregistered_inference": {
            "method": (
                "two-stage one-sided design-based bound with Bonferroni "
                "family-wise alpha control"
            ),
            "family_wise_alpha": ALPHA_PREVALENCE + ALPHA_TEST_COUNT,
            "prevalence_alpha": ALPHA_PREVALENCE,
            "test_count_alpha": ALPHA_TEST_COUNT,
            "all_successes_one_sided_prevalence_lower_bound": (
                all_successes_prevalence_lower_bound
            ),
            "test_cells": test_cells,
            "required_successful_test_cells": TARGET_TEST_CELLS,
            "binomial_tail_probability_at_lower_bound": (
                test_count_tail_probability
            ),
            "test_count_condition_passes": (
                test_count_tail_probability >= 1.0 - ALPHA_TEST_COUNT
            ),
            "formal_gate_rule": (
                "pass only if all 20 sampled cells succeed and the preregistered "
                "test-count tail probability is at least 0.975"
            ),
            "exchangeability_basis": (
                "train and test roles were assigned by a response-blind hash "
                "before this sample and use identical DDS eligibility"
            ),
        },
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "status": "sample frozen; response acquisition not started",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "frame_cells": len(frame),
                "sample_cells": len(sample),
                "products": len(product_sample),
                "dataset_numbers": selected_dataset_numbers,
                "prevalence_lower_bound": all_successes_prevalence_lower_bound,
                "test_count_tail_probability": test_count_tail_probability,
            }
        )
    )


if __name__ == "__main__":
    main()
