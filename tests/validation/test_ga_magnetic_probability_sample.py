from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def test_ga_probability_sample_is_cell_weighted_and_response_blind() -> None:
    sample = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-probability-sample.json"
        ).read_text(encoding="utf-8")
    )
    assert sample["sampling_frame"]["inference_unit"] == "eligible design cell"
    assert sample["sampling_frame"]["eligible_training_cells"] == 506
    assert sample["sampling_frame"]["eligible_test_cells"] == 305
    assert sample["sample_size"] == 20
    assert len(sample["sampled_cells"]) == 20
    assert sample["selected_product_count"] == 19
    assert len(set(sample["selected_dataset_numbers"])) == 19
    assert sample["selection_is_design_metadata_only"] is True
    assert sample["magnetic_response_values_interpreted"] == 0
    assert sample["test_responses_interpreted"] == 0
    assert sample["test_unseal_count"] == 0


def test_ga_probability_sample_preregisters_fail_closed_inference() -> None:
    sample = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-probability-sample.json"
        ).read_text(encoding="utf-8")
    )
    inference = sample["preregistered_inference"]
    assert inference["family_wise_alpha"] == 0.05
    assert inference["prevalence_alpha"] == 0.025
    assert inference["test_count_alpha"] == 0.025
    assert inference["all_successes_one_sided_prevalence_lower_bound"] > 0.83
    assert inference["required_successful_test_cells"] == 223
    assert inference["binomial_tail_probability_at_lower_bound"] > 0.975
    assert inference["test_count_condition_passes"] is True
    assert sample["success_definition"]["all_sampled_cells_must_succeed"] is True


def test_ga_probability_audit_preserves_heldout_responses_and_fails_honestly() -> None:
    audit = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-probability-audit.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["sampled_cells"] == 20
    assert audit["successful_sampled_cells"] == 18
    assert audit["total_training_rows_interpreted"] == 37_431_248
    assert audit["total_crossover_bins"] == 38_087
    assert audit["response_rows_interpreted"] == {
        "buffer": 0,
        "calibration": 0,
        "test": 0,
    }
    assert all(
        member["heldout_response_rows_interpreted"]
        == {"buffer": 0, "calibration": 0, "test": 0}
        for member in audit["members"]
    )
    assert audit["test_unseal_count"] == 0
    assert audit["all_sampled_cells_succeed"] is False
    assert audit["maximum_observed_correlation_range_m"] == 100_000.0
    assert audit["censored_product_count"] == 1
    assert audit["formal_correlation_power_gate_passes"] is False


def test_ga_probability_audit_records_both_preregistered_failures() -> None:
    audit = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-probability-audit.json"
        ).read_text(encoding="utf-8")
    )
    failures = {
        item["assigned_dataset_no"]: item
        for item in audit["sampled_cell_results"]
        if not item["success"]
    }
    assert set(failures) == {17852, 19448}
    assert failures[17852]["correlation_range_m"] == 82_500.0
    assert failures[17852]["range_censored_at_100km"] is False
    assert failures[19448]["correlation_range_m"] == 100_000.0
    assert failures[19448]["range_censored_at_100km"] is True


def test_combined_provider_separation_repairs_magnetic_cluster_gate() -> None:
    design_path = EVIDENCE / "combined-magnetic-provider-survey-design-v3.json"
    coordinate_path = EVIDENCE / "ga-magnetic-coordinate-only-v3.json"
    coordinates = json.loads(coordinate_path.read_text(encoding="utf-8"))
    separation = json.loads(
        (
            EVIDENCE / "combined-magnetic-provider-separation-v3.json"
        ).read_text(encoding="utf-8")
    )
    assert coordinates["combined_design_sha256"] == hashlib.sha256(
        design_path.read_bytes()
    ).hexdigest()
    assert coordinates["coordinate_pool_count"] == 289
    assert coordinates["candidate_count"] == 288
    assert coordinates["response_variables_requested"] == 0
    assert coordinates["test_unseal_count"] == 0
    assert separation["ga_coordinate_only_sha256"] == hashlib.sha256(
        coordinate_path.read_bytes()
    ).hexdigest()
    assert separation["correlation_range_km"] == 75.0
    assert separation["ga_actual_representative_independent_count"] == 218
    assert separation["usgs_conservative_bbox_independent_count"] == 14
    assert separation["combined_independent_test_count"] == 232
    assert separation["required_independent_test_count"] == 223
    assert separation["cluster_count_gate_passed"] is True
    assert separation["test_responses_interpreted"] == 0
