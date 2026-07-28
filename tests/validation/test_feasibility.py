import numpy as np
import pytest

from geodeepbayes.validation.feasibility import (
    METHOD_NAMES,
    REQUIRED_GATES,
    buffered_cluster_split,
    bind_gate_evidence,
    estimate_correlation_length,
    evaluate_feasibility,
    required_coverage_clusters,
    required_paired_clusters,
    exact_paired_randomization_test,
    bootstrap_stability_gate,
    select_required_dimensionality,
)


def _registration(status="passed"):
    producer_hash = "a" * 64
    return {
        "manifest_sha256": "1" * 64,
        "dataset_selection_sha256": "2" * 64,
        "preregistration_sha256": "3" * 64,
        "methods": {
            method: {
                "dataset_slug": f"{method}-dataset",
                "gates": {
                    gate: bind_gate_evidence(
                        method=method,
                        dataset_slug=f"{method}-dataset",
                        gate_name=gate,
                        status=status,
                        reason="test evidence",
                        producer="tests/validation/test_feasibility.py",
                        producer_sha256=producer_hash,
                        measurements={"observed": True},
                        thresholds={"required_status": "passed"},
                    )
                    for gate in REQUIRED_GATES
                }
            }
            for method in METHOD_NAMES
        }
    }

def _evaluate(registration):
    return evaluate_feasibility(
        registration,
        expected_registration_hashes={
            "manifest_sha256": "1" * 64,
            "dataset_selection_sha256": "2" * 64,
            "preregistration_sha256": "3" * 64,
        },
        trusted_producers={"tests/validation/test_feasibility.py": "a" * 64},
    )


def test_all_nine_must_pass():
    result = _evaluate(_registration())
    assert result["status"] == "passed"
    assert result["wp8_1_allowed"] is True
    assert len(result["methods"]) == 9


def test_one_failed_gate_blocks_wp8_1():
    registration = _registration()
    registration["methods"]["wfem"]["gates"]["observation_contract"] = bind_gate_evidence(
        method="wfem", dataset_slug="wfem-dataset",
        gate_name="observation_contract", status="blocked",
        reason="source geometry absent", producer="test", producer_sha256="a" * 64,
        measurements={"observed": False}, thresholds={"required_status": "passed"},
    )
    result = _evaluate(registration)
    assert result["status"] == "failed"
    assert result["wp8_1_allowed"] is False
    wfem = next(item for item in result["methods"] if item["method"] == "wfem")
    assert wfem["failed_gates"] == ["observation_contract"]


def test_missing_method_fails_closed():
    registration = _registration()
    del registration["methods"]["csamt"]
    result = _evaluate(registration)
    csamt = next(item for item in result["methods"] if item["method"] == "csamt")
    assert csamt["status"] == "failed"
    assert set(csamt["failed_gates"]) == set(REQUIRED_GATES)


def test_status_only_passed_gate_is_rejected_as_empty_shell():
    registration = _registration()
    registration["methods"]["gravity"]["gates"]["license"] = {
        "status": "passed", "reason": "trust me"
    }
    result = _evaluate(registration)
    gravity = next(item for item in result["methods"] if item["method"] == "gravity")
    assert gravity["status"] == "failed"
    assert "license" in gravity["failed_gates"]


@pytest.mark.parametrize(
    "attack", ["cross_method", "cross_gate", "cross_dataset", "producer", "nan"]
)
def test_gate_evidence_cannot_self_sign_or_cross_bind(attack):
    registration = _registration()
    registration["methods"]["gravity"]["gates"]["license"] = bind_gate_evidence(
        method="magnetic" if attack == "cross_method" else "gravity",
        dataset_slug="magnetic-dataset" if attack == "cross_dataset" else "gravity-dataset",
        gate_name="integrity" if attack == "cross_gate" else "license",
        status="passed", reason="forged",
        producer="forged.py" if attack == "producer" else "tests/validation/test_feasibility.py",
        producer_sha256="b" * 64 if attack == "producer" else "a" * 64,
        measurements={"observed": np.nan if attack == "nan" else True},
        thresholds={"required_status": "passed"},
    )
    result = _evaluate(registration)
    gravity = next(item for item in result["methods"] if item["method"] == "gravity")
    assert "license" in gravity["failed_gates"]


@pytest.mark.parametrize(
    "anchor",
    ["manifest_sha256", "dataset_selection_sha256", "preregistration_sha256"],
)
def test_registration_top_level_anchor_is_required(anchor):
    registration = _registration()
    registration[anchor] = "f" * 64
    with pytest.raises(ValueError, match="trusted anchor"):
        _evaluate(registration)


def test_power_uses_independent_cluster_count():
    assert required_paired_clusters(0.8) == 12
    assert required_paired_clusters(0.4) > required_paired_clusters(0.8)
    assert required_coverage_clusters(nominal=0.9) >= 1
    assert required_coverage_clusters(nominal=0.95) >= 1


def test_training_only_correlation_length_is_positive():
    x = np.arange(10.0)[:, None]
    values = np.sin(x[:, 0] / 2)
    assert estimate_correlation_length(x, values, bins=5) > 0


