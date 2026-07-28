"""磁法正演算子: SimPEG 3D 积分法（TMI）封装，matrix-free Jv/Jᵀv。

与重力同为线性积分法，敏感度矩阵 G 不依赖模型 m，故 J≡G；差别在于模型参数
为磁化率 χ、观测为总磁异常（TMI）、需指定背景地磁场（振幅、倾角、偏角）。
"""
from __future__ import annotations

import numpy as np
from simpeg.potential_fields import magnetics
from simpeg import maps
from .base import validate_vector


class MagneticOperator:
    """磁法 TMI 正演算子。

    Parameters
    ----------
    mesh : discretize.TensorMesh
        计算网格。
    receiver_locations : (n_rx, 3) ndarray
        观测点坐标。
    inducing_field : (amplitude_nT, inclination_deg, declination_deg), 默认 (55000, 75, 25)
        背景地磁场参数。
    components : str, 默认 ``'tmi'``
        观测量分量。
    ind_active : (n_cells,) bool ndarray | None
        活动单元掩膜；None 表示全部活动。
    """

    def __init__(self, mesh, receiver_locations, inducing_field=(55000.0, 75.0, 25.0),
                 components="tmi", ind_active=None):
        self.mesh = mesh
        self.receiver_locations = np.asarray(receiver_locations, dtype=float)
        self.components = components
        self.inducing_field = tuple(float(v) for v in inducing_field)
        if ind_active is None:
            ind_active = np.ones(mesh.n_cells, dtype=bool)
        self.ind_active = np.asarray(ind_active, dtype=bool)
        self.n_param = int(self.ind_active.sum())
        self.n_data = int(self.receiver_locations.shape[0])
        self._simulation = self._build_simulation()

    def _build_simulation(self):
        rx = magnetics.receivers.Point(self.receiver_locations, components=self.components)
        amplitude, inclination, declination = self.inducing_field
        try:
            src = magnetics.sources.UniformBackgroundField(
                receiver_list=[rx],
                amplitude=amplitude, inclination=inclination, declination=declination,
            )
        except AttributeError:  # 兼容旧 API: Source + parameters
            src = magnetics.sources.Source(
                receiver_list=[rx],
                parameters=(amplitude, inclination, declination),
            )
        survey = magnetics.Survey(src)
        chi_map = maps.IdentityMap(nP=self.mesh.n_cells)
        kw_cells = {"active_cells": self.ind_active}
        try:
            sim = magnetics.Simulation3DIntegral(
                mesh=self.mesh, survey=survey, chiMap=chi_map, **kw_cells)
        except TypeError:
            kw_cells = {"ind_active": self.ind_active}
            try:
                sim = magnetics.Simulation3DIntegral(
                    mesh=self.mesh, survey=survey, chiMap=chi_map, **kw_cells)
            except TypeError:
                sim = magnetics.Simulation3DIntegral(
                    mesh=self.mesh, survey=survey, chiMap=chi_map,
                    actInd=self.ind_active,
                )
        try:
            sim.sensitivity_dtype = np.float64
        except Exception:
            pass
        return sim

    @property
    def simulation(self):
        return self._simulation

    def _to_full(self, x):
        x = validate_vector(x, self.n_param, "model/vector")
        x_full = np.zeros(self.mesh.n_cells)
        x_full[self.ind_active] = np.asarray(x, dtype=float)
        return x_full

    def forward(self, model):
        return np.asarray(self._simulation.dpred(self._to_full(model)), dtype=float)

    predict = forward

    def jvp(self, v, model=None):
        m_full = self._to_full(model) if model is not None else np.zeros(self.mesh.n_cells)
        return np.asarray(self._simulation.Jvec(m_full, self._to_full(v)), dtype=float)

    def jtp(self, w, model=None):
        m_full = self._to_full(model) if model is not None else np.zeros(self.mesh.n_cells)
        w = validate_vector(w, self.n_data, "data vector").astype(float)
        jt_full = np.asarray(self._simulation.Jtvec(m_full, w), dtype=float)
        return jt_full[self.ind_active]
    method = "magnetic"
    dimensionality = "3d"
    data_mode = "real"
    source_type = "uniform_background_field"
    waveform = None
    units = "nT"
    parameterization = "cell_scalar_susceptibility_SI"
