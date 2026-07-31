"""Cluster-level predictive metrics recomputed from raw samples."""
from __future__ import annotations

import numpy as np
from scipy import stats


def _samples_observed(samples, observed):
    samples = np.asarray(samples, dtype=float)
    observed = np.asarray(observed, dtype=float)
    if samples.ndim != 2 or observed.shape != (samples.shape[1],):
        raise ValueError("samples must be (n_draws,n_observations) and observed must match")
    if not np.all(np.isfinite(samples)) or not np.all(np.isfinite(observed)):
        raise ValueError("metrics require finite samples and observations")
    return samples, observed


def crps_ensemble(samples, observed):
    samples, observed = _samples_observed(samples, observed)
    first = np.mean(np.abs(samples - observed[None, :]), axis=0)
    sorted_samples = np.sort(samples, axis=0)
    count = len(samples)
    weights = 2 * np.arange(1, count + 1) - count - 1
    pairwise_half = np.sum(weights[:, None] * sorted_samples, axis=0) / count**2
    return first - pairwise_half


def interval_coverage(samples, observed, level):
    samples, observed = _samples_observed(samples, observed)
    if not 0 < level < 1:
        raise ValueError("level must be in (0,1)")
    tail = (1 - level) / 2
    low, high = np.quantile(samples, [tail, 1 - tail], axis=0)
    return (observed >= low) & (observed <= high)


def coverage_equivalence_tost(
    covered,
    *,
    nominal,
    margin=0.05,
    alpha=0.05,
):
    covered = np.asarray(covered, dtype=float)
    if covered.ndim != 1 or len(covered) < 2:
        raise ValueError("coverage TOST requires at least two independent clusters")
    estimate = float(np.mean(covered))
    standard_error = float(stats.sem(covered))
    if standard_error == 0:
        passed = abs(estimate - nominal) <= margin
        return {"estimate": estimate, "lower_p": 0.0 if passed else 1.0, "upper_p": 0.0 if passed else 1.0, "passed": passed}
    lower_t = (estimate - (nominal - margin)) / standard_error
    upper_t = ((nominal + margin) - estimate) / standard_error
    lower_p = float(stats.t.sf(lower_t, len(covered) - 1))
    upper_p = float(stats.t.sf(upper_t, len(covered) - 1))
    return {
        "estimate": estimate,
        "lower_p": lower_p,
        "upper_p": upper_p,
        "passed": lower_p < alpha and upper_p < alpha,
    }


def paired_crps_improvement_test(candidate_cluster_crps, baseline_cluster_crps, *, alpha=0.05):
    candidate = np.asarray(candidate_cluster_crps, dtype=float)
    baseline = np.asarray(baseline_cluster_crps, dtype=float)
    if candidate.shape != baseline.shape or candidate.ndim != 1 or len(candidate) < 2:
        raise ValueError("paired cluster CRPS arrays must match and contain at least two clusters")
    relative = (baseline - candidate) / baseline
    statistic, pvalue = stats.ttest_1samp(relative, popmean=0.1, alternative="greater")
    return {
        "mean_relative_improvement": float(np.mean(relative)),
        "one_sided_p": float(pvalue),
        "lower_95": float(
            np.mean(relative)
            - stats.t.ppf(0.95, len(relative) - 1) * stats.sem(relative)
        ),
        "passed": bool(pvalue < alpha),
        "statistic": float(statistic),
    }


def pit_values(samples, observed):
    samples, observed = _samples_observed(samples, observed)
    return (np.sum(samples < observed[None, :], axis=0) + 0.5 * np.sum(samples == observed[None, :], axis=0)) / len(samples)


def sharpness(samples, level=0.9):
    samples = np.asarray(samples, dtype=float)
    tail = (1 - level) / 2
    low, high = np.quantile(samples, [tail, 1 - tail], axis=0)
    return high - low


def brier_score(probabilities, outcomes):
    probabilities = np.asarray(probabilities, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probabilities.shape != outcomes.shape or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("valid matching probabilities and outcomes required")
    return float(np.mean((probabilities - outcomes) ** 2))
