"""Verified one-dimensional TEM and natural-source MT operators."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from simpeg import maps
from simpeg.electromagnetics import natural_source, time_domain

from .base import validate_vector


class DimensionalityUpgradeRequired(RuntimeError):
    def __init__(self, required: str):
        self.required = required
        super().__init__(f"1-D path rejected; dimensionality diagnostic requires {required}")


def mt_dimensionality(
    phase_tensor_skew_deg,
    ellipticity,
    tipper_amplitude,
    *,
    skew_1d_max=3.0,
    ellipticity_1d_max=0.1,
    tipper_1d_max=0.1,
) -> str:
    """Fail-closed MT dimensionality rule using preregistered diagnostics."""
    arrays = [
        np.asarray(phase_tensor_skew_deg, dtype=float),
        np.asarray(ellipticity, dtype=float),
        np.asarray(tipper_amplitude, dtype=float),
    ]
    if any(array.size == 0 or not np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("complete finite skew, ellipticity and tipper diagnostics are required")
    skew = float(np.max(np.abs(arrays[0])))
    ellipse = float(np.max(np.abs(arrays[1])))
    tipper = float(np.max(np.abs(arrays[2])))
    if skew <= skew_1d_max and ellipse <= ellipticity_1d_max and tipper <= tipper_1d_max:
        return "1d"
    if skew <= 7.0 and tipper <= 0.3:
        return "2d"
    return "3d"


def tem_dimensionality(early_late_lateral_mismatch, *, one_d_max=0.1) -> str:
    mismatch = np.asarray(early_late_lateral_mismatch, dtype=float)
    if mismatch.size == 0 or not np.all(np.isfinite(mismatch)):
        raise ValueError("finite early/late lateral mismatch diagnostics are required")
    return "1d" if float(np.max(np.abs(mismatch))) <= one_d_max else "3d"


@dataclass(frozen=True)
class TDEM3DPathStatus:
    dependency_available: bool
    verified: bool
    reason: str


def tdem3d_path_status() -> TDEM3DPathStatus:
    simulations = (
        time_domain.Simulation3DElectricField,
        time_domain.Simulation3DMagneticField,
    )
    return TDEM3DPathStatus(
        dependency_available=all(simulation is not None for simulation in simulations),
        verified=False,
        reason="3-D dependency is installed but no frozen mesh/time-step resource budget and validation run exists",
    )


class TEM1DLayeredOperator:
    method = "tem"
    dimensionality = "1d_layered"
    data_mode = "time_decay"
    source_type = "circular_loop"
    waveform = "step_off"
    components = ("dbdt_z",)
    units = "T/s"
    parameterization = "layer_log_conductivity_S_m"

    def __init__(
        self,
        thicknesses,
        times,
        *,
        loop_radius,
        current=1.0,
        n_turns=1,
        receiver_location=(0.0, 0.0, 0.0),
        source_location=(0.0, 0.0, 0.0),
        time_filter="key_81_2009",
        dimensionality_diagnostic=None,
    ):
        if dimensionality_diagnostic is None:
            raise ValueError("TEM dimensionality diagnostic is required")
        required = tem_dimensionality(dimensionality_diagnostic)
        if required != "1d":
            raise DimensionalityUpgradeRequired(required)
        self.thicknesses = np.asarray(thicknesses, dtype=float)
        self.times = np.asarray(times, dtype=float)
        if (
            self.thicknesses.ndim != 1
            or np.any(self.thicknesses <= 0)
            or self.times.ndim != 1
            or len(self.times) == 0
            or np.any(self.times <= 0)
            or np.any(np.diff(self.times) <= 0)
        ):
            raise ValueError("positive thicknesses and strictly increasing positive times required")
        if loop_radius <= 0 or current == 0 or n_turns < 1:
            raise ValueError("invalid loop radius, current or turn count")
        receiver = time_domain.receivers.PointMagneticFluxTimeDerivative(
            np.asarray(receiver_location, dtype=float)[None, :],
            times=self.times,
            orientation="z",
        )
        source = time_domain.sources.CircularLoop(
            [receiver],
            location=np.asarray(source_location, dtype=float),
            radius=float(loop_radius),
            current=float(current),
            n_turns=int(n_turns),
            waveform=time_domain.sources.StepOffWaveform(),
        )
        self.survey = time_domain.Survey([source])
        self.n_param = len(self.thicknesses) + 1
        self.n_data = len(self.times)
        self._simulation = time_domain.Simulation1DLayered(
            survey=self.survey,
            thicknesses=self.thicknesses,
            sigmaMap=maps.ExpMap(nP=self.n_param),
            time_filter=time_filter,
        )
        self.time_filter = time_filter

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        return np.asarray(self._simulation.dpred(model), dtype=float)

    predict = forward

    def jvp(self, vector, model=None):
        if model is None:
            raise ValueError("TEM derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        return np.asarray(self._simulation.Jvec(model, vector), dtype=float)

    def jtp(self, vector, model=None):
        if model is None:
            raise ValueError("TEM derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_data, "data vector").astype(float)
        return np.asarray(self._simulation.Jtvec(model, vector), dtype=float)


class MT1DRecursiveOperator:
    method = "mt_amt"
    dimensionality = "1d_layered"
    data_mode = "complex"
    source_type = "natural_source_planewave"
    waveform = "frequency_domain"
    components = ("Zxy",)
    units = "V/A"
    parameterization = "layer_log_conductivity_S_m"
    complex_layout = "interleaved_real_imag"

    def __init__(
        self,
        thicknesses,
        frequencies,
        *,
        phase_tensor_skew_deg,
        ellipticity,
        tipper_amplitude,
        location=(0.0, 0.0, 0.0),
    ):
        required = mt_dimensionality(
            phase_tensor_skew_deg, ellipticity, tipper_amplitude
        )
        if required != "1d":
            raise DimensionalityUpgradeRequired(required)
        self.thicknesses = np.asarray(thicknesses, dtype=float)
        self.frequencies = np.asarray(frequencies, dtype=float)
        if (
            self.thicknesses.ndim != 1
            or np.any(self.thicknesses <= 0)
            or self.frequencies.ndim != 1
            or len(self.frequencies) == 0
            or np.any(self.frequencies <= 0)
            or np.any(np.diff(self.frequencies) <= 0)
        ):
            raise ValueError("positive thicknesses and strictly increasing positive frequencies required")
        sources = []
        receiver_location = np.asarray(location, dtype=float)[None, :]
        for frequency in self.frequencies:
            real = natural_source.receivers.Impedance(
                receiver_location, orientation="xy", component="real"
            )
            imaginary = natural_source.receivers.Impedance(
                receiver_location, orientation="xy", component="imag"
            )
            sources.append(
                natural_source.sources.Planewave([real, imaginary], frequency=float(frequency))
            )
        self.survey = natural_source.Survey(sources)
        self.n_param = len(self.thicknesses) + 1
        self.n_data = len(self.frequencies)
        self._simulation = natural_source.Simulation1DRecursive(
            survey=self.survey,
            thicknesses=self.thicknesses,
            sigmaMap=maps.ExpMap(nP=self.n_param),
        )

    @staticmethod
    def _to_complex(interleaved):
        values = np.asarray(interleaved, dtype=float).reshape(-1, 2)
        return values[:, 0] + 1j * values[:, 1]

    @staticmethod
    def _to_interleaved(values):
        values = np.asarray(values)
        return np.column_stack((values.real, values.imag)).ravel()

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
