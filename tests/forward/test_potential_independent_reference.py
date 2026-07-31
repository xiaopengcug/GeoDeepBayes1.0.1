from __future__ import annotations

import numpy as np
from discretize import TensorMesh
from geoana.em.static import MagneticPrism
from geoana.gravity import Prism
from scipy.constants import mu_0

from geodeepbayes.forward import GravityOperator, MagneticOperator


def _single_cell():
    mesh = TensorMesh([[100.0], [100.0], [100.0]], origin=[-50.0, -50.0, -100.0])
    receivers = np.array([[200.0, 100.0, 50.0], [-200.0, 50.0, 20.0]])
    return mesh, receivers


def test_gravity_matches_independent_geoana_prism() -> None:
    mesh, receivers = _single_cell()
    prediction = GravityOperator(mesh, receivers).predict(np.array([1.0]))
    # SimPEG model unit is g/cm^3 and output is mGal. Geoana uses kg/m^3
    # and m/s^2, so 1 g/cm^3 -> 1000 kg/m^3 and 1 m/s^2 -> 1e5 mGal.
    reference = (
        Prism([-50.0, -50.0, -100.0], [50.0, 50.0, 0.0], rho=1000.0)
        .gravitational_field(receivers)[:, 2]
        * 1e5
    )
    np.testing.assert_allclose(prediction, reference, rtol=2e-7, atol=1e-10)


def test_magnetic_tmi_matches_independent_geoana_prism() -> None:
    mesh, receivers = _single_cell()
    inducing_field = (50_000.0, 60.0, 20.0)
    susceptibility = 0.01
    prediction = MagneticOperator(
        mesh, receivers, inducing_field=inducing_field
    ).predict(np.array([susceptibility]))

    amplitude_nt, inclination_deg, declination_deg = inducing_field
    inclination = np.deg2rad(inclination_deg)
    declination = np.deg2rad(declination_deg)
    # SimPEG's potential-field coordinates are x=easting, y=northing,
    # z=positive-up; positive inclination points downward.
    field_unit = np.array(
        [
            np.cos(inclination) * np.sin(declination),
            np.cos(inclination) * np.cos(declination),
            -np.sin(inclination),
        ]
    )
    magnetization = susceptibility * (amplitude_nt * 1e-9 / mu_0) * field_unit
    magnetic_prism = MagneticPrism(
        [-50.0, -50.0, -100.0],
        [50.0, 50.0, 0.0],
        magnetization=magnetization,
    )
    reference = magnetic_prism.magnetic_flux_density(receivers) @ field_unit * 1e9
    np.testing.assert_allclose(prediction, reference, rtol=2e-7, atol=1e-9)
