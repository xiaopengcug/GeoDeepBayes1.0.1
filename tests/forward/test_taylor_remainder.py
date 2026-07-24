"""Taylor 余项测试。

对线性算子 F(m)=F(0)+J m，二阶余项应严格为 0（含数值舍入）；
此处对积分法线性算子验证 ||F(m+δv) − F(m) − δ J v|| 随 δ 的二阶（机器精度）衰减。
"""
import numpy as np


def _taylor_residual(op, m, v, delta):
    f0 = op.forward(m)
    f1 = op.forward(m + delta * v)
    jv = op.jvp(v)
    return np.linalg.norm(f1 - f0 - delta * jv)


def test_gravity_taylor_second_order(grav_op, rng):
    m = rng.uniform(0.0, 0.05, grav_op.n_param)
    v = rng.standard_normal(grav_op.n_param)
    deltas = [1e-2, 1e-3]
    res = [_taylor_residual(grav_op, m, v, d) for d in deltas]
    # 线性算子: 余项应在机器精度量级（不随 δ 变化）
    assert res[0] < 1e-8 * max(1.0, np.linalg.norm(grav_op.jvp(v))), (
        f"gravity taylor residual too large: {res}"
    )
    assert res[1] < 1e-8 * max(1.0, np.linalg.norm(grav_op.jvp(v))), f"{res}"


def test_magnetic_taylor_second_order(mag_op, rng):
    m = rng.uniform(0.0, 0.05, mag_op.n_param)
    v = rng.standard_normal(mag_op.n_param)
    res = _taylor_residual(mag_op, m, v, 1e-2)
    assert res < 1e-6 * max(1.0, np.linalg.norm(mag_op.jvp(v))), f"{res}"
