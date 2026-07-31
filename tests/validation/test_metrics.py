import numpy as np
import pytest

from geodeepbayes.validation.metrics import (
    brier_score,
    coverage_equivalence_tost,
    crps_ensemble,
    interval_coverage,
    paired_crps_improvement_test,
    pit_values,
    sharpness,
)


def test_metrics_recompute_from_raw_samples():
    rng = np.random.default_rng(1)
    samples = rng.normal(size=(1000, 20))
    observed = rng.normal(size=20)
    assert crps_ensemble(samples, observed).shape == (20,)
    assert interval_coverage(samples, observed, 0.9).shape == (20,)
    assert pit_values(samples, observed).shape == (20,)
    assert sharpness(samples).shape == (20,)
    assert brier_score([0.1, 0.9], [0, 1]) == pytest.approx(0.01)


def test_cluster_gates_do_not_treat_channels_as_clusters():
    coverage = np.r_[np.ones(900), np.zeros(100)]
    result = coverage_equivalence_tost(coverage, nominal=0.9)
    assert result["passed"] is True
    baseline = np.ones(40)
    candidate = np.linspace(0.82, 0.88, 40)
    improvement = paired_crps_improvement_test(candidate, baseline)
    assert improvement["mean_relative_improvement"] > 0.1
