"""重力正演算子: SimPEG 3D 积分法封装，提供 matrix-free Jv/Jᵀv。

积分法是线性的（敏感度矩阵 G 不依赖模型 m），故雅可比 J≡G；
matrix-free Jv/Jᵀv 通过 SimPEG Simulation.deriv(m, v, adjoint=...) 实现，
并经伴随点积 ⟨Jv,w⟩≈⟨v,Jᵀw⟩、Taylor 余项、有限差分三类测试验证离散伴随正确性。
"""
from __future__ import annotations

import numpy as np
from simpeg.potential_fields import gravity
from simpeg import maps


class GravityOperator:
    """重力（默认 gz 分量）正演算子。

    Parameters
    ----------
    mesh : discretize.TensorMesh
        计算网格。
    receiver_locations : (n_rx, 3) ndarray
        观测点坐标（x, y, z）。
    components : str | list[str], 默认 ``'gz'``
        重力分量，常用 ``'gz'``。
    ind_active : (n_cells,) bool ndarray | None
        活动单元掩膜；None 表示全部活动。模型参数维度 = 活动单元数。
    """

    def __init__(self, mesh, receiver_locations, components="gz", ind_active=None):
        self.mesh = mesh
        self.receiver_locations = np.asarray(receiver_locations, dtype=float)
        self.components = components
        if ind_active is None:
            ind_active = np.ones(mesh.n_cells, dtype=bool)
        self.ind_active = np.asarray(ind_active, dtype=bool)
        self.n_param = int(self.ind_active.sum())
        self.n_data = int(self.receiver_locations.shape[0])
        self._simulation = self._build_simulation()

    def _build_simulation(self):
        rx = gravity.receivers.Point(self.receiver_locations, components=self.components)
        src = gravity.sources.SourceField(receiver_list=[rx])
        survey = gravity.Survey(src)
        rho_map = maps.IdentityMap(nP=self.mesh.n_cells)
        # SimPEG 版本兼容: v0.24+ 用 active_cells，旧版回退 actInd/ind_active
        kw_cells = {"active_cells": self.ind_active}
        try:
            sim = gravity.Simulation3DIntegral(
                mesh=self.mesh, survey=survey, rhoMap=rho_map, **kw_cells)
        except TypeError:
            kw_cells = {"ind_active": self.ind_active}
            try:
                sim = gravity.Simulation3DIntegral(
                    mesh=self.mesh, survey=survey, rhoMap=rho_map, **kw_cells)
            except TypeError:
                sim = gravity.Simulation3DIntegral(
                    mesh=self.mesh, survey=survey, rhoMap=rho_map,
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
        x_full = np.zeros(self.mesh.n_cells)
        x_full[self.ind_active] = np.asarray(x, dtype=float)
        return x_full

    def forward(self, model):
        """正演 dpred(m)；model 长度为活动单元数。"""
        return np.asarray(self._simulation.dpred(self._to_full(model)), dtype=float)

    def jvp(self, v, model=None):
        """J @ v（matrix-free，经 SimPEG getJ 的 LinearOperator）。线性算子 J 不依赖 m。"""
        m_full = self._to_full(model) if model is not None else np.zeros(self.mesh.n_cells)
        return np.asarray(self._simulation.Jvec(m_full, self._to_full(v)), dtype=float)

    def jtp(self, w, model=None):
        """Jᵀ @ w（matrix-free），返回长度为活动单元数。"""
        m_full = self._to_full(model) if model is not None else np.zeros(self.mesh.n_cells)
        w = np.asarray(w, dtype=float)
        jt_full = np.asarray(self._simulation.Jtvec(m_full, w), dtype=float)
        return jt_full[self.ind_active]
