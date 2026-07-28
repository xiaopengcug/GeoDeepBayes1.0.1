import json
import pytest

import geodeepbayes.validation.wp8_method_synthetic as method_validation_module
from geodeepbayes.validation.wp8_method_synthetic import (
    ADVERSARIAL_SCENARIOS,
    CONVERGENCE_IDS,
    REFERENCE_IDS,
    REQUIRED_METHOD_CHECKS,
    run_method_synthetic_validation,
    run_single_method,
    write_method_synthetic_evidence,
)


def test_dispatcher_rejects_unknown_method():
    with pytest.raises(ValueError, match="unknown WP8 method"):
        run_single_method("gravity_crosswired")


def test_dispatcher_fails_closed_on_intrinsic_identity_crosswire(monkeypatch):
    original = method_validation_module.run_single_method

    def crosswired(method):
        payload = original(method)
        if method == "gravity":
            payload["method"] = "magnetic"
        return payload

    monkeypatch.setattr(method_validation_module, "run_single_method", crosswired)
    report = run_method_synthetic_validation()
    assert report["methods"]["gravity"]["status"] == "blocked"
    assert "dispatcher cross-wire" in report["methods"]["gravity"]["errors"][0]


def test_controlled_source_operator_owned_identity_blocks_crosswire(monkeypatch):
    original_wfem = method_validation_module.WFEMOperator

    def wrong_csamt(mesh, vertices, receivers, frequencies, *, current):
        return original_wfem(
            mesh, vertices, receivers, frequencies, current=current,
            apparent_resistivity_definition="not_available",
        )

    monkeypatch.setattr(method_validation_module, "CSAMTOperator", wrong_csamt)
    with pytest.raises(RuntimeError, match="controlled-source branch cross-wire"):
        run_single_method("csamt")


def test_method_synthetic_validation_is_deterministic_and_passes_required_checks():
    first = run_method_synthetic_validation()
    second = run_method_synthetic_validation()
    assert first["schema_version"] == "wp8-method-synthetic-validation-v1"
    assert first["status"] == "passed"
    assert first["field_validation_eligible"] is False
    assert set(first["methods"]) == set(REQUIRED_METHOD_CHECKS)
    for method, required in REQUIRED_METHOD_CHECKS.items():
        result = first["methods"][method]
        assert result["method"] == method
        assert result["status"] == "passed"
        checks = result["checks"]
        assert all(checks[name]["required"] for name in required)
        assert all(checks[name]["status"] == "passed" for name in required)
        assert checks["predict_reference_agreement"]["reference_id"] == REFERENCE_IDS[method]
        assert checks["three_level_convergence"]["convergence_id"] == CONVERGENCE_IDS[method]
        assert set(checks["method_adversarial_suite"]["metrics"]["scenarios"]) == ADVERSARIAL_SCENARIOS[method]
        taylor = checks["taylor_remainder_order"]["metrics"]
        assert taylor["order_kind"] in {
            "observed_remainder_orders",
            "linear_exact_with_scale_aware_tolerance",
        }
        assert len(taylor["remainders"]) == 3
        assert taylor["observed_orders"] is None or min(taylor["observed_orders"]) > 1.8
        assert (
            checks["sbc_at_least_400"]["metrics"]["raw_ranks"]
            == second["methods"][method]["checks"]["sbc_at_least_400"]["metrics"][
                "raw_ranks"
            ]
        )
        benchmark = checks["within_method_5x5_performance"]["metrics"]
        assert benchmark["record_count"] == 25
        assert {(item["scale"], item["repeat"]) for item in benchmark["records"]} == {
            (scale, repeat) for scale in range(1, 6) for repeat in range(1, 6)
        }
        assert all(item["elapsed_ns"] > 0 for item in benchmark["records"])
        assert all(item["elapsed_ns"] <= item["max_elapsed_ns"] for item in benchmark["records"])


def test_csamt_convergence_and_reference_tolerances_are_required_and_meaningful():
    report = run_method_synthetic_validation()
    convergence = report["methods"]["csamt"]["checks"]["three_level_convergence"]
    assert convergence["status"] == "passed"
    assert convergence["required"] is True
    assert convergence["metrics"]["medium_to_fine_error"] < convergence["metrics"][
        "coarse_to_fine_error"
    ]
    reference = report["methods"]["csamt"]["checks"]["predict_reference_agreement"]
    assert reference["metrics"]["absolute_log_amplitude_error"] < 0.65
    assert reference["metrics"]["case_frequencies_hz"] == [2.0, 5.0, 10.0]
    assert reference["metrics"]["case_receiver_xyz_m"] == [
        [35.0, 5.0, -8.0],
        [50.0, -7.0, -15.0],
    ]
    assert reference["metrics"]["absolute_phase_error_radians"] < 0.01


def test_tem_cross_filter_and_late_time_slope_sanity_are_explicit():
    report = run_method_synthetic_validation()
    metrics = report["methods"]["tem"]["checks"]["predict_reference_agreement"]["metrics"]
    assert metrics["scope"] == (
        "TEM 1-D layered cross-filter and halfspace late-time slope sanity only"
    )
    assert (
        metrics["alternate_filter_relative_error"]
        < metrics["alternate_filter_relative_error_threshold"]
        == 0.002
    )
    assert abs(
        metrics["homogeneous_late_time_loglog_slope"]
        - metrics["expected_late_time_loglog_slope"]
    ) < metrics["absolute_slope_tolerance"] == 0.05


def test_method_synthetic_evidence_is_machine_readable(tmp_path):
    path = tmp_path / "method-validation.json"
    written = write_method_synthetic_evidence(path)
    assert json.loads(path.read_text(encoding="utf-8")) == written
    assert path.read_bytes().endswith(b"\n")
