"""自适应随机游走 Metropolis-Hastings (RWMH)。

在对数空间工作以避免下溢；采用 Robbins-Monro 标量步长自适应，
目标接受率 0.234（多维最优）。适用于固定维、连续参数的贝叶斯反演。

注: 离散岩性、变维模型需配合 RJMCMC（后续阶段）；非光滑先验（TV/L1）
需变量分裂或其他核——本采样器不适用于这些情形（审查意见02 / 02:87）。
"""
from __future__ import annotations

import numpy as np


class AdaptiveMetropolis:
    """自适应 RWMH 采样器（标量步长 Robbins-Monro 自适应）。

    Parameters
    ----------
    log_posterior : callable(m) -> float
        非归一化对数后验。
    dim : int
        参数维度。
    init : (dim,) ndarray | None
        初始状态；默认 zeros。
    init_scale : float, 默认 0.1
        初始提议步长。
    target_accept : float, 默认 0.234
        目标接受率（多维 0.234；一维可用 0.44）。
    rng : np.random.Generator | int | None
    """

    def __init__(self, log_posterior, dim, init=None, init_scale=0.1,
                 target_accept=0.234, rng=None):
        self.log_posterior = log_posterior
        self.dim = int(dim)
        self.target_accept = float(target_accept)
        if isinstance(rng, np.random.Generator):
            self.rng = rng
        else:
            self.rng = np.random.default_rng(rng)
        self.state = np.zeros(self.dim, dtype=float) if init is None else np.asarray(init, float).copy()
        self.log_scale = float(np.log(init_scale))
        self._log_p_current = float(self.log_posterior(self.state))
        self.n_accept = 0
        self.n_step = 0

    @property
    def scale(self):
        return float(np.exp(self.log_scale))

    def step(self):
        eps = self.rng.standard_normal(self.dim)
        proposal = self.state + self.scale * eps
        log_p_proposal = float(self.log_posterior(proposal))
        log_alpha = log_p_proposal - self._log_p_current
        if np.isfinite(log_alpha) and np.log(self.rng.random()) < log_alpha:
            self.state = proposal
            self._log_p_current = log_p_proposal
            accepted = True
        else:
            accepted = False
        # Robbins-Monro 标量步长自适应（Haario et al. 2001 风格）
        gamma = 1.0 / (self.n_step + 1) ** 0.6
        self.log_scale += gamma * ((1.0 if accepted else 0.0) - self.target_accept)
        self.n_step += 1
        if accepted:
            self.n_accept += 1
        return accepted

    def sample(self, n_draws, n_warmup=0, thin=1):
        """预热后采样 n_draws（隔 thin 取一）。返回 (samples, info)。"""
        for _ in range(int(n_warmup)):
            self.step()
        kept = []
        for i in range(int(n_draws) * int(thin)):
            self.step()
            if (i % thin) == 0:
                kept.append(self.state.copy())
        info = {
            "accept_rate": self.n_accept / max(self.n_step, 1),
            "scale": self.scale,
            "n_step": self.n_step,
        }
        return np.asarray(kept), info
