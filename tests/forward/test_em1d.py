import numpy as np
import pytest
from scipy.constants import mu_0

from geodeepbayes.forward import (
    DimensionalityUpgradeRequired,
    MT1DRecursiveOperator,
    TEM1DLayeredOperator,
    mt_dimensionality,
    tdem3d_path_status,
)


def _adjoint(operator, model, rng):
    direction = rng.normal(size=operator.n_param)
    if operator.data_mode == "complex":
        data_direction = rng.normal(size=operator.n_data) + 1j * rng.normal(
            size=operator.n_data
        )
    else:
        data_direction = rng.normal(size=operator.n_data)
    left = float(np.real(np.vdot(data_direction, operator.jvp(direction, model))))
    right = float(direction @ operator.jtp(data_direction, model))
    return abs(left - right) / (abs(left) + abs(right) + 1e-30)


def _finite(operator, model, rng, step=1e-5):
    direction = rng.normal(size=operator.n_param)
    finite = (
        operator.predict(model + step * direction)
        - operator.predict(model - step * direction)
    ) / (2 * step)
    tangent = operator.jvp(direction, model)
    np.testing.assert_allclose(finite, tangent, rtol=3e-4, atol=1e-10)
    residuals = []
    for scale in (1e-2, 5e-3):
        residuals.append(
            np.linalg.norm(
                operator.predict(model + scale * direction)
                - operator.predict(model)
                - scale * tangent
            )
        )
    assert residuals[0] / max(residuals[1], 1e-30) > 3


def _tem(times, time_filter="key_81_2009"):
    return TEM1DLayeredOperator(
        [20.0, 40.0],
        times,
        loop_radius=10.0,
        current=2.0,
        dimensionality_diagnostic=[0.03, 0.07],
        time_filter=time_filter,
    )


def _mt(frequencies, thicknesses=(100.0, 300.0)):
    return MT1DRecursiveOperator(
        thicknesses,
        frequencies,
        phase_tensor_skew_deg=[1.0, 2.0],
        ellipticity=[0.03],
        tipper_amplitude=[0.04],
    )


def test_tem_forward_derivatives_and_independent_filter_reference():
    times = np.geomspace(1e-5, 1e-3, 7)
    model = np.log([0.01, 0.1, 0.02])
    operator = _tem(times, "key_81_2009")
    reference = _tem(times, "key_201_2012").predict(model)
    prediction = operator.predict(model)
    assert np.all(prediction < 0)
    np.testing.assert_allclose(prediction, reference, rtol=2e-3, atol=1e-12)
    rng = np.random.default_rng(30)
    assert _adjoint(operator, model, rng) < 1e-8
    _finite(operator, model, rng)


def test_tem_three_level_time_resolution_convergence():
    model = np.log([0.01, 0.1, 0.02])
    qoi = []
    for count in (9, 33, 129):
        times = np.geomspace(1e-5, 1e-3, count)
        response = _tem(times).predict(model)
        qoi.append(
            np.trapezoid(response, x=np.log(times))
            / (np.log(times[-1]) - np.log(times[0]))
        )
    assert abs(qoi[1] - qoi[2]) < abs(qoi[0] - qoi[2])


def test_tem_dimensionality_upgrade_and_3d_path_fail_closed():
    with pytest.raises(DimensionalityUpgradeRequired) as exc:
        TEM1DLayeredOperator(
            [20.0],
            [1e-4],
            loop_radius=10,
            dimensionality_diagnostic=[0.2],
        )
    assert exc.value.required == "3d"
    status = tdem3d_path_status()
    assert status.dependency_available is True
    assert status.verified is False
    assert "resource budget" in status.reason


def test_mt_homogeneous_halfspace_reference_and_derivatives():
    frequencies = np.geomspace(0.01, 100, 9)
    conductivity = 0.02
    operator = _mt(frequencies, thicknesses=())
    model = np.array([np.log(conductivity)])
    prediction = operator.predict(model)
    reference = -np.sqrt(1j * 2 * np.pi * frequencies * mu_0 / conductivity)
    np.testing.assert_allclose(prediction, reference, rtol=1e-12, atol=1e-14)
    rng = np.random.default_rng(31)
    assert _adjoint(operator, model, rng) < 1e-8
    _finite(operator, model, rng)


def test_mt_three_level_frequency_qoi_convergence():
    model = np.log([0.01, 0.1, 0.02])
    qoi = []
    for count in (9, 33, 129):
        frequencies = np.geomspace(0.01, 100, count)
        impedance = _mt(frequencies).predict(model)
        qoi.append(
            np.trapezoid(np.abs(impedance), x=np.log(frequencies))
            / (np.log(frequencies[-1]) - np.log(frequencies[0]))
        )
    assert abs(qoi[1] - qoi[2]) < abs(qoi[0] - qoi[2])


def test_mt_dimensionality_routes_to_2d_or_3d_and_bad_inputs_fail():
    assert mt_dimensionality([5.0], [0.2], [0.2]) == "2d"
    assert mt_dimensionality([10.0], [0.2], [0.4]) == "3d"
    for skew, tipper, expected in (([5.0], [0.2], "2d"), ([10.0], [0.4], "3d")):
        with pytest.raises(DimensionalityUpgradeRequired) as exc:
            MT1DRecursiveOperator(
                [100.0],
                [1.0],
                phase_tensor_skew_deg=skew,
                ellipticity=[0.2],
                tipper_amplitude=tipper,
            )
        assert exc.value.required == expected
    with pytest.raises(ValueError, match="strictly increasing"):
        _mt([10.0, 1.0])
