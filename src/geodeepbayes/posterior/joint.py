"""联合后验装配（EVD-JOINT-001 设计 §3/§5，v1.1-frozen）。

式 2.3-WP1-1 的本实验实例（条件独立乘积的合法性 = 条件于共享潜变量 ξ_g）：

    log p(θ|d) = log N(d_g; G_g(ξ_g)m_ρ, s_ρ²C_g) + log N(d_m; G_m(ξ_g)m_χ, s_χ²C_m)
               + log p_str(m_ρ, m_χ; λ_gm) + log p_GMRF(m_ρ) + log p_GMRF(m_χ)
               + log p(ξ_g) + log p(s_ρ) + log p(s_χ) + const

状态布局：θ = (m_ρ[n], m_χ[n], ξ_g[3], η_ρ, η_χ)，η_k = log s_k，
维度 2n+5（本实验 n=500 → 1005；设计文档 §3「500+500+3+1+1=1010」为算术
笔误，冻结纪律下不改设计文档，登记于 M1 实现报告设计偏差节）。

关键实现事实：
- 正演核经 kernel_provider 依赖注入（本模块不 import SimPEG），按 ξ_g 缓存；
  缓存键为 ξ 的字节表示——块A 期间 ξ 不变故命中，块B 接受后重建。
- C_k 只支持对角结构（设计 §2：Σ_k=D_k R D_k，R=I）。
- GMRF：log p ∝ −β_k/2·‖Lm_k‖² − ε_r/2·‖m_k‖²，L 为面相邻一阶差分，
  ridge ε_r>0 仅保证 proper（处理常数零模），pilot 取小值。
- 噪声尺度乘子 s_k 在 log 空间采样：η_k ~ N(0, 0.25²) ⇔ s_k ~ LogNormal(0, 0.25²)。
- ξ_g 均匀盒先验（水平 ±15 m、垂直 ±3 m，v1.1 修订量程），出界 log p = −∞。
- 广义贝叶斯加权臂（weighted=True）：log p_w = w_g·ll_g + w_m·ll_m + 先验，
  w_k(θ) = [share_k + ε_w]^α，share_k = ‖C_k(s_k)^{-1/2}G_k(ξ_g)‖_F²/Σ_j(·)，
  α=1、ε_w=0.01 冻结；白化协方差随采样节点 s_k（D-E2 批准解释）。
- MAP：块坐标上升——m 块（λ=0 精确二次型闭式解；λ>0 闭式热启动 +
  L-BFGS-B 解析梯度）与 (ξ,η) 块（L-BFGS-B 数值梯度）交替；
  pin_eta 支持 η 钉死的条件 MAP（DA 代理中心，见 find_map 文档串）。
- Laplace 代理：H = 两似然 GN Hessian + GMRF 精度 + 交叉梯度 GN 半正定块
  + η 解析曲率 + ξ 数值 GN 块；m-ξ/η 交叉块置零（GN 残差二阶项忽略，
  属工程近似，已记录）。H 加微小 jitter 保证 Cholesky 可分解。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
from scipy.optimize import minimize

from ..priors.cross_gradient import CrossGradientPenalty

#: 冻结注册值（设计 §3；M3 manifest 冻结项）
XI_BOUNDS_HORIZONTAL_M = 15.0   # ξ_gx, ξ_gy ~ U[−15, 15] m（v1.1）
XI_BOUNDS_VERTICAL_M = 3.0      # ξ_gz ~ U[−3, 3] m（v1.1 修订）
S_LOG_SIGMA = 0.25              # s_k ~ LogNormal(0, 0.25²)
WEIGHT_ALPHA = 1.0              # 广义贝叶斯权重指数
WEIGHT_EPS = 0.01               # 广义贝叶斯权重地板

#: η 的优化器数值防护界（非先验截断；±4 已距先验中心 16σ）
_ETA_OPT_BOUNDS = (-4.0, 4.0)


def build_first_difference_operator(shape_cells, ind_active=None) -> sp.csr_matrix:
    """面相邻一阶差分算子 L（GMRF 平滑先验用）。

    每条内部面一行：L[e, c⁺]=+1、L[e, c⁻]=−1（c⁺ 为轴正向邻居）。
    仅活动单元参与；行列均在活动单元空间。

    Parameters
    ----------
    shape_cells : (nx, ny, nz)
    ind_active : (n_cells,) bool ndarray | None，None 表示全部活动
    """
    nx, ny, nz = (int(v) for v in shape_cells)
    n_cells = nx * ny * nz
    if ind_active is None:
        ind_active = np.ones(n_cells, dtype=bool)
    ind_active = np.asarray(ind_active, dtype=bool)
    active_index = -np.ones(n_cells, dtype=int)
    active_index[ind_active] = np.arange(int(ind_active.sum()))
    rows, cols, vals = [], [], []
    e = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                c = i + nx * (j + ny * k)
                ac = active_index[c]
                if ac < 0:
                    continue
                for delta in (1, nx, nx * ny):
                    cn = c + delta
                    # 轴正向邻居须同轴相邻（防跨边界环绕）
                    if delta == 1 and i == nx - 1:
                        continue
                    if delta == nx and j == ny - 1:
                        continue
                    if delta == nx * ny and k == nz - 1:
                        continue
                    an = active_index[cn]
                    if an < 0:
                        continue
                    rows += [e, e]
                    cols += [ac, an]
                    vals += [-1.0, 1.0]
                    e += 1
    n_act = int(ind_active.sum())
    return sp.csr_matrix((vals, (rows, cols)), shape=(e, n_act))


class JointPosterior:
    """重力 gz + 磁法 TMI 共平台联合后验（设计 §3）。

    Parameters
    ----------
    data_g, data_m : (n_data,) ndarray
        观测数据（mGal / nT），在名义站位测得（推断侧只见名义站位）。
    noise_var_g, noise_var_m : (n_data,) ndarray
        冻结噪声结构 C_k 的对角线（设计 §2：Σ_k=D_k R D_k，R=I）；
        推断协方差为 s_k²·C_k。
    diff_op : (n_edges, n_act) csr_matrix
        GMRF 一阶差分算子 L。
    cross_gradient : CrossGradientPenalty
        交叉梯度惩罚（λ=0 即关闭臂）。
    kernel_provider : callable(xi=(3,)) -> (G_g, G_m)
        在偏移后站位（名义+ξ_g）求值的正演核矩阵工厂。
    beta_rho, beta_chi : float
        GMRF 平滑精度。
    eps_ridge : float
        ridge ε_r>0（保证 proper）。
    xi_bounds : (3, 2) ndarray | None
        ξ_g 均匀先验盒；None 用冻结注册值（±15/±15/±3 m）。
    s_log_sigma : float
        η_k = log s_k 的正态先验 sd（0.25 冻结）。
    weighted : bool
        True 启用广义贝叶斯权重臂（端点(ii) 两臂）；False 为主后验 w≡1。
    weight_alpha, weight_eps : float
        权重公式冻结参数（α=1、ε_w=0.01）。
    """

    def __init__(self, *, data_g, data_m, noise_var_g, noise_var_m,
                 diff_op, cross_gradient: CrossGradientPenalty,
                 kernel_provider, beta_rho, beta_chi, eps_ridge,
                 xi_bounds=None, s_log_sigma=S_LOG_SIGMA,
                 weighted=False, weight_alpha=WEIGHT_ALPHA,
                 weight_eps=WEIGHT_EPS):
        self.data_g = np.asarray(data_g, dtype=float)
        self.data_m = np.asarray(data_m, dtype=float)
        self.noise_var_g = np.asarray(noise_var_g, dtype=float)
        self.noise_var_m = np.asarray(noise_var_m, dtype=float)
        if self.data_g.shape != self.noise_var_g.shape:
            raise ValueError("data_g 与 noise_var_g 形状不一致")
        if self.data_m.shape != self.noise_var_m.shape:
            raise ValueError("data_m 与 noise_var_m 形状不一致")
        if np.any(self.noise_var_g <= 0) or np.any(self.noise_var_m <= 0):
            raise ValueError("噪声方差必须严格为正")
        self.diff_op = sp.csr_matrix(diff_op)
        self.cross_gradient = cross_gradient
        self.kernel_provider = kernel_provider
        self.beta_rho = float(beta_rho)
        self.beta_chi = float(beta_chi)
        self.eps_ridge = float(eps_ridge)
        if min(self.beta_rho, self.beta_chi, self.eps_ridge) <= 0:
            raise ValueError("β_k 与 ε_r 必须为正（proper 先验）")
        if xi_bounds is None:
            xi_bounds = np.array([
                [-XI_BOUNDS_HORIZONTAL_M, XI_BOUNDS_HORIZONTAL_M],
                [-XI_BOUNDS_HORIZONTAL_M, XI_BOUNDS_HORIZONTAL_M],
                [-XI_BOUNDS_VERTICAL_M, XI_BOUNDS_VERTICAL_M],
            ])
        self.xi_bounds = np.asarray(xi_bounds, dtype=float)
        if self.xi_bounds.shape != (3, 2) or np.any(self.xi_bounds[:, 0] >= self.xi_bounds[:, 1]):
            raise ValueError("xi_bounds 须为 (3,2) 且下界<上界")
        self.s_log_sigma = float(s_log_sigma)
        self.weighted = bool(weighted)
        self.weight_alpha = float(weight_alpha)
        self.weight_eps = float(weight_eps)
        self.n_act = int(self.diff_op.shape[1])
        if self.cross_gradient.n_param != self.n_act:
            raise ValueError("差分算子与交叉梯度的活动单元数不一致")
        self.dim = 2 * self.n_act + 5
        # GMRF 精度矩阵（稀疏，预组装）
        lt_l = self.diff_op.T @ self.diff_op
        eye = sp.identity(self.n_act, format="csr")
        self._prec_rho = self.beta_rho * lt_l + self.eps_ridge * eye
        self._prec_chi = self.beta_chi * lt_l + self.eps_ridge * eye
        self._kernel_cache: dict[bytes, tuple[np.ndarray, np.ndarray, float, float]] = {}

    # ------------------------------------------------------------------ 状态

    def unpack(self, theta):
        """θ → (m_ρ, m_χ, ξ_g, η)。η = (log s_ρ, log s_χ)。"""
        theta = np.asarray(theta, dtype=float)
        if theta.shape != (self.dim,):
            raise ValueError(f"状态维度须为 {self.dim}，实际 {theta.shape}")
        n = self.n_act
        return theta[:n], theta[n:2 * n], theta[2 * n:2 * n + 3], theta[2 * n + 3:]

    def pack(self, m_rho, m_chi, xi, eta):
        return np.concatenate([m_rho, m_chi, xi, eta])

    # ------------------------------------------------------------------ 核缓存

    def kernels(self, xi):
        """G_k(ξ_g) 带缓存求值；同时返回两核的 whitened Frobenius 平方。

        返回 (G_g, G_m, frob_g, frob_m)，frob_k = ‖C_k^{-1/2} G_k‖_F²
        （不随 s_k 的部分；s_k 缩放调用方处理，D-E2 批准解释）。
        """
        xi = np.asarray(xi, dtype=float)
        key = xi.tobytes()
        hit = self._kernel_cache.get(key)
        if hit is None:
            G_g, G_m = self.kernel_provider(xi)
            G_g = np.asarray(G_g, dtype=float)
            G_m = np.asarray(G_m, dtype=float)
            if G_g.shape != (self.data_g.size, self.n_act):
                raise ValueError(f"G_g 形状 {G_g.shape} 与数据/参数维不符")
            if G_m.shape != (self.data_m.size, self.n_act):
                raise ValueError(f"G_m 形状 {G_m.shape} 与数据/参数维不符")
            frob_g = float(np.sum(G_g * G_g / self.noise_var_g[:, None]))
            frob_m = float(np.sum(G_m * G_m / self.noise_var_m[:, None]))
            hit = (G_g, G_m, frob_g, frob_m)
            self._kernel_cache[key] = hit
        return hit

    # ------------------------------------------------------------------ 部件

    def _log_gaussian_diag(self, data, pred, s, noise_var) -> float:
        """log N(d; pred, s²·diag(noise_var))，含归一化项。"""
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            r = data - pred
            s2 = s * s
            q = float(np.sum(r * r / noise_var)) / s2
            out = -0.5 * (q + float(np.sum(np.log(noise_var)))
                          + data.size * (2.0 * np.log(s) + np.log(2.0 * np.pi)))
        return float(out) if np.isfinite(out) else -np.inf

    def weights(self, theta):
        """广义贝叶斯权重 (w_g, w_m)（weighted=False 时恒 (1,1)）。

        w_k(θ)=[share_k+ε_w]^α；share_k=(‖C_k^{-1/2}G_k‖_F²/s_k²)/Σ_j(·)。
        """
        if not self.weighted:
            return 1.0, 1.0
        m_rho, m_chi, xi, eta = self.unpack(theta)
        _, _, frob_g, frob_m = self.kernels(xi)
        a_g = frob_g / np.exp(2.0 * eta[0])
        a_m = frob_m / np.exp(2.0 * eta[1])
        total = a_g + a_m
        if not np.isfinite(total) or total <= 0:
            return 0.0, 0.0
        share_g, share_m = a_g / total, a_m / total
        return (
            float((share_g + self.weight_eps) ** self.weight_alpha),
            float((share_m + self.weight_eps) ** self.weight_alpha),
        )

    def terms(self, theta) -> dict:
        """分解求值（测试/调试用）。ξ 出界返回 dict(log_density=-inf)。"""
        m_rho, m_chi, xi, eta = self.unpack(theta)
        lo, hi = self.xi_bounds[:, 0], self.xi_bounds[:, 1]
        if not np.all(np.isfinite(theta)):
            return {"log_density": -np.inf}
        if np.any(xi < lo) or np.any(xi > hi):
            return {"log_density": -np.inf, "xi_out_of_bounds": True}
        G_g, G_m, _, _ = self.kernels(xi)
        s_rho, s_chi = np.exp(eta[0]), np.exp(eta[1])
        ll_g = self._log_gaussian_diag(self.data_g, G_g @ m_rho, s_rho, self.noise_var_g)
        ll_m = self._log_gaussian_diag(self.data_m, G_m @ m_chi, s_chi, self.noise_var_m)
        gmrf_rho = -0.5 * float(m_rho @ (self._prec_rho @ m_rho))
        gmrf_chi = -0.5 * float(m_chi @ (self._prec_chi @ m_chi))
        cg = self.cross_gradient.log_prior(m_rho, m_chi)
        eta_var = self.s_log_sigma ** 2
        eta_prior = -0.5 * float(eta @ eta) / eta_var
        w_g, w_m = self.weights(theta)
        total = w_g * ll_g + w_m * ll_m + gmrf_rho + gmrf_chi + cg + eta_prior
        out = {
            "log_density": float(total),
            "loglik_g": ll_g, "loglik_m": ll_m,
            "gmrf_rho": gmrf_rho, "gmrf_chi": gmrf_chi,
            "cross_gradient": cg, "xi_prior": 0.0, "eta_prior": eta_prior,
            "w_g": w_g, "w_m": w_m,
        }
        return out

    def log_density(self, theta) -> float:
        return self.terms(theta)["log_density"]

    def whitened_residuals(self, theta):
        """共站白化残差 (r̃_g, r̃_m)：r̃ = (d−Gm)/(s_k·√C_k)（端点(ii) T_gm 用）。"""
        m_rho, m_chi, xi, eta = self.unpack(theta)
        G_g, G_m, _, _ = self.kernels(xi)
        r_g = (self.data_g - G_g @ m_rho) / (np.exp(eta[0]) * np.sqrt(self.noise_var_g))
        r_m = (self.data_m - G_m @ m_chi) / (np.exp(eta[1]) * np.sqrt(self.noise_var_m))
        return r_g, r_m

    def grad_m(self, theta):
        """对 (m_ρ, m_χ) 的解析梯度（1000 维；ξ、η 固定）。"""
        m_rho, m_chi, xi, eta = self.unpack(theta)
        G_g, G_m, _, _ = self.kernels(xi)
        w_g, w_m = self.weights(theta)
        s2_rho = np.exp(2.0 * eta[0])
        s2_chi = np.exp(2.0 * eta[1])
        r_g = self.data_g - G_g @ m_rho
        r_m = self.data_m - G_m @ m_chi
        g_rho = w_g * (G_g.T @ (r_g / self.noise_var_g)) / s2_rho
        g_chi = w_m * (G_m.T @ (r_m / self.noise_var_m)) / s2_chi
        g_rho -= self._prec_rho @ m_rho
        g_chi -= self._prec_chi @ m_chi
        cg_rho, cg_chi = self.cross_gradient.log_prior_gradient(m_rho, m_chi)
        return np.concatenate([g_rho + cg_rho, g_chi + cg_chi])


@dataclass(frozen=True)
class MapResult:
    """联合 MAP 估计结果（坐标上升）。"""
    theta: np.ndarray
    log_density: float
    converged: bool
    n_outer: int
    history: tuple  # 每外层轮 (log_density,) 记录


def _m_block_closed_form(posterior: JointPosterior, theta: np.ndarray) -> np.ndarray:
    """m 块条件最优的闭式解（λ=0 时 m 块目标为精确二次型）。

    A_k = (w_k/s_k²)·G̃_kᵀG̃_k + Q_k，b_k = (w_k/s_k²)·G̃_kᵀd̃_k，
    G̃/d̃ 为 C_k^{-1/2} 白化量。w_k 不依赖 m（仅依赖 ξ、η），故该二次型
    对加权臂同样精确。λ>0 时交叉梯度项使目标偏离二次型，本解作热启动。
    """
    from scipy.linalg import cho_factor, cho_solve

    _, _, xi, eta = posterior.unpack(theta)
    G_g, G_m, _, _ = posterior.kernels(xi)
    w_g, w_m = posterior.weights(theta)
    a_g = w_g / np.exp(2.0 * eta[0])
    a_m = w_m / np.exp(2.0 * eta[1])
    wg = G_g / np.sqrt(posterior.noise_var_g)[:, None]
    wm = G_m / np.sqrt(posterior.noise_var_m)[:, None]
    a_r = a_g * (wg.T @ wg) + posterior._prec_rho.toarray()
    a_c = a_m * (wm.T @ wm) + posterior._prec_chi.toarray()
    b_r = a_g * (wg.T @ (posterior.data_g / np.sqrt(posterior.noise_var_g)))
    b_c = a_m * (wm.T @ (posterior.data_m / np.sqrt(posterior.noise_var_m)))
    return np.concatenate([
        cho_solve(cho_factor(a_r), b_r),
        cho_solve(cho_factor(a_c), b_c),
    ])


def find_map(posterior: JointPosterior, theta0, *, max_outer=30,
             tol_logp=1e-6, m_maxiter=400, xi_eta_maxiter=200,
             pin_eta=None) -> MapResult:
    """联合 MAP：m 块与 (ξ,η) 块坐标上升交替。

    m 块：λ=0 时目标为精确二次型，用闭式 Cholesky 解（单步到位）；
    λ>0 时先以 λ=0 闭式解热启动，再 L-BFGS-B（解析梯度，含交叉梯度
    双二次项）。(ξ,η) 块：L-BFGS-B 数值梯度，ξ 受均匀盒约束、η 有数值
    防护界 ±4（非先验截断，距先验中心 16σ）。

    pin_eta : (2,) float | None
        若非 None，η 钉死于给定值（块B 只优化 ξ）。用途：pilot 标定证据
        （marginal_eta_evidence，M2 正式落盘 evaluation/marginal-eta-evidence.json）
        表明自由 η 的联合 MAP 塌缩到噪声插值尖峰（II 型 ML 病态），DA 代理
        中心改取 η=0 的条件 MAP（设计 §5「联合 MAP」文本的实现层偏差，
        登记于 M1 实现报告设计偏差节）。
        代理只需合理且处处有限——DA 第二阶段保证采样目标精确。
    """
    theta = np.asarray(theta0, dtype=float).copy()
    n = posterior.n_act
    if pin_eta is not None:
        pin_eta = np.asarray(pin_eta, dtype=float)
        if pin_eta.shape != (2,):
            raise ValueError("pin_eta 须为 (2,) 或 None")
        theta[2 * n + 3:] = pin_eta
    if not np.isfinite(posterior.log_density(theta)):
        raise ValueError("MAP 初值 log-density 非有限")
    history = []
    prev = -np.inf

    def neg_m(m_vec):
        theta[:n * 2] = m_vec
        val = -posterior.log_density(theta)
        grad = -posterior.grad_m(theta)
        if not np.isfinite(val):
            return 1e300, np.zeros_like(m_vec)
        return val, grad

    def neg_xi_eta(v):
        theta[2 * n:] = v
        val = -posterior.log_density(theta)
        return val if np.isfinite(val) else 1e300

    def neg_xi(v):
        theta[2 * n:2 * n + 3] = v
        val = -posterior.log_density(theta)
        return val if np.isfinite(val) else 1e300

    xi_bounds = [(posterior.xi_bounds[j, 0], posterior.xi_bounds[j, 1])
                 for j in range(3)]
    bounds = xi_bounds + [_ETA_OPT_BOUNDS, _ETA_OPT_BOUNDS]
    lam = float(posterior.cross_gradient.lam)

    converged = False
    for outer in range(int(max_outer)):
        if lam == 0.0:
            theta[:n * 2] = _m_block_closed_form(posterior, theta)
        else:
            if outer == 0:
                theta[:n * 2] = _m_block_closed_form(posterior, theta)  # 热启动
            sol_m = minimize(neg_m, theta[:n * 2].copy(), method="L-BFGS-B",
                             jac=True, options={"maxiter": int(m_maxiter)})
            theta[:n * 2] = sol_m.x
        if pin_eta is None:
            sol_v = minimize(neg_xi_eta, theta[2 * n:].copy(), method="L-BFGS-B",
                             bounds=bounds, options={"maxiter": int(xi_eta_maxiter)})
            theta[2 * n:] = sol_v.x
        else:
            sol_v = minimize(neg_xi, theta[2 * n:2 * n + 3].copy(),
                             method="L-BFGS-B", bounds=xi_bounds,
                             options={"maxiter": int(xi_eta_maxiter)})
            theta[2 * n:2 * n + 3] = sol_v.x
            theta[2 * n + 3:] = pin_eta
        lp = posterior.log_density(theta)
        history.append(float(lp))
        if np.isfinite(prev) and (lp - prev) <= tol_logp * max(1.0, abs(prev)):
            converged = True
            break
        prev = lp
    # 收尾抛光：循环末 ξ 块移动过 G，返回点须对 m 块最优（Laplace 中心性质）
    if lam == 0.0:
        theta[:n * 2] = _m_block_closed_form(posterior, theta)
    else:
        sol_m = minimize(neg_m, theta[:n * 2].copy(), method="L-BFGS-B",
                         jac=True, options={"maxiter": int(m_maxiter)})
        theta[:n * 2] = sol_m.x
    lp = float(posterior.log_density(theta))
    history.append(lp)
    return MapResult(theta=theta.copy(), log_density=lp,
                     converged=converged, n_outer=len(history) - 1,
                     history=tuple(history))


class LaplaceApproximation:
    """联合 MAP 处 Laplace 二次近似（DA 代理 + 提议协方差）。

    log q(θ) = −½(θ−θ̂)ᵀ H (θ−θ̂)（常数省略，DA 只用差值）。
    H = LLᵀ；子块独立提议采样用 H 块对角结构（m 块 / (ξ,η) 块）。
    """

    def __init__(self, theta_map: np.ndarray, hessian: np.ndarray):
        self.theta_map = np.asarray(theta_map, dtype=float)
        self.hessian = np.asarray(hessian, dtype=float)
        if self.hessian.shape != (self.theta_map.size,) * 2:
            raise ValueError("Hessian 形状与 MAP 维度不符")
        self.chol = np.linalg.cholesky(self.hessian)

    def log_density(self, theta) -> float:
        d = np.asarray(theta, dtype=float) - self.theta_map
        return -0.5 * float(d @ (self.hessian @ d))

    def sample_block(self, block_slice, rng) -> np.ndarray:
        """从子块边缘 N(θ̂_block, H_block⁻¹) 采样（块对角近似）。"""
        from scipy.linalg import solve_triangular

        h_block = self.hessian[np.ix_(block_slice, block_slice)]
        chol = np.linalg.cholesky(h_block)
        z = rng.standard_normal(len(block_slice))
        return self.theta_map[block_slice] + solve_triangular(
            chol.T, z, lower=False)

    def log_block_density(self, theta_block, block_slice) -> float:
        d = np.asarray(theta_block, dtype=float) - self.theta_map[block_slice]
        h_block = self.hessian[np.ix_(block_slice, block_slice)]
        return -0.5 * float(d @ (h_block @ d))


def build_laplace(posterior: JointPosterior, theta_map,
                  xi_fd_eps=(1.0, 1.0, 0.2)) -> LaplaceApproximation:
    """组装 Laplace Hessian（设计 §5：两似然 GN + 先验精度 + 耦合 MAP 线性化）。

    - m 块：G_kᵀ(s_k²C_k)⁻¹G_k + GMRF 精度 + 交叉梯度 GN 半正定块；
      加权臂冻结 w_k 于 MAP 点缩放似然块（近似，记录）。
    - ξ 块：数值灵敏度 Jξ_k = ∂(G_k m̂_k)/∂ξ（中心差分，步长 ξ_fd_eps）
      的 whitened GN：H_ξξ = Σ_k J̃_kᵀJ̃_k。
    - η 块（对角）：2·Q̃_k + 1/σ_η²，Q̃_k = 白化残差平方和（MAP 处）。
    - 交叉块（m-ξ、m-η、ξ-η）置零：GN 残差二阶项忽略（工程近似，记录）。
    - 加 jitter = 1e-9·mean(diag H)·I 保证 Cholesky。
    """
    theta_map = np.asarray(theta_map, dtype=float)
    n = posterior.n_act
    m_rho, m_chi, xi, eta = posterior.unpack(theta_map)
    G_g, G_m, _, _ = posterior.kernels(xi)
    w_g, w_m = posterior.weights(theta_map)
    s2_rho = np.exp(2.0 * eta[0])
    s2_chi = np.exp(2.0 * eta[1])

    # m 块（dense 2n×2n）
    wg = G_g / np.sqrt(posterior.noise_var_g)[:, None]
    wm = G_m / np.sqrt(posterior.noise_var_m)[:, None]
    h_rr = (wg.T @ wg) * (w_g / s2_rho) + posterior._prec_rho.toarray()
    h_mm = (wm.T @ wm) * (w_m / s2_chi) + posterior._prec_chi.toarray()
    cg_rr, cg_mm = posterior.cross_gradient.gauss_newton_blocks(m_rho, m_chi)
    h_rr = h_rr + cg_rr.toarray()
    h_mm = h_mm + cg_mm.toarray()

    # ξ 块（数值 GN）：H_ξξ = J̃ᵀJ̃，J̃ 为白化灵敏度 ∂(Gm̂)/∂ξ/(s√C)
    eps = np.asarray(xi_fd_eps, dtype=float)
    j_cols = []
    for j in range(3):
        step = np.zeros(3)
        step[j] = eps[j]
        g_plus = posterior.kernels(xi + step)
        g_minus = posterior.kernels(xi - step)
        j_g = (g_plus[0] @ m_rho - g_minus[0] @ m_rho) / (2.0 * eps[j])
        j_m = (g_plus[1] @ m_chi - g_minus[1] @ m_chi) / (2.0 * eps[j])
        j_cols.append(np.concatenate([
            j_g / (np.exp(eta[0]) * np.sqrt(posterior.noise_var_g)),
            j_m / (np.exp(eta[1]) * np.sqrt(posterior.noise_var_m)),
        ]))
    j_tilde = np.column_stack(j_cols)
    h_xi = j_tilde.T @ j_tilde

    # η 块（对角解析）
    r_g, r_m = posterior.whitened_residuals(theta_map)
    q_g = float(r_g @ r_g)
    q_m = float(r_m @ r_m)
    h_eta = np.diag([2.0 * q_g + 1.0 / posterior.s_log_sigma ** 2,
                     2.0 * q_m + 1.0 / posterior.s_log_sigma ** 2])

    hessian = np.zeros((posterior.dim, posterior.dim))
    hessian[:n, :n] = h_rr
    hessian[n:2 * n, n:2 * n] = h_mm
    hessian[2 * n:2 * n + 3, 2 * n:2 * n + 3] = h_xi
    hessian[2 * n + 3:, 2 * n + 3:] = h_eta
    jitter = 1e-9 * float(np.mean(np.diag(hessian)))
    hessian += jitter * np.eye(posterior.dim)
    return LaplaceApproximation(theta_map, hessian)
