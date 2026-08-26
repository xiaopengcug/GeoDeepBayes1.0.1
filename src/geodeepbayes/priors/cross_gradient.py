"""交叉梯度软耦合惩罚项（EVD-JOINT-001 设计 §3，v1.1-frozen）。

语料式(6) 的恒等变换实例（ρ_d 有号、χ 含零不可取 log）：

    u_ρ = m_ρ / s_ρ*，u_χ = m_χ / s_χ*（冻结尺度 s_ρ*=0.5 g/cm³、s_χ*=0.05 SI）
    q_ij(x) ≡ 1
    p_str ∝ exp(−λ_gm · Σ_cells ‖∇u_ρ × ∇u_χ‖² · V_cell)

梯度在规则 TensorMesh 上用单元中心差分近似：内部单元中心差分 (u⁺−u⁻)/(2Δ)，
边界单元退化为单边差分 (u⁺−u)/Δ。差分算子是线性的，故"处处平行梯度零罚"
与差分格式无关（u_χ = c·u_ρ ⇒ Du_χ = c·Du_ρ ⇒ 叉积恒为零）。

惩罚值对单位重参数化不变：m 与对应冻结尺度同步缩放时 u 不变、惩罚不变；
但对 u 本身不是零次齐次（叉积为双线性、惩罚为四次齐次），设计据此冻结
s_ρ*/s_χ* 而不做自适应缩放。

解析梯度（逐单元向量 a=∇u_ρ、b=∇u_χ、c=a×b，利用 |a×b|²=|a|²|b|²−(a·b)²）：

    ∂‖c‖²/∂a = 2(b×c)，  ∂‖c‖²/∂b = 2(c×a)

再经差分算子转置链式回到单元场上，最后除以冻结尺度还原到 m 空间。
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

#: 冻结归一化尺度（设计 §3；M3 manifest 冻结项，此处为注册默认值）
S_RHO_STAR_G_CM3 = 0.5   # g/cm³
S_CHI_STAR_SI = 0.05     # SI


def _axis_difference(n_cells_axis: int, spacing: float) -> sp.csr_matrix:
    """单轴单元中心差分（内部中心差分、边界单边差分）。

    返回 (n_cells_axis, n_cells_axis) 稀疏矩阵，作用于按该轴排列的场。
    """
    rows, cols, vals = [], [], []
    for i in range(n_cells_axis):
        if i == 0:
            rows += [i, i]
            cols += [i, i + 1]
            vals += [-1.0 / spacing, 1.0 / spacing]
        elif i == n_cells_axis - 1:
            rows += [i, i]
            cols += [i - 1, i]
            vals += [-1.0 / spacing, 1.0 / spacing]
        else:
            rows += [i, i]
            cols += [i - 1, i + 1]
            half = 0.5 / spacing
            vals += [-half, half]
    return sp.csr_matrix(
        (vals, (rows, cols)), shape=(n_cells_axis, n_cells_axis)
    )


def build_cell_gradient_operators(mesh, ind_active=None):
    """构造单元中心梯度差分算子 (Dx, Dy, Dz)，作用于活动单元向量。

    仅支持规则 TensorMesh（等距三轴）。活动单元掩膜用于从全网格向量空间
    压缩到活动空间；不活动的邻居视同缺失（该方向退化为可用的单边差分，
    两侧邻居均缺失时该单元该方向梯度行为零行）。

    Returns
    -------
    (Dx, Dy, Dz) : tuple of (n_active, n_active) csr_matrix
    """
    if ind_active is None:
        ind_active = np.ones(mesh.n_cells, dtype=bool)
    ind_active = np.asarray(ind_active, dtype=bool)
    nx, ny, nz = mesh.shape_cells
    hx = np.asarray(mesh.h[0], dtype=float)
    hy = np.asarray(mesh.h[1], dtype=float)
    hz = np.asarray(mesh.h[2], dtype=float)
    if not (np.allclose(hx, hx[0]) and np.allclose(hy, hy[0]) and np.allclose(hz, hz[0])):
        raise ValueError("交叉梯度差分算子仅支持等距 TensorMesh")
    # discretize 默认 x 最快序：cell (i,j,k) → i + nx*(j + ny*k)
    active_index = -np.ones(mesh.n_cells, dtype=int)
    active_index[ind_active] = np.arange(int(ind_active.sum()))
    n_act = int(ind_active.sum())

    def _build_axis(axis: int, spacing: float) -> sp.csr_matrix:
        rows, cols, vals = [], [], []

        def emit(center: int, lo: int, hi: int) -> None:
            """向 rows/cols/vals 追加一行：中心单元的该方向差分。"""
            a = active_index[center]
            if a < 0:
                return
            alo = active_index[lo] if lo is not None else -1
            ahi = active_index[hi] if hi is not None else -1
            if alo >= 0 and ahi >= 0:
                rows.extend((a, a))
                cols.extend((alo, ahi))
                vals.extend((-0.5 / spacing, 0.5 / spacing))
            elif ahi >= 0:
                rows.extend((a, a))
                cols.extend((a, ahi))
                vals.extend((-1.0 / spacing, 1.0 / spacing))
            elif alo >= 0:
                rows.extend((a, a))
                cols.extend((alo, a))
                vals.extend((-1.0 / spacing, 1.0 / spacing))
            # 两侧皆缺失 → 零行（不追加）

        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    c = i + nx * (j + ny * k)
                    if axis == 0:
                        lo = c - 1 if i > 0 else None
                        hi = c + 1 if i < nx - 1 else None
                    elif axis == 1:
                        lo = c - nx if j > 0 else None
                        hi = c + nx if j < ny - 1 else None
                    else:
                        lo = c - nx * ny if k > 0 else None
                        hi = c + nx * ny if k < nz - 1 else None
                    emit(c, lo, hi)
        return sp.csr_matrix((vals, (rows, cols)), shape=(n_act, n_act))

    return (
        _build_axis(0, float(hx[0])),
        _build_axis(1, float(hy[0])),
        _build_axis(2, float(hz[0])),
    )


class CrossGradientPenalty:
    """交叉梯度软耦合惩罚 P = λ Σ_cells ‖∇u_ρ × ∇u_χ‖² V_cell。

    Parameters
    ----------
    mesh : discretize.TensorMesh
        规则等距网格。
    ind_active : (n_cells,) bool ndarray | None
        活动单元掩膜；None 表示全部活动。输入场向量长度 = 活动单元数。
    s_rho_star : float，默认 0.5
        密度对比冻结归一化尺度（g/cm³）。
    s_chi_star : float，默认 0.05
        磁化率冻结归一化尺度（SI）。
    lam : float，默认 0.0
        耦合强度 λ_gm；0 为语料登记的关闭态基线臂。
    """

    def __init__(self, mesh, ind_active=None, s_rho_star=S_RHO_STAR_G_CM3,
                 s_chi_star=S_CHI_STAR_SI, lam=0.0):
        self.mesh = mesh
        if ind_active is None:
            ind_active = np.ones(mesh.n_cells, dtype=bool)
        self.ind_active = np.asarray(ind_active, dtype=bool)
        self.n_param = int(self.ind_active.sum())
        self.s_rho_star = float(s_rho_star)
        self.s_chi_star = float(s_chi_star)
        self.lam = float(lam)
        if self.s_rho_star <= 0 or self.s_chi_star <= 0:
            raise ValueError("冻结尺度必须为正")
        if self.lam < 0:
            raise ValueError("耦合强度 λ 必须非负")
        self.dx, self.dy, self.dz = build_cell_gradient_operators(mesh, self.ind_active)
        self.cell_volumes = np.asarray(mesh.cell_volumes, dtype=float)[self.ind_active]

    def _check_pair(self, m_rho, m_chi):
        m_rho = np.asarray(m_rho, dtype=float)
        m_chi = np.asarray(m_chi, dtype=float)
        if m_rho.shape != (self.n_param,) or m_chi.shape != (self.n_param,):
            raise ValueError(
                f"物性场长度须为活动单元数 {self.n_param}，"
                f"实际 {m_rho.shape} / {m_chi.shape}"
            )
        return m_rho, m_chi

    def _gradients(self, m_rho, m_chi):
        """返回 (a, b)：u_ρ 与 u_χ 的单元中心梯度，各 (n_param, 3)。"""
        u_rho = m_rho / self.s_rho_star
        u_chi = m_chi / self.s_chi_star
        a = np.column_stack([self.dx @ u_rho, self.dy @ u_rho, self.dz @ u_rho])
        b = np.column_stack([self.dx @ u_chi, self.dy @ u_chi, self.dz @ u_chi])
        return a, b

    def value(self, m_rho, m_chi) -> float:
        """惩罚值 P（含 λ 与 V_cell 权重）。log p_str = −P。"""
        m_rho, m_chi = self._check_pair(m_rho, m_chi)
        a, b = self._gradients(m_rho, m_chi)
        c = np.cross(a, b)
        return float(self.lam * np.sum(self.cell_volumes * np.sum(c * c, axis=1)))

    def gradient(self, m_rho, m_chi):
        """解析梯度 (∂P/∂m_ρ, ∂P/∂m_χ)，各 (n_param,)。"""
        m_rho, m_chi = self._check_pair(m_rho, m_chi)
        a, b = self._gradients(m_rho, m_chi)
        c = np.cross(a, b)
        # ∂P/∂u_ρ = 2λ Σ_dir D_dirᵀ (V·(b×c)_dir)；∂P/∂u_χ 同构用 (c×a)
        bc = np.cross(b, c)
        ca = np.cross(c, a)
        ops = (self.dx, self.dy, self.dz)
        grad_u_rho = sum(op.T @ (self.cell_volumes * bc[:, d]) for d, op in enumerate(ops))
        grad_u_chi = sum(op.T @ (self.cell_volumes * ca[:, d]) for d, op in enumerate(ops))
        factor = 2.0 * self.lam
        return (
            factor * grad_u_rho / self.s_rho_star,
            factor * grad_u_chi / self.s_chi_star,
        )

    def log_prior(self, m_rho, m_chi) -> float:
        """非归一化对数结构先验 −P（Z(λ) 不可解，按设计登记 EB 冻结）。"""
        return -self.value(m_rho, m_chi)

    def log_prior_gradient(self, m_rho, m_chi):
        """log p_str 的解析梯度（= −∂P/∂m）。"""
        g_rho, g_chi = self.gradient(m_rho, m_chi)
        return -g_rho, -g_chi

    def gauss_newton_blocks(self, m_rho, m_chi):
        """惩罚 Hessian 在当前的 Gauss-Newton 半正定块（Laplace 代理用）。

        对 a=∇u_ρ：∂²‖c‖²/∂a_s∂a_t = 2(|b|²δ_st − b_s b_t)（半正定）；
        对 b 同构。返回 (H_rr, H_mm) 两个 (n_param, n_param) 稀疏矩阵，
        分别为 ∂²P/∂m_ρ² 与 ∂²P/∂m_χ² 的半正定近似；交叉块按 GN 线性化
        置零（含不定号项，见设计 §5 "耦合在 MAP 线性化"）。
        """
        m_rho, m_chi = self._check_pair(m_rho, m_chi)
        a, b = self._gradients(m_rho, m_chi)
        ops = (self.dx, self.dy, self.dz)

        def _block(g, s_star):
            g_sq = np.sum(g * g, axis=1)
            h = None
            for s in range(3):
                for t in range(3):
                    weight = self.cell_volumes * (
                        (g_sq if s == t else 0.0) - g[:, s] * g[:, t]
                    )
                    term = ops[s].T @ sp.diags(weight) @ ops[t]
                    h = term if h is None else h + term
            return 2.0 * self.lam * h / (s_star * s_star)

        return _block(b, self.s_rho_star), _block(a, self.s_chi_star)
