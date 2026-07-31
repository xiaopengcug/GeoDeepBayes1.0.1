import numpy as np
from discretize import TensorMesh
from scipy.constants import mu_0

from geodeepbayes.forward import MT3DOperator


def _operator(count=6, conductivity=0.01):
    extent = 1200.0
    width = extent / count
    mesh = TensorMesh(
        [[width] * count, [width] * count, [width] * count],
        origin=[-width * count / 2, -width * count / 2, -width * count],
    )
    operator = MT3DOperator(
        mesh,
        [[0.0, 0.0, 0.0]],
        [1.0],
        primary_conductivity=conductivity,
        include_tipper=True,
    )
    return operator, np.full(mesh.n_cells, np.log(conductivity))


def test_mt3d_homogeneous_halfspace_independent_analytic_reference():
    conductivity = 0.01
    operator, model = _operator(6, conductivity)
    prediction = operator.predict(model)
    by_component = dict(zip(operator.components, prediction))
    reference = np.sqrt(1j * 2 * np.pi * mu_0 / conductivity)
    np.testing.assert_allclose(by_component["Zxy"], -reference, rtol=5e-2)
    np.testing.assert_allclose(by_component["Zyx"], reference, rtol=5e-2)
    scale = abs(reference)
    assert abs(by_component["Zxx"]) < 1e-8 * scale
    assert abs(by_component["Zyy"]) < 1e-8 * scale
    assert abs(by_component["Tx"]) < 1e-8
    assert abs(by_component["Ty"]) < 1e-8


def test_mt3d_derivative_adjoint_and_finite_difference():
    operator, model = _operator(4, 0.02)
    rng = np.random.default_rng(52)
    direction = rng.normal(size=operator.n_param)
    data_direction = rng.normal(size=operator.n_data) + 1j * rng.normal(
        size=operator.n_data
    )
    left = float(np.real(np.vdot(data_direction, operator.jvp(direction, model))))
    right = float(direction @ operator.jtp(data_direction, model))
    assert abs(left - right) / (abs(left) + abs(right) + 1e-30) < 1e-8
    step = 1e-4
    finite = (
        operator.predict(model + step * direction)
        - operator.predict(model - step * direction)
    ) / (2 * step)
    np.testing.assert_allclose(
        finite, operator.jvp(direction, model), rtol=5e-3, atol=1e-9
    )


def test_mt3d_three_level_boundary_convergence():
    conductivity = 0.01
    reference = np.sqrt(1j * 2 * np.pi * mu_0 / conductivity)
    errors = []
    for count in (4, 6, 8):
        operator, model = _operator(count, conductivity)
        zxy = operator.predict(model)[operator.components.index("Zxy")]
        errors.append(abs(zxy + reference))
    assert errors[-1] < errors[0], errors
