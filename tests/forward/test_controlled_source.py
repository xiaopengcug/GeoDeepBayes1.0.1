import numpy as np
import pytest
from discretize import TensorMesh
from geoana.em.fdem import ElectricDipoleWholeSpace

from geodeepbayes.forward import CSAMTOperator, WFEMOperator, source_zone


def _mesh(cell_width=20.0, count=6):
    extent = cell_width * count
    return TensorMesh(
        [[cell_width] * count] * 3,
        origin=[-extent / 2, -extent / 2, -extent / 2],
    )


def _geometry():
    return (
        np.array([[-20.0, 0.0, -10.0], [20.0, 0.0, -10.0]]),
        np.array([[40.0, 0.0, -10.0]]),
    )


def _adjoint(operator, model, rng):
    direction = rng.normal(size=operator.n_param)
    data = rng.normal(size=operator.n_data) + 1j * rng.normal(size=operator.n_data)
    left = float(np.real(np.vdot(data, operator.jvp(direction, model))))
    right = float(direction @ operator.jtp(data, model))
    return abs(left - right) / (abs(left) + abs(right) + 1e-30)


def test_csamt_real_simpeg_path_and_geoana_reference():
    mesh = _mesh()
    vertices, receivers = _geometry()
    frequency = 10.0
    conductivity = 0.01
    operator = CSAMTOperator(
        mesh, vertices, receivers, [frequency], current=1.0
    )
    model = np.full(mesh.n_cells, np.log(conductivity))
    fields = operator.predict(model)
    assert fields.shape == (2,)
    assert np.all(np.isfinite(fields))
    apparent = operator.apparent_resistivity(fields)
    assert apparent.shape == (1, 1)
    assert apparent[0, 0] > 0

    # Independent codebase reference: Geoana electric dipole whole-space.
    reference = ElectricDipoleWholeSpace(
        frequency,
        sigma=conductivity,
        location=np.array([0.0, 0.0, -10.0]),
        orientation="X",
        current=1.0,
        length=40.0,
        quasistatic=True,
    )
    electric = reference.electric_field(receivers)[0, 0]
    # Finite-volume boundary and finite-wire discretization differ, but phase
    # quadrant and engineering order must agree with the independent code.
    assert np.sign(fields[0].real) == np.sign(electric.real)
    assert 1e-2 < abs(fields[0] / electric) < 1e2
    # The whole-space point-dipole Hy vanishes on this symmetry axis, whereas
    # the finite-volume bounded wire problem does not; only Ex is compared.
    assert abs(fields[1]) > 0


def test_csamt_derivatives_taylor_and_adjoint():
    mesh = _mesh()
    vertices, receivers = _geometry()
    operator = CSAMTOperator(mesh, vertices, receivers, [5.0], current=1.0)
    model = np.full(mesh.n_cells, np.log(0.02))
    rng = np.random.default_rng(40)
    assert _adjoint(operator, model, rng) < 1e-8
    direction = rng.normal(size=operator.n_param)
    step = 1e-4
    finite = (
        operator.predict(model + step * direction)
        - operator.predict(model - step * direction)
    ) / (2 * step)
    tangent = operator.jvp(direction, model)
    np.testing.assert_allclose(finite, tangent, rtol=3e-3, atol=1e-9)
    errors = []
    for scale in (1e-2, 5e-3):
        errors.append(
            np.linalg.norm(
                operator.predict(model + scale * direction)
                - operator.predict(model)
                - scale * tangent
            )
        )
    assert errors[0] / errors[1] > 3


def test_wfem_independent_contract_and_apparent_resistivity():
    mesh = _mesh()
    vertices, receivers = _geometry()
    operator = WFEMOperator(
        mesh,
        vertices,
        receivers,
        [5.0],
        current=2.0,
        apparent_resistivity_definition="electric_geometric_factor",
        geometric_factor=np.array([100.0]),
    )
    fields = operator.predict(np.full(mesh.n_cells, np.log(0.02)))
    assert operator.components == ("Ex", "Ey")
    assert operator.source_type != CSAMTOperator.source_type
    np.testing.assert_allclose(
        operator.apparent_resistivity(fields),
        np.abs(operator.component(fields, 0) / 2.0) * 100.0,
    )
    # Independent Geoana whole-space electric-dipole calculation.  The
    # bounded finite-volume wire has different discretization and boundaries,
    # so require phase quadrant and engineering order rather than equality.
    reference = ElectricDipoleWholeSpace(
        5.0,
        sigma=0.02,
        location=np.array([0.0, 0.0, -10.0]),
        orientation="X",
        current=2.0,
        length=40.0,
        quasistatic=True,
    ).electric_field(receivers)[0, 0]
    assert np.sign(fields[0].real) == np.sign(reference.real)
    assert 1e-2 < abs(fields[0] / reference) < 1e2
    model = np.full(mesh.n_cells, np.log(0.02))
    rng = np.random.default_rng(41)
    assert _adjoint(operator, model, rng) < 1e-8
    direction = rng.normal(size=operator.n_param)
    step = 1e-4
    finite = (
        operator.predict(model + step * direction)
        - operator.predict(model - step * direction)
    ) / (2 * step)
    tangent = operator.jvp(direction, model)
    np.testing.assert_allclose(finite, tangent, rtol=3e-3, atol=1e-9)
    coarse = np.linalg.norm(
        operator.predict(model + 1e-2 * direction)
        - operator.predict(model)
        - 1e-2 * tangent
    )
    fine = np.linalg.norm(
        operator.predict(model + 5e-3 * direction)
        - operator.predict(model)
        - 5e-3 * tangent
    )
    assert coarse / fine > 3


def test_wfem_three_level_discretization_convergence():
    vertices, receivers = _geometry()
    predictions = []
    for width, count in ((30.0, 4), (20.0, 6), (15.0, 8)):
        mesh = _mesh(width, count)
        operator = WFEMOperator(
            mesh,
            vertices,
            receivers,
            [5.0],
            current=1.0,
            apparent_resistivity_definition="not_available",
        )
        predictions.append(operator.predict(np.full(mesh.n_cells, np.log(0.02))))
    assert np.linalg.norm(predictions[1] - predictions[2]) < np.linalg.norm(
        predictions[0] - predictions[2]
    )


def test_zones_and_contract_misspecification_fail():
    conductivity = 0.01
    frequency = 10.0
    skin = np.sqrt(2 / (2 * np.pi * frequency * 4e-7 * np.pi * conductivity))
    assert source_zone(0.5 * skin, frequency, conductivity) == "near"
    assert source_zone(2 * skin, frequency, conductivity) == "transition"
    assert source_zone(6 * skin, frequency, conductivity) == "far"
    mesh = _mesh()
    _, receivers = _geometry()
    with pytest.raises(ValueError, match="non-degenerate"):
        CSAMTOperator(
            mesh,
            [[0, 0, -10], [0, 0, -10]],
            receivers,
            [1.0],
            current=1.0,
        )
    with pytest.raises(ValueError, match="must be explicit"):
        WFEMOperator(
            mesh,
            [[-20, 0, -10], [20, 0, -10]],
            receivers,
            [1.0],
            current=1.0,
            apparent_resistivity_definition="assumed_rho_mn",
        )
    unavailable = WFEMOperator(
        mesh,
        [[-20, 0, -10], [20, 0, -10]],
        receivers,
        [1.0],
        current=1.0,
        apparent_resistivity_definition="not_available",
    )
    with pytest.raises(ValueError, match="does not define"):
        unavailable.apparent_resistivity(
            unavailable.predict(np.full(mesh.n_cells, np.log(0.02)))
        )
