import pytest

from geodeepbayes.validation import ValidationResult, ValidationScenario


ROOT = "1" * 64


def test_scenario_and_result_contracts_are_immutable():
    scenario = ValidationScenario(
        scenario_id="gravity-v1",
        method="gravity",
        preregistration_version="wp8-0-v1",
        split_root=ROOT,
        thresholds={"crps_relative_improvement": 0.1},
        seed=7,
        dimensionality="3d",
        baseline_id="equal-information-equal-compute-v1",
    )
    assert scenario.thresholds["crps_relative_improvement"] == 0.1
    with pytest.raises(TypeError):
        scenario.thresholds["x"] = 1
    result = ValidationResult(
        scenario_id=scenario.scenario_id,
        status="failed",
        evidence_id="evidence-1",
        failure_reasons=({"code": "POWER_NOT_PASSED"},),
        raw_prediction_root=ROOT,
    )
    assert result.failure_reasons[0]["code"] == "POWER_NOT_PASSED"


def test_failed_result_requires_reason_and_roots_are_hashes():
    with pytest.raises(ValueError, match="reasons"):
        ValidationResult(scenario_id="x", status="failed", evidence_id="e")
    with pytest.raises(ValueError, match="split_root"):
        ValidationScenario("x", "gravity", "v1", "bad", {}, 1, "3d", "b")
