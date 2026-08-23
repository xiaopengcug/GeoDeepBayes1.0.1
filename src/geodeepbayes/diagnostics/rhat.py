"""rank-normalized split-R̂（Vehtari et al., 2021）。

输入约定: chains shape 为 (n_chains, n_draws)（单参数）或
(n_chains, n_draws, n_params)（批量，沿末维逐参数计算，返回 (n_params,)）。

参考: Vehtari, Gelman, Simpson, Carpenter, Bürkner (2021),
"Rank-normalization, folding, and localization: An improved R̂ for assessing
convergence of MCMC", Bayesian Analysis.
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def _as_3d(chains):
    """统一为 (M, N, P)；若输入 2D 视为单参数 (M, N)→(M, N, 1)。"""
    a = np.asarray(chains, dtype=float)
    if a.ndim == 2:
        a = a[..., None]
    elif a.ndim == 3:
        pass
    else:
        raise ValueError(f"chains 须为 2D 或 3D, 实际 ndim={a.ndim}")
    nonfinite_count = int(a.size - np.count_nonzero(np.isfinite(a)))
    if nonfinite_count:
        raise ValueError(
            f"chains 含 {nonfinite_count} 个非有限值，诊断已按 fail-closed 中止")
    return a


def _split_chains_2d(x):
    """(M, N) -> (2M, N//2) 按链对半切分。N 奇数时丢弃末位。"""
    M, N = x.shape
    if N % 2 == 1:
        x = x[:, :-1]
        N = N - 1
    half = N // 2
    return np.concatenate([x[:, :half], x[:, half:2 * half]], axis=0)


def _rhat_basic_2d(x):
    """对 split 后的 (M', N') 计算经典 R̂（未 rank-normalize）。"""
    M, N = x.shape
    if N < 2 or M < 2:
        return np.nan
    chain_means = x.mean(axis=1)
    chain_vars = x.var(axis=1, ddof=1)
    W = chain_vars.mean()
    if not np.isfinite(W) or W == 0:
        return np.nan
    B = N * chain_means.var(ddof=1)
    var_hat = (N - 1) / N * W + B / N
    return float(np.sqrt(var_hat / W))


def _rank_normalize_2d(x):
    """rank-normalize 到标准正态分位数 (Vehtari 2021, 式 (3))。"""
    flat = x.ravel()
    ranks = stats.rankdata(flat, method="average")
    z = stats.norm.ppf((ranks - 0.375) / (flat.size + 0.25))
    return z.reshape(x.shape)


def _folded_2d(x):
    """folded 变换 |x - median(x)|，用于检测尾部不收敛。"""
    med = np.median(x)
    return np.abs(x - med)


def split_rhat(chains):
    """经典 split-R̂（仅按链对半切分，不做 rank-normalize）。

    返回 float（单参数）或 (n_params,) ndarray。
    """
    x = _as_3d(chains)
    out = np.array([_rhat_basic_2d(_split_chains_2d(x[:, :, p])) for p in range(x.shape[2])])
    return out[0] if out.size == 1 else out


def rank_normalized_split_rhat(chains):
    """Vehtari (2021) 改进 R̂ = max(bulk-R̂, tail-R̂)。

    bulk-R̂: 对 split 后样本做 rank-normalize 再算 R̂。
    tail-R̂: 对 split 后样本做 folded(|x-med|) 再 rank-normalize 再算 R̂。
    取二者最大，同时覆盖中心与尾部不收敛。
    """
    x = _as_3d(chains)
    res = []
    for p in range(x.shape[2]):
        sp = _split_chains_2d(x[:, :, p])
        bulk = _rhat_basic_2d(_rank_normalize_2d(sp))
        tail = _rhat_basic_2d(_rank_normalize_2d(_folded_2d(sp)))
        a, b = (np.nan, np.nan) if np.isnan(bulk) else (bulk, tail)
        res.append(max(a, b) if not np.isnan(a) else np.nan)
    out = np.array(res)
    return out[0] if out.size == 1 else out
