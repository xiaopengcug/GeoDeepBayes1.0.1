"""Three-component effective-susceptibility magnetic integral operator."""
from __future__ import annotations

import numpy as np
from simpeg import maps
from simpeg.potential_fields import magnetics

from .base import validate_vector


class MagneticVectorOperator:
    """3-D vector magnetization path for induced plus remanent directions.

    Model ordering follows SimPEG's vector convention: all active-cell x
    components, followed by all y components, then all z components.
    """

    method = "magnetic"
    dimensionality = "3d"
    data_mode = "real"
    source_type = "uniform_background_field"
    waveform = None
    units = "nT"
    parameterization = "active_cell_effective_susceptibility_xyz_component_blocks"

    def __init__(
        self,
        mesh,
        receiver_locations,
        inducing_field=(55000.0, 75.0, 25.0),
        components="tmi",
        ind_active=None,
    ):
        self.mesh = mesh
        self.receiver_locations = np.asarray(receiver_locations, dtype=float)
        if self.receiver_locations.ndim != 2 or self.receiver_locations.shape[1] != 3:
            raise ValueError("receiver_locations must have shape (n_receivers, 3)")
        self.components = components
        self.inducing_field = tuple(float(value) for value in inducing_field)
        if len(self.inducing_field) != 3 or not np.all(np.isfinite(self.inducing_field)):
            raise ValueError("inducing_field must contain amplitude, inclination, declination")
        if ind_active is None:
            ind_active = np.ones(mesh.n_cells, dtype=bool)
        self.ind_active = np.asarray(ind_active, dtype=bool)
        if self.ind_active.shape != (mesh.n_cells,):
            raise ValueError("ind_active must have shape (mesh.n_cells,)")
        self.n_active = int(self.ind_active.sum())
        self.n_param = 3 * self.n_active
        component_count = 1 if isinstance(components, str) else len(components)
        self.n_data = len(self.receiver_locations) * component_count
        self._simulation = self._build_simulation()

    def _build_simulation(self):
        receiver = magnetics.receivers.Point(
            self.receiver_locations, components=self.components
        )
        amplitude, inclination, declination = self.inducing_field
        source = magnetics.sources.UniformBackgroundField(
            receiver_list=[receiver],
            amplitude=amplitude,
            inclination=inclination,
            declination=declination,
        )
        survey = magnetics.Survey(source)
        simulation = magnetics.Simulation3DIntegral(
            mesh=self.mesh,
            survey=survey,
            chiMap=maps.IdentityMap(nP=self.n_param),
            active_cells=self.ind_active,
            model_type="vector",
        )
        simulation.sensitivity_dtype = np.float64
        return simulation

    @property
    def simulation(self):
        return self._simulation

    def forward(self, model):
        model = validate_vector(model, self.n_param, "model").astype(float)
        return np.asarray(self._simulation.dpred(model), dtype=float)

    predict = forward

    def jvp(self, vector, model=None):
        vector = validate_vector(vector, self.n_param, "parameter vector").astype(float)
        reference = (
            np.zeros(self.n_param)
            if model is None
            else validate_vector(model, self.n_param, "model").astype(float)
        )
        return np.asarray(self._simulation.Jvec(reference, vector), dtype=float)

    def jtp(self, vector, model=None):
        vector = validate_vector(vector, self.n_data, "data vector").astype(float)
        reference = (
            np.zeros(self.n_param)
            if model is None
            else validate_vector(model, self.n_param, "model").astype(float)
        )
        return np.asarray(self._simulation.Jtvec(reference, vector), dtype=float)
