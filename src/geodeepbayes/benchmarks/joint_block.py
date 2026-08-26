"""EVD-JOINT-001 联合块体生产器（重力 gz + 磁法 TMI 共平台联合后验）。

实现设计 v1.1-frozen §2（场景规格）、§3（模型与先验）、§5（推断与诊断）；
落盘纪律沿用 synthetic_block_v2.py（metrics.json / run-manifest.json /
原始链 npz / evidence-run-v2.json 哈希清单）。

种子流纪律：pilot 场景族种子基 = 90_000_000（场景 i 用 90_000_000+10_000·i），
与建议的 400 注册场景流（基 20_260_819 + 10_000·i，i=0..399）互斥；
M3 冻结注册流时不得使用 pilot 段。场景内全部随机量由场景种子单 rng 顺序
抽取（场参数 → 诱饵 → ξ_g → 噪声实现），保证同场景配对臂共享同一噪声实现。

盲态程序（单操作员分角色，哈希强制）：generate 阶段冻结真值/噪声/种子入
scene-pack.json（附 SHA-256）；run 阶段只读观测数据 + 名义站位 + 冻结噪声
结构 C_k（C_k 由真值信号幅度构成是设计 §3 裁定的冻结结构，属登记的
same-kernel 性质）；evaluate 阶段解封真值计算预注册指标。

pilot 期 Design-assumption（M3 待冻结，均为本文件常量，运行快照进 manifest）：
β_ρ=100 (g/cm³)⁻²、β_χ=10000 SI⁻²（归一化一阶差分 sd≈0.2）、ε_r=0.01
（仅保证 proper）、ξ_fd_eps=(1,1,0.2) m（Laplace 数值灵敏度步长）。
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

import numpy as np
from scipy.linalg import solve_triangular

from geodeepbayes.diagnostics import (
    bulk_ess,
    monte_carlo_standard_error,
    rank_normalized_split_rhat,
    tail_ess,
)
from geodeepbayes.diagnostics.rhat import (
    _folded_2d,
    _rank_normalize_2d,
    _rhat_basic_2d,
    _split_chains_2d,
)
from geodeepbayes.io.run_contract import RunContract, TaskSpec
from geodeepbayes.posterior import (
    JointPosterior,
    build_first_difference_operator,
    build_laplace,
    find_map,
)
from geodeepbayes.priors import CrossGradientPenalty
from geodeepbayes.sampling import AdaptiveMetropolis, delayed_acceptance_metropolis

# ---------------------------------------------------------------- 冻结/试点常量

MESH_SHAPE = (10, 10, 5)           # 设计 §2：10×10×5 单元
CELL_SIZE_M = 50.0
MESH_ORIGIN = (0.0, -250.0, -250.0)
NOISE_R = 0.02                     # 相对噪声系数 r
NOISE_FLOOR_G_MGAL = 0.02          # a_g 指示值（M3 精确冻结）
NOISE_FLOOR_M_NT = 2.0             # a_m 指示值（M3 精确冻结）
BETA_RHO = 100.0                   # pilot 建议 (g/cm³)⁻²（归一化差分 sd≈0.2）
BETA_CHI = 10000.0                 # pilot 建议 SI⁻²
EPS_RIDGE = 0.01                   # ridge（仅 proper）
XI_FD_EPS = (1.0, 1.0, 0.2)        # Laplace ξ 数值灵敏度步长（m）
PILOT_SEED_BASE = 90_000_000       # pilot 种子段（与注册流互斥）
REGISTRY_SEED_BASE_SUGGESTION = 20_260_819  # 建议注册场景流基（M3 裁定）
SCENE_SEED_STRIDE = 10_000
N_PILOT_SCENARIOS = 5
LAMBDA_GRID = (1.0, 10.0, 100.0, 1000.0, 10000.0)  # 设计 §3 候选网格
N_CHAINS = 4
N_WARMUP = 4000
N_DRAWS = 8000
WARMUP_SEGMENTS = 20               # warmup 分段数（段内提议固定，段间自适应）
BLOCK_B_EVERY = 5                  # 块B 每 5 步一次（设计 §5）
P_INDEP = 0.2                      # 独立提议占比（80/20 混合）
TARGET_ACCEPT = 0.234
INIT_DISPERSION = 1.5              # 链初始过散因子（Laplace 采样 ×1.5）
OVERDISPERSE_NOTE = "链初始=Laplace×1.5 过散采样（pilot 登记，M3 可复审）"
# 场景生成分布（设计 §2；snap 规则见 _snap50 注释，属实现层记录解释）
BLOCK_RHO_RANGE = (0.35, 0.65)     # g/cm³
BLOCK_CHI_RANGE = (0.035, 0.065)   # SI
LENS_CHI_RANGE = (0.08, 0.12)      # SI
LENS_SHAPE_CELLS = (2, 2, 1)       # 诱饵透镜体尺寸 100×100×50 m（设计未指定，保守取）
MULTISTART_N = 8                   # 单峰性判据随机起点数（D-E1 条件 3）

_PAPER_TREE = (
    Path(__file__).resolve().parents[5]
    / "papers" / "paper01-multi-scale-physics-informed-bayesian-fusion"
    / "evd-joint-001" / "design-preregistration.md"
)
_ARCHIVE_ROOT = Path(__file__).resolve().parents[3]
_DIAGNOSTIC_CONTRACT = _ARCHIVE_ROOT / "validation" / "wp2-toy" / "diagnostic-contract.json"


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _json_dump(path: Path, obj) -> str:
    """规范 JSON 落盘（排序键、UTF-8、LF），返回内容 SHA-256。"""
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    data = text.encode("utf-8")
    Path(path).write_bytes(data)
    return _sha256_bytes(data)


def load_diagnostic_thresholds(contract_path: Path | None = None) -> dict:
    """WP2 诊断契约阈值（唯一来源，运行时读取，不复制数值）。"""
    path = Path(contract_path) if contract_path else _DIAGNOSTIC_CONTRACT
    return json.loads(path.read_text(encoding="utf-8"))["thresholds"]


# ---------------------------------------------------------------- 网格与场景

def build_mesh():
    """设计 §2 模型域：10×10×5×50 m，origin (0,−250,−250)，z 为 elevation。"""
    from discretize import TensorMesh

    return TensorMesh(
        [[CELL_SIZE_M] * MESH_SHAPE[0], [CELL_SIZE_M] * MESH_SHAPE[1],
         [CELL_SIZE_M] * MESH_SHAPE[2]],
        origin=list(MESH_ORIGIN),
    )


def nominal_stations() -> np.ndarray:
    """共平台 6×6=36 站名义站位（x∈[50,450]、y∈[−200,200]、z=+10 m）。"""
    x = np.linspace(50.0, 450.0, 6)
    y = np.linspace(-200.0, 200.0, 6)
    xx, yy = np.meshgrid(x, y)
    return np.c_[xx.ravel(), yy.ravel(), np.full(36, 10.0)]


def _snap50(value: float) -> float:
    """连续抽取值对齐到 50 m 单元网格（算术舍入，确定性好复现）。

    设计 §2 给出连续分布而块体以整数单元构成（4×4×2 单元），单元对齐
    是必要离散化：抽取后 snap 到最近格点，原值与 snap 值同存场景包。
    """
    return float(np.floor(value / CELL_SIZE_M + 0.5) * CELL_SIZE_M)


@dataclass(frozen=True)
class Scenario:
    """pilot 场景（真值参数；单元对齐后的 snap 值为实现真值）。"""
    scenario_id: int
    seed: int
    block_cx_raw: float
    block_cy_raw: float
    block_ztop_raw: float
    block_cx: float        # snap 后块中心 x（∈{200,250,300}）
    block_cy: float        # ∈{−50,0,50}
    block_ztop: float      # 顶深（埋深正值，∈{50,100} m）
    block_rho: float       # g/cm³
    block_chi: float       # SI
    lens_cx_raw: float
    lens_cy_raw: float
    lens_ztop_raw: float
    lens_cx: float
    lens_cy: float
    lens_ztop: float       # ∈{0,50} m
    lens_chi: float        # SI
    xi_true: tuple         # (3,) m，逐场景抽取


def generate_scenario(scenario_id: int, seed: int) -> Scenario:
    """按设计 §2 分布抽取单场景（rng 顺序消费，确定性）。

    诱饵透镜体位置与目标块不交叠（单元集合不相交，允许相邻），拒绝重抽
    上限 100 次（几何上极易满足；超限为实现缺陷显式报错）。
    """
    rng = np.random.default_rng(seed)
    cx_raw = float(rng.uniform(200.0, 300.0))
    cy_raw = float(rng.uniform(-75.0, 75.0))
    zt_raw = float(rng.uniform(50.0, 100.0))
    rho = float(rng.uniform(*BLOCK_RHO_RANGE))
    chi = float(rng.uniform(*BLOCK_CHI_RANGE))
    block = (_snap50(cx_raw), _snap50(cy_raw), _snap50(zt_raw))
    lens = None
    for _ in range(100):
        lcx_raw = float(rng.uniform(100.0, 400.0))
        lcy_raw = float(rng.uniform(-150.0, 150.0))
        lzt_raw = float(rng.uniform(0.0, 50.0))
        lchi = float(rng.uniform(*LENS_CHI_RANGE))
        cand = (_snap50(lcx_raw), _snap50(lcy_raw), _snap50(lzt_raw))
        if not _cells_overlap(block, (4, 4, 2), cand, LENS_SHAPE_CELLS):
            lens = (lcx_raw, lcy_raw, lzt_raw, cand[0], cand[1], cand[2], lchi)
            break
    if lens is None:
        raise RuntimeError("诱饵透镜体 100 次重抽仍与目标块交叠（实现缺陷）")
    xi = (
        float(rng.uniform(-15.0, 15.0)),
        float(rng.uniform(-15.0, 15.0)),
        float(rng.uniform(-3.0, 3.0)),
    )
    return Scenario(
        scenario_id=int(scenario_id), seed=int(seed),
        block_cx_raw=cx_raw, block_cy_raw=cy_raw, block_ztop_raw=zt_raw,
        block_cx=block[0], block_cy=block[1], block_ztop=block[2],
        block_rho=rho, block_chi=chi,
        lens_cx_raw=lens[0], lens_cy_raw=lens[1], lens_ztop_raw=lens[2],
        lens_cx=lens[3], lens_cy=lens[4], lens_ztop=lens[5], lens_chi=lens[6],
        xi_true=xi,
    )


def _cells_overlap(center_a, shape_a, center_b, shape_b) -> bool:
    """两轴对齐块（中心+单元数尺寸，50 m 网格）单元集合是否相交。"""
    for axis in range(3):
        half_a = shape_a[axis] * CELL_SIZE_M / 2.0
        half_b = shape_b[axis] * CELL_SIZE_M / 2.0
        lo_a, hi_a = center_a[axis] - half_a, center_a[axis] + half_a
        lo_b, hi_b = center_b[axis] - half_b, center_b[axis] + half_b
        if hi_a <= lo_b or hi_b <= lo_a:
            return False
    return True


def _block_cell_mask(mesh, center, shape_cells, *, depth_positive_down=True) -> np.ndarray:
    """轴对齐块覆盖的活动单元掩膜（全网格布尔）。

    center=(cx, cy, ztop)：ztop 为顶面埋深（正值向下），块体
    z∈[−ztop−h, −ztop]，h=shape_cells[2]·50 m。
    """
    cc = mesh.cell_centers
    half_x = shape_cells[0] * CELL_SIZE_M / 2.0
    half_y = shape_cells[1] * CELL_SIZE_M / 2.0
    z_top = -center[2]
    z_bot = -center[2] - shape_cells[2] * CELL_SIZE_M
    return (
        (cc[:, 0] >= center[0] - half_x - 1e-9) & (cc[:, 0] <= center[0] + half_x + 1e-9)
        & (cc[:, 1] >= center[1] - half_y - 1e-9) & (cc[:, 1] <= center[1] + half_y + 1e-9)
        & (cc[:, 2] >= z_bot - 1e-9) & (cc[:, 2] <= z_top + 1e-9)
    )


def scenario_models(mesh, sc: Scenario):
    """场景 → 真值物性场（全网格）。返回 (m_rho_full, m_chi_full, block_mask, lens_mask)。"""
    m_rho = np.zeros(mesh.n_cells)
    m_chi = np.zeros(mesh.n_cells)
    block = _block_cell_mask(mesh, (sc.block_cx, sc.block_cy, sc.block_ztop), (4, 4, 2))
    lens = _block_cell_mask(mesh, (sc.lens_cx, sc.lens_cy, sc.lens_ztop), LENS_SHAPE_CELLS)
    if np.any(block & lens):
        raise RuntimeError("块与诱饵单元相交（生成约束被破坏）")
    m_rho[block] = sc.block_rho
    m_chi[block] = sc.block_chi
    m_chi[lens] = sc.lens_chi
    return m_rho, m_chi, block, lens


def make_kernel_provider(mesh, rx_nominal, ind_active):
    """ξ_g → (G_g, G_m) 核矩阵工厂（SimPEG 积分法，设计 §3 G_k(ξ_g)）。

    G 经由算子 getJ 显式物化（36×500 dense，毫秒级），供块A 缓存使用。
    """
    from geodeepbayes.forward import GravityOperator, MagneticOperator

    rx_nominal = np.asarray(rx_nominal, dtype=float)

    def provide(xi):
        rx = rx_nominal + np.asarray(xi, dtype=float)[None, :]
        g_op = GravityOperator(mesh, rx, "gz", ind_active)
        m_op = MagneticOperator(mesh, rx, components="tmi", ind_active=ind_active)
        m0 = np.zeros(mesh.n_cells)
        return (
            np.asarray(g_op.simulation.getJ(m0), dtype=float),
            np.asarray(m_op.simulation.getJ(m0), dtype=float),
        )

    return provide


def generate_observations(mesh, sc: Scenario, rng: np.random.Generator):
    """真值正演 + 噪声实现（Σ_k=D_k R D_k，R=I，D_ii²=(r|s_i|)²+a_k²）。

    返回 dict：真站位、真响应、观测、噪声方差对角，以及入地检查结果。
    入地检查（DA 复审 Major #1 兜底）：z_true>0 恒成立（构造保证站高
    ∈[7,13] m）且无站位落入活动单元内部（z>0 ⇒ 位于网格顶面以上域外，
    积分法核对该区域有定义；此处仍逐站显式断言）。
    """
    from geodeepbayes.forward import GravityOperator, MagneticOperator

    ind_active = mesh.cell_centers[:, 2] <= -1e-9
    m_rho, m_chi, _, _ = scenario_models(mesh, sc)
    rx_nominal = nominal_stations()
    xi = np.asarray(sc.xi_true, dtype=float)
    rx_true = rx_nominal + xi[None, :]
    if not np.all(rx_true[:, 2] > 0.0):
        raise RuntimeError(f"场景 {sc.scenario_id}：真实站位入地（z_true≤0）")
    cc = mesh.cell_centers
    for s in range(rx_true.shape[0]):
        inside = (
            (cc[:, 0] >= rx_true[s, 0] - CELL_SIZE_M / 2)
            & (cc[:, 0] < rx_true[s, 0] + CELL_SIZE_M / 2)
            & (cc[:, 1] >= rx_true[s, 1] - CELL_SIZE_M / 2)
            & (cc[:, 1] < rx_true[s, 1] + CELL_SIZE_M / 2)
            & (cc[:, 2] >= rx_true[s, 2] - CELL_SIZE_M / 2)
            & (cc[:, 2] < rx_true[s, 2] + CELL_SIZE_M / 2)
        )
        if np.any(inside):
            raise RuntimeError(f"场景 {sc.scenario_id}：站位 {s} 落入活动单元内部")
    g_op = GravityOperator(mesh, rx_true, "gz", ind_active)
    m_op = MagneticOperator(mesh, rx_true, components="tmi", ind_active=ind_active)
    d_true_g = g_op.forward(m_rho[ind_active])
    d_true_m = m_op.forward(m_chi[ind_active])
    cvar_g = (NOISE_R * np.abs(d_true_g)) ** 2 + NOISE_FLOOR_G_MGAL ** 2
    cvar_m = (NOISE_R * np.abs(d_true_m)) ** 2 + NOISE_FLOOR_M_NT ** 2
    d_obs_g = d_true_g + rng.normal(0.0, np.sqrt(cvar_g))
    d_obs_m = d_true_m + rng.normal(0.0, np.sqrt(cvar_m))
    return {
        "rx_nominal": rx_nominal,
        "rx_true": rx_true,
        "d_true_g": d_true_g,
        "d_true_m": d_true_m,
        "d_obs_g": d_obs_g,
        "d_obs_m": d_obs_m,
        "cvar_g": cvar_g,
        "cvar_m": cvar_m,
        "underground_check": {
            "z_true_min": float(rx_true[:, 2].min()),
            "z_true_max": float(rx_true[:, 2].max()),
            "all_above_ground": bool(np.all(rx_true[:, 2] > 0.0)),
            "no_station_inside_active_cell": True,
        },
    }


#: DA 代理中心钉死的 η 值（s_k≡1，冻结噪声结构的名义信念）。
#: pilot 标定证据（marginal_eta_evidence，M2 正式落盘）：自由 η 的联合 MAP
#: 塌缩到噪声插值尖峰（II 型 ML 病态），代理中心改取 η=0 条件 MAP——采样
#: 目标密度、硬门、先验族、β pilot 值均不变（设计 §5「联合 MAP」文本的实现
#: 层偏差，登记于 M1 实现报告设计偏差节）。
SURROGATE_PIN_ETA = (0.0, 0.0)


def marginal_eta_evidence(posterior: JointPosterior, xi=(0.0, 0.0, 0.0),
                          eta_grid=None) -> dict:
    """λ=0 线性-高斯精确边际 log p(d_k|η)+log p(η)（Woodbury 恒等式）。

    给定 η 时 m 的条件后验为高斯，可解析积分：
    log p(d|η) = −½[q(η) + logdet A(η) − logdet Q + 2n·η]（省略 η 无关常数），
    A = Q + Gᵀ(s²C)⁻¹G。盲态合法（只用 d、C_k、G_k(ξ)、先验精度；ξ 取名义
    0，曲线对 ±15 m 站位偏移不敏感）。用途：登记 DA 代理中心偏差裁定的
    证据——尖峰（η≈−2.2）相对峰值的边际密度差、峰值位置是否落在 s≈1。
    """
    from scipy.linalg import cho_factor, cho_solve

    if eta_grid is None:
        eta_grid = np.linspace(-2.6, 1.0, 19)
    eta_grid = np.asarray(eta_grid, dtype=float)
    G_g, G_m, _, _ = posterior.kernels(np.asarray(xi, dtype=float))

    def _curve(G, d, cvar, prec):
        _, logdet_q = np.linalg.slogdet(prec)
        vals = []
        for e in eta_grid:
            s2 = float(np.exp(2.0 * e))
            w = 1.0 / (s2 * cvar)
            a = prec + (G.T * w) @ G
            chol, low = cho_factor(a)
            logdet_a = 2.0 * float(np.sum(np.log(np.diag(chol))))
            u = cho_solve((chol, low), G.T @ (w * d))
            q = float(d @ (w * d) - (d * w) @ (G @ u))
            vals.append(
                -0.5 * (q + logdet_a - logdet_q + d.size * 2.0 * e)
                - 0.5 * float(e * e) / posterior.s_log_sigma ** 2)
        return np.asarray(vals)

    lg = _curve(G_g, posterior.data_g, posterior.noise_var_g,
                posterior._prec_rho.toarray())
    lm = _curve(G_m, posterior.data_m, posterior.noise_var_m,
                posterior._prec_chi.toarray())
    i_spike = int(np.argmin(np.abs(eta_grid - (-2.2))))
    return {
        "eta_grid": eta_grid.tolist(),
        "log_marginal_g": lg.tolist(),
        "log_marginal_m": lm.tolist(),
        "peak_eta_g": float(eta_grid[int(np.argmax(lg))]),
        "peak_eta_m": float(eta_grid[int(np.argmax(lm))]),
        "spike_drop_nats_at_eta_-2.2": float(
            (lg[i_spike] - lg.max()) + (lm[i_spike] - lm.max())),
        "note": ("完整归一化（含 2n·η 项）；仅 λ=0 精确（λ>0 交叉梯度 "
                 "破坏线性-高斯，机制不变）。峰值≈0 表明后验质量在 s≈1，"
                 "自由 η 联合 MAP 尖峰为低体积病态点。"),
    }


# ---------------------------------------------------------------- 后验与采样

def build_posterior(mesh, obs_view, *, lam, weighted=False, freeze_xi=False,
                    beta_rho=BETA_RHO, beta_chi=BETA_CHI,
                    eps_ridge=EPS_RIDGE) -> JointPosterior:
    """由观测盲态视图装配联合后验（设计 §3）。

    obs_view 只含 d_obs / 名义站位 / 冻结噪声结构 C_k（盲态边界）。
    freeze_xi=True 为端点(ii) 失配臂：ξ_g 均匀盒退化为 [−1e-9,1e-9]³，
    数值上等价 ξ_g≡0（设计：失配臂推断冻结 ξ_g≡0）。
    """
    ind_active = mesh.cell_centers[:, 2] <= -1e-9
    diff_op = build_first_difference_operator(MESH_SHAPE, ind_active)
    cg = CrossGradientPenalty(mesh, ind_active, lam=lam)
    provider = make_kernel_provider(mesh, obs_view["rx_nominal"], ind_active)
    xi_bounds = None
    if freeze_xi:
        xi_bounds = np.array([[-1e-9, 1e-9]] * 3)
    return JointPosterior(
        data_g=obs_view["d_obs_g"], data_m=obs_view["d_obs_m"],
        noise_var_g=obs_view["cvar_g"], noise_var_m=obs_view["cvar_m"],
        diff_op=diff_op, cross_gradient=cg, kernel_provider=provider,
        beta_rho=beta_rho, beta_chi=beta_chi, eps_ridge=eps_ridge,
        xi_bounds=xi_bounds, weighted=weighted,
    )


def make_block_proposal(posterior: JointPosterior, laplace, scale_a, scale_b,
                        *, block_b_every=BLOCK_B_EVERY, p_indep=P_INDEP):
    """子块混合提议（设计 §5）。

    调度：计数器确定性轮换，每 block_b_every 步一次块B (ξ_g, η)，其余为
    块A (m_ρ, m_χ)。块内 80% 预条件 RWMH（Laplace 协方差 Cholesky 白化）
    + 20% 代理子块独立提议。分量各自满足细致平衡、随机混合保持平稳性；
    RWMH 分量 log q 比为 0，独立分量比为子块代理对数密度差。
    """
    n = posterior.n_act
    sl_a = np.arange(0, 2 * n)
    sl_b = np.arange(2 * n, posterior.dim)
    chol_a = np.linalg.cholesky(laplace.hessian[: 2 * n, : 2 * n])
    chol_b = np.linalg.cholesky(laplace.hessian[2 * n:, 2 * n:])
    theta_map = laplace.theta_map
    counter = {"k": 0}

    def proposal(x, rng):
        k = counter["k"]
        counter["k"] = k + 1
        y = x.copy()
        if k % block_b_every == block_b_every - 1:
            z = rng.standard_normal(5)
            if rng.random() < p_indep:
                cand = theta_map[sl_b] + solve_triangular(chol_b.T, z, lower=False)
                y[sl_b] = cand
                # 契约 log_q_reverse_minus_forward = log q(x)−log q(y)
                # = −½‖Lᵀ(x−θ̂)‖² + ½‖Lᵀ(y−θ̂)‖²（F-M2-1：曾实现为相反数）
                dx = chol_b.T @ (x[sl_b] - theta_map[sl_b])
                dy = chol_b.T @ (y[sl_b] - theta_map[sl_b])
                return y, float(0.5 * (dy @ dy - dx @ dx)), "b-indep"
            y[sl_b] = x[sl_b] + scale_b * solve_triangular(chol_b.T, z, lower=False)
            return y, 0.0, "b-rw"
        z = rng.standard_normal(2 * n)
        if rng.random() < p_indep:
            y[sl_a] = theta_map[sl_a] + solve_triangular(chol_a.T, z, lower=False)
            # 契约 log_q_reverse_minus_forward = log q(x)−log q(y)
            # = −½‖Lᵀ(x−θ̂)‖² + ½‖Lᵀ(y−θ̂)‖²（F-M2-1：曾实现为相反数）
            dx = chol_a.T @ (x[sl_a] - theta_map[sl_a])
            dy = chol_a.T @ (y[sl_a] - theta_map[sl_a])
            return y, float(0.5 * (dy @ dy - dx @ dx)), "a-indep"
        y[sl_a] = x[sl_a] + scale_a * solve_triangular(chol_a.T, z, lower=False)
        return y, 0.0, "a-rw"

    return proposal


def run_chain(posterior: JointPosterior, laplace, theta_init, *, seed,
              n_warmup, n_draws):
    """单链：分段 warmup（段内提议冻结满足 DA 框架约束，段间 Robbins-Monro
    diminishing 自适应 scale，γ_seg=(seg+1)^-0.6），生产段提议完全冻结。
    每段均为完整 DA 两阶段调用（设计 §5 语义保持）。
    """
    scale_a, scale_b = 1.0, 1.0
    state = np.asarray(theta_init, dtype=float).copy()
    seg_len = int(n_warmup) // WARMUP_SEGMENTS
    if seg_len < 1:
        raise ValueError("n_warmup 小于分段数")
    warmup_draws = []
    adapt_log = []
    t0 = perf_counter()
    for seg in range(WARMUP_SEGMENTS):
        proposal = make_block_proposal(posterior, laplace, scale_a, scale_b)
        tr = delayed_acceptance_metropolis(
            posterior.log_density, laplace.log_density, proposal, state,
            n_warmup=0, n_draws=seg_len, seed=seed + seg,
        )
        state = tr.draws[-1].copy()
        warmup_draws.append(tr.draws)
        acc = {}
        for kind in ("a-rw", "b-rw"):
            mask = tr.proposal_kind == kind
            acc[kind] = float(np.mean(tr.stage2_accepted[mask])) if np.any(mask) else float("nan")
        gamma = (seg + 1) ** -0.6
        if np.isfinite(acc["a-rw"]):
            scale_a = float(np.clip(
                scale_a * np.exp(gamma * (acc["a-rw"] - TARGET_ACCEPT)), 1e-3, 20.0))
        if np.isfinite(acc["b-rw"]):
            scale_b = float(np.clip(
                scale_b * np.exp(gamma * (acc["b-rw"] - TARGET_ACCEPT)), 1e-3, 20.0))
        adapt_log.append({
            "segment": seg, "scale_a": scale_a, "scale_b": scale_b,
            "accept_a_rw": acc["a-rw"], "accept_b_rw": acc["b-rw"],
            "accept_stage1": float(np.mean(tr.stage1_accepted)),
        })
    warmup_seconds = perf_counter() - t0
    proposal = make_block_proposal(posterior, laplace, scale_a, scale_b)
    t0 = perf_counter()
    prod = delayed_acceptance_metropolis(
        posterior.log_density, laplace.log_density, proposal, state,
        n_warmup=0, n_draws=int(n_draws), seed=seed + 10_000,
    )
    return {
        "draws": prod.draws,
        "warmup": np.concatenate(warmup_draws, axis=0),
        "log_density": prod.full_log_density,
        "stage1_accepted": prod.stage1_accepted,
        "stage2_accepted": prod.stage2_accepted,
        "proposal_kind": prod.proposal_kind,
        "scale_a_final": scale_a,
        "scale_b_final": scale_b,
        "adapt_log": adapt_log,
        "warmup_seconds": warmup_seconds,
        "production_seconds": perf_counter() - t0,
    }


# ---------------------------------------------------------------- 诊断（WP2 契约）

def _rhat_pair(chains) -> tuple[np.ndarray, np.ndarray]:
    """逐通道 (rank-normalized split-R̂, folded split-R̂)。

    复用 diagnostics.rhat 的内部原语（不修改既有模块）：契约 required_fields
    要求两字段分别报告；硬门取 max（validate-wp2.ps1 第 224 行同语义）。
    """
    x = np.asarray(chains, dtype=float)
    if x.ndim == 2:
        x = x[..., None]
    rank_vals, fold_vals = [], []
    for p in range(x.shape[2]):
        sp_x = _split_chains_2d(x[:, :, p])
        rank_vals.append(_rhat_basic_2d(_rank_normalize_2d(sp_x)))
        fold_vals.append(_rhat_basic_2d(_rank_normalize_2d(_folded_2d(sp_x))))
    return np.asarray(rank_vals), np.asarray(fold_vals)


def mode_visits_operationalized(log_density_chains) -> dict:
    """D-E1 批准操作化：每链 post-warmup 平均 log-density 落在合并样本
    共同高密度域（±3 sd，sd 为合并 post-warmup 样本标准差，M3 manifest
    记录口径）内记 1，否则记 0。契约字段字面预设多模态目标，本目标为
    登记单峰设计（run-manifest 披露替代理由）。"""
    arr = np.asarray(log_density_chains, dtype=float)
    chain_means = arr.mean(axis=1)
    pooled_sd = float(arr.std(ddof=1))
    grand = float(chain_means.mean())
    in_domain = np.abs(chain_means - grand) <= 3.0 * pooled_sd
    return {
        "mode_visits_per_chain": [int(v) for v in in_domain],
        "chain_mean_log_density": [float(v) for v in chain_means],
        "pooled_sd": pooled_sd,
        "sd_estimation": "合并 post-warmup 样本（D-E1 条件1口径）",
    }


def _failed_diagnostic_result(
        channels, reason: str, *, nonfinite_input_count: int = 0,
        nonfinite_channels_count: int = 0,
        nonfinite_log_density_count: int = 0,
        nonfinite_diagnostic_count: int = 0,
        nonfinite_diagnostic_fields: list[str] | None = None,
        degenerate_channel_count: int = 0) -> dict:
    """构造保留字段形状的 fail-closed 诊断结果。"""
    n_chains = int(channels.shape[0]) if channels.ndim >= 1 else 0
    n_channels = int(channels.shape[-1]) if channels.ndim >= 1 else 0
    checks = {
        "rhat": False,
        "bulk_ess": False,
        "tail_ess": False,
        "relative_mcse": False,
        "mode_visits": False,
    }
    stop_detail = {
        "reason": reason,
        "nonfinite_channels_count": nonfinite_channels_count,
        "nonfinite_log_density_count": nonfinite_log_density_count,
        "nonfinite_diagnostic_count": nonfinite_diagnostic_count,
        "nonfinite_diagnostic_fields": nonfinite_diagnostic_fields or [],
        "degenerate_channel_count": degenerate_channel_count,
    }
    return {
        "rank_normalized_split_rhat": None,
        "folded_split_rhat": None,
        "bulk_ess": None,
        "tail_ess": None,
        "relative_mcse": None,
        "mode_visits_per_chain": [0] * n_chains,
        "mode_visits_operationalization": stop_detail,
        "failed_replicate_rate": 1.0,
        "status": "Failed",
        "checks": checks,
        "n_channels": n_channels,
        "quantiles": {
            "rhat_max_p99": None,
            "bulk_ess_p01": None,
            "tail_ess_p01": None,
        },
        "diagnostic_stop_reason": reason,
        "nonfinite_input_count": nonfinite_input_count,
        "nonfinite_channels_count": nonfinite_channels_count,
        "nonfinite_log_density_count": nonfinite_log_density_count,
        "nonfinite_diagnostic_count": nonfinite_diagnostic_count,
        "nonfinite_diagnostic_fields": nonfinite_diagnostic_fields or [],
        "degenerate_channel_count": degenerate_channel_count,
    }


def compute_diagnostics(channels, log_density_chains, thresholds) -> dict:
    """诊断域 = 全部状态参数 + F1/F2/F3 泛函 + log-density（channels 已含后两者）。

    channels : (n_chains, n_draws, n_channels)
    """
    channels = np.asarray(channels, dtype=float)
    log_density_chains = np.asarray(log_density_chains, dtype=float)
    nonfinite_channels = int(
        channels.size - np.count_nonzero(np.isfinite(channels)))
    nonfinite_log_density = int(
        log_density_chains.size
        - np.count_nonzero(np.isfinite(log_density_chains)))
    nonfinite_total = nonfinite_channels + nonfinite_log_density
    if nonfinite_total:
        return _failed_diagnostic_result(
            channels,
            "nonfinite_input",
            nonfinite_input_count=nonfinite_total,
            nonfinite_channels_count=nonfinite_channels,
            nonfinite_log_density_count=nonfinite_log_density,
        )
    flat = channels.reshape(-1, channels.shape[-1])
    degenerate_channel_count = int(np.count_nonzero(np.ptp(flat, axis=0) == 0.0))
    if degenerate_channel_count:
        return _failed_diagnostic_result(
            channels,
            "nonfinite_diagnostic",
            nonfinite_diagnostic_count=2 * degenerate_channel_count,
            nonfinite_diagnostic_fields=[
                "rank_normalized_split_rhat",
                "folded_split_rhat",
            ],
            degenerate_channel_count=degenerate_channel_count,
        )
    rank_rhat, fold_rhat = _rhat_pair(channels)
    bess = np.atleast_1d(bulk_ess(channels))
    tess = np.atleast_1d(tail_ess(channels))
    mcse = np.atleast_1d(monte_carlo_standard_error(channels))
    sd = flat.std(axis=0, ddof=1)
    rel_mcse = mcse / np.maximum(sd, 1e-12)
    diagnostic_arrays = {
        "rank_normalized_split_rhat": rank_rhat,
        "folded_split_rhat": fold_rhat,
        "bulk_ess": bess,
        "tail_ess": tess,
        "relative_mcse": rel_mcse,
    }
    nonfinite_diagnostic_fields = []
    nonfinite_diagnostic_count = 0
    for field, values in diagnostic_arrays.items():
        count = int(values.size - np.count_nonzero(np.isfinite(values)))
        if count:
            nonfinite_diagnostic_fields.append(field)
            nonfinite_diagnostic_count += count
    if nonfinite_diagnostic_count:
        return _failed_diagnostic_result(
            channels,
            "nonfinite_diagnostic",
            nonfinite_diagnostic_count=nonfinite_diagnostic_count,
            nonfinite_diagnostic_fields=nonfinite_diagnostic_fields,
        )
    visits = mode_visits_operationalized(log_density_chains)
    checks = {
        "rhat": bool(np.max(np.maximum(rank_rhat, fold_rhat))
                     <= thresholds["rank_normalized_split_rhat_max"]),
        "bulk_ess": bool(np.min(bess) >= thresholds["bulk_ess_min"]),
        "tail_ess": bool(np.min(tess) >= thresholds["tail_ess_min"]),
        "relative_mcse": bool(np.max(rel_mcse) <= thresholds["relative_mcse_max"]),
        "mode_visits": bool(all(v == 1 for v in visits["mode_visits_per_chain"])),
    }
    status = "Passed" if all(checks.values()) else "Failed"
    return {
        "rank_normalized_split_rhat": float(np.max(rank_rhat)),
        "folded_split_rhat": float(np.max(fold_rhat)),
        "bulk_ess": float(np.min(bess)),
        "tail_ess": float(np.min(tess)),
        "relative_mcse": float(np.max(rel_mcse)),
        "mode_visits_per_chain": visits["mode_visits_per_chain"],
        "mode_visits_operationalization": visits,
        "failed_replicate_rate": 0.0,
        "status": status,
        "checks": checks,
        "n_channels": int(channels.shape[-1]),
        "quantiles": {
            "rhat_max_p99": float(np.quantile(np.maximum(rank_rhat, fold_rhat), 0.99)),
            "bulk_ess_p01": float(np.quantile(bess, 0.01)),
            "tail_ess_p01": float(np.quantile(tess, 0.01)),
        },
        "diagnostic_stop_reason": None,
        "nonfinite_input_count": 0,
        "nonfinite_channels_count": 0,
        "nonfinite_log_density_count": 0,
        "nonfinite_diagnostic_count": 0,
        "nonfinite_diagnostic_fields": [],
        "degenerate_channel_count": 0,
    }


# ---------------------------------------------------------------- 具名泛函（设计 §4）

def f3_search_box_mask(mesh, sc: Scenario) -> np.ndarray:
    """F3 冻结搜索盒（全网格布尔）：目标块真值水平范围各扩 ±100 m
    （2 单元缓冲）、深度全域。由冻结真值参数确定性导出，评价阶段解封后
    使用（盲态纪律允许：评价者角色可见真值）。"""
    cc = mesh.cell_centers
    half_x = 4 * CELL_SIZE_M / 2.0 + 100.0
    half_y = 4 * CELL_SIZE_M / 2.0 + 100.0
    return (
        (cc[:, 0] >= sc.block_cx - half_x - 1e-9)
        & (cc[:, 0] <= sc.block_cx + half_x + 1e-9)
        & (cc[:, 1] >= sc.block_cy - half_y - 1e-9)
        & (cc[:, 1] <= sc.block_cy + half_y + 1e-9)
    )


def functional_chains(draws, mesh, sc: Scenario, block_mask_full, box_mask_full):
    """逐 draw 计算具名泛函链 (F1, F2, F3)。

    F1 总异常质量 M=Σ ρ_d·V_cell（kg；g/cm³×m³×1000）；
    F2 目标块平均磁化率 χ̄_block（真值掩膜内）；
    F3 顶深：盒内首个满足 χ ≥ 0.5·max(χ_全网格) 的最浅单元埋深；未触发
    （盒内无单元达全局 max 之半——例如后验把异常放到盒外）回退为盒内
    argmax 深度并记失败标记（失败计入报告，不重抽）。

    返回 (n_draws_total, 3) 与 f3_fallback_rate。draws 可为
    (n_chains, n_draws, dim)，内部展平。
    """
    n = int(np.sum(mesh.cell_centers[:, 2] <= -1e-9))
    x = draws.reshape(-1, draws.shape[-1])
    m_chi_all = x[:, n:2 * n]
    m_rho_all = x[:, :n]
    volumes = mesh.cell_volumes[mesh.cell_centers[:, 2] <= -1e-9]
    block = block_mask_full[mesh.cell_centers[:, 2] <= -1e-9]
    box = box_mask_full[mesh.cell_centers[:, 2] <= -1e-9]
    cc_active = mesh.cell_centers[mesh.cell_centers[:, 2] <= -1e-9]
    depth = -cc_active[:, 2]
    f1 = (m_rho_all * volumes[None, :]).sum(axis=1) * 1000.0
    f2 = m_chi_all[:, block].mean(axis=1)
    box_idx = np.where(box)[0]
    box_depth = depth[box_idx]
    f3 = np.empty(x.shape[0])
    fallback = np.zeros(x.shape[0], dtype=bool)
    for r in range(x.shape[0]):
        chi = m_chi_all[r]
        threshold = 0.5 * float(chi.max())
        hits = box_idx[chi[box_idx] >= threshold]
        if hits.size and threshold > 0:
            f3[r] = float(depth[hits].min())
        else:
            fallback[r] = True
            f3[r] = float(box_depth[np.argmax(chi[box_idx])])
    return (
        np.column_stack([f1, f2, f3]),
        float(fallback.mean()),
    )


def summarize_functionals(func_vals, sc: Scenario, mesh) -> dict:
    """单 run 泛函摘要：后验均值、90% 等尾宽度、真值与误差。"""
    f1_true = sc.block_rho * 1000.0 * 4 * 4 * 2 * CELL_SIZE_M ** 3
    f2_true = sc.block_chi
    f3_true = sc.block_ztop
    out = {}
    for j, (name, truth) in enumerate(
            [("F1_mass_kg", f1_true), ("F2_chi_block", f2_true), ("F3_ztop_m", f3_true)]):
        vals = func_vals[:, j]
        q05, q95 = np.quantile(vals, [0.05, 0.95])
        out[name] = {
            "truth": float(truth),
            "post_mean": float(vals.mean()),
            "error_abs": float(abs(vals.mean() - truth)),
            "ci90_width": float(q95 - q05),
            "ci90": [float(q05), float(q95)],
            "covered_90": bool(q05 <= truth <= q95),
        }
    return out


def analytic_r_xi(mesh, sc: Scenario, obs) -> dict:
    """R_ξ 解析值（设计 §4 端点(ii)：冻结核、真实 m、真实 ξ vs ξ=0）。

    R_ξ = RMS([G(ξ_true)−G(0)]m_true 全 72 数据) / RMS(σ 全 72 数据)。
    """
    ind_active = mesh.cell_centers[:, 2] <= -1e-9
    m_rho, m_chi, _, _ = scenario_models(mesh, sc)
    provider = make_kernel_provider(mesh, obs["rx_nominal"], ind_active)
    xi = np.asarray(sc.xi_true, dtype=float)
    g0, m0 = provider(np.zeros(3))
    g1, m1 = provider(xi)
    delta = np.concatenate([
        g1 @ m_rho[ind_active] - g0 @ m_rho[ind_active],
        m1 @ m_chi[ind_active] - m0 @ m_chi[ind_active],
    ])
    sigma = np.sqrt(np.concatenate([obs["cvar_g"], obs["cvar_m"]]))
    return {
        "r_xi": float(np.sqrt(np.mean(delta ** 2)) / np.sqrt(np.mean(sigma ** 2))),
        "rms_signal_shift": float(np.sqrt(np.mean(delta ** 2))),
        "rms_noise": float(np.sqrt(np.mean(sigma ** 2))),
        "rms_shift_g": float(np.sqrt(np.mean(delta[:36] ** 2))),
        "rms_shift_m": float(np.sqrt(np.mean(delta[36:] ** 2))),
    }


# ---------------------------------------------------------------- 场景包

def generate_pilot_pack(n_scenarios=N_PILOT_SCENARIOS, seed_base=PILOT_SEED_BASE):
    """生成 pilot 场景包（含真值；生成者角色）。返回 (pack dict, mesh)。"""
    mesh = build_mesh()
    ind_active = mesh.cell_centers[:, 2] <= -1e-9
    scenarios = []
    for i in range(int(n_scenarios)):
        seed = seed_base + SCENE_SEED_STRIDE * i
        sc = generate_scenario(i, seed)
        rng_noise = np.random.default_rng(seed + 1)
        obs = generate_observations(mesh, sc, rng_noise)
        m_rho, m_chi, block, lens = scenario_models(mesh, sc)
        scenarios.append({
            "scenario": asdict(sc),
            "truth": {
                "m_rho_active_g_cm3": m_rho[ind_active].tolist(),
                "m_chi_active_SI": m_chi[ind_active].tolist(),
                "block_mask_active": block[ind_active].astype(int).tolist(),
                "lens_mask_active": lens[ind_active].astype(int).tolist(),
            },
            "observations": {
                "d_obs_g": obs["d_obs_g"].tolist(),
                "d_obs_m": obs["d_obs_m"].tolist(),
                "cvar_g": obs["cvar_g"].tolist(),
                "cvar_m": obs["cvar_m"].tolist(),
                "rx_nominal": obs["rx_nominal"].tolist(),
            },
            "sealed": {
                "rx_true": obs["rx_true"].tolist(),
                "d_true_g": obs["d_true_g"].tolist(),
                "d_true_m": obs["d_true_m"].tolist(),
                "underground_check": obs["underground_check"],
            },
        })
    pack = {
        "schema": "evd-joint-001-scene-pack-v1",
        "evidence_id": "EVD-JOINT-001",
        "design_version": "v1.1-frozen",
        "seed_base": int(seed_base),
        "seed_stride": SCENE_SEED_STRIDE,
        "registry_seed_base_suggestion": REGISTRY_SEED_BASE_SUGGESTION,
        "seed_mutual_exclusion": (
            "pilot 段 [90_000_000, 90_000_000+10_000·n) 与建议注册段 "
            "[20_260_819+10_000·i, i=0..399] 不相交；M3 冻结注册流时复核"
        ),
        "mesh": {
            "shape_cells": list(MESH_SHAPE), "cell_size_m": CELL_SIZE_M,
            "origin": list(MESH_ORIGIN), "n_active": int(ind_active.sum()),
        },
        "survey": {"grid": "6x6", "x": [50.0, 450.0], "y": [-200.0, 200.0],
                   "z_nominal": 10.0, "n_stations": 36},
        "noise": {"r": NOISE_R, "a_g_mGal": NOISE_FLOOR_G_MGAL,
                  "a_m_nT": NOISE_FLOOR_M_NT, "R": "identity"},
        "priors_pilot": {
            "beta_rho": BETA_RHO, "beta_chi": BETA_CHI, "eps_ridge": EPS_RIDGE,
            "s_rho_star": 0.5, "s_chi_star": 0.05,
            "s_log_sigma": 0.25, "weight_alpha": 1.0, "weight_eps": 0.01,
            "xi_bounds": [[-15.0, 15.0], [-15.0, 15.0], [-3.0, 3.0]],
        },
        "geomagnetic_field": {"amplitude_nT": 55000.0, "inclination_deg": 75.0,
                              "declination_deg": 25.0},
        "lens_shape_cells": list(LENS_SHAPE_CELLS),
        "snap_rule": "round-to-nearest-50m (floor(v/50+0.5)*50)，原抽取值同存",
        "scenario_reuse_disclosure": (
            "pilot 场景独立于未来 400 注册场景；端点(i)/(ii) 的 pilot 配对 "
            "复用同场景同噪声实现（设计 §6 场景复用纪律的 pilot 类比）"
        ),
        "scenarios": scenarios,
    }
    return pack, mesh


def write_scene_pack(pack, out_dir: Path) -> dict:
    path = Path(out_dir) / "scene-pack.json"
    digest = _json_dump(path, pack)
    (Path(out_dir) / "scene-pack.json.sha256").write_text(
        f"{digest}  scene-pack.json\n", encoding="utf-8")
    return {"path": str(path), "sha256": digest}


def load_scene_pack(path: Path):
    pack = json.loads(Path(path).read_text(encoding="utf-8"))
    return pack


def observation_view(pack, scenario_id: int) -> dict:
    """盲态视图：推断侧只见观测、名义站位与冻结噪声结构。"""
    entry = pack["scenarios"][scenario_id]
    obs = entry["observations"]
    return {
        "d_obs_g": np.asarray(obs["d_obs_g"], dtype=float),
        "d_obs_m": np.asarray(obs["d_obs_m"], dtype=float),
        "cvar_g": np.asarray(obs["cvar_g"], dtype=float),
        "cvar_m": np.asarray(obs["cvar_m"], dtype=float),
        "rx_nominal": np.asarray(obs["rx_nominal"], dtype=float),
    }


def scenario_from_pack(pack, scenario_id: int) -> Scenario:
    fields = pack["scenarios"][scenario_id]["scenario"]
    fields = dict(fields)
    fields["xi_true"] = tuple(fields["xi_true"])
    return Scenario(**fields)


# ---------------------------------------------------------------- 单 run 执行

def _chain_inits(posterior: JointPosterior, laplace, n_chains, rng,
                 max_tries=200):
    """链初值：Laplace 边缘采样 × INIT_DISPERSION 过散（记录 OVERDISPERSE_NOTE）。

    Laplace 代理在 ξ 盒先验之外仍有质量，过散采样的 ξ 分量可越界使完整
    log-density 非有限，而 DA 要求初始状态密度有限（sampling/delayed_
    acceptance.py 契约）。此处拒绝重抽至 max_tries；仍失败则回退 MAP 中心
    （有限性由 find_map 构造保证），兜底仍非有限属实现缺陷显式报错。
    重抽使 rng 消费次数随拒绝数变化，但固定种子下全流程确定可复现。
    """
    chol = laplace.chol
    inits = []
    for _ in range(n_chains):
        cand = None
        for _ in range(int(max_tries)):
            z = rng.standard_normal(laplace.theta_map.size)
            trial = (laplace.theta_map
                     + INIT_DISPERSION * solve_triangular(chol.T, z, lower=False))
            if np.isfinite(posterior.log_density(trial)):
                cand = trial
                break
        if cand is None:
            cand = laplace.theta_map.copy()
            if not np.isfinite(posterior.log_density(cand)):
                raise RuntimeError("链初值拒绝重抽后 MAP 中心回退仍非有限（实现缺陷）")
        inits.append(cand)
    return inits


def run_one(job: dict, pack: dict, out_dir: Path, *, quick=False) -> dict:
    """单 run：MAP → Laplace → 4 链 DA（或 AM 基线）→ 诊断 → 落盘。

    盲态：只经 observation_view 接触 pack。真值评价在 evaluate 阶段。
    """
    mesh = build_mesh()
    sc_id = int(job["scenario_id"])
    lam = float(job["lam"])
    weighted = bool(job.get("weighted", False))
    freeze_xi = bool(job.get("freeze_xi", False))
    sampler = job.get("sampler", "da")
    run_id = job["run_id"]
    run_dir = Path(out_dir) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    obs = observation_view(pack, sc_id)
    sc = scenario_from_pack(pack, sc_id)
    seed = int(pack["seed_base"]) + SCENE_SEED_STRIDE * sc_id
    posterior = build_posterior(mesh, obs, lam=lam, weighted=weighted,
                                freeze_xi=freeze_xi)
    n_chains = 2 if quick else N_CHAINS
    n_warmup = 400 if quick else N_WARMUP
    n_draws = 800 if quick else N_DRAWS
    timings = {}
    t0 = perf_counter()
    theta0 = np.zeros(posterior.dim)
    # DA 代理中心：η=0 条件 MAP（SURROGATE_PIN_ETA 注释链；M1 实现报告设计偏差节）
    map_result = find_map(posterior, theta0, pin_eta=SURROGATE_PIN_ETA)
    timings["map_seconds"] = perf_counter() - t0
    t0 = perf_counter()
    laplace = build_laplace(posterior, map_result.theta, xi_fd_eps=XI_FD_EPS)
    timings["laplace_seconds"] = perf_counter() - t0
    rng_init = np.random.default_rng(seed + 100)
    thresholds = load_diagnostic_thresholds()

    if sampler == "am":
        # 基线复核（设计 §5：AdaptiveMetropolis 子集一致性抽查）
        chains, logps, infos = [], [], []
        t0 = perf_counter()
        for c in range(n_chains):
            am = AdaptiveMetropolis(
                posterior.log_density, posterior.dim,
                init=map_result.theta, init_scale=0.02,
                target_accept=TARGET_ACCEPT, rng=seed + 1000 + c,
            )
            draws, info = am.sample(n_draws, n_warmup=n_warmup)
            chains.append(draws)
            logps.append([posterior.log_density(row) for row in draws])
            infos.append(info)
        timings["sampling_seconds"] = perf_counter() - t0
        draws_arr = np.asarray(chains)
        logp_arr = np.asarray(logps)
        extra = {"sampler": "AdaptiveMetropolis", "am_info": infos}
        stage_summary = {}
    else:
        chains, warmups, logps = [], [], []
        stage1_all, stage2_all, kinds_all = [], [], []
        adapt_logs, scales = [], []
        t0 = perf_counter()
        inits = _chain_inits(posterior, laplace, n_chains, rng_init)
        for c in range(n_chains):
            res = run_chain(posterior, laplace, inits[c],
                            seed=seed + 1000 + c * 100,
                            n_warmup=n_warmup, n_draws=n_draws)
            chains.append(res["draws"])
            warmups.append(res["warmup"])
            logps.append(res["log_density"])
            stage1_all.append(res["stage1_accepted"])
            stage2_all.append(res["stage2_accepted"])
            kinds_all.append(res["proposal_kind"])
            adapt_logs.append(res["adapt_log"])
            scales.append({"scale_a": res["scale_a_final"],
                           "scale_b": res["scale_b_final"]})
        timings["sampling_seconds"] = perf_counter() - t0
        draws_arr = np.asarray(chains)
        logp_arr = np.asarray(logps)
        stage1 = np.concatenate(stage1_all)
        stage2 = np.concatenate(stage2_all)
        stage_summary = {
            "stage1_accept_rate": float(np.mean(stage1)),
            "stage2_accept_rate_overall": float(np.mean(stage2)),
            "scales_final": scales,
        }
        extra = {
            "sampler": "delayed_acceptance_metropolis",
            "warmup_segments": WARMUP_SEGMENTS,
            "adapt_log_chain0": adapt_logs[0],
        }

    # 诊断域 = 1010 状态 + F1/F2/F3 + log-density
    t0 = perf_counter()
    block_mask_active = np.asarray(
        pack["scenarios"][sc_id]["truth"]["block_mask_active"], dtype=bool)
    # 搜索盒由冻结真值参数确定性导出（诊断域泛函通道属评价性质通道；
    # 真值场本身不进入推断路径，推断只经 obs 视图）
    scn = scenario_from_pack(pack, sc_id)
    box_full = f3_search_box_mask(mesh, scn)
    func_vals, f3_fallback = functional_chains(
        draws_arr, mesh, scn,
        block_mask_full=_active_to_full(mesh, block_mask_active),
        box_mask_full=box_full,
    )
    f3_chains = func_vals.reshape(draws_arr.shape[0], draws_arr.shape[1], 3)
    channels = np.concatenate(
        [draws_arr, f3_chains, logp_arr[..., None]], axis=2)
    diag = compute_diagnostics(channels, logp_arr, thresholds)
    diag["f3_fallback_rate"] = f3_fallback
    timings["diagnostics_seconds"] = perf_counter() - t0
    timings["total_seconds"] = sum(v for v in timings.values())

    metrics = {
        "run_id": run_id,
        "scenario_id": sc_id,
        "arm": {"lam": lam, "weighted": weighted, "freeze_xi": freeze_xi,
                "sampler": sampler},
        "config": {
            "n_chains": n_chains, "n_warmup": n_warmup, "n_draws": n_draws,
            "block_b_every": BLOCK_B_EVERY, "p_indep": P_INDEP,
            "beta_rho": BETA_RHO, "beta_chi": BETA_CHI, "eps_ridge": EPS_RIDGE,
            "xi_fd_eps": list(XI_FD_EPS),
            "init_dispersion": INIT_DISPERSION,
            "quick_mode": bool(quick),
            "seed": seed,
        },
        "map": {
            "log_density": map_result.log_density,
            "converged": map_result.converged,
            "n_outer": map_result.n_outer,
            "xi_map": map_result.theta[-5:-2].tolist(),
            "eta_map": map_result.theta[-2:].tolist(),
            "surrogate_center": "conditional_map_pin_eta_0",
        },
        "diagnostics": diag,
        "diagnostic_contract_thresholds": thresholds,
        "diagnostic_contract_source": str(_DIAGNOSTIC_CONTRACT),
        "timing_seconds": timings,
        **stage_summary,
        **extra,
    }
    status_overall = "Synthetic-run" if diag["status"] == "Passed" else "Failed"
    np.savez_compressed(
        run_dir / "raw-chains.npz",
        draws=draws_arr,
        log_density=logp_arr,
        functional_chains=f3_chains,
        map_theta=map_result.theta,
        laplace_theta_map=laplace.theta_map,
        laplace_hessian=laplace.hessian,
        **({"warmup": np.asarray(warmups)} if sampler == "da" else {}),
    )
    _json_dump(run_dir / "metrics.json", metrics)
    started_at = datetime.now(timezone.utc).isoformat()
    _json_dump(run_dir / "run-manifest.json", {
        "schema": "evd-joint-001-run-manifest-v1",
        "run_id": run_id,
        "status": status_overall,
        "completed_at": started_at,
        "command": " ".join(sys.argv),
        "script": {
            "path": Path(__file__).resolve().as_posix(),
            "sha256": _sha256_file(Path(__file__)),
        },
        "config": metrics["config"],
        "mode_visits_disclosure": (
            "契约字段 mode_visits_per_chain 字面预设多模态目标；本目标为登记"
            "单峰设计，按 D-E1 批准操作化为「每链 post-warmup 平均 log-density "
            "落在合并样本 ±3sd（合并样本估计）内」，modal-access 证据由 "
            "EVD-ALGO-002 承担。"
        ),
        "approval": {"owner": "M2 pilot 待用户复核", "date": None,
                     "decision": "pending"},
    })
    return {"run_id": run_id, "status": status_overall, "metrics": metrics,
            "run_dir": str(run_dir)}


def _active_to_full(mesh, active_mask):
    full = np.zeros(mesh.n_cells, dtype=bool)
    full[mesh.cell_centers[:, 2] <= -1e-9] = active_mask
    return full


def map_multistart(posterior: JointPosterior, seed: int,
                   n_starts: int = MULTISTART_N) -> dict:
    """D-E1 条件 3 单峰性判据：n_starts 个随机多起点 MAP。

    起点（盲态合法——量级取自设计 §2 已登记的场景生成分布，非真值）：
    m_ρ0~U[0,0.6] g/cm³、m_χ0~U[0,0.06] SI 逐单元独立，ξ0~U（先验盒）。
    η 钉 0（与 DA 代理中心同一操作化：自由 η 联合 MAP 塌缩尖峰的低体积
    病态已由精确边际证据登记，多起点考察的是质量区的 (m,ξ) 条件面）。
    判据：最优两解 log-density 差 <5 且连线中点 log-density
    相对两解均值下降 >10 → 多模态（D-E1 重开警报）。
    """
    rng = np.random.default_rng(seed)
    n = posterior.n_act
    results = []
    for _ in range(int(n_starts)):
        theta0 = np.zeros(posterior.dim)
        theta0[:n] = rng.uniform(0.0, 0.6, n)
        theta0[n:2 * n] = rng.uniform(0.0, 0.06, n)
        for j in range(3):
            lo, hi = posterior.xi_bounds[j]
            theta0[2 * n + j] = rng.uniform(lo, hi)
        try:
            res = find_map(posterior, theta0, pin_eta=SURROGATE_PIN_ETA)
            results.append(res)
        except Exception:
            continue  # 起点失败不计入解集（记录于 n_failed）
    if len(results) < 2:
        return {"multimodal": None, "n_failed": n_starts - len(results),
                "error": "有效起点不足 2 个"}
    results.sort(key=lambda r: -r.log_density)
    top1, top2 = results[0], results[1]
    mid = 0.5 * (top1.theta + top2.theta)
    lp_mid = posterior.log_density(mid)
    delta_top = float(top1.log_density - top2.log_density)
    drop = float(0.5 * (top1.log_density + top2.log_density) - lp_mid)
    multimodal = bool(delta_top < 5.0 and drop > 10.0)
    return {
        "multimodal": multimodal,
        "delta_top2_log_density": delta_top,
        "midpoint_drop": drop,
        "midpoint_log_density": float(lp_mid),
        "top_log_densities": [float(r.log_density) for r in results],
        "n_starts": int(n_starts),
        "n_failed": int(n_starts - len(results)),
        "criterion": "delta_top2<5 且 midpoint_drop>10 → 多模态（D-E1 条件3）",
    }


def evaluate_run(run_dir: Path, pack: dict, mesh, *, n_track=500) -> dict:
    """评价者角色：解封真值，计算泛函误差/宽度/覆盖与 w_k、T_gm 轨迹。

    w_k 与 T_gm 逐 draw 需核重建（~ms/draw），pilot 操作化为 n_track 个
    等距 draw 子集（M3 可加密，记录于 summary）。
    """
    run_dir = Path(run_dir)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    data = np.load(run_dir / "raw-chains.npz")
    draws = data["draws"]
    sc_id = int(metrics["scenario_id"])
    scn = scenario_from_pack(pack, sc_id)
    obs = observation_view(pack, sc_id)
    arm = metrics["arm"]
    truth = pack["scenarios"][sc_id]["truth"]
    block_full = _active_to_full(
        mesh, np.asarray(truth["block_mask_active"], dtype=bool))
    box_full = f3_search_box_mask(mesh, scn)
    flat = draws.reshape(-1, draws.shape[-1])
    func_vals, f3_fallback = functional_chains(draws, mesh, scn, block_full, box_full)
    func_summary = summarize_functionals(func_vals, scn, mesh)
    posterior = build_posterior(
        mesh, obs, lam=float(arm["lam"]), weighted=True,
        freeze_xi=bool(arm.get("freeze_xi", False)))
    idx = np.linspace(0, flat.shape[0] - 1, min(n_track, flat.shape[0])).astype(int)
    w_g, w_m, t_gm = [], [], []
    for i in idx:
        theta = flat[i]
        wg, wm = posterior.weights(theta)
        r_g, r_m = posterior.whitened_residuals(theta)
        denom = float(np.linalg.norm(r_g) * np.linalg.norm(r_m))
        t_gm.append(float(abs(r_g @ r_m) / denom) if denom > 0 else 0.0)
        w_g.append(wg)
        w_m.append(wm)
    sealed = pack["scenarios"][sc_id]["sealed"]
    return {
        "run_id": metrics["run_id"],
        "scenario_id": sc_id,
        "arm": arm,
        "functionals": func_summary,
        "f3_fallback_rate": f3_fallback,
        "w_trajectory": {
            "n_track": int(len(idx)),
            "w_g_mean": float(np.mean(w_g)), "w_m_mean": float(np.mean(w_m)),
            "w_g_sd": float(np.std(w_g, ddof=1)),
            "w_m_sd": float(np.std(w_m, ddof=1)),
        },
        "t_gm": {"mean": float(np.mean(t_gm)), "p95": float(np.quantile(t_gm, 0.95))},
        "r_xi": analytic_r_xi(mesh, scn, {**obs, }),
        "underground_check": sealed["underground_check"],
        "map": metrics["map"],
        "diagnostics_status": metrics["diagnostics"]["status"],
        "timing_seconds": metrics["timing_seconds"],
    }


def _scan_run_id(sid, lam):
    return f"s{sid:02d}__lam-{lam:g}__da"


def select_lambda_star(scan_evals: dict, lambdas=LAMBDA_GRID) -> dict:
    """λ* 护栏（设计 §3）：满足「耦合臂 F1 恢复误差（pilot 族均值）不劣于
    关闭臂」的最大网格 λ。操作化：mean_s(e_on(λ)) ≤ mean_s(e_off)；
    逐场景配对差同时报告供 M3 裁定。若空集 → 取最小网格 λ 并置警报。"""
    offs = [e for e in scan_evals.values() if e["arm"]["lam"] == 0.0]
    e_off = {e["scenario_id"]: e["functionals"]["F1_mass_kg"]["error_abs"]
             for e in offs}
    mean_off = float(np.mean(list(e_off.values())))
    table = []
    eligible = []
    for lam in lambdas:
        ons = [e for e in scan_evals.values()
               if e["arm"]["lam"] == lam and e["arm"]["sampler"] == "da"]
        e_on = {e["scenario_id"]: e["functionals"]["F1_mass_kg"]["error_abs"]
                for e in ons}
        mean_on = float(np.mean(list(e_on.values())))
        passed = mean_on <= mean_off
        table.append({
            "lam": float(lam), "mean_e_on": mean_on, "mean_e_off": mean_off,
            "per_scenario_delta_e": {
                str(s): float(e_off[s] - e_on[s]) for s in sorted(e_on)},
            "guardrail_pass": bool(passed),
        })
        if passed:
            eligible.append(float(lam))
    if eligible:
        star = max(eligible)
        alert = None
    else:
        star = float(min(lambdas))
        alert = "护栏空集：全部网格 λ 的 F1 均值误差均劣于关闭臂（R3 方向信号）"
    return {"lambda_star": float(star), "guardrail_table": table,
            "alert": alert,
            "rule": "max{λ∈grid : mean_s e_on(λ) ≤ mean_s e_off}"}


# ---------------------------------------------------------------- pilot 驱动

def _job_entry(args):
    """进程池入口（Windows spawn 需模块级可 pickle）。"""
    job, pack_path, out_dir, quick = args
    pack = load_scene_pack(Path(pack_path))
    return run_one(job, pack, Path(out_dir), quick=quick)


def _run_jobs(jobs_spec, pack_path, out_dir, jobs, quick):
    results = []
    if jobs and int(jobs) > 1:
        with ProcessPoolExecutor(max_workers=int(jobs)) as pool:
            for res in pool.map(
                    _job_entry,
                    [(j, str(pack_path), str(out_dir), quick) for j in jobs_spec]):
                results.append(res)
    else:
        for j in jobs_spec:
            results.append(run_one(j, load_scene_pack(pack_path),
                                   Path(out_dir), quick=quick))
    return results


def _environment_hash() -> str:
    import importlib.metadata as md

    parts = [platform.platform(), sys.version.split()[0]]
    for pkg in ("numpy", "scipy", "simpeg", "discretize"):
        try:
            parts.append(f"{pkg}=={md.version(pkg)}")
        except md.PackageNotFoundError:
            parts.append(f"{pkg}=missing")
    return _sha256_bytes("|".join(parts).encode("utf-8"))


def _code_manifest() -> list:
    """证据代码清单（新增 + 复用的冻结路径，相对档案根）。"""
    rel = [
        "src/geodeepbayes/priors/cross_gradient.py",
        "src/geodeepbayes/priors/__init__.py",
        "src/geodeepbayes/posterior/__init__.py",
        "src/geodeepbayes/posterior/joint.py",
        "src/geodeepbayes/benchmarks/joint_block.py",
        "src/geodeepbayes/forward/gravity.py",
        "src/geodeepbayes/forward/magnetic.py",
        "src/geodeepbayes/forward/base.py",
        "src/geodeepbayes/sampling/delayed_acceptance.py",
        "src/geodeepbayes/sampling/metropolis.py",
        "src/geodeepbayes/diagnostics/rhat.py",
        "src/geodeepbayes/diagnostics/ess.py",
        "src/geodeepbayes/diagnostics/mcse.py",
        "src/geodeepbayes/io/run_contract.py",
    ]
    entries = []
    for r in rel:
        p = _ARCHIVE_ROOT / r
        entries.append({
            "path": r, "bytes": p.stat().st_size,
            "sha256": _sha256_file(p), "locator": None,
        })
    return entries


def pilot(output, *, n_scenarios=N_PILOT_SCENARIOS, lambdas=LAMBDA_GRID,
          jobs=1, quick=False, lambda_star_override=None) -> dict:
    """M2 烟跑一键驱动：场景包 → λ 扫描（含 off 臂）→ 护栏选 λ* →
    端点(ii) 加权配对 → AM 基线抽查 → 多起点 MAP 单峰性 → 汇总落盘。

    失败纪律：输出目录必须不存在（不可覆盖）；失败 run 以 Failed 归档保留。
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc)
    pack, mesh = generate_pilot_pack(n_scenarios)
    pack_info = write_scene_pack(pack, output)
    pack_path = output / "scene-pack.json"

    # 阶段 0：η 精确边际证据（盲态；DA 代理中心偏差裁定的登记依据）
    (output / "evaluation").mkdir(parents=True, exist_ok=True)
    eta_evidence = {}
    for sid in range(int(n_scenarios)):
        obs0 = observation_view(pack, sid)
        eta_evidence[str(sid)] = marginal_eta_evidence(
            build_posterior(mesh, obs0, lam=0.0))
    _json_dump(output / "evaluation" / "marginal-eta-evidence.json", {
        "schema": "evd-joint-001-marginal-eta-evidence-v1",
        "surrogate_pin_eta": list(SURROGATE_PIN_ETA),
        "per_scenario": eta_evidence,
    })

    # 阶段 1：λ 扫描（off 臂 λ=0 + 网格；端点(i) 同场景同噪声配对）
    scan_jobs = []
    for sid in range(int(n_scenarios)):
        for lam in (0.0, *lambdas):
            scan_jobs.append({
                "scenario_id": sid, "lam": float(lam), "weighted": False,
                "freeze_xi": False, "sampler": "da",
                "run_id": _scan_run_id(sid, lam),
            })
    scan_results = _run_jobs(scan_jobs, pack_path, output, jobs, quick)

    # 阶段 1.5：评价扫描 → 护栏选 λ*
    scan_evals = {}
    for res in scan_results:
        scan_evals[res["run_id"]] = evaluate_run(res["run_dir"], pack, mesh)
    selection = select_lambda_star(scan_evals, lambdas)
    lambda_star = (float(lambda_star_override) if lambda_star_override is not None
                   else selection["lambda_star"])
    selection["lambda_star_override"] = (
        None if lambda_star_override is None else float(lambda_star_override))

    # 阶段 2：端点(ii) 加权配对（两臂均加权，良设 vs ξ≡0 失配）
    weight_jobs = []
    for sid in range(int(n_scenarios)):
        for frozen in (False, True):
            weight_jobs.append({
                "scenario_id": sid, "lam": float(lambda_star), "weighted": True,
                "freeze_xi": frozen, "sampler": "da",
                "run_id": f"s{sid:02d}__lam-{lambda_star:g}__w"
                          + ("-xifrozen" if frozen else "") + "__da",
            })
    # 阶段 3：AM 基线抽查（pilot 2 场景，λ* on 臂——耦合项存在的最难情形）
    baseline_jobs = [
        {"scenario_id": sid, "lam": float(lambda_star), "weighted": False,
         "freeze_xi": False, "sampler": "am",
         "run_id": f"s{sid:02d}__lam-{lambda_star:g}__am"}
        for sid in range(min(2, int(n_scenarios)))
    ]
    later_results = _run_jobs(weight_jobs + baseline_jobs, pack_path, output,
                              jobs, quick)

    # 阶段 4：多起点 MAP 单峰性判据（D-E1 条件 3，λ* 主后验）
    multistart = {}
    for sid in range(int(n_scenarios)):
        obs = observation_view(pack, sid)
        posterior = build_posterior(mesh, obs, lam=float(lambda_star))
        seed = int(pack["seed_base"]) + SCENE_SEED_STRIDE * sid
        multistart[str(sid)] = map_multistart(posterior, seed + 7000)

    # 阶段 5：汇总评价
    all_evals = dict(scan_evals)
    for res in later_results:
        all_evals[res["run_id"]] = evaluate_run(res["run_dir"], pack, mesh)
    summary = _summarize_pilot(pack, selection, all_evals, multistart,
                               scan_results + later_results, quick)
    summary["marginal_eta_evidence"] = {
        "surrogate_pin_eta": list(SURROGATE_PIN_ETA),
        "peak_eta_g": {sid: ev["peak_eta_g"] for sid, ev in eta_evidence.items()},
        "peak_eta_m": {sid: ev["peak_eta_m"] for sid, ev in eta_evidence.items()},
        "spike_drop_nats": {
            sid: ev["spike_drop_nats_at_eta_-2.2"]
            for sid, ev in eta_evidence.items()},
        "artifact": "evaluation/marginal-eta-evidence.json",
    }

    # RunContract 任务图登记 + pilot 级 manifest + evidence 哈希清单
    contract = RunContract(
        input_hashes={
            "scene_pack": pack_info["sha256"],
            "design_preregistration": _sha256_file(_PAPER_TREE),
            "diagnostic_contract": _sha256_file(_DIAGNOSTIC_CONTRACT),
        },
        operator_version=_environment_hash(),
        model_contract="EVD-JOINT-001 design v1.1-frozen §2/§3",
        algorithm_contract="EVD-JOINT-001 design v1.1-frozen §5 + WP2-DIAGNOSTIC-CONTRACT-v1",
        environment_hash=_environment_hash(),
        tasks=(
            TaskSpec("generate-scenes"),
            TaskSpec("marginal-eta-evidence", ("generate-scenes",)),
            TaskSpec("lambda-scan", ("marginal-eta-evidence",)),
            TaskSpec("guardrail-select", ("lambda-scan",)),
            TaskSpec("weighted-arms", ("guardrail-select",)),
            TaskSpec("baseline-recheck", ("guardrail-select",)),
            TaskSpec("map-multistart", ("guardrail-select",)),
            TaskSpec("evaluate", ("weighted-arms", "baseline-recheck",
                                  "map-multistart")),
        ),
    )
    contract.validate()
    summary_path = output / "evaluation" / "pilot-summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_digest = _json_dump(summary_path, summary)
    _json_dump(output / "run-contract.json", {
        "contract_hash": contract.contract_hash,
        "input_hashes": dict(contract.input_hashes),
        "tasks": [asdict(t) for t in contract.tasks],
        "topological_order": list(contract.topological_order()),
    })
    ended_at = datetime.now(timezone.utc)
    _json_dump(output / "run-manifest.json", {
        "schema": "evd-joint-001-run-manifest-v1",
        "run_id": output.name,
        "status": "Synthetic-run",
        "started_at": started_at.isoformat(),
        "completed_at": ended_at.isoformat(),
        "command": " ".join(sys.argv),
        "script": {"path": Path(__file__).resolve().as_posix(),
                   "sha256": _sha256_file(Path(__file__))},
        "contract_hash": contract.contract_hash,
        "quick_mode": bool(quick),
        "mode_visits_disclosure": (
            "契约字段 mode_visits_per_chain 字面预设多模态目标；本目标为登记"
            "单峰设计，按 D-E1 批准操作化为「每链 post-warmup 平均 log-density "
            "落在合并样本 ±3sd（合并样本估计）内」，modal-access 证据由 "
            "EVD-ALGO-002 承担。"
        ),
        "approval": {"owner": "M2 pilot 待用户复核", "date": None,
                     "decision": "pending"},
    })
    code_manifest = _code_manifest()
    code_digest = _sha256_bytes(json.dumps(
        code_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    outputs = [{"path": str(summary_path), "bytes": summary_path.stat().st_size,
                "sha256": summary_digest, "locator": None}]
    _json_dump(output / "evidence-run-v2.json", {
        "schema_version": "2.0.0",
        "run_id": output.name,
        "evidence_id": "EVD-JOINT-001",
        "execution": {
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "outcome": "succeeded",
            "exit_code": 0,
            "failure_reason": None,
        },
        "code": {"algorithm": "sha256-canonical-manifest-v1",
                 "manifest": code_manifest, "sha256": code_digest},
        "inputs": [{
            "path": str(pack_path), "bytes": pack_path.stat().st_size,
            "sha256": pack_info["sha256"], "locator": None,
        }, {
            "path": str(_PAPER_TREE), "bytes": _PAPER_TREE.stat().st_size,
            "sha256": _sha256_file(_PAPER_TREE), "locator": None,
        }, {
            "path": str(_DIAGNOSTIC_CONTRACT),
            "bytes": _DIAGNOSTIC_CONTRACT.stat().st_size,
            "sha256": _sha256_file(_DIAGNOSTIC_CONTRACT), "locator": None,
        }],
        "configs": [],
        "outputs": outputs,
        "environment": {
            "os": platform.platform(), "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "environment_hash": _environment_hash(),
        },
        "randomness": {
            "stochastic": True,
            "seeds": [int(pack["seed_base"]) + SCENE_SEED_STRIDE * i
                      for i in range(int(n_scenarios))],
        },
        "approval": {"identity": "M2 pilot 待用户复核", "identity_type": "ai",
                     "decided_at": ended_at.isoformat(), "decision": "pending"},
        "claims": [{"claim_id": "EVD-JOINT-001", "scope": "synthetic",
                    "max_maturity": "Synthetic-run"}],
        "attestation": {"required": False, "subject_digest": None,
                        "workflow": None, "commit_sha": None, "verified": False},
    })
    return summary


def _summarize_pilot(pack, selection, all_evals, multistart, run_results,
                     quick) -> dict:
    """pilot-summary：M2 验收物逐项（耗时、硬门、R_ξ、w 排序、入地、单峰性、
    s_Δ、护栏表）。"""
    mesh = build_mesh()
    n_scen = len(pack["scenarios"])
    da_runs = [r for r in run_results if r["metrics"]["arm"]["sampler"] == "da"]
    wall = [r["metrics"]["timing_seconds"]["total_seconds"] for r in run_results]
    gate = [r["metrics"]["diagnostics"]["status"] for r in run_results]
    failed = [r["run_id"] for r, s in zip(run_results, gate) if s != "Passed"]

    # 端点(i)：逐场景配对差（λ* 与 off 臂）
    lam_star = selection["lambda_star"]
    delta_e = {"F1_mass_kg": [], "F2_chi_block": [], "F3_ztop_m": []}
    delta_w = {"F1_mass_kg": [], "F2_chi_block": [], "F3_ztop_m": []}
    for sid in range(n_scen):
        off = all_evals[_scan_run_id(sid, 0.0)]
        on = all_evals.get(_scan_run_id(sid, lam_star))
        if on is None:
            continue
        for name in delta_e:
            delta_e[name].append(
                off["functionals"][name]["error_abs"]
                - on["functionals"][name]["error_abs"])
            delta_w[name].append(
                off["functionals"][name]["ci90_width"]
                - on["functionals"][name]["ci90_width"])
    s_delta = {
        name: float(np.std(vals, ddof=1)) if len(vals) > 1 else None
        for name, vals in delta_e.items()
    }
    f1_truths = [scenario_from_pack(pack, s).block_rho * 1000.0 * 4 * 4 * 2
                 * CELL_SIZE_M ** 3 for s in range(n_scen)]
    delta_mid = {
        "F1_mass_kg_per_scenario": [0.10 * v for v in f1_truths],
        "F2_chi_block_per_scenario": [
            0.20 * scenario_from_pack(pack, s).block_chi for s in range(n_scen)],
        "F3_ztop_m": 50.0,
    }

    # 端点(ii)：w 排序与 T_gm（λ* 加权配对臂）
    w_pairs = []
    for sid in range(n_scen):
        well = all_evals.get(f"s{sid:02d}__lam-{lam_star:g}__w__da")
        mis = all_evals.get(f"s{sid:02d}__lam-{lam_star:g}__w-xifrozen__da")
        if well is None or mis is None:
            continue
        w_pairs.append({
            "scenario_id": sid,
            "w_g_well": well["w_trajectory"]["w_g_mean"],
            "w_m_well": well["w_trajectory"]["w_m_mean"],
            "w_g_mismatch": mis["w_trajectory"]["w_g_mean"],
            "w_m_mismatch": mis["w_trajectory"]["w_m_mean"],
            "delta_w_g": well["w_trajectory"]["w_g_mean"]
            - mis["w_trajectory"]["w_g_mean"],
            "delta_w_m": well["w_trajectory"]["w_m_mean"]
            - mis["w_trajectory"]["w_m_mean"],
            "t_gm_well": well["t_gm"]["mean"],
            "t_gm_mismatch": mis["t_gm"]["mean"],
        })

    # AM 基线一致性（后验均值差 / 主链 MCSE 量级抽查）
    baseline = []
    for ev in all_evals.values():
        if ev["arm"]["sampler"] != "am":
            continue
        sid = ev["scenario_id"]
        ref = all_evals.get(_scan_run_id(sid, lam_star))
        if ref is None:
            continue
        baseline.append({
            "scenario_id": sid,
            "F1_mean_da": ref["functionals"]["F1_mass_kg"]["post_mean"],
            "F1_mean_am": ev["functionals"]["F1_mass_kg"]["post_mean"],
            "F2_mean_da": ref["functionals"]["F2_chi_block"]["post_mean"],
            "F2_mean_am": ev["functionals"]["F2_chi_block"]["post_mean"],
        })

    underground = [ev["underground_check"] for ev in all_evals.values()]
    n1 = 100  # 设计 §4 端点(i) 冻结场景数
    return {
        "schema": "evd-joint-001-pilot-summary-v1",
        "quick_mode": bool(quick),
        "n_scenarios": n_scen,
        "n_runs": len(run_results),
        "wall_seconds_per_run": {
            "min": float(min(wall)), "median": float(np.median(wall)),
            "max": float(max(wall)), "total": float(sum(wall)),
        },
        "hard_gate": {
            "n_passed": int(sum(1 for s in gate if s == "Passed")),
            "n_failed": int(len(failed)),
            "failed_run_ids": failed,
            "failed_replicate_rate": float(len(failed) / max(len(gate), 1)),
        },
        "lambda_selection": selection,
        "endpoint_i": {
            "delta_e": {k: [float(v) for v in vals] for k, vals in delta_e.items()},
            "delta_w": {k: [float(v) for v in vals] for k, vals in delta_w.items()},
            "s_delta": s_delta,
            "s_delta_over_sqrt_N1": {
                k: (v / np.sqrt(n1) if v is not None else None)
                for k, v in s_delta.items()},
            "delta_mid": delta_mid,
        },
        "endpoint_ii": {
            "w_pairs": w_pairs,
            "mean_delta_w_g": float(np.mean([p["delta_w_g"] for p in w_pairs]))
            if w_pairs else None,
            "mean_delta_w_m": float(np.mean([p["delta_w_m"] for p in w_pairs]))
            if w_pairs else None,
            "preregistered_expectation": "Δw_χ > Δw_ρ（失配方法标量权重下降，"
            "磁法相对灵敏度更高；逆转须并列披露）",
        },
        "r_xi": {str(s): analytic_r_xi(mesh, scenario_from_pack(pack, s),
                                       observation_view(pack, s))
                 for s in range(n_scen)},
        "underground_check": {
            "all_above_ground": bool(all(c["all_above_ground"] for c in underground)),
            "no_station_inside_active_cell": bool(all(
                c["no_station_inside_active_cell"] for c in underground)),
            "z_true_min": float(min(c["z_true_min"] for c in underground)),
            "z_true_max": float(max(c["z_true_max"] for c in underground)),
        },
        "unimodality": multistart,
        "baseline_recheck": baseline,
    }


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description="EVD-JOINT-001 pilot 生产器")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_pilot = sub.add_parser("pilot", help="M2 烟跑一键驱动")
    p_pilot.add_argument("--output", type=Path, required=True)
    p_pilot.add_argument("--scenarios", type=int, default=N_PILOT_SCENARIOS)
    p_pilot.add_argument("--jobs", type=int, default=1)
    p_pilot.add_argument("--quick", action="store_true",
                         help="自检模式（2 链×(400+800)），不作报告依据")
    p_pilot.add_argument("--lambda-star", type=float, default=None,
                         help="跳过护栏直接指定 λ*（调试用）")
    args = parser.parse_args(argv)
    if args.cmd == "pilot":
        summary = pilot(args.output, n_scenarios=args.scenarios,
                        jobs=args.jobs, quick=args.quick,
                        lambda_star_override=args.lambda_star)
        print(json.dumps({
            "lambda_star": summary["lambda_selection"]["lambda_star"],
            "hard_gate": summary["hard_gate"],
            "wall_seconds_per_run": summary["wall_seconds_per_run"],
        }, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
