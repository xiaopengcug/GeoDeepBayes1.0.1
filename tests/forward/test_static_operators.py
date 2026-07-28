import numpy as np
import pytest
from discretize import TensorMesh

from geodeepbayes.forward import (
    ColeCole2DOperator,
    ColeColeFrequencyOperator,
    DCOperator,
    DipoleDipoleSurvey,
    ForwardOperator,
    TDIPOperator,
)


@pytest.fixture(scope="module")
def static_mesh():
    return TensorMesh([[10.0] * 5, [10.0] * 5, [10.0] * 4], origin=[-25, -25, -40])


@pytest.fixture(scope="module")
def static_survey():
    return DipoleDipoleSurvey(
        a=np.array([[-20.0, 0, 0], [-15.0, 0, 0]]),
        b=np.array([[-15.0, 0, 0], [-10.0, 0, 0]]),
        m=np.array([[-5.0, 0, 0], [0.0, 0, 0]]),
        n=np.array([[0.0, 0, 0], [5.0, 0, 0]]),
        current=np.array([1.0, 0.5]),
    )


def _adjoint(operator, model, rng):
    direction = rng.normal(size=operator.n_param)
    data_direction = rng.normal(size=operator.n_data)
    jv = operator.jvp(direction, model)
    jt = operator.jtp(data_direction, model)
    left = float(np.real(np.vdot(data_direction, jv)))
    right = float(direction @ jt)
    return abs(left - right) / (abs(left) + abs(right) + 1e-30)


def _finite_difference(operator, model, rng, step=1e-5):
    direction = rng.normal(size=operator.n_param)
    finite = (operator.predict(model + step * direction) - operator.predict(model)) / step
    return finite, operator.jvp(direction, model)


def _taylor_ratio(operator, model, rng, step):
    direction = rng.normal(size=operator.n_param)
    tangent = operator.jvp(direction, model)
    errors = []
    for scale in (step, step / 2):
        residual = (
            operator.predict(model + scale * direction)
            - operator.predict(model)
            - scale * tangent
        )
        errors.append(np.linalg.norm(residual))
    return errors[0] / max(errors[1], 1e-30)


def test_dc_forward_derivatives_and_halfspace_reference(static_mesh, static_survey):
    operator = DCOperator(static_mesh, static_survey)
    assert isinstance(operator, ForwardOperator)
    conductivity = 0.02
    model = np.full(operator.n_param, np.log(conductivity))
    prediction = operator.predict(model)
    geometric = ColeColeFrequencyOperator(static_survey, [1.0])._geometric_voltage
    reference = geometric / conductivity
    # Finite mesh/boundary error is expected; sign and engineering-scale
    # agreement with the independent homogeneous halfspace formula are required.
    assert np.all(np.sign(prediction) == np.sign(reference))
    ratio = np.abs(prediction / reference)
    assert np.all((ratio > 0.2) & (ratio < 3.0)), ratio
    rng = np.random.default_rng(22)
    assert _adjoint(operator, model, rng) < 1e-8
    # SolverLU loses the perturbation below roughly 1e-5 on this mesh.
    finite, tangent = _finite_difference(operator, model, rng, step=1e-4)
    np.testing.assert_allclose(finite, tangent, rtol=2e-3, atol=1e-6)
    assert _taylor_ratio(operator, model, rng, 1e-2) > 3.0


def test_tdip_forward_taylor_adjoint_and_wrong_convention(static_mesh, static_survey):
    operator = TDIPOperator(
        static_mesh,
        static_survey,
        [0.01, 0.03, 0.1],
        background_conductivity=0.02,
        tau=0.08,
        exponent_c=0.7,
    )
    model = np.full(operator.n_param, 0.05)
    prediction = operator.predict(model)
    assert prediction.shape == (static_survey.n_measurements * 3,)
    assert np.all(np.isfinite(prediction))
    assert np.linalg.norm(prediction) > 0
    rng = np.random.default_rng(23)
    assert _adjoint(operator, model, rng) < 1e-8
    finite, tangent = _finite_difference(operator, model, rng, step=1e-6)
    np.testing.assert_allclose(finite, tangent, rtol=3e-4, atol=1e-8)
    direction = rng.normal(size=operator.n_param)
    residual = (
        operator.predict(model + 1e-3 * direction)
        - operator.predict(model)
        - 1e-3 * operator.jvp(direction, model)
    )
    assert np.linalg.norm(residual) < 1e-12
    # Independent implementation of SimPEG's documented two-pulse convention.
    eta, tau, exponent, period = 0.05, 0.08, 0.7, operator.survey.T
    step_off = lambda t: eta * np.exp(-((t / tau) ** exponent))
    pulse_off = lambda t: step_off(t) - step_off(t + period / 4)
    independent_weights = np.array(
        [
            (2 * pulse_off(t) - pulse_off(t + period / 2)) / 2
            for t in operator.times
        ]
    )
    rows = prediction.reshape(len(operator.times), static_survey.n_measurements).T
    for row in rows:
        np.testing.assert_allclose(
            row / row[0], independent_weights / independent_weights[0], rtol=1e-10
        )
    with pytest.raises(ValueError, match="0<=eta<1"):
        operator.predict(np.ones(operator.n_param))
    with pytest.raises(ValueError, match="strictly increasing"):
        TDIPOperator(
            static_mesh,
            static_survey,
            [0.1, 0.01],
            background_conductivity=0.02,
            tau=0.1,
            exponent_c=0.5,
        )


