"""Simulation-based-calibration rank utilities."""
from __future__ import annotations

import numpy as np
from scipy import stats


def sbc_rank(truth: float, posterior_draws) -> int:
    draws = np.asarray(posterior_draws, dtype=float)
    if draws.ndim != 1 or len(draws) == 0 or not np.all(np.isfinite(draws)):
        raise ValueError("posterior_draws must be a finite vector")
    return int(np.sum(draws < truth))


def rank_uniformity(ranks, *, posterior_draw_count: int, bins: int = 10):
    ranks = np.asarray(ranks, dtype=int)
    if len(ranks) < 400:
        raise ValueError("WP8 SBC requires at least 400 repetitions")
    if np.any((ranks < 0) | (ranks > posterior_draw_count)):
        raise ValueError("rank outside posterior draw support")
    counts, _ = np.histogram(
        ranks, bins=np.linspace(0, posterior_draw_count + 1, bins + 1)
    )
    statistic, pvalue = stats.chisquare(counts)
    return {
        "repetitions": int(len(ranks)),
        "posterior_draw_count": int(posterior_draw_count),
        "bins": int(bins),
        "counts": counts.tolist(),
        "chi_square": float(statistic),
        "pvalue": float(pvalue),
        "raw_ranks": ranks.tolist(),
    }


def required_sbc_repetitions(*, target_binomial_se=0.025):
    if not 0 < target_binomial_se < 0.5:
        raise ValueError("target_binomial_se must be in (0,0.5)")
    return max(400, int(np.ceil(0.25 / target_binomial_se**2)))


def normal_conjugate_reference_sbc(
    *,
    repetitions=None,
    posterior_draw_count=99,
    seed=0,
    sensitivity=1.0,
    qoi="scalar_parameter",
):
    """Independent analytic calibration-engine reference, not a physics SBC."""
    if repetitions is None:
        repetitions = required_sbc_repetitions()
    if repetitions < 400:
        raise ValueError("WP8 SBC requires at least 400 repetitions")
    if sensitivity == 0:
        raise ValueError("sensitivity must be non-zero")
    rng = np.random.default_rng(seed)
    noise_sd = 0.7
    ranks = []
    for _ in range(repetitions):
        truth = rng.normal()
        observed = sensitivity * truth + rng.normal(scale=noise_sd)
        posterior_variance = 1 / (1 + sensitivity**2 / noise_sd**2)
        posterior_mean = posterior_variance * sensitivity * observed / noise_sd**2
        draws = rng.normal(posterior_mean, np.sqrt(posterior_variance), posterior_draw_count)
        ranks.append(sbc_rank(truth, draws))
    result = rank_uniformity(
        ranks, posterior_draw_count=posterior_draw_count, bins=10
    )
    result["scope"] = "normal_conjugate_calibration_engine_reference"
    result["qoi"] = qoi
    result["sensitivity"] = float(sensitivity)
    return result
