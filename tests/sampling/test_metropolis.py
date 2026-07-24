"""AdaptiveMetropolis 测试: 在已知高斯后验上恢复均值、检查收敛诊断。"""
import numpy as np

from geodeepbayes.sampling import AdaptiveMetropolis
from geodeepbayes.diagnostics import rank_normalized_split_rhat, bulk_ess


def _run_chains(log_post, dim, n_chains=4, n_draws=2000, n_warmup=1000, seed=0):
    rng = np.random.default_rng(seed)
    all_samples = []
    for c in range(n_chains):
        init = rng.standard_normal(dim) * 0.5
        s = AdaptiveMetropolis(log_post, dim, init=init, rng=rng, target_accept=0.234)
        draws, info = s.sample(n_draws, n_warmup=n_warmup)
        all_samples.append(draws)
    return np.asarray(all_samples)   # (n_chains, n_draws, dim)


def test_recovers_gaussian_posterior_mean():
    mu = np.array([1.0, -1.0])
    sigma = np.array([0.5, 1.0])

    def log_post(m):
        return -0.5 * np.sum(((m - mu) / sigma) ** 2)

    chains = _run_chains(log_post, 2, seed=0)
    post_mean = chains.reshape(-1, 2).mean(axis=0)
    assert abs(post_mean[0] - 1.0) < 0.20, f"mean[0]={post_mean[0]:.3f}"
    assert abs(post_mean[1] + 1.0) < 0.30, f"mean[1]={post_mean[1]:.3f}"


def test_rhat_converges_on_gaussian():
    mu = np.array([0.0, 0.0])
    sigma = np.array([0.5, 0.5])

    def log_post(m):
        return -0.5 * np.sum(((m - mu) / sigma) ** 2)

    chains = _run_chains(log_post, 2, n_draws=2000, n_warmup=1000, seed=1)
    r = rank_normalized_split_rhat(chains)
    assert np.all(r < 1.05), f"R̂={r}"


def test_accept_rate_near_target():
    def log_post(m):
        return -0.5 * np.sum(m ** 2)

    rng = np.random.default_rng(2)
    s = AdaptiveMetropolis(log_post, 2, init=np.zeros(2), rng=rng, target_accept=0.234)
    _, info = s.sample(3000, n_warmup=2000)
    assert 0.1 < info["accept_rate"] < 0.5, f"accept_rate={info['accept_rate']:.3f}"
