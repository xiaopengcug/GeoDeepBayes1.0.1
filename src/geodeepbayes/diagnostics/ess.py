"""有效样本量 (ESS): 经典 ESS、bulk-ESS、tail-ESS。

bulk-ESS 与 tail-ESS 采用 Vehtari et al. (2021) 定义；自协方差经 FFT 计算，
ESS 经 Geyer 初始正序列 + 初始单调序列截断估计积分自相关时间 τ，ESS = MN/τ。
"""
from __future__ import annotations

import numpy as np

from .rhat import _as_3d, _split_chains_2d, _rank_normalize_2d


def _autocov_1d(x):
    """单链有偏自协方差 (1/N 归一), FFT 实现, 返回长度 N。"""
    N = len(x)
    x = x - x.mean()
    n2 = 1
    while n2 < 2 * N:
        n2 *= 2
    f = np.fft.rfft(x, n=n2)
    acf = np.fft.irfft(f * np.conj(f), n=n2)[:N].real
    return acf / N


def _ess_2d(x):
    """对 (M, N) 计算多链 ESS（Geyer 初始正序列 + 单调序列）。"""
    M, N = x.shape
    if N < 4:
        return np.nan
    acov = np.array([_autocov_1d(x[m]) for m in range(M)])
    chain_means = x.mean(axis=1)
    chain_var = acov[:, 0] * N / (N - 1)   # 有偏方差 → 无偏
    W = chain_var.mean()
    if not np.isfinite(W) or W == 0:
        return np.nan
    B = N * chain_means.var(ddof=1) if M > 1 else 0.0
    var_plus = (N - 1) / N * W + B / N
    acov_mean = acov.mean(axis=0)
    rho_hat = np.ones(N)
    for t in range(1, N):
        rho_hat[t] = 1.0 - (W - acov_mean[t]) / var_plus
    # 成对 P_k = rho_{2k} + rho_{2k+1}
    P = []
    k = 0
    while 2 * k + 1 <= N - 1:
        P.append(rho_hat[2 * k] + rho_hat[2 * k + 1])
        k += 1
    P = np.array(P)
    neg = np.where(P < 0)[0]
    if len(neg) > 0:
        P = P[: neg[0]]
    if len(P) == 0:
        return float(M * N)
    for i in range(1, len(P)):    # 初始单调序列
        if P[i] > P[i - 1]:
            P[i] = P[i - 1]
    tau = -1.0 + 2.0 * float(P.sum())
    if tau < 1.0:
        tau = 1.0
    return float(M * N / tau)


def effective_sample_size(chains):
    """经典 ESS（不做 rank-normalize）。返回 float 或 (n_params,)。"""
    x = _as_3d(chains)
    out = np.array([_ess_2d(x[:, :, p]) for p in range(x.shape[2])])
    return out[0] if out.size == 1 else out


def bulk_ess(chains):
    """bulk-ESS: split 后 rank-normalize 再算 ESS。"""
    x = _as_3d(chains)
    out = np.array([
        _ess_2d(_rank_normalize_2d(_split_chains_2d(x[:, :, p])))
        for p in range(x.shape[2])
    ])
    return out[0] if out.size == 1 else out


def tail_ess(chains):
    """tail-ESS: 5% 与 95% 分位指示函数的 ESS 之最小值。"""
    x = _as_3d(chains)
    out = []
    for p in range(x.shape[2]):
        sp = _split_chains_2d(x[:, :, p])
        q05, q95 = np.quantile(sp, [0.05, 0.95])
        e05 = _ess_2d((sp <= q05).astype(float))
        e95 = _ess_2d((sp <= q95).astype(float))
        out.append(np.nanmin([e05, e95]))
    out = np.array(out)
    return out[0] if out.size == 1 else out
