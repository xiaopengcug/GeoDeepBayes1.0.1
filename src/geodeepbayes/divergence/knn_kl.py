"""k-NN (KSG) KL 散度估计器。

参考 Wang, Kulkarni & Verdú (2009), "Divergence estimation for multidimensional
densities via k-nearest-neighbor distances", IEEE Trans. Inf. Theory;
及 Pérez-Cruz (2008) 的 k-NN KL 估计。

用于多维后验样本的 D_KL(P‖Q)。相比 05 章原"逐维边际直方图"实现，
k-NN 法能捕捉参数间相关性，不会系统性低估联合 KL（审查意见02 / E7 的整改目标）。

估计量:
    D̂ = ψ(k) + log(M/(N−1)) − (1/N) Σ_i ψ(ν_i + 1)
其中 ρ_i = x 中到 x_i 第 k 近邻距离（不含自身），ν_i = y 中落入以 x_i 为心、
ρ_i 为半径球内的点数，ψ 为 digamma 函数。
"""
from __future__ import annotations

import numpy as np
from scipy.special import digamma
from scipy.spatial import cKDTree


def _as_2d(samples):
    a = np.asarray(samples, dtype=float)
    if a.ndim == 1:
        return a.reshape(-1, 1)
    return a


def knn_kl_divergence(x, y, k=5):
    """估计 D_KL(P‖Q)。

    Parameters
    ----------
    x, y : array_like
        来自 P 与 Q 的样本，形状 (N,) / (N, d)。
    k : int, 默认 5
        近邻数；自动裁剪到 ≤ N−1。
    """
    x = _as_2d(x)
    y = _as_2d(y)
    N, M = len(x), len(y)
    if N < 2 or M < 1:
        return float("nan")
    k = int(min(max(k, 1), N - 1))
    tree_x = cKDTree(x)
    tree_y = cKDTree(y)
    # ρ_i: x 中第 k 近邻距离（query k+1，首列为自身距离 0）
    dist_xx, _ = tree_x.query(x, k=k + 1)
    rho = np.maximum(dist_xx[:, k], 1e-12)
    nu = tree_y.query_ball_point(x, rho, p=2, return_length=True)   # (N,)
    kl = digamma(k) + np.log(M / (N - 1)) - np.mean(digamma(nu + 1))
    return float(kl)
