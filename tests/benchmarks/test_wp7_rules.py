import numpy as np

from geodeepbayes.benchmarks.wp7 import (
    RidgeTrial, acceptance_flags, ridge_gcv_path, select_gcv_stronger_tie_break,
)


def test_gcv_path_uses_frozen_sigma_and_not_truth_for_selection():
    rng = np.random.default_rng(4)
    G = rng.normal(size=(30, 6))
    truth = rng.normal(size=6)
    data = G @ truth + rng.normal(scale=0.2, size=30)
    path = ridge_gcv_path(G, data, 0.2, truth, (0.01, 0.1, 1.0, 10.0))
    selected = select_gcv_stronger_tie_break(path)
    assert selected in path
    assert selected.gcv <= 1.01 * min(item.gcv for item in path)
    changed_truth = ridge_gcv_path(G, data, 0.2, truth + 100, (0.01, 0.1, 1.0, 10.0))
    assert select_gcv_stronger_tie_break(changed_truth).alpha == selected.alpha


def test_one_percent_tie_selects_stronger_alpha():
    base = dict(
        solution=np.zeros(1), prediction=np.zeros(1), residual=np.zeros(1),
        normalized_rms=1.0, model_rmse=1.0, effective_df=1.0,
        solution_norm=1.0, residual_norm=1.0,
    )
    trials = [
        RidgeTrial(alpha=1.0, gcv=1.0, **base),
        RidgeTrial(alpha=10.0, gcv=1.009, **base),
        RidgeTrial(alpha=100.0, gcv=1.02, **base),
    ]
    assert select_gcv_stronger_tie_break(trials).alpha == 10.0


def test_three_acceptance_flags_are_independent():
    flags = acceptance_flags(
        stop_code=7, iterations=2000, iteration_limit=2000,
        values_finite=True, normalized_rms=1.0,
        model_rmse=0.8, zero_model_rmse=1.0,
    )
    assert flags == {
        "solver_converged": False,
        "data_fit_accepted": True,
        "model_recovery_accepted": True,
    }
    assert not acceptance_flags(
        stop_code=2, iterations=10, iteration_limit=2000,
        values_finite=True, normalized_rms=0.1,
        model_rmse=0.8, zero_model_rmse=1.0,
    )["data_fit_accepted"]
