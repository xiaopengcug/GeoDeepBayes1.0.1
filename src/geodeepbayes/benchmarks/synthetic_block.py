"""小块状重力模型端到端链路验证 (审查意见02 / F)。

链路: 合成数据 → MAP(LSQR+Tikhonov) → POD 降维 → 自适应 MH 采样 →
收敛诊断(R̂/ESS/MCSE) → k-NN 信息增益(posterior vs 弱先验)。

证据状态: Synthetic-run（端到端链路验证, 审批 pending）。本脚本仅验证
"代码链路贯通与诊断可达 R̂<1.05、ESS>100", 不构成完整 benchmark（需算力）
或矿区验证（需真实数据）。

用法:
    python -m geodeepbayes.benchmarks.synthetic_block --output <run_dir>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
from scipy.sparse.linalg import lsmr

from geodeepbayes.forward import GravityOperator
from geodeepbayes.sampling import AdaptiveMetropolis, PODReducer
from geodeepbayes.diagnostics import rank_normalized_split_rhat, bulk_ess, monte_carlo_standard_error
from geodeepbayes.divergence import knn_kl_divergence


def build_model(seed=20260717):
    """构造小块状重力模型: 10×10×5=500 单元, 中央密度异常块。"""
    from discretize import TensorMesh
    mesh = TensorMesh([10 * [50.0], 10 * [50.0], 5 * [50.0]],
                      origin=[0.0, -250.0, -250.0])
    ind_active = mesh.cell_centers[:, 2] <= -1e-9
    m_true = np.zeros(mesh.n_cells)
    # 中央块 (索引), density contrast 500 kg/m³ (≈0.5 g/cc)
    cc = mesh.cell_centers
    block = (
        (cc[:, 0] > 150) & (cc[:, 0] < 350) &
        (cc[:, 1] > -100) & (cc[:, 1] < 100) &
        (cc[:, 2] > -150) & (cc[:, 2] < -50)
    )
    m_true[block] = 500.0
    # 地表观测点 6×6
    x = np.linspace(50.0, 450.0, 6)
    y = np.linspace(-200.0, 200.0, 6)
    xx, yy = np.meshgrid(x, y)
    rx = np.c_[xx.ravel(), yy.ravel(), np.full(36, 10.0)]
    return mesh, ind_active, m_true, rx


def sensitivity_matrix(op):
    """显式构造 G (n_data, n_param)。优先 getJ, 回退逐列 jvp。"""
    m0 = np.zeros(op.n_param)
    try:
        J = op.simulation.getJ(np.zeros(op.mesh.n_cells))
        if isinstance(J, np.ndarray) and J.shape == (op.n_data, op.n_param):
            return J
    except Exception:
        pass
    cols = []
    eye = np.eye(op.n_param)
    for i in range(op.n_param):
        cols.append(op.jvp(eye[:, i]))
    return np.column_stack(cols)


def run(output_dir, seed=20260717, n_draws=1500, n_warmup=800, n_chains=4, noise_pct=0.02):
    rng = np.random.default_rng(seed)
    mesh, ind_active, m_true, rx = build_model(seed=seed)
    op = GravityOperator(mesh, rx, "gz", ind_active)
    G = sensitivity_matrix(op)                       # (n_data, n_param)
    d_true = op.forward(m_true[ind_active])
    sigma = noise_pct * (np.abs(d_true).max() + 1e-12)
    d_obs = d_true + rng.normal(0.0, sigma, size=d_true.shape)

    # MAP: Tikhonov 正则化 LSQR  min ||d-Gm||² + α||m||²
    alpha_reg = 1.0
    A = np.vstack([G, np.sqrt(alpha_reg) * np.eye(op.n_param)])
    b = np.concatenate([d_obs, np.zeros(op.n_param)])
    sol = lsmr(A, b, atol=1e-9, btol=1e-9, maxiter=2000)
    m_map = sol[0]
    map_misfit = float(np.linalg.norm(d_obs - G @ m_map) / np.linalg.norm(d_obs))

    # POD: MAP 周围 16 个平滑扰动快照
    n_snap = 16
    snaps = np.zeros((op.n_param, n_snap))
    snaps[:, 0] = m_map
    smooth = rng.standard_normal((op.n_param, n_snap - 1))
    # 列归一化后施加平滑（用相邻平均近似低通）
    for j in range(n_snap - 1):
        v = smooth[:, j].reshape(10, 10, 5).mean(axis=(0, 1), keepdims=False)
        v2 = np.broadcast_to(v[None, None, :], (10, 10, 5)).ravel()
        snaps[:, j + 1] = m_map + 50.0 * (v2 - v2.mean())
    pod = PODReducer(snaps, energy=0.999, max_rank=6)

    # 后验定义: 高斯似然 + 弱先验, 在 POD 空间
    def log_post(alpha):
        m = pod.reconstruct(alpha)
        r = d_obs - G @ m
        return -0.5 * np.dot(r, r) / (sigma ** 2) - 0.5 * np.dot(alpha, alpha)

    chains_alpha = []
    for c in range(n_chains):
        init = rng.standard_normal(pod.rank) * 0.3
        s = AdaptiveMetropolis(log_post, pod.rank, init=init, rng=rng, target_accept=0.234)
        draws, info = s.sample(n_draws, n_warmup=n_warmup)
        chains_alpha.append(draws)
    chains_alpha = np.asarray(chains_alpha)         # (n_chains, n_draws, rank)

    rhat = rank_normalized_split_rhat(chains_alpha)
    ess = bulk_ess(chains_alpha)
    mcse = monte_carlo_standard_error(chains_alpha)
    # 信息增益: 后验 alpha vs 弱先验 N(0, I) 样本
    prior_samples = rng.standard_normal((n_chains * n_draws, pod.rank))
    post_flat = chains_alpha.reshape(-1, pod.rank)
    ig_knn = knn_kl_divergence(post_flat, prior_samples, k=5)

    metrics = {
        "evidence_id": "EVD-ALGO-002",
        "status": "Synthetic-run",
        "approval": {"decision": "pending", "reason": "端到端链路验证, 未人工审批"},
        "config": {
            "mesh_cells": int(mesh.n_cells),
            "n_param": int(op.n_param),
            "n_data": int(op.n_data),
            "pod_rank": int(pod.rank),
            "pod_energy_retained": float(pod.energy_retained),
            "n_chains": n_chains, "n_draws": n_draws, "n_warmup": n_warmup,
            "noise_pct": noise_pct, "alpha_reg": alpha_reg, "seed": seed,
        },
        "metrics": {
            "map_misfit": map_misfit,
            "max_rhat": float(np.max(rhat)),
            "min_ess": float(np.min(ess)),
            "max_mcse": float(np.max(mcse)),
            "info_gain_knn_nats": float(ig_knn),
        },
        "checks": {
            "rhat_below_1.05": bool(np.all(rhat < 1.05)),
            "ess_above_100": bool(np.all(ess > 100)),
            "map_misfit_reasonable": bool(map_misfit < 0.5),
        },
        "notes": ("端到端链路验证（合成）: 不构成完整 benchmark（需算力）或矿区验证（需真实数据）。"
                  "POD 在 MAP 周围局部构造, 实际 MCMC 应扩充快照来源以避免子空间偏差（审查意见01/03:95）。"),
        "generated_at": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    # run-manifest（简化, 不强求符合 evidence-run schema 的全字段）
    script_text = Path(__file__).read_text(encoding="utf-8")
    manifest = {
        "script": str(Path(__file__)),
        "script_sha256": hashlib.sha256(script_text.encode()).hexdigest(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {"simpeg": _pkg_version("simpeg"), "numpy": _pkg_version("numpy"),
                     "scipy": _pkg_version("scipy")},
        "started_at": metrics["generated_at"],
    }
    (out / "run-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics


def _pkg_version(name):
    try:
        import importlib.metadata as md
        return md.version(name)
    except Exception:
        return "unknown"


def main(argv=None):
    p = argparse.ArgumentParser(description="小块状重力端到端链路验证")
    p.add_argument("--output", default=None, help="run 输出目录")
    p.add_argument("--seed", type=int, default=20260717)
    args = p.parse_args(argv)
    # 2026-08-02 文档治理：src 已随验证代码迁入治理档案，parents[3] 即档案根。
    out_dir = args.output or str(
        Path(__file__).resolve().parents[3] / "validation" /
        "runs" / f"synthetic-block-{_dt.datetime.utcnow().strftime('%Y%m%d')}")
    m = run(out_dir, seed=args.seed)
    print(json.dumps(m, indent=2, ensure_ascii=False))
    ok = all(m["checks"].values())
    print("\n链路验证:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
