"""边际平均直方图 KL（对照实现）。

⚠️ 系统性低估联合 KL：D_KL(p(m)‖q(m)) ≠ (1/d) Σ_i D_KL(p(m_i)‖q(m_i))，
边际平均忽略参数间相关性，对强相关高维后验会显著低估信息增益。

保留作为对照与回退；高维强相关后验应优先使用 knn_kl_divergence。
本实现对应 05 章 automated_ig_test 的 compute_kl_divergence。
"""
from __future__ import annotations

import numpy as np


def _as_2d(samples):
    a = np.asarray(samples, dtype=float)
    return a.reshape(-1, 1) if a.ndim == 1 else a


def histogram_kl_divergence(p_samples, q_samples, n_bins=100, eps=1e-10):
    """逐维直方图 KL 后取均值（低估联合 KL 的近似估计）。"""
    p_samples = _as_2d(p_samples)
    q_samples = _as_2d(q_samples)
    d = p_samples.shape[1]
    total = 0.0
    for dim in range(d):
        all_data = np.concatenate([p_samples[:, dim], q_samples[:, dim]])
        lo, hi = float(all_data.min()), float(all_data.max())
        if hi <= lo:
            continue
        bins = np.linspace(lo, hi, n_bins + 1)
        ph = np.histogram(p_samples[:, dim], bins=bins)[0].astype(float) + eps
        qh = np.histogram(q_samples[:, dim], bins=bins)[0].astype(float) + eps
        ph /= ph.sum()
        qh /= qh.sum()
        total += float(np.sum(ph * np.log(ph / qh)))
    return total / d
