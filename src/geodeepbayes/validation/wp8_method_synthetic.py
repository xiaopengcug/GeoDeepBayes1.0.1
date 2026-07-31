"""Deterministic method-level synthetic checks for the WP8-1 development track.

The report produced here is solver-development evidence.  It deliberately does
not satisfy or replace any WP8 field-data feasibility gate.
"""
from __future__ import annotations

import json
import hashlib
import importlib.metadata
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from discretize import TensorMesh
from geoana.em.fdem import ElectricDipoleWholeSpace
from geoana.em.static import MagneticPrism
from geoana.gravity import Prism
from scipy.constants import mu_0

from geodeepbayes.forward import (
    CSAMTOperator,
    ColeColeFrequencyOperator,
    DipoleDipoleSurvey,
    DCOperator,
    DimensionalityUpgradeRequired,
    GravityOperator,
    MagneticOperator,
    MT1DRecursiveOperator,
    TDIPOperator,
    TEM1DLayeredOperator,
    WFEMOperator,
    source_zone,
)
from geodeepbayes.validation.sbc import normal_conjugate_reference_sbc, rank_uniformity


REQUIRED_METHOD_CHECKS = {
    **{
        method: (
            "predict_reference_agreement",
            "misspecification_detection",
            "jvp_finite_difference",
            "jvp_jtp_adjoint",
            "taylor_remainder_order",
            "three_level_convergence",
            "method_adversarial_suite",
            "sbc_at_least_400",
            "within_method_5x5_performance",
        )
        for method in ("gravity", "magnetic", "dc", "tdip", "tem", "mt_amt")
    },
    "sip_fdip": (
        "predict_reference_agreement",
        "misspecification_detection",
        "jvp_finite_difference",
        "jvp_jtp_adjoint",
        "taylor_remainder_order",
        "three_level_convergence",
        "method_adversarial_suite",
        "sbc_at_least_400",
        "within_method_5x5_performance",
    ),
    "csamt": (
        "predict_reference_agreement",
        "misspecification_detection",
        "jvp_finite_difference",
        "jvp_jtp_adjoint",
        "taylor_remainder_order",
        "three_level_convergence",
        "method_adversarial_suite",
        "sbc_at_least_400",
        "within_method_5x5_performance",
    ),
    "wfem": (
        "predict_reference_agreement",
        "misspecification_detection",
        "jvp_finite_difference",
        "jvp_jtp_adjoint",
        "taylor_remainder_order",
        "three_level_convergence",
        "method_adversarial_suite",
        "sbc_at_least_400",
        "within_method_5x5_performance",
    ),
}

REFERENCE_IDS = {
    "gravity": "geoana-gravity-prism-v1",
    "magnetic": "geoana-magnetic-prism-v1",
    "dc": "manual-homogeneous-halfspace-geometric-factor-v1",
    "tdip": "independent-two-pulse-weight-shape-v1",
    "sip_fdip": "manual-cole-cole-halfspace-v1",
    "tem": "empymod-cross-filter-plus-halfspace-late-time-slope-sanity-v4",
    "mt_amt": "analytic-mt-halfspace-impedance-v1",
    "csamt": "geoana-uniform-wholespace-frequency-geometry-sanity-v3",
    "wfem": "geoana-uniform-wholespace-frequency-geometry-sanity-v3",
}

CONVERGENCE_IDS = {
    "gravity": "uniform-prism-1-2-4-cells-per-axis-stability-v1",
    "magnetic": "uniform-prism-1-2-4-cells-per-axis-stability-v1",
    "dc": "20-10-5m-mesh-to-halfspace-v1",
    "tdip": "20-10-5m-mesh-self-convergence-v1",
    "sip_fdip": "9-33-129-log-frequency-qoi-v1",
    "tem": "9-33-129-log-time-qoi-v1",
    "mt_amt": "9-33-129-log-frequency-qoi-v1",
    "csamt": "30-20-15m-mesh-self-convergence-v1",
    "wfem": "30-20-15m-mesh-self-convergence-v1",
}

ADVERSARIAL_SCENARIOS = {
    "gravity": {"parameter_scaling", "parameter_sign_reversal", "receiver_geometry_perturbation", "wrong_model_shape", "wrong_data_shape"},
    "magnetic": {"parameter_scaling", "parameter_sign_reversal", "receiver_geometry_perturbation", "wrong_model_shape", "wrong_data_shape"},
    "dc": {"conductivity_doubling", "coincident_electrode", "zero_current", "wrong_model_shape", "wrong_data_shape"},
    "tdip": {"zero_chargeability", "invalid_chargeability", "unsorted_times", "wrong_model_shape", "time_decay_nonzero"},
    "sip_fdip": {"current_geometry_scaling", "frequency_coupling_perturbation", "frequency_order_contract", "coincident_electrode_contract", "homogeneous_model_rejects_spatial_parameter_vector"},
    "tem": {"layer_conductivity_perturbation", "unsorted_times", "three_dimensional_diagnostic", "negative_loop_radius", "wrong_model_shape"},
    "mt_amt": {"layer_conductivity_perturbation", "unsorted_frequencies", "two_dimensional_diagnostic", "three_dimensional_diagnostic", "wrong_model_shape"},
    "csamt": {"near_transition_far", "finite_source_degeneracy", "source_endpoint_perturbation", "phase_component_index_contract", "receiver_topography_geometry_shape_contract"},
    "wfem": {"near_transition_far", "finite_source_degeneracy", "source_endpoint_perturbation", "phase_component_index_contract", "receiver_topography_geometry_shape_contract"},
}


def _passed(metrics: dict[str, Any]) -> dict[str, Any]:
    return {"status": "passed", "required": True, "metrics": metrics}


def _mesh(cell_width: float = 20.0, count: int = 6) -> TensorMesh:
    extent = cell_width * count
    return TensorMesh(
        [[cell_width] * count] * 3,
        origin=[-extent / 2, -extent / 2, -extent / 2],
    )


def _line_geometry() -> tuple[np.ndarray, np.ndarray]:
    return (
        np.array([[-20.0, 0.0, -10.0], [20.0, 0.0, -10.0]]),
        np.array([[40.0, 0.0, -10.0]]),
    )


def _survey() -> DipoleDipoleSurvey:
    return DipoleDipoleSurvey(
        a=np.array([[-30.0, 0.0, 0.0]]),
        b=np.array([[-10.0, 0.0, 0.0]]),
        m=np.array([[10.0, 0.0, 0.0]]),
        n=np.array([[30.0, 0.0, 0.0]]),
        current=np.array([1.0]),
    )


def _manual_geometric_voltage(survey: DipoleDipoleSurvey) -> np.ndarray:
    def inverse_distance(left, right):
        distance = np.linalg.norm(left - right, axis=1)
        if np.any(~np.isfinite(distance)) or np.any(distance <= 0):
            raise ValueError("manual halfspace geometry requires finite non-coincident electrodes")
        return 1.0 / distance

    return survey.current / (2 * np.pi) * (
        inverse_distance(survey.a, survey.m)
        - inverse_distance(survey.a, survey.n)
        - inverse_distance(survey.b, survey.m)
        + inverse_distance(survey.b, survey.n)
    )


