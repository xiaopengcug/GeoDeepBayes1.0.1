"""DC, time-domain IP and homogeneous Cole-Cole frequency-domain operators."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.special import expit
from simpeg import maps
from simpeg.electromagnetics.static import (
    resistivity,
    spectral_induced_polarization,
)

from .base import validate_vector


@dataclass(frozen=True)
class DipoleDipoleSurvey:
    """Explicit ABMN geometry; rows correspond to independent measurements."""

    a: np.ndarray
    b: np.ndarray
    m: np.ndarray
    n: np.ndarray
    current: np.ndarray

    def __post_init__(self):
        arrays = {}
        for name in ("a", "b", "m", "n"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.ndim != 2 or value.shape[1] != 3:
                raise ValueError(f"{name} must have shape (n_measurements, 3)")
            arrays[name] = value
        count = len(arrays["a"])
        if count == 0 or any(len(value) != count for value in arrays.values()):
            raise ValueError("ABMN arrays must have the same non-zero length")
        current = np.asarray(self.current, dtype=float)
        if current.shape == ():
            current = np.full(count, float(current))
        if current.shape != (count,) or not np.all(np.isfinite(current)) or np.any(current == 0):
            raise ValueError("current must contain one finite non-zero value per measurement")
        for left, right in (("a", "b"), ("m", "n"), ("a", "m"), ("a", "n"), ("b", "m"), ("b", "n")):
            if np.any(np.linalg.norm(arrays[left] - arrays[right], axis=1) == 0):
                raise ValueError(f"electrodes {left.upper()} and {right.upper()} must not coincide")
        for name, value in arrays.items():
            value = value.copy()
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        current = current.copy()
        current.setflags(write=False)
        object.__setattr__(self, "current", current)

    @property
    def n_measurements(self) -> int:
        return len(self.current)


def _build_survey(spec: DipoleDipoleSurvey, module, *, times=None):
    sources = []
    for index in range(spec.n_measurements):
        receiver_kwargs = {
            "locations_m": spec.m[index : index + 1],
            "locations_n": spec.n[index : index + 1],
            "data_type": "volt",
        }
        if times is not None:
            receiver_kwargs["times"] = times
        receiver = module.receivers.Dipole(**receiver_kwargs)
        source = module.sources.Dipole(
            [receiver],
            location_a=spec.a[index],
            location_b=spec.b[index],
            current=float(spec.current[index]),
        )
        sources.append(source)
    return module.Survey(sources)


class DCOperator:
    method = "dc"
    dimensionality = "3d"
    data_mode = "real"
    source_type = "galvanic_dipole"
    waveform = "direct_current"
    components = ("voltage",)
    units = "V"
    parameterization = "cell_log_conductivity_S_m"

    def __init__(self, mesh, survey: DipoleDipoleSurvey):
        self.mesh = mesh
        self.survey_spec = survey
        self.survey = _build_survey(survey, resistivity)
        self.n_param = mesh.n_cells
        self.n_data = self.survey.nD
        self._simulation = resistivity.Simulation3DNodal(
            mesh, survey=self.survey, sigmaMap=maps.ExpMap(mesh)
        )

    @property
    def simulation(self):
        return self._simulation

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        return np.asarray(self._simulation.dpred(model), dtype=float)

    predict = forward

    def jvp(self, vector, model=None):
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        model = np.zeros(self.n_param) if model is None else validate_vector(model, self.n_param, "model")
        return np.asarray(self._simulation.Jvec(model, vector), dtype=float)

    def jtp(self, vector, model=None):
        vector = validate_vector(vector, self.n_data, "data vector").astype(float)
        model = np.zeros(self.n_param) if model is None else validate_vector(model, self.n_param, "model")
        return np.asarray(self._simulation.Jtvec(model, vector), dtype=float)


class TDIPOperator:
    """SimPEG spectral-IP time-window path with fixed Cole-Cole tau and c."""

    method = "tdip"
    dimensionality = "3d"
    data_mode = "time_decay"
    source_type = "galvanic_dipole"
    waveform = "two_pulse"
    components = ("secondary_voltage",)
    units = "V"
    parameterization = "cell_chargeability_eta"
    data_layout = "time_major_then_measurement"
    derivative_implementation = (
        "simpeg_Jvec_with_explicit_transpose_due_to_simpeg_0_25_2_multi_time_Jtvec_defect"
    )

    def __init__(
        self,
        mesh,
        survey: DipoleDipoleSurvey,
        times,
        *,
        background_conductivity,
        tau: float,
        exponent_c: float,
    ):
        self.mesh = mesh
        self.survey_spec = survey
        self.times = np.asarray(times, dtype=float)
        if self.times.ndim != 1 or len(self.times) == 0 or np.any(self.times <= 0):
            raise ValueError("times must be a non-empty positive vector")
        if np.any(np.diff(self.times) <= 0):
            raise ValueError("times must be strictly increasing")
        if tau <= 0 or not 0 < exponent_c <= 1:
            raise ValueError("Cole-Cole convention requires tau>0 and 0<c<=1")
        self.tau = float(tau)
        self.exponent_c = float(exponent_c)
        sigma = np.asarray(background_conductivity, dtype=float)
        if sigma.shape == ():
            sigma = np.full(mesh.n_cells, float(sigma))
        if sigma.shape != (mesh.n_cells,) or np.any(sigma <= 0):
            raise ValueError("background_conductivity must be positive per cell")
        self.survey = _build_survey(survey, spectral_induced_polarization, times=self.times)
        self.n_param = mesh.n_cells
        self.n_data = self.survey.nD
        self._simulation = spectral_induced_polarization.Simulation3DNodal(
            mesh,
            survey=self.survey,
            sigma=sigma,
            etaMap=maps.IdentityMap(mesh),
            tau=self.tau,
            c=self.exponent_c,
        )
        self._jacobian_model = None
        self._jacobian_cache = None

    @property
    def simulation(self):
        return self._simulation

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        if np.any((model < 0) | (model >= 1)):
            raise ValueError("chargeability eta must satisfy 0<=eta<1")
        return np.asarray(self._simulation.dpred(model), dtype=float)

    predict = forward

    def _jacobian(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        if self._jacobian_model is not None and np.array_equal(model, self._jacobian_model):
            return self._jacobian_cache
        columns = []
        for index in range(self.n_param):
            basis = np.zeros(self.n_param)
            basis[index] = 1.0
            columns.append(np.asarray(self._simulation.Jvec(model, basis), dtype=float))
        self._jacobian_model = model.copy()
        self._jacobian_cache = np.column_stack(columns)
        return self._jacobian_cache

    def jvp(self, vector, model=None):
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        if model is None:
            raise ValueError("TDIP derivatives require the evaluation model")
        # Jvec is reliable in SimPEG 0.25.2; Jtvec is not adjoint-consistent for
        # multiple time windows, so both operations share this explicit matrix.
        return self._jacobian(model) @ vector

    def jtp(self, vector, model=None):
        vector = validate_vector(vector, self.n_data, "data vector").astype(float)
        if model is None:
            raise ValueError("TDIP derivatives require the evaluation model")
        return self._jacobian(model).T @ vector


class ColeColeFrequencyOperator:
    """Exact homogeneous-halfspace SIP/FDIP response under one convention.

    ``sigma(omega) = sigma_inf * [1 - eta/(1 + (i*omega*tau)^c)]``.
    This restricted path is intentionally labelled 1-D homogeneous and cannot
    be used when dimensionality diagnostics require lateral structure.
    """

    method = "sip_fdip"
    dimensionality = "1d_homogeneous_halfspace"
    data_mode = "complex"
    source_type = "galvanic_dipole"
    waveform = "frequency_domain_sinusoid"
    components = ("complex_voltage",)
    units = "V"
    parameterization = "log_sigma_inf,logit_eta,log_tau,logit_c"
    complex_layout = "real_then_imag"

    def __init__(self, survey: DipoleDipoleSurvey, frequencies):
        self.survey_spec = survey
        self.frequencies = np.asarray(frequencies, dtype=float)
        if (
            self.frequencies.ndim != 1
            or len(self.frequencies) == 0
            or np.any(self.frequencies <= 0)
            or np.any(np.diff(self.frequencies) <= 0)
        ):
            raise ValueError("frequencies must be positive and strictly increasing")
        self.n_param = 4
        self.n_data = survey.n_measurements * len(self.frequencies)
        self._geometric_voltage = self._geometry()

    def _geometry(self):
        def inverse_distance(left, right):
            distance = np.linalg.norm(left - right, axis=1)
            if np.any(distance == 0):
                raise ValueError("source and receiver electrodes must not coincide")
            return 1.0 / distance

        return self.survey_spec.current / (2 * np.pi) * (
            inverse_distance(self.survey_spec.a, self.survey_spec.m)
            - inverse_distance(self.survey_spec.a, self.survey_spec.n)
            - inverse_distance(self.survey_spec.b, self.survey_spec.m)
            + inverse_distance(self.survey_spec.b, self.survey_spec.n)
        )

    @staticmethod
    def unpack(model):
        model = validate_vector(model, 4, "model").astype(float)
        sigma_inf = np.exp(model[0])
        eta = expit(model[1])
        tau = np.exp(model[2])
        exponent_c = expit(model[3])
        return sigma_inf, eta, tau, exponent_c

    def forward(self, model):
        sigma_inf, eta, tau, exponent_c = self.unpack(model)
        omega = 2 * np.pi * self.frequencies
        conductivity = sigma_inf * (
            1 - eta / (1 + (1j * omega * tau) ** exponent_c)
        )
        return (self._geometric_voltage[:, None] / conductivity[None, :]).ravel()

    predict = forward

    def _jacobian(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        steps = np.cbrt(np.finfo(float).eps) * np.maximum(1.0, np.abs(model))
        columns = []
        for index, step in enumerate(steps):
            delta = np.zeros(self.n_param)
            delta[index] = step
            columns.append((self.forward(model + delta) - self.forward(model - delta)) / (2 * step))
        return np.column_stack(columns)

    def jvp(self, vector, model=None):
        if model is None:
            raise ValueError("Cole-Cole derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        return self._jacobian(model) @ vector

    def jtp(self, vector, model=None):
        if model is None:
            raise ValueError("Cole-Cole derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_data, "data vector")
        # Real-parameter adjoint under Re(<Jv,w>).
        return np.real(self._jacobian(model).conj().T @ vector)


class ColeCole2DOperator:
    """2.5-D nodal finite-volume SIP/FDIP with cellwise Cole-Cole properties.

    The mesh is the profile ``x-z`` plane. Sources and receivers are supplied
    through the common 3-D ABMN contract and projected to ``x-z`` after a
    coplanarity check. The out-of-plane Fourier integral, source discretization,
    receiver interpolation, and Robin boundary operators are those of SimPEG's
    2-D nodal DC implementation. Complex systems are solved here explicitly
    because SimPEG 0.25.2's DC field container casts complex potentials to real.

    Model blocks are ``[log_sigma_inf, logit_eta, log_tau, logit_c]``, each of
    length ``mesh.n_cells``.
    """

    method = "sip_fdip"
    dimensionality = "2d_profile_2p5d_physics"
    data_mode = "complex"
    source_type = "galvanic_dipole"
    waveform = "frequency_domain_sinusoid"
    components = ("complex_voltage",)
    units = "V"
    parameterization = (
        "cell_log_sigma_inf,cell_logit_eta,cell_log_tau,cell_logit_c"
    )
    data_layout = "frequency_major_then_measurement"
    derivative_implementation = "central_directional_difference_and_explicit_jacobian"

    def __init__(
        self,
        mesh,
        survey: DipoleDipoleSurvey,
        frequencies,
        *,
        nky: int = 11,
        crossline_tolerance: float = 1e-6,
    ):
        if mesh.dim != 2:
            raise ValueError("ColeCole2DOperator requires a 2-D x-z mesh")
        if not isinstance(nky, int) or nky < 3:
            raise ValueError("nky must be an integer >= 3")
        self.mesh = mesh
        self.survey_spec = survey
        self.frequencies = np.asarray(frequencies, dtype=float)
        if (
            self.frequencies.ndim != 1
            or len(self.frequencies) == 0
            or np.any(self.frequencies <= 0)
            or np.any(np.diff(self.frequencies) <= 0)
        ):
            raise ValueError("frequencies must be positive and strictly increasing")

        crossline = np.concatenate(
            [survey.a[:, 1], survey.b[:, 1], survey.m[:, 1], survey.n[:, 1]]
        )
        if np.ptp(crossline) > float(crossline_tolerance):
            raise ValueError(
                "ABMN electrodes are not coplanar within crossline_tolerance"
            )

        def xz(values):
            return values[:, [0, 2]]

        sources = []
        for index in range(survey.n_measurements):
            receiver = resistivity.receivers.Dipole(
                locations_m=xz(survey.m[index : index + 1]),
                locations_n=xz(survey.n[index : index + 1]),
                data_type="volt",
            )
            source = resistivity.sources.Dipole(
                [receiver],
                location_a=xz(survey.a[index : index + 1])[0],
                location_b=xz(survey.b[index : index + 1])[0],
                current=float(survey.current[index]),
            )
            sources.append(source)
        self.survey = resistivity.Survey(sources)
        # This real-valued instance supplies the independently maintained
        # 2.5-D quadrature, source, receiver, and boundary discretizations.
        self._geometry_simulation = resistivity.Simulation2DNodal(
            mesh,
            survey=self.survey,
            sigma=np.ones(mesh.n_cells),
            nky=nky,
            bc_type="Robin",
        )
        self.n_param = 4 * mesh.n_cells
        self.n_data = len(self.frequencies) * survey.n_measurements
        self._jacobian_model = None
        self._jacobian_cache = None

    @property
    def simulation(self):
        return self._geometry_simulation

    def unpack(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        blocks = model.reshape(4, self.mesh.n_cells)
        return (
            np.exp(blocks[0]),
            expit(blocks[1]),
            np.exp(blocks[2]),
            expit(blocks[3]),
        )

    def _conductivity(self, model, frequency):
        sigma_inf, eta, tau, exponent_c = self.unpack(model)
        omega = 2 * np.pi * float(frequency)
        return sigma_inf * (
            1 - eta / (1 + (1j * omega * tau) ** exponent_c)
        )

    def _predict_frequency(self, conductivity):
        sim = self._geometry_simulation
        grad = self.mesh.nodal_gradient
        grad_t = grad.T.tocsr()
        volumes = self.mesh.cell_volumes
        mn_sigma = sparse.diags(
            self.mesh.aveN2CC.T @ (volumes * conductivity), format="csr"
        )
        me_sigma = self.mesh.get_edge_inner_product(model=conductivity)
        values = np.zeros(self.survey_spec.n_measurements, dtype=complex)

        for ky, weight in zip(sim._quad_points, sim._quad_weights, strict=True):
            sim.setBC(ky=ky)
            matrix = grad_t @ me_sigma @ grad + ky**2 * mn_sigma
            matrix = matrix + sparse.diags(
                sim._AvgBC[ky] @ conductivity, format="csr"
            )
            potential = splu(matrix.tocsc()).solve(sim.getRHS(ky))
            for index, source in enumerate(self.survey.source_list):
                receiver = source.receiver_list[0]
                projection = receiver.getP(self.mesh, "N")
                values[index] += weight * (projection @ potential[:, index])[0]
        return values

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        return np.concatenate(
            [
                self._predict_frequency(self._conductivity(model, frequency))
                for frequency in self.frequencies
            ]
        )

    predict = forward

    def _jacobian(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        if self._jacobian_model is not None and np.array_equal(
            model, self._jacobian_model
        ):
            return self._jacobian_cache
        steps = np.cbrt(np.finfo(float).eps) * np.maximum(1.0, np.abs(model))
        columns = []
        for index, step in enumerate(steps):
            delta = np.zeros(self.n_param)
            delta[index] = step
            columns.append(
                (self.forward(model + delta) - self.forward(model - delta))
                / (2 * step)
            )
        self._jacobian_model = model.copy()
        self._jacobian_cache = np.column_stack(columns)
        return self._jacobian_cache

    def jvp(self, vector, model=None):
        if model is None:
            raise ValueError("Cole-Cole derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        # Two solves per directional derivative avoid materializing the full
        # Jacobian for forward-mode use.
        scale = np.linalg.norm(vector)
        if scale == 0:
            return np.zeros(self.n_data, dtype=complex)
        model = validate_vector(model, self.n_param, "model").astype(float)
        step = np.cbrt(np.finfo(float).eps) * max(1.0, np.linalg.norm(model)) / scale
        return (
            self.forward(model + step * vector)
            - self.forward(model - step * vector)
        ) / (2 * step)

    def jtp(self, vector, model=None):
        if model is None:
            raise ValueError("Cole-Cole derivatives require the evaluation model")
        vector = validate_vector(vector, self.n_data, "data vector")
        return np.real(self._jacobian(model).conj().T @ vector)