def test_cole_cole_complex_reference_derivatives_and_limits(static_survey):
    frequencies = np.array([0.1, 1.0, 10.0, 1000.0])
    operator = ColeColeFrequencyOperator(static_survey, frequencies)
    # sigma_inf=.02, eta=.2, tau=.1, c=.6
    model = np.array([np.log(0.02), np.log(0.2 / 0.8), np.log(0.1), np.log(0.6 / 0.4)])
    sigma, eta, tau, exponent = operator.unpack(model)
    reference_sigma = sigma * (
        1 - eta / (1 + (1j * 2 * np.pi * frequencies * tau) ** exponent)
    )
    reference = (
        operator._geometric_voltage[:, None] / reference_sigma[None, :]
    ).ravel()
    np.testing.assert_allclose(operator.predict(model), reference, rtol=1e-13)
    assert np.iscomplexobj(reference)
    rng = np.random.default_rng(24)
    assert _adjoint(operator, model, rng) < 1e-10
    finite, tangent = _finite_difference(operator, model, rng, step=1e-5)
    np.testing.assert_allclose(finite, tangent, rtol=2e-4, atol=1e-8)
    assert _taylor_ratio(operator, model, rng, 1e-3) > 3.0
    high_frequency_resistivity = 1 / reference_sigma[-1]
    assert abs(high_frequency_resistivity - 1 / sigma) < abs(
        high_frequency_resistivity - 1 / (sigma * (1 - eta))
    )


def test_static_operator_bad_geometry_and_parameterization(static_survey):
    with pytest.raises(ValueError, match="positive"):
        ColeColeFrequencyOperator(static_survey, [0.0])
    with pytest.raises(ValueError, match="must not coincide"):
        DipoleDipoleSurvey(
            a=np.array([[0.0, 0, 0]]),
            b=np.array([[1.0, 0, 0]]),
            m=np.array([[0.0, 0, 0]]),
            n=np.array([[2.0, 0, 0]]),
            current=np.array([1.0]),
        ) and ColeColeFrequencyOperator(
            DipoleDipoleSurvey(
                a=np.array([[0.0, 0, 0]]),
                b=np.array([[1.0, 0, 0]]),
                m=np.array([[0.0, 0, 0]]),
                n=np.array([[2.0, 0, 0]]),
                current=np.array([1.0]),
            ),
            [1.0],
        )


def test_dc_three_level_mesh_convergence(static_survey):
    conductivity = 0.02
    reference = (
        ColeColeFrequencyOperator(static_survey, [1.0])._geometric_voltage / conductivity
    )
    errors = []
    for cell_width in (20.0, 10.0, 5.0):
        count_xy = int(80 / cell_width)
        count_z = int(60 / cell_width)
        mesh = TensorMesh(
            [[cell_width] * count_xy, [cell_width] * count_xy, [cell_width] * count_z],
            origin=[-40, -40, -60],
        )
        operator = DCOperator(mesh, static_survey)
        prediction = operator.predict(np.full(operator.n_param, np.log(conductivity)))
        errors.append(float(np.linalg.norm(prediction - reference)))
    assert errors[-1] < errors[0], errors


