import numpy as np
import pytest
import json
from pathlib import Path
import jsonschema

from geodeepbayes.validation.field_scaffold import (
    FIELD_LIKELIHOOD_CONTRACTS,
    aggregate_cluster_metrics,
    validate_field_preregistration,
)


def test_likelihood_contracts_preserve_method_specific_error_structure():
    assert FIELD_LIKELIHOOD_CONTRACTS["dc"]["error_model"] == "voltage_current_propagation_student_t"
    assert FIELD_LIKELIHOOD_CONTRACTS["tem"]["error_model"] == "correlated_heteroscedastic_time_channels"
    for method in ("mt_amt", "csamt", "wfem"):
        assert FIELD_LIKELIHOOD_CONTRACTS[method]["complex_covariance"] is True
        assert FIELD_LIKELIHOOD_CONTRACTS[method]["independent_real_imag"] is False


def test_cluster_metric_aggregation_is_itt_and_rejects_missing_clusters():
    samples = np.array([
        [0.0, 1.0, 2.0, 3.0],
        [0.1, 1.1, 1.9, 3.1],
        [-0.1, 0.9, 2.1, 2.9],
    ])
    observed = np.array([0.0, 1.0, 2.0, 3.0])
    result = aggregate_cluster_metrics(
        samples=samples,
        observed=observed,
        cluster_ids=np.array(["a", "a", "b", "b"]),
        preregistered_clusters=("a", "b"),
    )
    assert result["intent_to_analyze_clusters"] == ["a", "b"]
    assert set(result["cluster_crps"]) == {"a", "b"}
    assert set(result["cluster_coverage_90"]) == {"a", "b"}
    assert set(result["cluster_coverage_95"]) == {"a", "b"}
    with pytest.raises(ValueError, match="intent-to-analyze"):
        aggregate_cluster_metrics(
            samples=samples[:, :2],
            observed=observed[:2],
            cluster_ids=np.array(["a", "a"]),
            preregistered_clusters=("a", "b"),
        )
    with pytest.raises(ValueError, match="failed clusters"):
        aggregate_cluster_metrics(
            samples=samples, observed=observed,
            cluster_ids=np.array(["a", "a", "b", "b"]),
            preregistered_clusters=("a", "b"), failed_cluster_ids=("b",),
        )
    with pytest.raises(ValueError, match="unique"):
        aggregate_cluster_metrics(
            samples=samples, observed=observed,
            cluster_ids=np.array(["a", "a", "b", "b"]),
            preregistered_clusters=("a", "a"),
        )


def test_field_preregistration_scaffold_never_unseals_without_all_nine():
    scaffold = {
        "frozen": True,
        "test_endpoints_viewed": False,
        "field_test_unseal_count": 0,
        "all_nine_feasibility_passed": False,
        "selection_policy": "license_integrity_design_only",
        "feasibility_decision_sha256": "a" * 64,
        "protected_manifest_sha256": "b" * 64,
    }
    result = validate_field_preregistration(
        scaffold,
        feasibility_decision={
            "status": "failed", "wp8_1_allowed": False, "methods": []
        },
        feasibility_decision_sha256="a" * 64,
        protected_manifest_sha256="b" * 64,
    )
    assert result["status"] == "blocked"
    assert result["reason_code"] == "WP8_0_NOT_ALL_NINE_PASSED"
    spoofed = dict(scaffold)
    spoofed["all_nine_feasibility_passed"] = True
    assert validate_field_preregistration(
        spoofed,
        feasibility_decision={
            "status": "failed", "wp8_1_allowed": False,
            "methods": [{"status": "passed"}] * 9,
        },
        feasibility_decision_sha256="a" * 64,
        protected_manifest_sha256="b" * 64,
    )["status"] == "blocked"


def test_persisted_field_scaffold_is_schema_valid_and_blocked():
    root = Path(__file__).resolve().parents[2]
    payload = json.loads(
        (root / "validation/wp8/field/preregistration-scaffold-v1.json").read_text()
    )
    schema = json.loads(
        (root / "validation/wp8/contracts/field-preregistration-scaffold.schema.json").read_text()
    )
    jsonschema.validate(payload, schema)
    decision_path = root / "validation/wp8/evidence/feasibility-v1/decision.json"
    protected_path = root / "validation/wp8/evidence/feasibility-v1/protected-manifest.json"
    decision = json.loads(decision_path.read_text())
    import hashlib
    assert validate_field_preregistration(
        payload,
        feasibility_decision=decision,
        feasibility_decision_sha256=hashlib.sha256(decision_path.read_bytes()).hexdigest(),
        protected_manifest_sha256=hashlib.sha256(protected_path.read_bytes()).hexdigest(),
    )["status"] == "blocked"
