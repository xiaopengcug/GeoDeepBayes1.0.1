"""WP7预注册数值规则；runner与独立validator共用定义、独立实现重算。"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RidgeTrial:
    alpha: float
    solution: np.ndarray
    prediction: np.ndarray
    residual: np.ndarray
    normalized_rms: float
    model_rmse: float
    effective_df: float
    gcv: float
    solution_norm: float
    residual_norm: float


def ridge_gcv_path(
    matrix: np.ndarray,
    data: np.ndarray,
    sigma: np.ndarray | float,
    truth: np.ndarray,
    alphas: tuple[float, ...],
) -> list[RidgeTrial]:
    """Compute the complete whitened ridge path and exact data-space GCV."""
    G = np.asarray(matrix, float)
    d = np.asarray(data, float)
    target = np.asarray(truth, float)
    if G.ndim != 2 or d.ndim != 1 or d.size == 0 or G.shape[0] != d.size:
        raise ValueError("matrix/data dimensions are inconsistent or empty")
    if target.shape != (G.shape[1],):
        raise ValueError("truth must match the matrix parameter dimension")
    if not alphas:
        raise ValueError("at least one alpha is required")
    s = np.broadcast_to(np.asarray(sigma, float), d.shape)
    if np.any(s <= 0):
        raise ValueError("sigma must be strictly positive")
    Gw, dw = G / s[:, None], d / s
    singular = np.linalg.svd(Gw, compute_uv=False)
    gram = Gw.T @ Gw
    rhs = Gw.T @ dw
    trials = []
    for alpha in alphas:
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        model = np.linalg.solve(gram + alpha * np.eye(G.shape[1]), rhs)
        prediction = G @ model
        residual = prediction - d
        weighted = residual / s
        rss = float(weighted @ weighted)
        df = float(np.sum(singular**2 / (singular**2 + alpha)))
        denominator = max(1.0 - df / d.size, np.finfo(float).eps)
        trials.append(RidgeTrial(
            alpha=float(alpha),
            solution=model,
            prediction=prediction,
            residual=residual,
            normalized_rms=float(np.sqrt(np.mean(weighted**2))),
            model_rmse=float(np.sqrt(np.mean((model - target) ** 2))),
            effective_df=df,
            gcv=float((rss / d.size) / denominator**2),
            solution_norm=float(np.linalg.norm(model)),
            residual_norm=float(np.linalg.norm(weighted)),
        ))
    return trials


def select_gcv_stronger_tie_break(trials: list[RidgeTrial], tolerance: float = 0.01) -> RidgeTrial:
    if not trials:
        raise ValueError("at least one trial is required")
    minimum = min(item.gcv for item in trials)
    eligible = [item for item in trials if item.gcv <= (1.0 + tolerance) * minimum]
    return max(eligible, key=lambda item: item.alpha)


def acceptance_flags(
    *,
    stop_code: int,
    iterations: int,
    iteration_limit: int,
    values_finite: bool,
    normalized_rms: float,
    model_rmse: float,
    zero_model_rmse: float,
) -> dict[str, bool]:
    return {
        "solver_converged": bool(
            stop_code in (1, 2) and iterations < iteration_limit and values_finite
        ),
        "data_fit_accepted": bool(0.5 <= normalized_rms <= 1.2),
        "model_recovery_accepted": bool(model_rmse <= 0.95 * zero_model_rmse),
    }