def test_tdip_three_level_mesh_convergence(static_survey):
    predictions = []
    for cell_width in (20.0, 10.0, 5.0):
        count_xy = int(80 / cell_width)
        count_z = int(60 / cell_width)
        mesh = TensorMesh(
            [[cell_width] * count_xy, [cell_width] * count_xy, [cell_width] * count_z],
            origin=[-40, -40, -60],
        )
        operator = TDIPOperator(
            mesh,
            static_survey,
            [0.02],
            background_conductivity=0.02,
            tau=0.1,
            exponent_c=0.6,
        )
        predictions.append(operator.predict(np.full(operator.n_param, 0.05)))
    assert np.linalg.norm(predictions[1] - predictions[2]) < np.linalg.norm(
        predictions[0] - predictions[2]
    )


def test_cole_cole_three_level_frequency_qoi_convergence(static_survey):
    model = np.array([np.log(0.02), -1.2, np.log(0.1), 0.3])
    qoi = []
    for count in (9, 33, 129):
        frequencies = np.geomspace(0.1, 1000, count)
        operator = ColeColeFrequencyOperator(static_survey, frequencies)
        response = operator.predict(model).reshape(static_survey.n_measurements, count)
        # Mean over log-frequency is a resolution-stable spectral QoI.
        qoi.append(
            np.trapezoid(response[0], x=np.log(frequencies))
            / (np.log(frequencies[-1]) - np.log(frequencies[0]))
        )
    assert abs(qoi[1] - qoi[2]) < abs(qoi[0] - qoi[2])


def _profile_survey():
    return DipoleDipoleSurvey(
        a=np.array([[-7.5, 0.0, 0.0]]),
        b=np.array([[-2.5, 0.0, 0.0]]),
        m=np.array([[2.5, 0.0, 0.0]]),
        n=np.array([[7.5, 0.0, 0.0]]),
        current=np.array([1.0]),
    )


def test_cole_cole_2d_complex_limit_derivatives_and_geometry():
    mesh = TensorMesh([[5.0] * 4, [5.0] * 3], origin=[-10.0, -15.0])
    survey = _profile_survey()
    frequencies = np.array([1.0, 100.0])
    operator = ColeCole2DOperator(mesh, survey, frequencies, nky=7)
    cell_model = np.r_[
        np.full(mesh.n_cells, np.log(0.02)),
        np.full(mesh.n_cells, np.log(0.2 / 0.8)),
        np.full(mesh.n_cells, np.log(0.1)),
        np.full(mesh.n_cells, np.log(0.6 / 0.4)),
    ]
    prediction = operator.predict(cell_model)
    assert prediction.shape == (2,)
    assert np.iscomplexobj(prediction)
    assert np.all(np.isfinite(prediction))
    assert np.linalg.norm(prediction.imag) > 0

    # A vanishing chargeability must recover the real 2.5-D DC response.
    no_ip = cell_model.copy()
    no_ip[mesh.n_cells : 2 * mesh.n_cells] = -40.0
    dc_prediction = operator.predict(no_ip)
    assert np.max(np.abs(dc_prediction.imag)) < 1e-12
    np.testing.assert_allclose(dc_prediction[0], dc_prediction[1], rtol=1e-10)

    rng = np.random.default_rng(25)
    assert _adjoint(operator, cell_model, rng) < 2e-6
    finite, tangent = _finite_difference(operator, cell_model, rng, step=2e-5)
    np.testing.assert_allclose(finite, tangent, rtol=3e-3, atol=1e-7)
    assert _taylor_ratio(operator, cell_model, rng, 2e-3) > 3.0

    nonplanar = DipoleDipoleSurvey(
        a=survey.a,
        b=survey.b,
        m=survey.m + np.array([[0.0, 0.1, 0.0]]),
        n=survey.n,
        current=survey.current,
    )
    with pytest.raises(ValueError, match="not coplanar"):
        ColeCole2DOperator(mesh, nonplanar, frequencies)


def test_cole_cole_2d_three_level_homogeneous_convergence():
    survey = _profile_survey()
    frequency = [10.0]
    homogeneous = np.array(
        [np.log(0.02), np.log(0.2 / 0.8), np.log(0.1), np.log(0.6 / 0.4)]
    )
    analytic = ColeColeFrequencyOperator(survey, frequency).predict(homogeneous)[0]
    errors = []
    for width in (10.0, 5.0, 2.5):
        mesh = TensorMesh(
            [[width] * int(80 / width), [width] * int(60 / width)],
            origin=[-40.0, -60.0],
        )
        operator = ColeCole2DOperator(mesh, survey, frequency, nky=11)
        model = np.concatenate(
            [np.full(mesh.n_cells, value) for value in homogeneous]
        )
        errors.append(abs(operator.predict(model)[0] - analytic))
    assert errors[-1] < errors[0], errors
