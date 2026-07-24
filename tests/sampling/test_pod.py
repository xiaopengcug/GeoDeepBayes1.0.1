"""POD 降维与误差传播接口测试。"""
import numpy as np

from geodeepbayes.sampling import PODReducer


def test_pod_reconstructs_low_rank_linear_model():
    rng = np.random.default_rng(0)
    # 真实模型位于 3 维子空间: m = W @ z, z in R^3, m in R^20
    n, r_true = 20, 3
    W = rng.standard_normal((n, r_true))
    Z = rng.standard_normal((r_true, 200))
    snaps = W @ Z   # (20, 200) 全在 3 维子空间内
    pod = PODReducer(snaps, energy=0.999)
    assert pod.rank <= r_true + 1
    # 训练快照的投影误差应接近 0
    err = pod.reconstruction_error(snaps)
    assert err < 1e-6, f"低秩模型投影误差={err:.2e}"


def test_pod_holdout_error_increases_with_lower_rank():
    rng = np.random.default_rng(1)
    # 带噪声的模型，秩不明确
    snaps = rng.standard_normal((30, 100)) * np.linspace(1, 0.1, 30)[:, None]
    holdout = rng.standard_normal((30, 50)) * np.linspace(1, 0.1, 30)[:, None]
    pod_hi = PODReducer(snaps, energy=0.99)
    pod_lo = PODReducer(snaps, energy=0.5)
    assert pod_lo.rank <= pod_hi.rank
    err_lo = pod_lo.reconstruction_error(holdout)
    err_hi = pod_hi.reconstruction_error(holdout)
    assert err_lo >= err_hi, f"低秩留出误差 {err_lo:.3f} 应 ≥ 高秩 {err_hi:.3f}"


def test_pod_encode_reconstruct_roundtrip():
    rng = np.random.default_rng(2)
    snaps = rng.standard_normal((15, 80))
    pod = PODReducer(snaps, energy=0.95)
    m = snaps[:, 0].copy()
    alpha = pod.encode(m)
    assert alpha.shape == (pod.rank,)
    m_back = pod.reconstruct(alpha)
    assert m_back.shape == (15,)
