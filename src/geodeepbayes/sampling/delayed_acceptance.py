"""全维 delayed-acceptance Metropolis-Hastings。

代理密度只决定第一阶段筛选，不改变状态空间。实现允许非对称提议，
因此可用于局部随机游走与跨模态独立提议的混合核。
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class DelayedAcceptanceTrace:
    draws: np.ndarray
    warmup: np.ndarray
    initial_state: np.ndarray
    stage1_accepted: np.ndarray
    stage2_accepted: np.ndarray
    proposal_kind: np.ndarray
    full_log_density: np.ndarray
    surrogate_log_density: np.ndarray
    seed: int | None
    wall_seconds: float

    @property
    def stage1_accept_rate(self) -> float:
        return float(np.mean(self.stage1_accepted))

    @property
    def stage2_accept_rate(self) -> float:
        attempted = self.stage1_accepted
        return float(np.mean(self.stage2_accepted[attempted])) if np.any(attempted) else 0.0


Proposal = Callable[[np.ndarray, np.random.Generator], tuple[np.ndarray, float, str]]


def delayed_acceptance_metropolis(
    log_density: Callable[[np.ndarray], float],
    surrogate_log_density: Callable[[np.ndarray], float],
    proposal: Proposal,
    initial_state: np.ndarray,
    *,
    n_warmup: int,
    n_draws: int,
    seed: int | None = None,
) -> DelayedAcceptanceTrace:
    """Sample the exact full-dimensional target with a frozen surrogate.

    ``proposal`` returns ``(candidate, log_q_reverse_minus_forward, kind)``.
    Adaptation, if any, must be completed before this function is called.
    The surrogate must be finite wherever a proposal can reach finite
    full-target density; otherwise stage one can make valid target support
    unreachable.
    """
    if n_warmup < 0 or n_draws <= 0:
        raise ValueError("n_warmup must be non-negative and n_draws positive")
    rng = np.random.default_rng(seed)
    initial = np.asarray(initial_state, dtype=float).copy()
    state = initial.copy()
    lf = float(log_density(state))
    ls = float(surrogate_log_density(state))
    if not np.isfinite(lf) or not np.isfinite(ls):
        raise ValueError("initial state has non-finite density")
    total = n_warmup + n_draws
    states = np.empty((total, state.size))
    full = np.empty(total)
    surrogate = np.empty(total)
    accepted1 = np.zeros(total, dtype=bool)
    accepted2 = np.zeros(total, dtype=bool)
    kinds = np.empty(total, dtype="U32")
    started = perf_counter()
    for index in range(total):
        candidate, log_q_ratio, kind = proposal(state.copy(), rng)
        candidate = np.asarray(candidate, dtype=float)
        if candidate.shape != state.shape:
            raise ValueError("proposal changed the state dimension")
        ls_candidate = float(surrogate_log_density(candidate))
        log_a1 = ls_candidate - ls + float(log_q_ratio)
        if np.isfinite(log_a1) and np.log(rng.random()) < min(0.0, log_a1):
            accepted1[index] = True
            lf_candidate = float(log_density(candidate))
            # Christen-Fox correction; proposal ratio already appears in stage 1.
            log_a2 = (lf_candidate - lf) - (ls_candidate - ls)
            if np.isfinite(log_a2) and np.log(rng.random()) < min(0.0, log_a2):
                accepted2[index] = True
                state, lf, ls = candidate, lf_candidate, ls_candidate
        states[index] = state
        full[index] = lf
        surrogate[index] = ls
        kinds[index] = kind
    return DelayedAcceptanceTrace(
        draws=states[n_warmup:].copy(),
        warmup=states[:n_warmup].copy(),
        initial_state=initial,
        stage1_accepted=accepted1,
        stage2_accepted=accepted2,
        proposal_kind=kinds,
        full_log_density=full,
        surrogate_log_density=surrogate,
        seed=seed,
        wall_seconds=perf_counter() - started,
    )
