import numpy as np
import pytest

from geodeepbayes.forward import ForwardOperator, MagneticVectorOperator


def test_existing_operators_satisfy_protocol(grav_op, mag_op):
    for operator in (grav_op, mag_op):
        assert isinstance(operator, ForwardOperator)
        np.testing.assert_allclose(
            operator.predict(np.zeros(operator.n_param)),
            operator.forward(np.zeros(operator.n_param)),
        )
        assert operator.method in {"gravity", "magnetic"}


def test_existing_operators_reject_wrong_shape(grav_op, mag_op):
    for operator in (grav_op, mag_op):
        with pytest.raises(ValueError, match="shape"):
            operator.predict(np.zeros(operator.n_param + 1))
        with pytest.raises(ValueError, match="shape"):
            operator.jtp(np.zeros(operator.n_data + 1))


def test_magnetic_vector_adjoint_and_linearity(small_mesh, rx_locs, ind_active, rng):
    operator = MagneticVectorOperator(small_mesh, rx_locs, ind_active=ind_active)
    model = rng.normal(scale=1e-3, size=operator.n_param)
    direction = rng.normal(size=operator.n_param)
    data_vector = rng.normal(size=operator.n_data)
    left = float(operator.jvp(direction, model) @ data_vector)
    right = float(direction @ operator.jtp(data_vector, model))
    assert abs(left - right) / (abs(left) + abs(right) + 1e-30) < 1e-10
    np.testing.assert_allclose(
        operator.predict(model + 1e-6 * direction) - operator.predict(model),
        1e-6 * operator.jvp(direction, model),
        rtol=1e-6,
        atol=1e-10,
    )


def test_magnetic_vector_component_blocks_change_prediction(
    small_mesh, rx_locs, ind_active
):
    operator = MagneticVectorOperator(small_mesh, rx_locs, ind_active=ind_active)
    x_model = np.zeros(operator.n_param)
    z_model = np.zeros(operator.n_param)
    x_model[: operator.n_active] = 1e-3
    z_model[2 * operator.n_active :] = 1e-3
    assert not np.allclose(operator.predict(x_model), operator.predict(z_model))
