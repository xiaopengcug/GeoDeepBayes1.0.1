import numpy as np

from geodeepbayes.sampling import delayed_acceptance_metropolis


def _normal_logp(x):
    return -0.5 * float(x @ x)


def test_identity_surrogate_reduces_to_exact_mh_and_is_reproducible():
    def proposal(x, rng):
        return x + 0.8 * rng.standard_normal(x.size), 0.0, "rw"

    a = delayed_acceptance_metropolis(
        _normal_logp, _normal_logp, proposal, np.zeros(2),
        n_warmup=1000, n_draws=5000, seed=7,
    )
    b = delayed_acceptance_metropolis(
        _normal_logp, _normal_logp, proposal, np.zeros(2),
        n_warmup=1000, n_draws=5000, seed=7,
    )
    assert np.array_equal(a.draws, b.draws)
    assert np.all(a.stage2_accepted[a.stage1_accepted])
    assert np.max(np.abs(a.draws.mean(axis=0))) < 0.12
    assert np.max(np.abs(a.draws.var(axis=0) - 1.0)) < 0.15


def test_surrogate_correction_preserves_full_target():
    def surrogate(x):
        return -0.5 * float(x @ x) / 4.0

    def proposal(x, rng):
        return x + rng.standard_normal(x.size), 0.0, "rw"

    trace = delayed_acceptance_metropolis(
        _normal_logp, surrogate, proposal, np.zeros(1),
        n_warmup=1500, n_draws=8000, seed=11,
    )
    assert trace.draws.shape == (8000, 1)
    assert 0 < trace.stage2_accept_rate < 1
    assert abs(float(trace.draws.mean())) < 0.12
    assert abs(float(trace.draws.var()) - 1.0) < 0.15


def test_asymmetric_proposal_ratio_is_used():
    # Independence proposal q=N(0.5,1.5²); reverse-forward ratio is log q(x)-log q(y).
    def proposal(x, rng):
        y = rng.normal(0.5, 1.5, size=x.size)
        log_q_ratio = (
            -0.5 * float((x - 0.5) @ (x - 0.5)) / 1.5**2
            + 0.5 * float((y - 0.5) @ (y - 0.5)) / 1.5**2
        )
        return y, log_q_ratio, "independence"

    trace = delayed_acceptance_metropolis(
        _normal_logp, _normal_logp, proposal, np.zeros(1),
        n_warmup=1000, n_draws=8000, seed=19,
    )
    assert abs(float(trace.draws.mean())) < 0.15


def test_dimension_change_is_rejected():
    def bad(x, rng):
        return np.r_[x, 0.0], 0.0, "bad"

    try:
        delayed_acceptance_metropolis(
            _normal_logp, _normal_logp, bad, np.zeros(2),
            n_warmup=0, n_draws=1, seed=1,
        )
    except ValueError as exc:
        assert "dimension" in str(exc)
    else:
        raise AssertionError("dimension-changing proposal was accepted")
