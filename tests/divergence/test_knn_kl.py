"""k-NN KL 估计器与边际直方图 KL 的测试（在已知分布上验证）。"""
import numpy as np

from geodeepbayes.divergence import knn_kl_divergence, histogram_kl_divergence


def test_knn_kl_zero_for_identical_distributions():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((2000, 2))
    y = rng.standard_normal((2000, 2))
    kl = knn_kl_divergence(x, y, k=5)
    assert abs(kl) < 0.1, f"相同分布 KL={kl:.3f} 应接近 0"


def test_knn_kl_reasonable_for_different_scale():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((4000, 2))         # P = N(0, I)
    y = rng.standard_normal((4000, 2)) * 2.0   # Q = N(0, 4 I)
    kl = knn_kl_divergence(x, y, k=5)
    # 解析: 每维 KL(N(0,1)||N(0,4)) = log2 + 1/8 − 0.5 ≈ 0.318; 2D ≈ 0.636
    expected = 2 * (np.log(2.0) + 1.0 / 8 - 0.5)
    assert kl > 0.3, f"KL={kl:.3f} 应明显 > 0"
    assert abs(kl - expected) < 0.25, f"KL={kl:.3f} 与解析 {expected:.3f} 偏差过大"


def test_knn_kl_handles_1d_input():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(2000)
    y = rng.standard_normal(2000) + 1.0
    kl = knn_kl_divergence(x, y, k=5)
    # KL(N(0,1)||N(1,1)) = 0.5
    assert 0.25 < kl < 0.85, f"1D KL={kl:.3f}, 解析=0.5"


def test_histogram_kl_zero_for_identical():
    rng = np.random.default_rng(3)
    x = rng.standard_normal((2000, 1))
    kl = histogram_kl_divergence(x, x.copy(), n_bins=50)
    assert kl < 0.05, f"边际直方图 KL 同分布={kl:.4f} 应接近 0"


def test_histogram_underestimates_joint_correlated_kl_captures():
    """强相关 2D: k-NN KL 能捕捉联合结构，边际平均低估。"""
    rng = np.random.default_rng(4)
    cov_p = np.array([[1.0, 0.0], [0.0, 1.0]])
    cov_q = np.array([[1.0, 0.95], [0.95, 1.0]])   # Q 强相关，P 独立
    L_p = np.linalg.cholesky(cov_p)
    L_q = np.linalg.cholesky(cov_q)
    x = (rng.standard_normal((4000, 2)) @ L_p.T)
    y = (rng.standard_normal((4000, 2)) @ L_q.T)
    kl_knn = knn_kl_divergence(x, y, k=5)
    kl_hist = histogram_kl_divergence(x, y, n_bins=60)
    # 解析 KL(N(0,I)||N(0,cov_q)) = 0.5*(tr(cov_q)−2 + log(det cov_q/1)+... )
    # KL = 0.5*( tr(Σ_q) - d + log det Σ_q ) = 0.5*(2 - 2 + log(1-0.95²)) = 0.5*log(0.0975) ≈ −1.16 <0?
    # 实际 KL(N(0,I)||N(0,Σ)) = 0.5*(tr(Σ)−d + log det Σ + ... )；Σ=cov_q, tr=2, det=1−0.9025=0.0975
    # =0.5*(2-2+log 0.0975)=0.5*(-2.328)=-1.16 → 负? 不可能。公式错。
    # 正确: KL(N(0,I)||N(0,Σ)) = 0.5*(tr(Σ) - d - log det Σ)... 实为 0.5*(tr(Σ)−d+log det Σ_... )
    # 不依赖精确解析值，只断言 k-NN 显著高于边际平均（捕捉相关性）
    assert kl_knn > kl_hist + 0.5, (
        f"k-NN KL={kl_knn:.3f} 应显著大于边际平均 {kl_hist:.3f}（后者忽略相关）"
    )