def _finite_metric(*values: float) -> bool:
    return all(
        isinstance(value, (int, float, np.integer, np.floating))
        and not isinstance(value, (bool, np.bool_))
        and bool(np.isfinite(value))
        for value in values
    )


def _finite_metric_tree(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return bool(np.isfinite(value))
    if isinstance(value, dict):
        return all(_finite_metric_tree(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite_metric_tree(item) for item in value)
    return True


def _derivative_metrics(operator, model: np.ndarray, seed: int) -> tuple[dict, dict, dict]:
    rng = np.random.default_rng(seed)
    direction = rng.normal(size=operator.n_param)
    data_vector = rng.normal(size=operator.n_data)
    if np.iscomplexobj(operator.predict(model)):
        data_vector = data_vector + 1j * rng.normal(size=operator.n_data)
    tangent = operator.jvp(direction, model)
    step = 1e-4
    finite = (
        operator.predict(model + step * direction)
        - operator.predict(model - step * direction)
    ) / (2 * step)
    relative_fd_error = float(
        np.linalg.norm(finite - tangent) / (np.linalg.norm(finite) + 1e-30)
    )
    left = float(np.real(np.vdot(data_vector, tangent)))
    right = float(direction @ operator.jtp(data_vector, model))
    relative_adjoint_error = float(
        abs(left - right) / (abs(left) + abs(right) + 1e-30)
    )
    tangent_base = operator.predict(model)
    scales = (2e-3, 1e-3, 5e-4)
    output_scale = max(
        float(np.linalg.norm(tangent_base)),
        scales[0] * float(np.linalg.norm(tangent)),
        np.finfo(float).tiny,
    )
    remainders = [
        float(
            np.linalg.norm(
                operator.predict(model + scale * direction)
                - tangent_base
                - scale * tangent
            )
        )
        for scale in scales
    ]
    normalized_remainders = [value / output_scale for value in remainders]
    exact_tolerance = 100 * np.finfo(float).eps * output_scale
    linear_exact = (
        max(remainders) <= exact_tolerance
        and max(normalized_remainders) <= 1e-10
    )
    observed_orders = [
        float(
            np.log(max(remainders[index], np.finfo(float).tiny)
                   / max(remainders[index + 1], np.finfo(float).tiny))
            / np.log(scales[index] / scales[index + 1])
        )
        for index in range(2)
    ]
    if linear_exact:
        order_kind = "linear_exact_with_scale_aware_tolerance"
    else:
        order_kind = "observed_remainder_orders"
    if not _finite_metric(relative_fd_error, relative_adjoint_error, *remainders):
        raise RuntimeError("non-finite derivative metric")
    if relative_fd_error >= 5e-3:
        raise RuntimeError(f"finite-difference error {relative_fd_error} exceeds 5e-3")
    if relative_adjoint_error >= 1e-8:
        raise RuntimeError(f"adjoint error {relative_adjoint_error} exceeds 1e-8")
    if not linear_exact and (
        any(
            normalized_remainders[index + 1] >= normalized_remainders[index]
            for index in range(2)
        )
        or min(observed_orders) <= 1.8
    ):
        raise RuntimeError(
            f"Taylor remainder orders {observed_orders} do not establish second order"
        )
    derivative_kind = (
        "finite_difference_implementation_consistency"
        if "difference" in str(getattr(operator, "derivative_implementation", "")).lower()
        or isinstance(operator, ColeColeFrequencyOperator)
        else "analytic_or_solver_derivative_consistency"
    )
    return (
        _passed({
            "relative_error": relative_fd_error,
            "threshold": 5e-3,
            "derivative_check_kind": derivative_kind,
            "direction_l2_norm": float(np.linalg.norm(direction)),
            "jvp_l2_norm": float(np.linalg.norm(tangent)),
            "qoi_sensitivity_l2_ratio": float(
                np.linalg.norm(tangent) / max(np.linalg.norm(direction), np.finfo(float).tiny)
            ),
        }),
        _passed({"relative_error": relative_adjoint_error, "threshold": 1e-8}),
        _passed(
            {
                "step_sizes": list(scales),
                "remainders": remainders,
                "normalized_remainders": normalized_remainders,
                "normalization_scale": output_scale,
                "scale_aware_exact_tolerance": exact_tolerance,
                "observed_orders": None if linear_exact else observed_orders,
                "order_kind": order_kind,
                "minimum_order": 1.8,
            }
        ),
    )


def _sip_checks() -> dict[str, Any]:
    survey = _survey()
    frequencies = np.array([0.1, 1.0, 10.0, 1000.0])
    operator = ColeColeFrequencyOperator(survey, frequencies)
    model = np.array(
        [np.log(0.02), np.log(0.2 / 0.8), np.log(0.1), np.log(0.6 / 0.4)]
    )
    sigma, eta, tau, exponent = operator.unpack(model)
    reference_sigma = sigma * (
        1 - eta / (1 + (1j * 2 * np.pi * frequencies * tau) ** exponent)
    )
    reference = (
        _manual_geometric_voltage(survey)[:, None] / reference_sigma[None, :]
    ).ravel()
    relative_error = float(
        np.linalg.norm(operator.predict(model) - reference)
        / (np.linalg.norm(reference) + 1e-30)
    )
    if relative_error >= 1e-12:
        raise RuntimeError("SIP analytic reference agreement failed")
    rejected = False
    try:
        ColeColeFrequencyOperator(survey, [0.0])
    except ValueError:
        rejected = True
    if not rejected:
        raise RuntimeError("SIP invalid-frequency misspecification was accepted")
    finite, adjoint, taylor = _derivative_metrics(operator, model, 8101)

    qoi = []
    for count in (9, 33, 129):
        grid = np.geomspace(0.1, 1000.0, count)
        response = ColeColeFrequencyOperator(survey, grid).predict(model)
        qoi.append(
            np.trapezoid(response, x=np.log(grid))
            / (np.log(grid[-1]) - np.log(grid[0]))
        )
    coarse_error = float(abs(qoi[0] - qoi[2]))
    medium_error = float(abs(qoi[1] - qoi[2]))
    if medium_error >= coarse_error:
        raise RuntimeError("SIP three-level spectral convergence failed")
    return {
        "predict_reference_agreement": _passed(
            {"relative_error": relative_error, "threshold": 1e-12}
        ),
        "misspecification_detection": _passed(
            {"case": "non-positive frequency", "rejected": True}
        ),
        "jvp_finite_difference": finite,
        "jvp_jtp_adjoint": adjoint,
        "taylor_remainder_order": taylor,
        "three_level_convergence": _passed(
            {
                "levels": [9, 33, 129],
                "coarse_to_fine_error": coarse_error,
                "medium_to_fine_error": medium_error,
            }
        ),
    }


def _controlled_source_checks(method: str) -> dict[str, Any]:
    mesh = _mesh()
    vertices, receivers = _line_geometry()
    receivers = np.array([[35.0, 5.0, -8.0], [50.0, -7.0, -15.0]])
    conductivity = 0.02
    frequencies = np.array([2.0, 5.0, 10.0])
    model = np.full(mesh.n_cells, np.log(conductivity))
    if method == "csamt":
        operator = CSAMTOperator(mesh, vertices, receivers, frequencies, current=1.0)
    else:
        operator = WFEMOperator(
            mesh,
            vertices,
            receivers,
            frequencies,
            current=2.0,
            apparent_resistivity_definition="not_available",
        )
    if operator.method != method:
        raise RuntimeError(
            f"controlled-source branch cross-wire: requested {method}, operator owns {operator.method}"
        )
    prediction = operator.predict(model).reshape(
        len(frequencies), 2, len(receivers)
    )[:, 0, :]
    references = np.vstack([
        ElectricDipoleWholeSpace(
            frequency,
            sigma=conductivity,
            location=np.array([0.0, 0.0, -10.0]),
            orientation="X",
            current=operator.current,
            length=40.0,
            quasistatic=True,
        ).electric_field(receivers)[:, 0]
        for frequency in frequencies
    ])
    ratios = np.abs(prediction / references)
    log_amplitude_errors = np.abs(np.log(ratios))
    phase_errors = np.abs(np.angle(prediction / references))
    ratio = float(ratios[1, 0])
    log_amplitude_error = float(np.max(log_amplitude_errors))
    phase_error = float(np.max(phase_errors))
    log_amplitude_threshold = 0.65
    phase_threshold = 0.01
    if (
        log_amplitude_error >= log_amplitude_threshold
        or phase_error >= phase_threshold
    ):
        raise RuntimeError(f"{method} uniform whole-space sanity failed")

    rejected = False
    try:
        if method == "csamt":
            CSAMTOperator(
                mesh, [vertices[0], vertices[0]], receivers, [5.0], current=1.0
            )
        else:
            WFEMOperator(
                mesh,
                vertices,
                receivers,
                [5.0],
                current=1.0,
                apparent_resistivity_definition="assumed_rho_mn",
            )
    except ValueError:
        rejected = True
    if not rejected:
        raise RuntimeError(f"{method} contract misspecification was accepted")
    finite, adjoint, taylor = _derivative_metrics(
        operator, model, 8102 if method == "csamt" else 8103
    )
    checks = {
        "predict_reference_agreement": _passed(
            {
                "sanity_reference": "geoana.em.fdem.ElectricDipoleWholeSpace uniform whole-space",
                "case_frequencies_hz": frequencies.tolist(),
                "case_receiver_xyz_m": receivers.tolist(),
                "case_amplitude_ratios": ratios.tolist(),
                "case_absolute_log_amplitude_errors": log_amplitude_errors.tolist(),
                "case_absolute_phase_errors_radians": phase_errors.tolist(),
                "amplitude_ratio": ratio,
                "absolute_log_amplitude_error": log_amplitude_error,
                "log_amplitude_error_threshold": log_amplitude_threshold,
                "absolute_phase_error_radians": phase_error,
                "phase_error_threshold_radians": phase_threshold,
            }
        ),
        "misspecification_detection": _passed(
            {
                "case": (
                    "degenerate finite source"
                    if method == "csamt"
                    else "unspecified apparent-resistivity convention"
                ),
                "rejected": True,
            }
        ),
        "jvp_finite_difference": finite,
        "jvp_jtp_adjoint": adjoint,
        "taylor_remainder_order": taylor,
    }
    predictions = []
    for width, count in ((30.0, 4), (20.0, 6), (15.0, 8)):
        level_mesh = _mesh(width, count)
        if method == "csamt":
            level_operator = CSAMTOperator(
                level_mesh, vertices, receivers, [5.0], current=1.0
            )
        else:
            level_operator = WFEMOperator(
                level_mesh,
                vertices,
                receivers,
                [5.0],
                current=1.0,
                apparent_resistivity_definition="not_available",
            )
        predictions.append(
            level_operator.predict(
                np.full(level_mesh.n_cells, np.log(conductivity))
            )
        )
    coarse_error = float(np.linalg.norm(predictions[0] - predictions[2]))
    medium_error = float(np.linalg.norm(predictions[1] - predictions[2]))
    if medium_error >= coarse_error:
        raise RuntimeError(f"{method} three-level discretization convergence failed")
    checks["three_level_convergence"] = _passed(
        {
            "cell_widths_m": [30.0, 20.0, 15.0],
            "coarse_to_fine_error": coarse_error,
            "medium_to_fine_error": medium_error,
        }
    )
    return checks


def _other_method_checks(method: str) -> dict[str, Any]:
    if method in {"gravity", "magnetic"}:
        mesh = TensorMesh([[100.0], [100.0], [100.0]], origin=[-50, -50, -100])
        receivers = np.array([[200.0, 100.0, 50.0], [-200.0, 50.0, 20.0]])
        if method == "gravity":
            operator = GravityOperator(mesh, receivers)
            model = np.array([1.0])
            reference = (
                Prism([-50, -50, -100], [50, 50, 0], rho=1000)
                .gravitational_field(receivers)[:, 2]
                * 1e5
            )
        else:
            field = (50_000.0, 60.0, 20.0)
            operator = MagneticOperator(mesh, receivers, inducing_field=field)
            model = np.array([0.01])
            amplitude, inc_deg, dec_deg = field
            inc, dec = np.deg2rad(inc_deg), np.deg2rad(dec_deg)
            unit = np.array(
                [np.cos(inc) * np.sin(dec), np.cos(inc) * np.cos(dec), -np.sin(inc)]
            )
            magnetization = model[0] * (amplitude * 1e-9 / mu_0) * unit
            reference = (
                MagneticPrism(
                    [-50, -50, -100], [50, 50, 0], magnetization=magnetization
                ).magnetic_flux_density(receivers)
                @ unit
                * 1e9
            )
        relative = float(
            np.linalg.norm(operator.predict(model) - reference)
            / (np.linalg.norm(reference) + 1e-30)
        )
        if relative >= 1e-6:
            raise RuntimeError(f"{method} prism reference failed")
        levels = []
        for count in (1, 2, 4):
            level_mesh = TensorMesh(
                [[100.0 / count] * count] * 3, origin=[-50, -50, -100]
            )
            level_operator = (
                GravityOperator(level_mesh, receivers)
                if method == "gravity"
                else MagneticOperator(level_mesh, receivers, inducing_field=field)
            )
            levels.append(
                level_operator.predict(np.full(level_operator.n_param, model[0]))
            )
        stability = float(
            max(np.linalg.norm(value - levels[-1]) for value in levels[:-1])
            / (np.linalg.norm(levels[-1]) + 1e-30)
        )
        if stability >= 1e-6:
            raise RuntimeError(f"{method} three-level prism stability failed")
        convergence = _passed(
            {"cells_per_axis": [1, 2, 4], "maximum_relative_qoi_drift": stability, "threshold": 1e-6}
        )
    elif method in {"dc", "tdip"}:
        mesh = TensorMesh([[10.0] * 5, [10.0] * 5, [10.0] * 4], origin=[-25, -25, -40])
        survey = DipoleDipoleSurvey(
            a=np.array([[-20.0, 0, 0]]),
            b=np.array([[-15.0, 0, 0]]),
            m=np.array([[-5.0, 0, 0]]),
            n=np.array([[0.0, 0, 0]]),
            current=np.array([1.0]),
        )
        if method == "dc":
            operator = DCOperator(mesh, survey)
            model = np.full(operator.n_param, np.log(0.02))
            reference = _manual_geometric_voltage(survey) / 0.02
            ratio = float(abs(operator.predict(model)[0] / reference[0]))
            if not 0.2 < ratio < 3.0:
                raise RuntimeError("DC halfspace reference failed")
            reference_metrics = {"amplitude_ratio": ratio, "accepted_range": [0.2, 3.0]}
        else:
            operator = TDIPOperator(
                mesh, survey, [0.01, 0.03, 0.1],
                background_conductivity=0.02, tau=0.08, exponent_c=0.7,
            )
            model = np.full(operator.n_param, 0.05)
            prediction = operator.predict(model)
            eta, tau, exponent, period = 0.05, 0.08, 0.7, operator.survey.T
            step_off = lambda t: eta * np.exp(-((t / tau) ** exponent))
            pulse_off = lambda t: step_off(t) - step_off(t + period / 4)
            weights = np.array([(2 * pulse_off(t) - pulse_off(t + period / 2)) / 2 for t in operator.times])
            shape_error = float(np.linalg.norm(prediction / prediction[0] - weights / weights[0]))
            if shape_error >= 1e-10:
                raise RuntimeError("TDIP pulse reference failed")
            reference_metrics = {"normalized_shape_error": shape_error, "threshold": 1e-10}
        predictions = []
        for width in (20.0, 10.0, 5.0):
            lm = TensorMesh(
                [[width] * int(80 / width), [width] * int(80 / width), [width] * int(60 / width)],
                origin=[-40, -40, -60],
            )
            lo = (
                DCOperator(lm, survey)
                if method == "dc"
                else TDIPOperator(
                    lm, survey, [0.02], background_conductivity=0.02,
                    tau=0.1, exponent_c=0.6,
                )
            )
            predictions.append(lo.predict(
                np.full(lo.n_param, np.log(0.02) if method == "dc" else 0.05)
            ))
        if method == "dc":
            analytic = _manual_geometric_voltage(survey) / 0.02
            coarse, fine = float(np.linalg.norm(predictions[0] - analytic)), float(np.linalg.norm(predictions[2] - analytic))
        else:
            coarse, fine = float(np.linalg.norm(predictions[0] - predictions[2])), float(np.linalg.norm(predictions[1] - predictions[2]))
        if fine >= coarse:
            raise RuntimeError(f"{method} convergence failed")
        convergence = _passed({"levels_m": [20.0, 10.0, 5.0], "coarse_error": coarse, "fine_error": fine})
        relative = None
    else:
        if method == "tem":
            build = lambda grid: TEM1DLayeredOperator(
                [20.0, 40.0], grid, loop_radius=10.0, current=2.0,
                dimensionality_diagnostic=[0.03, 0.07],
            )
            grids = [np.geomspace(1e-5, 1e-3, n) for n in (9, 33, 129)]
            model = np.log([0.01, 0.1, 0.02])
            operator = build(np.geomspace(1e-5, 1e-3, 9))
            alternate = TEM1DLayeredOperator(
                [20.0, 40.0], operator.times, loop_radius=10.0, current=2.0,
                dimensionality_diagnostic=[0.03, 0.07], time_filter="key_201_2012",
            ).predict(model)
            relative = float(np.linalg.norm(operator.predict(model)-alternate)/(np.linalg.norm(alternate)+1e-30))
            threshold = 2e-3
            late_times = np.geomspace(1e-3, 1e-1, 20)
            homogeneous = TEM1DLayeredOperator(
                [], late_times, loop_radius=10.0, current=2.0,
                dimensionality_diagnostic=[0.01],
            )
            late_response = np.abs(
                homogeneous.predict(np.array([np.log(0.02)]))
            )
            late_time_slope = float(
                np.polyfit(np.log(late_times[-6:]), np.log(late_response[-6:]), 1)[0]
            )
            if abs(late_time_slope + 2.5) >= 0.05:
                raise RuntimeError("TEM homogeneous late-time asymptotic slope failed")
        else:
            build = lambda grid: MT1DRecursiveOperator(
                [100.0, 300.0], grid, phase_tensor_skew_deg=[1.0, 2.0],
                ellipticity=[0.03], tipper_amplitude=[0.04],
            )
            grids = [np.geomspace(0.01, 100, n) for n in (9, 33, 129)]
            model = np.log([0.01, 0.1, 0.02])
            operator = build(grids[0])
            homogeneous = MT1DRecursiveOperator(
                (), grids[0], phase_tensor_skew_deg=[1], ellipticity=[0.03], tipper_amplitude=[0.04]
            )
            hmodel = np.array([np.log(0.02)])
            href = -np.sqrt(1j * 2*np.pi*grids[0]*mu_0/0.02)
            relative = float(np.linalg.norm(homogeneous.predict(hmodel)-href)/np.linalg.norm(href))
            threshold = 1e-10
        if relative >= threshold:
            raise RuntimeError(f"{method} reference-or-sanity check failed")
        qoi = []
        for grid in grids:
            response = build(grid).predict(model)
            value = response if method == "tem" else np.abs(response)
            qoi.append(np.trapezoid(value, x=np.log(grid))/(np.log(grid[-1])-np.log(grid[0])))
        coarse, fine = float(abs(qoi[0]-qoi[2])), float(abs(qoi[1]-qoi[2]))
        if fine >= coarse:
            raise RuntimeError(f"{method} convergence failed")
        convergence = _passed({"levels": [9,33,129], "coarse_error": coarse, "fine_error": fine})

    rejected = False
    try:
        operator.predict(np.zeros(operator.n_param + 1))
    except ValueError:
        rejected = True
    if not rejected:
        raise RuntimeError(f"{method} model-shape misspecification accepted")
    finite, adjoint, taylor = _derivative_metrics(operator, model, 7000 + list(REQUIRED_METHOD_CHECKS).index(method))
    return {
        "predict_reference_agreement": _passed(
            reference_metrics if method in {"dc", "tdip"} else {
                "relative_error": relative,
                "threshold": 1e-6 if method in {"gravity","magnetic"} else threshold,
                **(
                    {
                        "scope": "TEM 1-D layered cross-filter and halfspace late-time slope sanity only",
                        "alternate_filter_relative_error": relative,
                        "alternate_filter_relative_error_threshold": threshold,
                        "homogeneous_late_time_loglog_slope": late_time_slope,
                        "expected_late_time_loglog_slope": -2.5,
                        "absolute_slope_tolerance": 0.05,
                    }
                    if method == "tem"
                    else {}
                ),
            }
        ),
        "misspecification_detection": _passed({"case": "wrong model shape", "rejected": True}),
        "jvp_finite_difference": finite,
        "jvp_jtp_adjoint": adjoint,
        "taylor_remainder_order": taylor,
        "three_level_convergence": convergence,
    }


def _rejection(expected_exception_classes, callable_) -> dict[str, Any]:
    try:
        callable_()
    except expected_exception_classes as exc:
        return {"rejected": True, "exception_type": type(exc).__name__}
    except Exception as exc:
        raise RuntimeError(
            f"unexpected {type(exc).__name__}; expected "
            f"{[item.__name__ for item in expected_exception_classes]}"
        ) from exc
    raise RuntimeError("adversarial input was unexpectedly accepted")


def _other_adversarial(method: str) -> dict[str, Any]:
    if method in {"gravity", "magnetic"}:
        mesh = TensorMesh([[100.0], [100.0], [100.0]], origin=[-50, -50, -100])
        receivers = np.array([[200.0, 100.0, 50.0]])
        operator = GravityOperator(mesh, receivers) if method == "gravity" else MagneticOperator(mesh, receivers)
        base_model = np.array([1.0 if method == "gravity" else 0.01])
        base = operator.predict(base_model)
        scaling_error = float(np.linalg.norm(operator.predict(2 * base_model) - 2 * base) / (np.linalg.norm(base) + 1e-30))
        sign_error = float(np.linalg.norm(operator.predict(-base_model) + base) / (np.linalg.norm(base) + 1e-30))
        shifted = (GravityOperator(mesh, receivers + [10, 0, 0]) if method == "gravity" else MagneticOperator(mesh, receivers + [10, 0, 0])).predict(base_model)
        receiver_change = float(np.linalg.norm(shifted - base) / (np.linalg.norm(base) + 1e-30))
        scenarios = {
            "parameter_scaling": {"relative_error": scaling_error, "maximum": 1e-12},
            "parameter_sign_reversal": {"relative_error": sign_error, "maximum": 1e-12},
            "receiver_geometry_perturbation": {"relative_change": receiver_change, "minimum": 1e-4},
            "wrong_model_shape": _rejection((ValueError,), lambda: operator.predict(np.zeros(2))),
            "wrong_data_shape": _rejection((ValueError,), lambda: operator.jtp(np.zeros(2))),
        }
        if not _finite_metric(scaling_error, sign_error, receiver_change) or scaling_error >= 1e-12 or sign_error >= 1e-12 or receiver_change <= 1e-4:
            raise RuntimeError(f"{method} adversarial metrics failed")
    elif method in {"dc", "tdip"}:
        mesh = TensorMesh([[10.0] * 5, [10.0] * 5, [10.0] * 4], origin=[-25, -25, -40])
        survey = DipoleDipoleSurvey(
            a=np.array([[-20.,0,0]]), b=np.array([[-15.,0,0]]),
            m=np.array([[-5.,0,0]]), n=np.array([[0.,0,0]]), current=np.array([1.]),
        )
        if method == "dc":
            operator = DCOperator(mesh, survey); model=np.full(operator.n_param,np.log(.02))
            high = operator.predict(np.full(operator.n_param,np.log(.04)))
            base = operator.predict(model)
            conductivity_ratio = float(abs(high[0]/base[0]))
            scenarios = {
                "conductivity_doubling": {"voltage_ratio": conductivity_ratio, "expected_near": 0.5, "absolute_tolerance": 0.2},
                "coincident_electrode": _rejection((ValueError,), lambda: DCOperator(mesh, DipoleDipoleSurvey(a=survey.a,b=survey.b,m=survey.a,n=survey.n,current=survey.current)).predict(model)),
                "zero_current": _rejection((ValueError,), lambda: DipoleDipoleSurvey(a=survey.a,b=survey.b,m=survey.m,n=survey.n,current=np.array([0.]))),
                "wrong_model_shape": _rejection((ValueError,), lambda: operator.predict(np.zeros(operator.n_param+1))),
                "wrong_data_shape": _rejection((ValueError,), lambda: operator.jtp(np.zeros(operator.n_data+1))),
            }
            if not _finite_metric(conductivity_ratio) or abs(conductivity_ratio-.5) >= .2: raise RuntimeError("DC adversarial response failed")
        else:
            operator=TDIPOperator(mesh,survey,[.01,.03,.1],background_conductivity=.02,tau=.08,exponent_c=.7)
            model=np.full(operator.n_param,.05); base=operator.predict(model)
            zero_norm=float(np.linalg.norm(operator.predict(np.zeros(operator.n_param))))
            scenarios={
                "zero_chargeability": {"response_norm":zero_norm,"maximum":1e-12},
                "invalid_chargeability":_rejection((ValueError,), lambda:operator.predict(np.ones(operator.n_param))),
                "unsorted_times":_rejection((ValueError,), lambda:TDIPOperator(mesh,survey,[.1,.01],background_conductivity=.02,tau=.1,exponent_c=.5)),
                "wrong_model_shape":_rejection((ValueError,), lambda:operator.predict(np.zeros(operator.n_param+1))),
                "time_decay_nonzero":{"response_norm":float(np.linalg.norm(base)),"minimum":1e-12},
            }
            if not _finite_metric(zero_norm,float(np.linalg.norm(base))) or zero_norm>=1e-12 or np.linalg.norm(base)<=1e-12: raise RuntimeError("TDIP adversarial response failed")
    elif method == "tem":
        times=np.geomspace(1e-5,1e-3,9); operator=TEM1DLayeredOperator([20.,40.],times,loop_radius=10.,dimensionality_diagnostic=[.03])
        model=np.log([.01,.1,.02]); base=operator.predict(model)
        perturbed=operator.predict(model+np.array([.1,0,0])); change=float(np.linalg.norm(perturbed-base)/(np.linalg.norm(base)+1e-30))
        scenarios={
            "layer_conductivity_perturbation":{"relative_change":change,"minimum":1e-4},
            "unsorted_times":_rejection((ValueError,), lambda:TEM1DLayeredOperator([20.],[1e-3,1e-4],loop_radius=10.,dimensionality_diagnostic=[.03])),
            "three_dimensional_diagnostic":_rejection((DimensionalityUpgradeRequired,), lambda:TEM1DLayeredOperator([20.],[1e-4],loop_radius=10.,dimensionality_diagnostic=[.2])),
            "negative_loop_radius":_rejection((ValueError,), lambda:TEM1DLayeredOperator([20.],[1e-4],loop_radius=-1.,dimensionality_diagnostic=[.03])),
            "wrong_model_shape":_rejection((ValueError,), lambda:operator.predict(np.zeros(operator.n_param+1))),
        }
        if not _finite_metric(change) or change<=1e-4: raise RuntimeError("TEM adversarial response failed")
    else:
        freq=np.geomspace(.01,100,9); operator=MT1DRecursiveOperator([100.,300.],freq,phase_tensor_skew_deg=[1],ellipticity=[.03],tipper_amplitude=[.04])
        model=np.log([.01,.1,.02]); base=operator.predict(model); perturbed=operator.predict(model+np.array([.1,0,0]))
        change=float(np.linalg.norm(perturbed-base)/(np.linalg.norm(base)+1e-30))
        scenarios={
            "layer_conductivity_perturbation":{"relative_change":change,"minimum":1e-4},
            "unsorted_frequencies":_rejection((ValueError,), lambda:MT1DRecursiveOperator([100.],[10.,1.],phase_tensor_skew_deg=[1],ellipticity=[.03],tipper_amplitude=[.04])),
            "two_dimensional_diagnostic":_rejection((DimensionalityUpgradeRequired,), lambda:MT1DRecursiveOperator([100.],[1.],phase_tensor_skew_deg=[5.],ellipticity=[.2],tipper_amplitude=[.2])),
            "three_dimensional_diagnostic":_rejection((DimensionalityUpgradeRequired,), lambda:MT1DRecursiveOperator([100.],[1.],phase_tensor_skew_deg=[10.],ellipticity=[.2],tipper_amplitude=[.4])),
            "wrong_model_shape":_rejection((ValueError,), lambda:operator.predict(np.zeros(operator.n_param+1))),
        }
        if not _finite_metric(change) or change<=1e-4: raise RuntimeError("MT adversarial response failed")
    return scenarios


def _adversarial_suite(method: str) -> dict[str, Any]:
    """Execute method-specific perturbations; every scenario has a numeric result or rejection."""
    scenarios: dict[str, Any] = {}
    if method == "sip_fdip":
        survey = _survey()
        model = np.array(
            [np.log(0.02), np.log(0.2 / 0.8), np.log(0.1), np.log(0.6 / 0.4)]
        )
        operator = ColeColeFrequencyOperator(survey, [0.1, 1.0, 10.0])
        response = operator.predict(model)
        doubled = DipoleDipoleSurvey(
            a=survey.a,
            b=survey.b,
            m=survey.m,
            n=survey.n,
            current=2 * survey.current,
        )
        scaling_error = float(
            np.linalg.norm(ColeColeFrequencyOperator(doubled, [0.1, 1.0, 10.0]).predict(model) - 2 * response)
            / np.linalg.norm(response)
        )
        frequency_effect = float(abs(response[0] - response[-1]) / abs(response[0]))
        rejected_frequency = rejected_geometry = rejected_spatial_model = False
        try:
            ColeColeFrequencyOperator(survey, [1.0, 1.0])
        except ValueError:
            rejected_frequency = True
        try:
            bad = DipoleDipoleSurvey(
                a=survey.a, b=survey.b, m=survey.a, n=survey.n, current=survey.current
            )
            ColeColeFrequencyOperator(bad, [1.0])
        except ValueError:
            rejected_geometry = True
        try:
            operator.predict(np.zeros(8))
        except ValueError:
            rejected_spatial_model = True
        if (
            scaling_error >= 1e-12
            or frequency_effect <= 1e-3
            or not all((rejected_frequency, rejected_geometry, rejected_spatial_model))
        ):
            raise RuntimeError("SIP adversarial suite failed")
        scenarios = {
            "current_geometry_scaling": {
                "expected": "doubling current doubles complex voltage",
                "relative_error": scaling_error,
                "threshold": 1e-12,
            },
            "frequency_coupling_perturbation": {
                "relative_endpoint_change": frequency_effect,
                "minimum": 1e-3,
            },
            "frequency_order_contract": {"rejected": rejected_frequency},
            "coincident_electrode_contract": {"rejected": rejected_geometry},
            "homogeneous_model_rejects_spatial_parameter_vector": {
                "rejected": rejected_spatial_model
            },
        }
    elif method in {"gravity", "magnetic", "dc", "tdip", "tem", "mt_amt"}:
        scenarios = _other_adversarial(method)
    else:
        conductivity = 0.02
        frequency = 5.0
        skin = np.sqrt(2 / (2 * np.pi * frequency * 4e-7 * np.pi * conductivity))
        zones = [
            source_zone(multiplier * skin, frequency, conductivity)
            for multiplier in (0.5, 2.0, 6.0)
        ]
        mesh = _mesh()
        vertices, receivers = _line_geometry()
        constructor = CSAMTOperator if method == "csamt" else WFEMOperator
        kwargs = (
            {}
            if method == "csamt"
            else {"apparent_resistivity_definition": "not_available"}
        )
        base = constructor(
            mesh, vertices, receivers, [frequency], current=1.0, **kwargs
        ).predict(np.full(mesh.n_cells, np.log(conductivity)))
        phase_stripping_change = float(
            np.linalg.norm(base - base.real) / np.linalg.norm(base)
        )
        shifted_vertices = vertices.copy()
        shifted_vertices[0, 0] -= 5.0
        shifted = constructor(
            mesh, shifted_vertices, receivers, [frequency], current=1.0, **kwargs
        ).predict(np.full(mesh.n_cells, np.log(conductivity)))
        geometry_change = float(np.linalg.norm(shifted - base) / np.linalg.norm(base))
        rejected_source = rejected_component = rejected_geometry = False
        try:
            constructor(
                mesh, [vertices[0], vertices[0]], receivers, [frequency], current=1.0, **kwargs
            )
        except ValueError:
            rejected_source = True
        operator = constructor(
            mesh, vertices, receivers, [frequency], current=1.0, **kwargs
        )
        try:
            operator.component(base, 2)
        except IndexError:
            rejected_component = True
        try:
            constructor(
                mesh, vertices, [[40.0, 0.0]], [frequency], current=1.0, **kwargs
            )
        except ValueError:
            rejected_geometry = True
        if (
            zones != ["near", "transition", "far"]
            or geometry_change <= 1e-3
            or phase_stripping_change <= 1e-6
            or not all((rejected_source, rejected_component, rejected_geometry))
        ):
            raise RuntimeError(f"{method} adversarial suite failed")
        scenarios = {
            "near_transition_far": {
                "skin_depth_m": float(skin),
                "multipliers": [0.5, 2.0, 6.0],
                "classifications": zones,
            },
            "finite_source_degeneracy": {"rejected": rejected_source},
            "source_endpoint_perturbation": {
                "relative_response_change": geometry_change,
                "minimum": 1e-3,
            },
            "phase_component_index_contract": {
                "invalid_component_rejected": rejected_component,
                "phase_stripping_relative_change": phase_stripping_change,
                "minimum_detectable_change": 1e-6,
            },
            "receiver_topography_geometry_shape_contract": {
                "rejected": rejected_geometry
            },
        }
    return _passed({"scenarios": scenarios})


def _sbc_check(method: str, checks: dict[str, Any]) -> dict[str, Any]:
    settings = {
        "gravity": (18095, 0.55, "density_contrast"),
        "magnetic": (18096, 0.65, "susceptibility"),
        "dc": (18097, 0.7, "homogeneous_log_conductivity"),
        "tdip": (18098, 0.75, "chargeability"),
        "tem": (18099, 0.9, "layer_log_conductivity"),
        "mt_amt": (18100, 1.0, "halfspace_log_conductivity"),
        "sip_fdip": (18101, 0.8, "log_sigma_inf"),
        "csamt": (18102, 1.1, "homogeneous_log_conductivity"),
        "wfem": (18103, 1.4, "homogeneous_log_conductivity"),
    }
    seed, nominal_sensitivity, qoi = settings[method]
    derivative_metrics = checks["jvp_finite_difference"]["metrics"]
    operator_sensitivity = float(derivative_metrics["qoi_sensitivity_l2_ratio"])
    sensitivity = max(operator_sensitivity, np.finfo(float).tiny)
    per_seed = [
        normal_conjugate_reference_sbc(
            repetitions=400,
            posterior_draw_count=99,
            seed=seed + offset,
            sensitivity=sensitivity,
            qoi=qoi,
        )
        for offset in (0, 10_000)
    ]
    result = rank_uniformity(
        [rank for run in per_seed for rank in run["raw_ranks"]],
        posterior_draw_count=99,
        bins=10,
    )
    expected = result["repetitions"] / result["bins"]
    max_standardized_bin_deviation = float(
        max(abs(count - expected) for count in result["counts"]) / np.sqrt(expected)
    )
    pvalue_threshold = 0.01 / (len(REQUIRED_METHOD_CHECKS) * 3)
    deviation_threshold = 4.0
    if (
        not _finite_metric(
            result["chi_square"], result["pvalue"], max_standardized_bin_deviation
        )
        or
        result["pvalue"] < pvalue_threshold
        or any(run["pvalue"] < pvalue_threshold for run in per_seed)
        or max_standardized_bin_deviation >= deviation_threshold
    ):
        raise RuntimeError(f"{method} SBC rank-uniformity diagnostic failed")
    result.update(
        {
            "seeds": [seed, seed + 10_000],
            "repetitions_per_seed": 400,
            "per_seed": [
                {
                    "seed": seed_value,
                    "repetitions": run["repetitions"],
                    "counts": run["counts"],
                    "chi_square": run["chi_square"],
                    "pvalue": run["pvalue"],
                    "raw_ranks": run["raw_ranks"],
                }
                for seed_value, run in zip((seed, seed + 10_000), per_seed)
            ],
            "pvalue_threshold": pvalue_threshold,
            "max_standardized_bin_deviation": max_standardized_bin_deviation,
            "max_standardized_bin_deviation_threshold": deviation_threshold,
            "reference_kind": "operator-sensitivity-conditioned scalar Gaussian reference rank test; not method-posterior calibration",
            "sensitivity": sensitivity,
            "sensitivity_source": {
                "operator_check": "jvp_finite_difference",
                "direction_l2_norm": derivative_metrics["direction_l2_norm"],
                "jvp_l2_norm": derivative_metrics["jvp_l2_norm"],
                "qoi_sensitivity_l2_ratio": operator_sensitivity,
                "nominal_method_sensitivity": nominal_sensitivity,
            },
            "qoi": qoi,
        }
    )
    return _passed(result)


def _benchmark_operator(method: str, scale: int):
    count = scale + 2
    if method in {"gravity", "magnetic"}:
        mesh = TensorMesh([[10.0] * count] * 3, origin=[-5 * count, -5 * count, -10 * count])
        receivers = np.array([[0.0, 0.0, 5.0]])
        operator = GravityOperator(mesh, receivers) if method == "gravity" else MagneticOperator(mesh, receivers)
        model = np.zeros(operator.n_param)
        definition = {"cells_per_axis": count, "mesh_cells": int(mesh.n_cells)}
    elif method in {"dc", "tdip"}:
        mesh = TensorMesh([[8.0] * count] * 3, origin=[-4 * count, -4 * count, -8 * count])
        benchmark_survey = DipoleDipoleSurvey(
            a=np.array([[-8.0, 0.0, 0.0]]),
            b=np.array([[-4.0, 0.0, 0.0]]),
            m=np.array([[4.0, 0.0, 0.0]]),
            n=np.array([[8.0, 0.0, 0.0]]),
            current=np.array([1.0]),
        )
        if method == "dc":
            operator = DCOperator(mesh, benchmark_survey)
            model = np.full(operator.n_param, np.log(0.02))
        else:
            operator = TDIPOperator(
                mesh, benchmark_survey, [0.01, 0.03], background_conductivity=0.02,
                tau=0.1, exponent_c=0.6,
            )
            model = np.full(operator.n_param, 0.05)
        definition = {"cells_per_axis": count, "mesh_cells": int(mesh.n_cells)}
    elif method == "tem":
        operator = TEM1DLayeredOperator(
            [20.0] * scale, np.geomspace(1e-5, 1e-3, count),
            loop_radius=10, dimensionality_diagnostic=[0.02],
        )
        model = np.log(np.linspace(0.01, 0.05, operator.n_param))
        definition = {"layer_count": scale + 1, "time_count": count}
    elif method == "mt_amt":
        operator = MT1DRecursiveOperator(
            [100.0] * scale, np.geomspace(0.01, 100, count),
            phase_tensor_skew_deg=[1], ellipticity=[0.03], tipper_amplitude=[0.04],
        )
        model = np.log(np.linspace(0.01, 0.05, operator.n_param))
        definition = {"layer_count": scale + 1, "frequency_count": count}
    elif method == "sip_fdip":
        operator = ColeColeFrequencyOperator(
            _survey(), np.geomspace(0.1, 100.0, 2**scale)
        )
        model = np.array([np.log(0.02), -1.3, np.log(0.1), 0.4])
        definition = {"frequency_count": int(2**scale)}
    else:
        mesh = _mesh()
        vertices, _ = _line_geometry()
        receiver_count = scale
        receivers = np.column_stack(
            (
                np.linspace(30.0, 50.0, receiver_count),
                np.zeros(receiver_count),
                np.full(receiver_count, -10.0),
            )
        )
        if method == "csamt":
            operator = CSAMTOperator(
                mesh, vertices, receivers, [5.0], current=1.0
            )
        else:
            operator = WFEMOperator(
                mesh,
                vertices,
                receivers,
                [5.0],
                current=1.0,
                apparent_resistivity_definition="not_available",
            )
        model = np.full(mesh.n_cells, np.log(0.02))
        definition = {"receiver_count": receiver_count, "mesh_cells": int(mesh.n_cells)}
    return operator, model, definition


def _performance_check(method: str) -> dict[str, Any]:
    records = []
    scales = []
    max_setup_ns = 5_000_000_000
    max_first_predict_ns = 5_000_000_000
    max_elapsed_ns = 2_000_000_000
    for scale in range(1, 6):
        setup_started = time.perf_counter_ns()
        operator, model, size_definition = _benchmark_operator(method, scale)
        setup_ns = time.perf_counter_ns() - setup_started
        first_started = time.perf_counter_ns()
        first_prediction = operator.predict(model)
        first_predict_ns = time.perf_counter_ns() - first_started
        if (
            setup_ns <= 0
            or setup_ns > max_setup_ns
            or first_predict_ns <= 0
            or first_predict_ns > max_first_predict_ns
            or not np.all(np.isfinite(first_prediction))
        ):
            raise RuntimeError(f"{method} cold performance execution failed")
        scale_elapsed = []
        for repeat in range(1, 6):
            started = time.perf_counter_ns()
            prediction = operator.predict(model)
            elapsed = time.perf_counter_ns() - started
            if elapsed <= 0 or elapsed > max_elapsed_ns or not np.all(np.isfinite(prediction)):
                raise RuntimeError(f"{method} performance execution failed")
            scale_elapsed.append(elapsed)
            records.append(
                {
                    "scale": scale,
                    "repeat": repeat,
                    "n_param": int(operator.n_param),
                    "n_data": int(operator.n_data),
                    "size_definition": size_definition,
                    "elapsed_ns": int(elapsed),
                    "max_elapsed_ns": max_elapsed_ns,
                    "finite": True,
                }
            )
        scales.append(
            {
                "scale": scale,
                "size_definition": size_definition,
                "setup_ns": int(setup_ns),
                "max_setup_ns": max_setup_ns,
                "first_predict_ns": int(first_predict_ns),
                "max_first_predict_ns": max_first_predict_ns,
                "median_warm_ns": float(np.median(scale_elapsed)),
            }
        )
    median_scaling_ratio = float(
        max(item["median_warm_ns"] for item in scales)
        / max(min(item["median_warm_ns"] for item in scales), 1)
    )
    if median_scaling_ratio >= 1000.0:
        raise RuntimeError(f"{method} warm scaling guard failed")
    return _passed(
        {
            "scale_count": 5,
            "repetitions_per_scale": 5,
            "record_count": len(records),
            "clock": "time.perf_counter_ns",
            "cross_method_ranking_forbidden": True,
            "regression_limit_kind": "environment-qualified-smoke-bounds-not-portable-performance-claims",
            "persistence_scope": "historical runtime smoke record only",
            "timings_replay_bound": False,
            "cross_run_timing_audit_forbidden": True,
            "environment_qualification": {
                "logical_cpu_count": os.cpu_count(),
                "thread_environment": {
                    name: os.environ.get(name)
                    for name in (
                        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                    )
                },
                "memory_bytes": (
                    int(importlib.import_module("psutil").virtual_memory().total)
                    if importlib.util.find_spec("psutil") is not None
                    else None
                ),
            },
            "cold_scale_records": scales,
            "median_warm_scaling_ratio": median_scaling_ratio,
            "max_median_warm_scaling_ratio": 1000.0,
            "records": records,
        }
    )


METHOD_ORDER = tuple(REQUIRED_METHOD_CHECKS)


def run_single_method(method: str) -> dict[str, Any]:
    """Dispatch one explicitly named method; the runner owns its identity."""
    if method not in REQUIRED_METHOD_CHECKS:
        raise ValueError(f"unknown WP8 method: {method}")
    if method == "sip_fdip":
        checks = _sip_checks()
    elif method in {"csamt", "wfem"}:
        checks = _controlled_source_checks(method)
    else:
        checks = _other_method_checks(method)
    return {"method": method, "checks": checks}


def _provenance_bindings() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    relative_files = [
        "src/geodeepbayes/forward/gravity.py",
        "src/geodeepbayes/forward/magnetic.py",
        "src/geodeepbayes/forward/static.py",
        "src/geodeepbayes/forward/em1d.py",
        "src/geodeepbayes/forward/controlled_source.py",
        "src/geodeepbayes/validation/sbc.py",
        "validation/wp8/validate_wp8.py",
        "validation/wp8/synthetic/method-validation-policy-v1.json",
        "uv.lock",
    ]
    return {
        "files_sha256": {
            relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
            for relative in relative_files
        },
        "dependency_versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "simpeg", "discretize", "geoana")
        },
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "byteorder": sys.byteorder,
        },
    }