def test_buffered_split_is_outcome_blind_and_separated():
    points = np.arange(30.0)[:, None] * 10
    split = buffered_cluster_split(points, buffer_distance=5, seed=8)
    assert sorted(sum(split.values(), [])) == list(range(30))
    for left_name, left in split.items():
        for right_name, right in split.items():
            if left_name >= right_name:
                continue
            assert all(abs(points[i, 0] - points[j, 0]) >= 5 for i in left for j in right)


def test_buffered_split_fails_when_geometry_cannot_support_it():
    points = np.arange(6.0)[:, None]
    try:
        buffered_cluster_split(points, buffer_distance=100, seed=3)
    except ValueError as exc:
        assert "component-partition search found no buffered split" in str(exc)
    else:
        raise AssertionError("infeasible split must fail closed")


def test_split_rejects_empty_target_and_excessive_bins():
    points = np.arange(3.0)[:, None]
    with pytest.raises(ValueError, match="every buffered split"):
        buffered_cluster_split(
            points, buffer_distance=0, seed=1, fractions=(0.9, 0.05, 0.05)
        )
    with pytest.raises(ValueError):
        estimate_correlation_length(
            np.arange(4.0)[:, None], np.arange(4.0), bins=7
        )
    with pytest.raises(ValueError, match="five-million-pair"):
        estimate_correlation_length(
            np.arange(3163.0)[:, None], np.arange(3163.0), bins=3
        )
    with pytest.raises(ValueError, match="distance-memory"):
        buffered_cluster_split(
            np.zeros((5001, 2)), buffer_distance=0, seed=1
        )


def test_small_cluster_exact_randomization_and_bootstrap_stability():
    differences = np.array([0.2, 0.3, 0.1, 0.4])
    exact = exact_paired_randomization_test(differences, null_improvement=0.0)
    assert exact["permutations"] == 16
    assert exact["one_sided_p"] == 1 / 16
    assert bootstrap_stability_gate(np.arange(30.0), seed=4)["passed"] is True
    assert bootstrap_stability_gate(np.arange(5.0), seed=4)["passed"] is False


def test_bootstrap_same_repetition_budget_can_reject_unstable_input():
    stable = bootstrap_stability_gate(np.arange(30.0), seed=1, repetitions=400)
    unstable = bootstrap_stability_gate(
        np.r_[np.linspace(-1.0, 1.0, 29), 100.0],
        seed=1,
        repetitions=400,
    )
    assert stable["passed"] is True
    assert unstable["passed"] is False
    assert unstable["relative_mc_error"] > unstable["maximum_relative_mc_error"]


def test_dimensionality_upgrade_is_mandatory_and_fail_closed():
    upgraded = select_required_dimensionality(
        method="tem", diagnostics={"lateral_inconsistency": 0.2},
        available_solver_dimensions=("1d", "3d"),
    )
    assert upgraded["selected"] == "3d"
    assert upgraded["status"] == "passed"
    blocked = select_required_dimensionality(
        method="tem", diagnostics={"lateral_inconsistency": 0.2},
        available_solver_dimensions=("1d",),
    )
    assert blocked["status"] == "failed"
    assert blocked["reason_code"] == "REQUIRED_DIMENSION_SOLVER_UNAVAILABLE"


def test_mt_and_controlled_source_dimensionality_inputs_are_strict():
    mt = select_required_dimensionality(
        method="mt_amt",
        diagnostics={"skew_deg": 7.0, "tipper_amplitude": 0.1},
        available_solver_dimensions=("1d", "2d", "3d"),
    )
    assert mt["selected"] == "3d"
    cs = select_required_dimensionality(
        method="csamt", diagnostics={"source_zone": "transition"},
        available_solver_dimensions=("3d",),
    )
    assert cs["selected"] == "3d"
    with pytest.raises(ValueError):
        select_required_dimensionality(
            method="mt_amt", diagnostics={"skew_deg": 2.0},
            available_solver_dimensions=("1d",),
        )
    with pytest.raises(ValueError):
        select_required_dimensionality(
            method="wfem", diagnostics={"source_zone": "unknown"},
            available_solver_dimensions=("1d",),
        )


def test_numeric_contracts_reject_nonfinite_and_invalid_ranges():
    with pytest.raises(ValueError):
        required_paired_clusters(np.inf)
    with pytest.raises(ValueError):
        required_coverage_clusters(nominal=0.9, alpha_two_sided=0.7)
    with pytest.raises(ValueError):
        estimate_correlation_length(
            np.array([[0.0], [1.0], [2.0], [np.inf]]),
            np.arange(4.0),
        )
    with pytest.raises(ValueError):
        buffered_cluster_split(
            np.arange(6.0)[:, None], buffer_distance=1,
            seed=1, fractions=(1.2, -0.2, 0.0),
        )


def test_bootstrap_zero_variance_is_blocked():
    result = bootstrap_stability_gate(np.ones(30), seed=2)
    assert result["passed"] is False
    assert result["reason_code"] == "ZERO_VARIANCE_BOOTSTRAP_UNINFORMATIVE"
