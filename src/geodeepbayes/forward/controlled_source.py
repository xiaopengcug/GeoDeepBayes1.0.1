"""Controlled-source and waveform FDEM over a shared finite-line Maxwell core."""
from __future__ import annotations

import numpy as np
from scipy.constants import mu_0
from simpeg import maps
from simpeg.electromagnetics import frequency_domain

from .base import validate_vector


def source_zone(distance, frequency, conductivity):
    """Classify source distance relative to one skin depth."""
    if distance <= 0 or frequency <= 0 or conductivity <= 0:
        raise ValueError("distance, frequency and conductivity must be positive")
    skin_depth = np.sqrt(2.0 / (2 * np.pi * frequency * mu_0 * conductivity))
    ratio = distance / skin_depth
    if ratio < 1:
        return "near"
    if ratio <= 5:
        return "transition"
    return "far"


class _FiniteLineFDEMCore:
    """Shared SimPEG Maxwell discretization; contracts remain in subclasses."""

    def __init__(
        self,
        mesh,
        source_vertices,
        receiver_locations,
        frequencies,
        receiver_components,
        *,
        current,
    ):
        self.mesh = mesh
        self.source_vertices = np.asarray(source_vertices, dtype=float)
        self.receiver_locations = np.asarray(receiver_locations, dtype=float)
        self.frequencies = np.asarray(frequencies, dtype=float)
        self.current = float(current)
        if (
            self.source_vertices.ndim != 2
            or self.source_vertices.shape[1] != 3
            or len(self.source_vertices) < 2
            or np.any(np.linalg.norm(np.diff(self.source_vertices, axis=0), axis=1) == 0)
        ):
            raise ValueError("source_vertices must define a non-degenerate finite polyline")
        if (
            self.receiver_locations.ndim != 2
            or self.receiver_locations.shape[1] != 3
            or len(self.receiver_locations) == 0
        ):
            raise ValueError("receiver_locations must have shape (n_receivers, 3)")
        if (
            self.frequencies.ndim != 1
            or len(self.frequencies) == 0
            or np.any(self.frequencies <= 0)
            or np.any(np.diff(self.frequencies) <= 0)
        ):
            raise ValueError("frequencies must be positive and strictly increasing")
        if self.current == 0:
            raise ValueError("source current must be non-zero")
        self.receiver_components = tuple(receiver_components)
        sources = []
        for frequency in self.frequencies:
            receivers = []
            for field, orientation in self.receiver_components:
                receiver_class = {
                    "electric": frequency_domain.receivers.PointElectricField,
                    "magnetic": frequency_domain.receivers.PointMagneticField,
                }.get(field)
                if receiver_class is None:
                    raise ValueError(f"unsupported field component: {field}")
                for part in ("real", "imag"):
                    receivers.append(
                        receiver_class(
                            self.receiver_locations,
                            orientation=orientation,
                            component=part,
                        )
                    )
            sources.append(
                frequency_domain.sources.LineCurrent(
                    receivers,
                    frequency=float(frequency),
                    location=self.source_vertices,
                    current=self.current,
                )
            )
        self.survey = frequency_domain.Survey(sources)
        self.n_param = mesh.n_cells
        self.n_complex_per_frequency = (
            len(self.receiver_components) * len(self.receiver_locations)
        )
        self.n_data = len(self.frequencies) * self.n_complex_per_frequency
        self._simulation = frequency_domain.Simulation3DElectricField(
            mesh,
            survey=self.survey,
            sigmaMap=maps.ExpMap(mesh),
        )

    def _to_complex(self, values):
        values = np.asarray(values, dtype=float)
        shaped = values.reshape(
            len(self.frequencies), len(self.receiver_components), 2, len(self.receiver_locations)
        )
        return (shaped[:, :, 0, :] + 1j * shaped[:, :, 1, :]).reshape(-1)

    def _to_interleaved(self, values):
        values = np.asarray(values).reshape(
            len(self.frequencies), len(self.receiver_components), len(self.receiver_locations)
        )
        return np.stack((values.real, values.imag), axis=2).ravel()

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        return self._to_complex(self._simulation.dpred(model))

    predict = forward

    def jvp(self, vector, model=None):
        if model is None:
            raise ValueError("FDEM derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        return self._to_complex(self._simulation.Jvec(model, vector))

    def jtp(self, vector, model=None):
        if model is None:
            raise ValueError("FDEM derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_data, "data vector")
        return np.asarray(
            self._simulation.Jtvec(model, self._to_interleaved(vector)), dtype=float
        )

    def component(self, values, component_index):
        values = np.asarray(values).reshape(
            len(self.frequencies),
            len(self.receiver_components),
            len(self.receiver_locations),
        )
        return values[:, component_index, :]


class CSAMTOperator(_FiniteLineFDEMCore):
    method = "csamt"
    dimensionality = "3d"
    data_mode = "complex"
    source_type = "grounded_finite_line_electric_dipole"
    waveform = "frequency_domain_sinusoid"
    components = ("Ex", "Hy")
    units = "E: V/m; H: A/m"
    parameterization = "cell_log_conductivity_S_m"
    complex_layout = "interleaved_real_imag"
    apparent_resistivity_contract = "abs(Ex/Hy)^2/(2*pi*f*mu0)"

    def __init__(
        self,
        mesh,
        source_vertices,
        receiver_locations,
        frequencies,
        *,
        current,
    ):
        super().__init__(
            mesh,
            source_vertices,
            receiver_locations,
            frequencies,
            (("electric", "x"), ("magnetic", "y")),
            current=current,
        )

    def apparent_resistivity(self, values):
        electric = self.component(values, 0)
        magnetic = self.component(values, 1)
        if np.any(magnetic == 0):
            raise ValueError("Hy is zero; apparent resistivity is undefined")
        return np.abs(electric / magnetic) ** 2 / (
            2 * np.pi * self.frequencies[:, None] * mu_0
        )


class WFEMOperator(_FiniteLineFDEMCore):
    method = "wfem"
    dimensionality = "3d"
    data_mode = "complex"
    source_type = "grounded_wire_finite_line"
    waveform = "frequency_domain_sinusoid"
    components = ("Ex", "Ey")
    units = "V/m"
    parameterization = "cell_log_conductivity_S_m"
    complex_layout = "interleaved_real_imag"

    def __init__(
        self,
        mesh,
        source_vertices,
        receiver_locations,
        frequencies,
        *,
        current,
        apparent_resistivity_definition,
        geometric_factor=None,
    ):
        if apparent_resistivity_definition not in {
            "electric_geometric_factor",
            "not_available",
        }:
            raise ValueError("WFEM apparent-resistivity definition must be explicit")
        if apparent_resistivity_definition == "electric_geometric_factor":
            factor = np.asarray(geometric_factor, dtype=float)
            if factor.shape not in {
                (len(np.asarray(receiver_locations)),),
                (len(np.asarray(frequencies)), len(np.asarray(receiver_locations))),
            } or np.any(~np.isfinite(factor)):
                raise ValueError("a finite receiver or frequency/receiver geometric factor is required")
            self.geometric_factor = factor
        else:
            self.geometric_factor = None
        self.apparent_resistivity_definition = apparent_resistivity_definition
        super().__init__(
            mesh,
            source_vertices,
            receiver_locations,
            frequencies,
            (("electric", "x"), ("electric", "y")),
            current=current,
        )

    def apparent_resistivity(self, values):
        if self.apparent_resistivity_definition == "not_available":
            raise ValueError("WFEM source package does not define apparent resistivity")
        electric_x = self.component(values, 0)
        return np.abs(electric_x / self.current) * self.geometric_factor
