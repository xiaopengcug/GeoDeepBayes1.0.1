"""诊断模块测试: 在已知分布上验证 R̂、ESS、MCSE 的行为。"""
import numpy as np
import pytest

from geodeepbayes.diagnostics import (
    split_rhat,
    rank_normalized_split_rhat,
    effective_sample_size,
    bulk_ess,
    tail_ess,
    monte_carlo_standard_error,
)
from geodeepbayes.diagnostics.rhat import _rank_normalize_2d


def test_rank_normalization_uses_contract_blom_plotting_position():
    """捕获 Blom plotting position 分母误写为 N-1/4 的回归。"""
    values = np.array([[1.0, 2.0], [3.0, 4.0]])
    expected = np.array([
        [-1.0491313979639707, -0.2993069104656671],
        [0.2993069104656671, 1.0491313979639707],
    ])

    np.testing.assert_allclose(
        _rank_normalize_2d(values), expected, rtol=0.0, atol=1e-15)


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_rank_rhat_rejects_nonfinite_input(bad_value):
    """捕获 NaN/Inf 被静默送入聚合路径而未 fail-closed 的回归。"""
    chains = np.zeros((4, 20))
    chains[0, 0] = bad_value

    with pytest.raises(ValueError, match="非有限"):
        rank_normalized_split_rhat(chains)


def test_iid_normal_rhat_close_to_one():
    rng = np.random.default_rng(0)
    chains = rng.standard_normal((4, 2000))  # iid N(0,1), 4 链 × 2000
    r = rank_normalized_split_rhat(chains)
    assert 0.99 < r < 1.01, f"iid 链 R̂={r:.4f} 应接近 1.0"


def test_iid_normal_bulk_ess_near_total():
    rng = np.random.default_rng(1)
    chains = rng.standard_normal((4, 2000))
    e = bulk_ess(chains)
    # iid: ESS 应接近 MN=8000；放宽到 >2000 容许估计波动
    assert e > 2000, f"iid bulk_ess={e:.0f} 应较大"


def test_ar1_high_autocorr_low_ess():
    rng = np.random.default_rng(2)
    phi, M, N = 0.9, 4, 2000
    chains = np.empty((M, N))
    for m in range(M):
        x = 0.0
        for t in range(N):
            x = phi * x + rng.standard_normal() * np.sqrt(1 - phi ** 2)
            chains[m, t] = x
    e = effective_sample_size(chains)
    # 理论 ESS/MN ≈ (1-phi)/(1+phi) ≈ 0.053 ⇒ ≈421；高自相关应显著低于 MN
    assert e < 800, f"AR(1) phi=0.9 ESS={e:.0f} 应远低于 MN=8000"
    assert e > 50, f"AR(1) ESS={e:.0f} 不应过度低估"


def test_bimodal_rhat_large():
    rng = np.random.default_rng(3)
    a = rng.standard_normal((2, 1000)) - 3.0
    b = rng.standard_normal((2, 1000)) + 3.0
    chains = np.vstack([a, b])  # 不同链落在不同峰，未混合
    r = rank_normalized_split_rhat(chains)
    assert r > 1.1, f"双峰未混合 R̂={r:.3f} 应显著 >1.1"


def test_batch_shape_3d():
    rng = np.random.default_rng(4)
    chains = rng.standard_normal((4, 1000, 3))
    assert rank_normalized_split_rhat(chains).shape == (3,)
    assert bulk_ess(chains).shape == (3,)
    assert tail_ess(chains).shape == (3,)
    assert monte_carlo_standard_error(chains).shape == (3,)


def test_mcse_decreases_with_more_draws():
    rng = np.random.default_rng(5)
    e_short = monte_carlo_standard_error(rng.standard_normal((4, 500)))
    e_long = monte_carlo_standard_error(rng.standard_normal((4, 4000)))
    assert e_long < e_short, "更多样本 MCSE 应更小"


def test_split_rhat_classical_consistent_with_rank():
    rng = np.random.default_rng(6)
    chains = rng.standard_normal((4, 2000))
    r_classic = split_rhat(chains)
    r_rank = rank_normalized_split_rhat(chains)
    # 对良态 iid 链，经典 split-R̂ 与 rank-normalized 都接近 1
    assert 0.99 < r_classic < 1.02
    assert 0.99 < r_rank < 1.02
