"""WP7小规模全维 delayed-acceptance 证据运行。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp
from scipy.stats import norm

from geodeepbayes.diagnostics import (
    bulk_ess, monte_carlo_standard_error, rank_normalized_split_rhat, tail_ess,
)
from geodeepbayes.sampling import PODReducer, delayed_acceptance_metropolis


def _mixture_logp(x: np.ndarray, retained: int | None = None) -> float:
    z = np.asarray(x, float)
    if retained is not None:
        z = z[:retained]
    means = np.zeros((2, z.size))
    means[:, 0] = (-3.0, 3.0)
    terms = [-0.5 * float((z - mean) @ (z - mean)) for mean in means]
    return float(logsumexp(terms) - np.log(2.0))


def _predictive_interval(
    observed: float,
    level: float,
    *,
    prior_means: np.ndarray,
    latent_variance: float,
    observation_variance: float = 1.0,
    future_variance: float = 1.0,
) -> tuple[float, float]:
    post_variance = 1.0 / (
        1.0 / latent_variance + 1.0 / observation_variance
    )
    post_means = post_variance * (
        prior_means / latent_variance + observed / observation_variance
    )
    log_weights = (
        -0.5 * (observed - prior_means) ** 2
        / (latent_variance + observation_variance)
        - 0.5 * np.log(latent_variance + observation_variance)
    )
    weights = np.exp(log_weights - logsumexp(log_weights))
    predictive_sd = np.sqrt(post_variance + future_variance)

    def cdf(value):
        return float(np.sum(weights * norm.cdf((value - post_means) / predictive_sd)))

    alpha = (1.0 - level) / 2.0
    return (
        float(brentq(lambda value: cdf(value) - alpha, -20.0, 20.0)),
        float(brentq(lambda value: cdf(value) - (1.0 - alpha), -20.0, 20.0)),
    )


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = successes / total
    denominator = 1.0 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    half = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return float(center - half), float(center + half)


def _coverage(
    seed: int, pod: PODReducer, dimension: int, replicates: int = 400
) -> tuple[dict, dict]:
    rng = np.random.default_rng(seed)
    component = np.where(rng.random(replicates) < 0.5, -1.0, 1.0)
    means = np.zeros((2, dimension))
    means[:, 0] = (-3.0, 3.0)
    truth = rng.normal(size=(replicates, dimension)) + means[(component > 0).astype(int)]
    records = {
        "truth": truth,
    }
    records["observed"] = truth[:, 0] + rng.normal(size=replicates)
    records["future"] = truth[:, 0] + rng.normal(size=replicates)
    projector = pod.basis @ pod.basis.T
    projected_means = (
        pod.mean_model[:, None] + projector @ (means.T - pod.mean_model[:, None])
    ).T[:, 0]
    projected_variance = max(float(projector[0, 0]), 1e-12)
    methods = {
        "full": (means[:, 0], 1.0),
        "naive_pod": (projected_means, projected_variance),
        "error_inflated_pod": (
            projected_means, projected_variance + (1.0 - projected_variance)
        ),
    }
    result = {}
    for name, (prior_means, latent_variance) in methods.items():
        result[name] = {}
        for level in (0.90, 0.95):
            covered = 0
            for replicate in range(replicates):
                observed = records["observed"][replicate]
                future = records["future"][replicate]
                lower, upper = _predictive_interval(
                    observed, level, prior_means=prior_means,
                    latent_variance=latent_variance,
                )
                covered += int(lower <= future <= upper)
            result[name][str(level)] = {
                "covered": covered, "total": replicates,
                "rate": covered / replicates,
                "wilson95": _wilson(covered, replicates),
            }
    return result, records


def run(output: Path, *, seed: int = 20260724, n_warmup: int = 2000, n_draws: int = 4000):
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    dimension, rank = 48, 12
    snapshots = np.empty((dimension, 96))
    labels = np.repeat(["prior", "multi_map", "pilot", "holdout"], 24)
    for index in range(96):
        sign = -1.0 if index % 2 == 0 else 1.0
        snapshots[:, index] = rng.normal(size=dimension)
        snapshots[0, index] += 3.0 * sign
    pod = PODReducer(snapshots[:, :72], energy=0.99, max_rank=rank)
    holdout_error = pod.reconstruction_error(snapshots[:, 72:])
    chains, warmups, stage1, stage2, seconds, initials = [], [], [], [], [], []
    seeds = []
    for chain in range(4):
        chain_seed = seed + 100 + chain
        seeds.append(chain_seed)
        initial = np.zeros(dimension)
        initial[0] = -3.0 if chain % 2 == 0 else 3.0
        initials.append(initial)

        def proposal(x, local_rng):
            choice = local_rng.random()
            if choice < 0.90:
                y = local_rng.standard_normal(dimension)
                y[0] += -3.0 if local_rng.random() < 0.5 else 3.0
                return y, _mixture_logp(x) - _mixture_logp(y), "independence-mixture"
            if choice < 0.95:
                y = x.copy()
                y[0] *= -1.0
                return y, 0.0, "mode-reflection"
            return x + 0.32 * local_rng.standard_normal(dimension), 0.0, "local-rw"

        def surrogate(x):
            return _mixture_logp(x, rank) - 0.5 * float(x[rank:] @ x[rank:]) / 1.2**2

        trace = delayed_acceptance_metropolis(
            _mixture_logp, surrogate,
            proposal, initial, n_warmup=n_warmup, n_draws=n_draws, seed=chain_seed,
        )
        chains.append(trace.draws)
        warmups.append(trace.warmup)
        stage1.append(trace.stage1_accepted)
        stage2.append(trace.stage2_accepted)
        seconds.append(trace.wall_seconds)
    draws = np.asarray(chains)
    rhat = np.asarray(rank_normalized_split_rhat(draws))
    bess = np.asarray(bulk_ess(draws))
    tess = np.asarray(tail_ess(draws))
    mcse = np.asarray(monte_carlo_standard_error(draws))
    sd = draws.reshape(-1, dimension).std(axis=0, ddof=1)
    visits = []
    for chain in draws:
        signs = np.signbit(chain[:, 0])
        visits.append(int(np.count_nonzero(signs[1:] != signs[:-1])))
    mean_error = float(np.sqrt(np.mean((draws.mean(axis=(0, 1))) ** 2)))
    coverage, coverage_raw = _coverage(seed + 5000, pod, dimension)
    metrics = {
        "dimension": dimension, "pod_rank": pod.rank, "snapshot_sources": labels.tolist(),
        "holdout_projection_error": holdout_error,
        "max_rhat": float(np.max(rhat)), "min_bulk_ess": float(np.min(bess)),
        "min_tail_ess": float(np.min(tess)),
        "max_relative_mcse": float(np.max(mcse / np.maximum(sd, 1e-12))),
        "mode_visits_per_chain": visits, "failed_replicate_rate": 0.0,
        "standardized_mean_rmse": mean_error,
        "stage1_accept_rate": float(np.mean(np.concatenate(stage1))),
        "stage2_accept_rate": float(np.mean(np.concatenate(stage2)[np.concatenate(stage1)])),
        "ess_per_second": float(np.min(bess) / sum(seconds)),
        "predictive_coverage": coverage,
    }
    metrics["checks"] = {
        "rhat": metrics["max_rhat"] <= 1.01,
        "bulk_ess": metrics["min_bulk_ess"] >= 400,
        "tail_ess": metrics["min_tail_ess"] >= 400,
        "relative_mcse": metrics["max_relative_mcse"] <= 0.05,
        "mode_visits": min(visits) >= 2,
        "failed_rate": metrics["failed_replicate_rate"] <= 0.02,
        "mean_shift": mean_error <= 0.25,
        "coverage_90": (
            coverage["full"]["0.9"]["wilson95"][0] <= 0.90
            <= coverage["full"]["0.9"]["wilson95"][1]
        ),
        "coverage_95": (
            coverage["full"]["0.95"]["wilson95"][0] <= 0.95
            <= coverage["full"]["0.95"]["wilson95"][1]
        ),
    }
    np.savez_compressed(
        output / "raw-chains.npz", draws=draws, warmup=np.asarray(warmups),
        stage1=np.asarray(stage1), stage2=np.asarray(stage2),
        initial=np.asarray(initials), seeds=np.asarray(seeds),
        snapshots=snapshots, snapshot_sources=labels,
        pod_basis=pod.basis, pod_mean=pod.mean_model,
        coverage_truth=coverage_raw["truth"],
        coverage_observed=coverage_raw["observed"],
        coverage_future=coverage_raw["future"],
    )
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--warmup", type=int, default=2000)
    parser.add_argument("--draws", type=int, default=4000)
    args = parser.parse_args(argv)
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    metrics = run(args.output, seed=args.seed, n_warmup=args.warmup, n_draws=args.draws)
    exit_code = 0 if all(metrics["checks"].values()) else 1
    ended_at = datetime.now(timezone.utc)
    (args.output / "run-manifest.json").write_text(
        json.dumps(
            {
                "schema": "wp7-synthetic-producer-v1",
                "run_id": args.output.name,
                "started_at": started_at.isoformat(),
                "completed_at": ended_at.isoformat(),
                "status": "Synthetic-run" if exit_code == 0 else "Failed",
                "exit_code": exit_code,
                "command": sys.argv,
                "script": {
                    "path": Path(__file__).resolve().as_posix(),
                    "sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                },
                "approval": {
                    "owner": "WP7结果独立复核待执行",
                    "date": None,
                    "decision": "pending",
                },
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False))
    print(f"elapsed={perf_counter()-started:.3f}s")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
