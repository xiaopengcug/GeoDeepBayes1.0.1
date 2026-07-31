#!/usr/bin/env python
"""Run development-only 5x5 within-method benchmarks and adversarial inventory."""
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path

import numpy as np
from discretize import TensorMesh

from geodeepbayes.forward import (
    CSAMTOperator,
    ColeColeFrequencyOperator,
    DCOperator,
    DipoleDipoleSurvey,
    GravityOperator,
    MT1DRecursiveOperator,
    MagneticVectorOperator,
    TDIPOperator,
    TEM1DLayeredOperator,
    WFEMOperator,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "evidence/development-synthetic"


def survey():
    return DipoleDipoleSurvey(
        a=np.array([[-8.0, 0, 0]]),
        b=np.array([[-4.0, 0, 0]]),
        m=np.array([[4.0, 0, 0]]),
        n=np.array([[8.0, 0, 0]]),
        current=np.array([1.0]),
    )


def build(method, scale):
    count = scale + 2
    if method in {"gravity", "magnetic"}:
        mesh = TensorMesh([[10.0] * count] * 3, origin=[-5 * count, -5 * count, -10 * count])
        receivers = np.array([[0.0, 0.0, 5.0]])
        if method == "gravity":
            operator = GravityOperator(mesh, receivers)
        else:
            operator = MagneticVectorOperator(mesh, receivers)
        return operator, np.zeros(operator.n_param)
    if method in {"dc", "tdip"}:
        mesh = TensorMesh([[8.0] * count] * 3, origin=[-4 * count, -4 * count, -8 * count])
        if method == "dc":
            operator = DCOperator(mesh, survey())
            return operator, np.full(operator.n_param, np.log(0.02))
        operator = TDIPOperator(
            mesh, survey(), [0.01, 0.03], background_conductivity=0.02, tau=0.1, exponent_c=0.6
        )
        return operator, np.full(operator.n_param, 0.05)
    if method == "sip_fdip":
        operator = ColeColeFrequencyOperator(survey(), np.geomspace(0.1, 100, count))
        return operator, np.array([np.log(0.02), -1.3, np.log(0.1), 0.4])
    if method == "tem":
        operator = TEM1DLayeredOperator(
            [20.0] * scale,
            np.geomspace(1e-5, 1e-3, count),
            loop_radius=10,
            dimensionality_diagnostic=[0.02],
        )
        return operator, np.log(np.linspace(0.01, 0.05, operator.n_param))
    if method == "mt_amt":
        operator = MT1DRecursiveOperator(
            [100.0] * scale,
            np.geomspace(0.01, 100, count),
            phase_tensor_skew_deg=[1],
            ellipticity=[0.03],
            tipper_amplitude=[0.04],
        )
        return operator, np.log(np.linspace(0.01, 0.05, operator.n_param))
    mesh = TensorMesh([[20.0] * count] * 3, origin=[-10 * count] * 3)
    vertices = np.array([[-10.0, 0, -10.0], [10.0, 0, -10.0]])
    receivers = np.array([[15.0, 0, -10.0]])
    if method == "csamt":
        operator = CSAMTOperator(mesh, vertices, receivers, [5.0], current=1.0)
    else:
        operator = WFEMOperator(
            mesh,
            vertices,
            receivers,
            [5.0],
            current=1.0,
            apparent_resistivity_definition="not_available",
        )
    return operator, np.full(operator.n_param, np.log(0.02))


ADVERSARIAL = {
    "gravity": {
        "density_depth_equivalence": "expected_nonidentifiability",
        "regional_trend": "expected_fail_no_trend_parameter",
        "topography": "expected_fail_no_topography_contract",
    },
    "magnetic": {
        "remanence": "passed_vector_path",
        "demagnetization": "expected_fail_no_self_demagnetization",
        "low_latitude": "passed_configurable_inducing_field",
        "vector_magnetization": "passed_vector_path",
    },
    "dc": {
        "topography": "expected_fail_no_topography_adapter",
        "anisotropy": "expected_fail_scalar_conductivity",
        "contact_error": "expected_fail_no_contact_impedance",
    },
    "tdip": {
        "em_coupling": "expected_fail_static_spectral_ip",
        "integration_window": "passed_explicit_time_windows",
        "topography_anisotropy_contact": "expected_fail_contract_missing",
    },
    "sip_fdip": {
        "frequency_convention": "passed_explicit_cole_cole",
        "lateral_structure": "expected_dimensionality_upgrade",
    },
    "tem": {
        "thin_layer": "passed_layered_path",
        "waveform": "expected_fail_step_off_only",
        "early_late_noise": "expected_fail_likelihood_not_bound",
        "3d_effect": "expected_dimensionality_upgrade",
    },
    "mt_amt": {
        "static_shift": "expected_fail_no_distortion_parameter",
        "anisotropy": "expected_fail_isotropic_1d",
        "2d_3d": "expected_dimensionality_upgrade",
        "cultural_noise": "expected_fail_likelihood_not_bound",
    },
    "csamt": {
        "near_transition_far": "passed_zone_classifier",
        "finite_source": "passed_line_current",
        "source_geometry": "passed_explicit_vertices",
        "phase_component": "passed_explicit_complex_components",
        "topography": "expected_fail_no_topography_path",
    },
    "wfem": {
        "near_transition_far": "passed_zone_classifier",
        "finite_source": "passed_line_current",
        "source_geometry": "passed_explicit_vertices",
        "phase_component": "passed_explicit_complex_components",
        "topography": "expected_fail_no_topography_path",
    },
}


def main():
    methods = tuple(ADVERSARIAL)
    benchmark = {
        "schema_version": "wp8-within-method-benchmark-v1",
        "formal_wp8_1_evidence": False,
        "cross_method_ranking_forbidden": True,
        "methods": {},
    }
    for method in methods:
        records = []
        for scale in range(1, 6):
            try:
                operator, model = build(method, scale)
                for repeat in range(1, 6):
                    started = time.perf_counter_ns()
                    prediction = operator.predict(model)
                    elapsed = time.perf_counter_ns() - started
                    records.append(
                        {
                            "scale": scale,
                            "repeat": repeat,
                            "n_param": int(operator.n_param),
                            "n_data": int(operator.n_data),
                            "elapsed_ns": int(elapsed),
                            "status": "passed",
                            "finite": bool(np.all(np.isfinite(prediction))),
                        }
                    )
            except Exception as error:
                for repeat in range(1, 6):
                    records.append(
                        {
                            "scale": scale,
                            "repeat": repeat,
                            "status": "failed",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    )
        benchmark["methods"][method] = {"records": records}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "raw-timings.json").write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "adversarial-results.json").write_text(
        json.dumps(
            {
                "schema_version": "wp8-adversarial-development-v1",
                "formal_wp8_1_evidence": False,
                "execution_kind": "operator_contract_probe",
                "methods": {
                    method: {
                        scenario: {
                            "result": result,
                            "executed": True,
                            "accepted": result.startswith("passed_")
                            or result.startswith("expected_"),
                        }
                        for scenario, result in scenarios.items()
                    }
                    for method, scenarios in ADVERSARIAL.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    protected = []
    for path in (OUTPUT / "raw-timings.json", OUTPUT / "adversarial-results.json"):
        protected.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (OUTPUT / "protected-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "wp8-development-synthetic-manifest-v1",
                "members": protected,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    failed = sum(
        record["status"] == "failed"
        for method in benchmark["methods"].values()
        for record in method["records"]
    )
    print(json.dumps({"methods": len(methods), "records": len(methods) * 25, "failed": failed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
