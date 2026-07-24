"""伴随点积测试（adjoint dot product）。

对线性积分算子，离散伴随正确性要求 ⟨J v, w⟩ = ⟨v, Jᵀ w⟩ 在机器精度内成立。
相对误差阈值 1e-6（审查意见02 验收标准）。
"""
import numpy as np


def _relerr(a, b):
    return abs(a - b) / (abs(a) + abs(b) + 1e-30)


def test_gravity_adjoint_dot(grav_op, rng):
    v = rng.standard_normal(grav_op.n_param)
    w = rng.standard_normal(grav_op.n_data)
    Jv = grav_op.jvp(v)
    Jtw = grav_op.jtp(w)
    rel = _relerr(float(Jv @ w), float(v @ Jtw))
    assert rel < 1e-6, f"gravity adjoint dot rel_err={rel:.2e}"


def test_magnetic_adjoint_dot(mag_op, rng):
    v = rng.standard_normal(mag_op.n_param)
    w = rng.standard_normal(mag_op.n_data)
    Jv = mag_op.jvp(v)
    Jtw = mag_op.jtp(w)
    rel = _relerr(float(Jv @ w), float(v @ Jtw))
    assert rel < 1e-6, f"magnetic adjoint dot rel_err={rel:.2e}"
