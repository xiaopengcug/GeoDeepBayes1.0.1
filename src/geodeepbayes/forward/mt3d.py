"""Three-dimensional natural-source MT impedance and tipper operator."""
from __future__ import annotations

import numpy as np
from simpeg import maps
from simpeg.electromagnetics import natural_source

from .base import validate_vector


class MT3DOperator:
    """SimPEG primary-secondary 3-D MT path with explicit complex layout."""

    method = "mt_amt"
    dimensionality = "3d"
    data_mode = "complex"
    source_type = "natural_source_planewave_xy"
    waveform = "frequency_domain"
    units = "V/A for Z; dimensionless for tipper"
    parameterization = "cell_log_conductivity_S_m"
    complex_layout = "frequency_then_component; complex values"

    def __init__(
        self,
        mesh,
        receiver_locations,
        frequencies,
        *,
        primary_conductivity,
        include_tipper=True,
    ):
        self.mesh = mesh
        self.receiver_locations = np.asarray(receiver_locations, dtype=float)
        self.frequencies = np.asarray(frequencies, dtype=float)
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
        primary = np.asarray(primary_conductivity, dtype=float)
        if primary.shape == ():
            primary = np.full(mesh.n_cells, float(primary))
        if primary.shape != (mesh.n_cells,) or np.any(primary <= 0):
            raise ValueError("primary_conductivity must be positive per cell")
        self.primary_conductivity = primary
        self.include_tipper = bool(include_tipper)
        receiver_specs = [
            ("impedance", "xx"),
            ("impedance", "xy"),
            ("impedance", "yx"),
            ("impedance", "yy"),
        ]
        if self.include_tipper:
            receiver_specs.extend([("tipper", "zx"), ("tipper", "zy")])
        self.components = tuple(
            {"xx": "Zxx", "xy": "Zxy", "yx": "Zyx", "yy": "Zyy", "zx": "Tx", "zy": "Ty"}[
                orientation
            ]
            for _, orientation in receiver_specs
        )
        receivers = []
        for kind, orientation in receiver_specs:
            receiver_class = (
                natural_source.receivers.Impedance
                if kind == "impedance"
                else natural_source.receivers.Tipper
            )
            for part in ("real", "imag"):
                receivers.append(
                    receiver_class(
                        self.receiver_locations,
                        orientation=orientation,
                        component=part,
                    )
                )
        sources = [
            natural_source.sources.PlanewaveXYPrimary(
                receivers,
                float(frequency),
                sigma_primary=primary,
            )
            for frequency in self.frequencies
        ]
        self.survey = natural_source.Survey(sources)
        self.n_param = mesh.n_cells
        self.n_complex_per_frequency = len(self.components) * len(
            self.receiver_locations
        )
        self.n_data = len(self.frequencies) * self.n_complex_per_frequency
        self._simulation = natural_source.Simulation3DPrimarySecondary(
            mesh,
            survey=self.survey,
            sigmaPrimary=primary,
            sigmaMap=maps.ExpMap(mesh),
        )

    @property
    def simulation(self):
        return self._simulation

    def _to_complex(self, values):
        values = np.asarray(values, dtype=float).reshape(
            len(self.frequencies),
            len(self.components),
            2,
            len(self.receiver_locations),
        )
        return (values[:, :, 0, :] + 1j * values[:, :, 1, :]).reshape(-1)

    def _to_interleaved(self, values):
        values = np.asarray(values).reshape(
            len(self.frequencies),
            len(self.components),
            len(self.receiver_locations),
        )
        return np.stack((values.real, values.imag), axis=2).ravel()

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        return self._to_complex(self._simulation.dpred(model))

    predict = forward

    def jvp(self, vector, model=None):
        if model is None:
            raise ValueError("MT derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        return self._to_complex(self._simulation.Jvec(model, vector))

    def jtp(self, vector, model=None):
        if model is None:
            raise ValueError("MT derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_data, "data vector")
        return np.asarray(
            self._simulation.Jtvec(model, self._to_interleaved(vector)), dtype=float
        )
