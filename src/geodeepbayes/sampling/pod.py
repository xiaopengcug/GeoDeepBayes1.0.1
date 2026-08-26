"""本征正交分解 (POD) 降维与代理误差传播框架。

POD: 从模型快照矩阵经截断 SVD 得到正交基 Φ_r，模型参数化 m ≈ m̄ + Φ_r α（低维 α）。

误差传播框架（审查意见02 / E3）：在独立留出快照集上报告
  - 投影误差 ‖m − Φ_r Φ_rᵀ (m − m̄)‖
  - 似然误差 ‖F(m) − F(Φ_r Φ_rᵀ m)‖（正演层面的代理偏差）
  - 后验偏移（k-NN KL）：代理后验 vs 原始后验（需采样器，本模块提供接口）

并提供二阶段延迟接受（delayed acceptance）骨架：先用 POD 投影上的廉价后验筛选，
再以原始正演做精确接受校正，避免把代理后验当作原始后验。
"""
from __future__ import annotations

import numpy as np


class PODReducer:
    """POD 降维器（截断 SVD，Eckart–Young 最优）。

    Parameters
    ----------
    snapshots : (n_params, n_snapshots) ndarray
        模型快照矩阵，**行=参数、列=快照**（POD 通常 n_params ≫ n_snapshots）。
    energy : float, 默认 0.95
        累计奇异值能量保留比。
    max_rank : int | None
        最大秩上限。
    mean_model : (n_params,) | None
        参考模型；默认为快照列均值。
    """

    def __init__(self, snapshots, energy=0.95, max_rank=None, mean_model=None):
        S = np.asarray(snapshots, dtype=float)
        if S.ndim != 2:
            raise ValueError("snapshots 须为 2D (n_params, n_snapshots)")
        self.n_params, self.n_snap = S.shape
        self.mean_model = (S.mean(axis=1) if mean_model is None
                           else np.asarray(mean_model, float))
        Sc = S - self.mean_model[:, None]
        U, sigma, _ = np.linalg.svd(Sc, full_matrices=False)
        total = float(np.sum(sigma ** 2)) + 1e-30
        cum = np.cumsum(sigma ** 2) / total
        r = int(np.searchsorted(cum, energy) + 1)
        if max_rank is not None:
            r = min(r, int(max_rank))
        self.rank = max(1, min(r, len(sigma)))
        self.basis = U[:, : self.rank]            # (n_params, rank)
        self.singular_values = sigma
        self.energy_retained = float(cum[self.rank - 1]) if len(cum) else 1.0

    def encode(self, m):
        return self.basis.T @ (np.asarray(m, float) - self.mean_model)

    def reconstruct(self, alpha):
        return self.mean_model + self.basis @ np.asarray(alpha, float)

    def project(self, m):
        return self.reconstruct(self.encode(np.asarray(m, float)))

    def reconstruction_error(self, holdout):
        """独立留出集平均相对投影误差（L2）。holdout: (n_params, n_holdout)。"""
        H = np.asarray(holdout, float)
        rel = []
        for j in range(H.shape[1]):
            denom = np.linalg.norm(H[:, j]) + 1e-30
            rel.append(np.linalg.norm(H[:, j] - self.project(H[:, j])) / denom)
        return float(np.mean(rel))

    def likelihood_error(self, forward_op, holdout, m_norm=None):
        """留出集平均相对似然误差 ‖F(m) − F(project(m))‖。

        forward_op 须实现 ``forward(m)``（如 GravityOperator/MagneticOperator）。
        holdout: (n_params, n_holdout)。
        """
        H = np.asarray(holdout, float)
        rel = []
        for j in range(H.shape[1]):
            m = H[:, j]
            f_full = np.asarray(forward_op.forward(m))
            f_proj = np.asarray(forward_op.forward(self.project(m)))
            denom = np.linalg.norm(f_full) + 1e-30
            rel.append(np.linalg.norm(f_full - f_proj) / denom)
        return float(np.mean(rel))

    def delayed_acceptance(self, log_post_full, log_post_reduced, proposal_draw, n_steps,
                           rng=None):
        """二阶段延迟接受骨架。

        1) 在 POD 低维空间由 ``proposal_draw(alpha)`` 提议；返回候选值，或
           ``(候选值, log q(alpha|candidate)-log q(candidate|alpha))``；
        2) 以廉价 ``log_post_reduced(alpha)`` 做粗筛；
        3) 通过粗筛者再以 ``log_post_full(m_reconstructed)`` 做精确接受校正。

        本方法仅提供循环骨架，``log_post_full`` 须用原始（非代理）正演；
        调用方负责构造两个后验。返回 (samples_alpha, samples_full, n_stage2)。
        """
        rng = np.random.default_rng(rng)
        alpha = np.zeros(self.rank)
        m_cur = self.reconstruct(alpha)
        lp_r_cur = float(log_post_reduced(alpha))
        lp_f_cur = float(log_post_full(m_cur))
        kept_alpha, kept_full, n2 = [], [], 0
        for _ in range(int(n_steps)):
            proposal = proposal_draw(alpha, rng)
            if isinstance(proposal, tuple):
                a_prop, log_q_reverse_minus_forward = proposal
            else:
                a_prop, log_q_reverse_minus_forward = proposal, 0.0
            a_prop = np.asarray(a_prop, dtype=float)
            lp_r_prop = float(log_post_reduced(a_prop))
            # 第一阶段（廉价）
            if np.log(rng.random()) < (
                lp_r_prop - lp_r_cur + float(log_q_reverse_minus_forward)
            ):
                m_prop = self.reconstruct(a_prop)
                lp_f_prop = float(log_post_full(m_prop))
                n2 += 1
                # 第二阶段校正代理比率。注意：状态仍受限于POD子空间，
                # 因而本方法不能支持“全维后验恢复”主张。
                log_a2 = (lp_f_prop - lp_f_cur) - (lp_r_prop - lp_r_cur)
                if np.log(rng.random()) < log_a2:
                    alpha, m_cur = a_prop, m_prop
                    lp_r_cur, lp_f_cur = lp_r_prop, lp_f_prop
            kept_alpha.append(alpha.copy())
            kept_full.append(m_cur.copy())
        return np.asarray(kept_alpha), np.asarray(kept_full), n2