def run_method_synthetic_validation() -> dict[str, Any]:
    """Run the frozen deterministic development slice and return JSON-safe evidence."""
    methods: dict[str, Any] = {}
    for method in METHOD_ORDER:
        try:
            payload = run_single_method(method)
            if payload.get("method") != method:
                raise RuntimeError(
                    f"dispatcher cross-wire: requested {method}, got {payload.get('method')}"
                )
            checks = payload["checks"]
            checks["predict_reference_agreement"]["reference_id"] = REFERENCE_IDS[method]
            checks["three_level_convergence"]["convergence_id"] = CONVERGENCE_IDS[method]
            checks["method_adversarial_suite"] = _adversarial_suite(method)
            checks["sbc_at_least_400"] = _sbc_check(method, checks)
            checks["within_method_5x5_performance"] = _performance_check(method)
            if not _finite_metric_tree(checks):
                raise RuntimeError(f"{method} produced non-finite validation metrics")
            missing = set(REQUIRED_METHOD_CHECKS[method]) - set(checks)
            failed = [
                name
                for name in REQUIRED_METHOD_CHECKS[method]
                if checks.get(name, {}).get("status") != "passed"
            ]
            status = "passed" if not missing and not failed else "blocked"
            methods[method] = {
                "method": method,
                "status": status,
                "required_checks": list(REQUIRED_METHOD_CHECKS[method]),
                "checks": checks,
                "errors": sorted(missing) + failed,
            }
        except Exception as exc:  # fail closed while retaining machine evidence
            methods[method] = {
                "method": method,
                "status": "blocked",
                "required_checks": list(REQUIRED_METHOD_CHECKS[method]),
                "checks": {},
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
    return {
        "schema_version": "wp8-method-synthetic-validation-v1",
        "status": (
            "passed"
            if all(item["status"] == "passed" for item in methods.values())
            else "blocked"
        ),
        "purpose": "method-level solver development validation only",
        "provenance": "deterministic-semantics-with-nondeterministic-wall-clock-timings",
        "producer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "provenance_bindings": _provenance_bindings(),
        "field_validation_eligible": False,
        "closes_formal_field_gaps": False,
        "methods": methods,
    }


def write_method_synthetic_evidence(path: str | Path) -> dict[str, Any]:
    report = run_method_synthetic_validation()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
