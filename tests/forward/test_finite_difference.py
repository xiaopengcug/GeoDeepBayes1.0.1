"""有限差分对照测试。

J v 应与中心差分 (F(m+εv) − F(m−εv)) / (2ε) 一致。
对线性算子理论上严格相等；此处容许 1e-4 的数值扰动（含正演积分与差分步长误差）。
"""
import numpy as np


def _fd_jvp(op, m, v, eps):
    return (op.forward(m + eps * v) - op.forward(m - eps * v)) / (2 * eps)


def test_gravity_finite_difference(grav_op, rng):
    m = rng.uniform(0.0, 0.05, grav_op.n_param)
    v = rng.standard_normal(grav_op.n_param)
    eps = 1e-4
    jvp = grav_op.jvp(v)
    fd = _fd_jvp(grav_op, m, v, eps)
    rel = np.linalg.norm(jvp - fd) / (np.linalg.norm(jvp) + 1e-30)
    assert rel < 1e-4, f"gravity finite-diff rel_err={rel:.2e}"


def test_magnetic_finite_difference(mag_op, rng):
    m = rng.uniform(0.0, 0.05, mag_op.n_param)
    v = rng.standard_normal(mag_op.n_param)
    eps = 1e-4
    jvp = mag_op.jvp(v)
    fd = _fd_jvp(mag_op, m, v, eps)
    rel = np.linalg.norm(jvp - fd) / (np.linalg.norm(jvp) + 1e-30)
    assert rel < 1e-4, f"magnetic finite-diff rel_err={rel:.2e}"
