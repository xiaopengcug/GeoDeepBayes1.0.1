"""Fail-closed WP8 field-validation contracts without unsealing field test data."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .metrics import crps_ensemble, interval_coverage
from .feasibility import METHOD_NAMES


FIELD_LIKELIHOOD_CONTRACTS = {
    "gravity": {"error_model": "amplitude_plus_noise_floor", "complex_covariance": False},
    "magnetic": {"error_model": "amplitude_plus_noise_floor", "complex_covariance": False},
    "dc": {"error_model": "voltage_current_propagation_student_t", "complex_covariance": False},
    "tdip": {"error_model": "voltage_current_propagation_student_t", "complex_covariance": False},
    "sip_fdip": {"error_model": "complex_cole_cole_covariance", "complex_covariance": True, "independent_real_imag": False},
    "tem": {"error_model": "correlated_heteroscedastic_time_channels", "complex_covariance": False},
    "mt_amt": {"error_model": "complex_impedance_covariance", "complex_covariance": True, "independent_real_imag": False},
    "csamt": {"error_model": "complex_field_covariance", "complex_covariance": True, "independent_real_imag": False},
    "wfem": {"error_model": "complex_field_covariance", "complex_covariance": True, "independent_real_imag": False},
}


def aggregate_cluster_metrics(
    *,
    samples: np.ndarray,
    observed: np.ndarray,
    cluster_ids: np.ndarray,
    preregistered_clusters: Sequence[str],
    failed_cluster_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Recompute cluster-level CRPS/coverage under strict intent-to-analyze."""
    samples = np.asarray(samples, dtype=float)
    observed = np.asarray(observed, dtype=float)
    clusters = np.asarray(cluster_ids)
    expected = tuple(str(value) for value in preregistered_clusters)
    if (
        samples.ndim != 2 or samples.shape[0] < 1
        or observed.shape != (samples.shape[1],)
        or not np.all(np.isfinite(samples))
        or not np.all(np.isfinite(observed))
    ):
        raise ValueError("samples and observed shapes do not match")
    if clusters.shape != observed.shape:
        raise ValueError("cluster_ids must align with observations")
    if (
        not expected or len(set(expected)) != len(expected)
        or any(not value.strip() or value.lower() in {"nan", "inf", "-inf"} for value in expected)
    ):
        raise ValueError("preregistered clusters must be unique non-empty identifiers")
    failed = {str(value) for value in failed_cluster_ids}
    if failed:
        raise ValueError(
            "intent-to-analyze includes failed clusters; unresolved failures: "
            + ", ".join(sorted(failed))
        )
    present = {str(value) for value in np.unique(clusters)}
    if present != set(expected):
        raise ValueError("intent-to-analyze requires every preregistered cluster exactly")
    point_crps = crps_ensemble(samples, observed)
    coverage90 = interval_coverage(samples, observed, 0.9)
    coverage95 = interval_coverage(samples, observed, 0.95)
    return {
        "intent_to_analyze_clusters": list(expected),
        "cluster_crps": {
            cluster: float(np.mean(point_crps[clusters.astype(str) == cluster]))
            for cluster in expected
        },
        "cluster_coverage_90": {
            cluster: float(np.mean(coverage90[clusters.astype(str) == cluster]))
            for cluster in expected
        },
        "cluster_coverage_95": {
            cluster: float(np.mean(coverage95[clusters.astype(str) == cluster]))
            for cluster in expected
        },
        "failure_count": 0,
    }


def validate_field_preregistration(
    payload: Mapping[str, Any],
    *,
    feasibility_decision: Mapping[str, Any],
    feasibility_decision_sha256: str,
    protected_manifest_sha256: str,
) -> dict[str, Any]:
    """Validate only the scaffold; never perform or authorize field unsealing."""
    required = (
        payload.get("frozen") is True
        and payload.get("test_endpoints_viewed") is False
        and payload.get("field_test_unseal_count") == 0
        and payload.get("selection_policy") == "license_integrity_design_only"
        and payload.get("feasibility_decision_sha256") == feasibility_decision_sha256
        and payload.get("protected_manifest_sha256") == protected_manifest_sha256
    )
    if not required:
        return {"status": "blocked", "reason_code": "FIELD_PREREGISTRATION_INVALID"}
    methods = feasibility_decision.get("methods", [])
    actual_all_nine = (
        feasibility_decision.get("status") == "passed"
        and feasibility_decision.get("wp8_1_allowed") is True
        and isinstance(methods, list)
        and len(methods) == 9
        and {item.get("method") for item in methods if isinstance(item, Mapping)}
        == set(METHOD_NAMES)
        and all(
            isinstance(item, Mapping) and item.get("status") == "passed"
            for item in methods
        )
    )
    if payload.get("all_nine_feasibility_passed") is not True or not actual_all_nine:
        return {"status": "blocked", "reason_code": "WP8_0_NOT_ALL_NINE_PASSED"}
    return {
        "status": "ready-for-single-unseal",
        "reason_code": "ALL_NINE_FEASIBILITY_PASSED",
    }
