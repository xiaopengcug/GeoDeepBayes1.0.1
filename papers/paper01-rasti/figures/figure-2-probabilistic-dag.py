#!/usr/bin/env python3
"""生成论文图 2 的唯一概率图 DAG，并在发布前执行失败关闭验收。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

# 禁止本脚本及其可选解析器导入产生 __pycache__。
sys.dont_write_bytecode = True

# 图 2 是冻结的概念模型，不对应某次运行；因此不借用图 5 的运行时间。
# 这里固定为仓内 methodology-blueprint 的 Phase 1 冻结检查点日期。
PROJECT_FREEZE_UTC = datetime(2026, 8, 19, 0, 0, 0, tzinfo=timezone.utc)
SOURCE_DATE_EPOCH = int(PROJECT_FREEZE_UTC.timestamp())
FIGURE_SIZE_IN = (10.5, 5.4)
PNG_DPI = 450
OUTPUT_STEM = "figure-2-probabilistic-dag"
INDEX_NOTATION = "k = 1 … K"
LAMBDA_PARENT_LABEL = r"$\nu \subset \Theta$"
CJK_PATTERN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
DIGIT_PATTERN = re.compile(r"[0-9０-９]")


class RenderError(RuntimeError):
    """图件规格、渲染或验收失败。"""


@dataclass(frozen=True)
class NodeSpec:
    """保存一个图节点的冻结语义与形态。"""

    node_id: str
    symbol: str
    description: str
    kind: str
    container: str | None = None


@dataclass(frozen=True)
class PlateSpec:
    """保存方法 plate 的符号重复语义。"""

    index: str
    upper_bound: str
    members: tuple[str, ...]
    label: str


NODES = (
    NodeSpec("theta", r"$\Theta$", "hyperparameters", "rounded"),
    NodeSpec("c", r"$c$", "model / dimension index", "rounded"),
    NodeSpec("z", r"$z$", "within-model lithology labels", "rounded"),
    NodeSpec("m", r"$m$", "continuous property fields", "rounded"),
    NodeSpec("xi", r"$\xi$", "shared systematic nuisance", "rounded"),
    NodeSpec("lambda", r"$\lambda$", "scalar precision mixing variable", "rounded"),
    NodeSpec("delta", r"$\delta$", "model discrepancy", "rounded-segment", "discrepancy"),
    NodeSpec(
        "delta_surr",
        r"$\delta_{\mathrm{surr}}$",
        "surrogate error",
        "rounded-segment",
        "discrepancy",
    ),
    NodeSpec("f_k", r"$f_k$", "observation factor", "square-factor"),
    NodeSpec("d_k", r"$d_k$", "observed data, method k", "rounded"),
)

PLATE = PlateSpec(
    index="k",
    upper_bound="K",
    members=("f_k", "d_k"),
    label=f"observation factors, {INDEX_NOTATION}",
)

EDGES = frozenset(
    {
        ("theta", "c"),
        ("theta", "z"),
        ("theta", "m"),
        ("theta", "xi"),
        ("theta", "lambda"),
        ("theta", "delta"),
        ("theta", "delta_surr"),
        ("c", "z"),
        ("c", "m"),
        ("c", "xi"),
        ("c", "delta"),
        ("c", "delta_surr"),
        ("c", "f_k"),
        ("z", "m"),
        ("z", "delta_surr"),
        ("z", "f_k"),
        ("m", "delta_surr"),
        ("m", "f_k"),
        ("xi", "delta_surr"),
        ("xi", "f_k"),
        ("lambda", "f_k"),
        ("delta", "f_k"),
        ("delta_surr", "f_k"),
        ("theta", "f_k"),
        ("f_k", "d_k"),
    }
)

FOOTNOTE = (
    r"States live on $\bigsqcup_c \{c\}\times\mathcal{Z}_c\times\mathcal{M}_c$ "
    "— disjoint-union state space."
)

EXPECTED_NODE_IDS = {
    "theta",
    "c",
    "z",
    "m",
    "xi",
    "lambda",
    "delta",
    "delta_surr",
    "f_k",
    "d_k",
}
EXPECTED_EDGES = frozenset(
    {
        ("theta", "c"),
        ("theta", "z"),
        ("theta", "m"),
        ("theta", "xi"),
        ("theta", "lambda"),
        ("theta", "delta"),
        ("theta", "delta_surr"),
        ("c", "z"),
        ("c", "m"),
        ("c", "xi"),
        ("c", "delta"),
        ("c", "delta_surr"),
        ("c", "f_k"),
        ("z", "m"),
        ("z", "delta_surr"),
        ("z", "f_k"),
        ("m", "delta_surr"),
        ("m", "f_k"),
        ("xi", "delta_surr"),
        ("xi", "f_k"),
        ("lambda", "f_k"),
        ("delta", "f_k"),
        ("delta_surr", "f_k"),
        ("theta", "f_k"),
        ("f_k", "d_k"),
    }
)


def require(condition: bool, message: str) -> None:
    """用统一异常类型执行失败关闭检查。"""
    if not condition:
        raise RenderError(message)


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locate_paths() -> dict[str, Path]:
    """校验脚本文件名并明确解析同目录唯一输出路径。"""
    script_path = Path(__file__).resolve()
    output_dir = script_path.parent.parent / "manuscript"
    require(output_dir.is_dir(), f"脚本输出目录不存在：{output_dir}")
    require(script_path.name == f"{OUTPUT_STEM}.py", "脚本文件名不符合冻结输出契约。")
    return {
        "script": script_path,
        "output_dir": output_dir,
        "pdf": output_dir / f"{OUTPUT_STEM}.pdf",
        "png": output_dir / f"{OUTPUT_STEM}.png",
    }


def visible_texts(
    nodes: tuple[NodeSpec, ...] | None = None,
    plate: PlateSpec | None = None,
) -> list[str]:
    """集中返回全部预期图面文字，供绘图前验收。"""
    active_nodes = NODES if nodes is None else nodes
    active_plate = PLATE if plate is None else plate
    texts: list[str] = []
    for node in active_nodes:
        if node.node_id == "theta":
            texts.append(r"$\Theta$  —  hyperparameters")
        elif node.node_id == "f_k":
            texts.extend([node.symbol, "observation\nfactor"])
        else:
            texts.extend([node.symbol, node.description])
    texts.extend([active_plate.label, LAMBDA_PARENT_LABEL, FOOTNOTE])
    return texts


def validate_display_texts(texts: list[str]) -> None:
    """拒绝中文、运行读数、第二后验与非许可数字。"""
    require(all(isinstance(text, str) and text for text in texts), "图面文字存在空值或非字符串。")
    combined = "\n".join(texts)
    require(not CJK_PATTERN.search(combined), "图面文字含中文字符。")
    require("posterior" not in combined.lower(), "图面不得出现第二个联合后验或后验捷径。")

    forbidden_runtime_terms = ("runtime", "elapsed", "iteration", "draws", "sha256", "bytes")
    lowered = combined.lower()
    require(
        not any(term in lowered for term in forbidden_runtime_terms),
        "图面文字含运行读数或产物诊断字段。",
    )

    index_occurrences = sum(text.count(INDEX_NOTATION) for text in texts)
    require(index_occurrences == 1, "方法索引必须且只能以 k = 1 … K 出现一次。")
    stripped = combined.replace(INDEX_NOTATION, "")
    digits = sorted(set(DIGIT_PATTERN.findall(stripped)))
    require(not digits, f"图面出现方法索引之外的数字字符：{digits}")


def validate_graph_spec(
    *,
    nodes: tuple[NodeSpec, ...] | None = None,
    edges: frozenset[tuple[str, str]] | None = None,
    plate: PlateSpec | None = None,
) -> None:
    """在导入 Matplotlib 前核对冻结节点、边与 plate 语义。"""
    active_nodes = NODES if nodes is None else nodes
    active_edges = EDGES if edges is None else edges
    active_plate = PLATE if plate is None else plate
    node_ids = [node.node_id for node in active_nodes]
    counts = Counter(node_ids)
    require(set(node_ids) == EXPECTED_NODE_IDS, "DAG 节点集合与冻结规格不一致。")
    require(all(count == 1 for count in counts.values()), "DAG 存在重复节点。")
    require(counts["xi"] == 1, "共享系统误差 ξ 必须是唯一单节点。")
    require(active_edges == EXPECTED_EDGES, "DAG 边集合与冻结规格不一致。")
    require(("c", "z") in active_edges and ("z", "m") in active_edges, "主状态链必须为 c→z→m。")
    require(len(active_edges) == 25, "DAG 必须恰含 25 条注册父边。")
    require(("xi", "f_k") in active_edges, "唯一 ξ 必须进入方法观测因子。")
    require(
        {("lambda", "f_k"), ("delta", "f_k"), ("delta_surr", "f_k")}.issubset(active_edges),
        "λ、δ 与 δ_surr 必须全部连接观测因子。",
    )
    require(("f_k", "d_k") in active_edges, "观测因子必须指向观测数据 d_k。")

    node_by_id = {node.node_id: node for node in active_nodes}
    variable_ids = EXPECTED_NODE_IDS - {"f_k"}
    require(
        all(node_by_id[node_id].kind.startswith("rounded") for node_id in variable_ids),
        "所有变量节点必须使用圆角形态。",
    )
    require(node_by_id["f_k"].kind == "square-factor", "观测因子必须使用方形因子节点。")
    require(
        node_by_id["delta"].container == node_by_id["delta_surr"].container == "discrepancy",
        "δ 与 δ_surr 必须位于同一个分格圆角框。",
    )
    require(
        active_plate.index == "k"
        and active_plate.upper_bound == "K"
        and not active_plate.upper_bound.isdigit(),
        "方法 plate 必须将 K 保持为符号上界，不能解析为具体计数。",
    )
    require(set(active_plate.members) == {"f_k", "d_k"}, "方法 plate 的成员必须恰为因子与数据节点。")
    validate_display_texts(visible_texts(active_nodes, active_plate))
    print(
        "[规格] DAG=PASS 节点与边完整；ξ 为单节点；K 保持符号；"
        "变量圆角、因子方形；无第二后验"
    )


def validate_drawn_topology(drawn_edges: set[tuple[str, str]] | frozenset[tuple[str, str]]) -> None:
    """将实际绘制并登记的语义边与冻结拓扑逐边比较。"""
    actual_edges = frozenset(drawn_edges)
    missing = sorted(EXPECTED_EDGES - actual_edges)
    unexpected = sorted(actual_edges - EXPECTED_EDGES)
    require(
        actual_edges == EXPECTED_EDGES,
        f"实际箭头拓扑与冻结拓扑不一致：缺失 {missing}；多余 {unexpected}",
    )


def validate_factor_render_signature(
    shape_kind: str,
    width: float,
    height: float,
    alpha: float,
) -> None:
    """验收实际因子艺术家的方形、无圆角与实心签名。"""
    require(shape_kind == "square-factor", "观测因子的实际艺术家不是无圆角方形。")
    require(
        math.isclose(width, height, rel_tol=0.0, abs_tol=1e-12),
        "观测因子在画布上不是正方形。",
    )
    require(alpha == 1.0, "观测因子必须为不透明实心方块。")


def expect_render_error(label: str, action) -> None:
    """要求纯内存负向构造触发 RenderError，否则自身失败关闭。"""
    try:
        action()
    except RenderError as exc:
        print(f"[负向探针] {label}=REJECTED 原因={exc}")
        return
    raise RenderError(f"负向探针未能拒绝缺陷：{label}")


def run_negative_probes() -> None:
    """证明拓扑、形态、符号上界与图面文字门具有鉴别力。"""
    for edge in sorted(EXPECTED_EDGES):
        expect_render_error(
            f"删除实际登记 {edge[0]}→{edge[1]}",
            lambda edge=edge: validate_drawn_topology(set(EXPECTED_EDGES - {edge})),
        )

    concrete_plate = PlateSpec(
        index="k",
        upper_bound="4",
        members=PLATE.members,
        label=PLATE.label,
    )
    expect_render_error(
        "将 K 具体化",
        lambda: validate_graph_spec(plate=concrete_plate),
    )

    expect_render_error(
        "将实际因子改为圆角艺术家",
        lambda: validate_factor_render_signature("rounded", 1.0, 1.0, 1.0),
    )
    expect_render_error(
        "注入运行读数",
        lambda: validate_display_texts([*visible_texts(), "runtime: 42 seconds"]),
    )
    print(f"[负向探针] ALL=PASS count={len(EXPECTED_EDGES) + 3}")


def configure_determinism() -> None:
    """在导入 Matplotlib 前固定可复现时间与相关环境。"""
    require(PROJECT_FREEZE_UTC.tzinfo is timezone.utc, "冻结时间必须显式使用 UTC。")
    require(SOURCE_DATE_EPOCH >= 0, "SOURCE_DATE_EPOCH 必须为非负整数。")
    os.environ["SOURCE_DATE_EPOCH"] = str(SOURCE_DATE_EPOCH)
    print(
        "[确定性] 时间源=methodology-blueprint Phase 1 冻结检查点 "
        f"SOURCE_DATE_EPOCH={SOURCE_DATE_EPOCH} PDF_TIME={PROJECT_FREEZE_UTC.isoformat()}"
    )


def add_arrow(
    ax,
    start,
    end,
    *,
    semantic_edges: tuple[tuple[str, str], ...],
    drawn_edges: set[tuple[str, str]],
    linestyle="-",
    linewidth=1.15,
    connectionstyle="arc3,rad=0",
):
    """添加有向边，并将同一次实际绘制原子绑定到语义拓扑登记。"""
    from matplotlib.patches import FancyArrowPatch

    require(bool(semantic_edges), "实际箭头必须绑定至少一条语义边。")
    require(len(set(semantic_edges)) == len(semantic_edges), "单个实际箭头重复绑定同一语义边。")
    require(
        all(edge in EXPECTED_EDGES for edge in semantic_edges),
        f"实际箭头绑定了冻结拓扑之外的语义边：{semantic_edges}",
    )
    require(
        drawn_edges.isdisjoint(semantic_edges),
        f"实际箭头重复登记语义边：{sorted(drawn_edges.intersection(semantic_edges))}",
    )

    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=10.0,
        linewidth=linewidth,
        linestyle=linestyle,
        color="#303842",
        shrinkA=0.0,
        shrinkB=0.0,
        connectionstyle=connectionstyle,
        capstyle="round",
        joinstyle="round",
        zorder=2,
    )
    ax.add_patch(arrow)
    drawn_edges.update(semantic_edges)
    return arrow


def rounded_node(ax, center, width, height, symbol, description, *, fill="#f5f7f9"):
    """绘制圆角变量节点并返回边框对象。"""
    from matplotlib.patches import FancyBboxPatch

    x_value = center[0] - width / 2.0
    y_value = center[1] - height / 2.0
    patch = FancyBboxPatch(
        (x_value, y_value),
        width,
        height,
        boxstyle="round,pad=0.035,rounding_size=0.13",
        facecolor=fill,
        edgecolor="#27313b",
        linewidth=1.15,
        zorder=3,
    )
    ax.add_patch(patch)
    ax.text(
        center[0],
        center[1] + 0.17,
        symbol,
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="semibold",
        color="#1d252d",
        zorder=4,
    )
    ax.text(
        center[0],
        center[1] - 0.22,
        description,
        ha="center",
        va="center",
        fontsize=7.4,
        color="#394551",
        zorder=4,
    )
    return patch


def draw_figure():
    """构造单轴、全矢量友好的冻结 DAG。"""
    import matplotlib

    matplotlib.use("Agg", force=True)
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )

    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyBboxPatch, Rectangle
    from matplotlib.text import Text

    fig = plt.figure(figsize=FIGURE_SIZE_IN, facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0.0, 21.0)
    ax.set_ylim(0.0, 10.8)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    drawn_edges: set[tuple[str, str]] = set()

    # 方法 plate 同时包含复制的观测因子与对应数据；K 始终是符号上界。
    plate = Rectangle(
        (6.05, 1.38),
        14.25,
        3.72,
        facecolor="#fbfcfd",
        edgecolor="#7b8794",
        linewidth=1.0,
        linestyle=(0, (5, 3)),
        zorder=0,
    )
    ax.add_patch(plate)
    ax.text(
        6.32,
        4.76,
        PLATE.label,
        ha="left",
        va="center",
        fontsize=8.0,
        fontweight="semibold",
        color="#3e4954",
        bbox={"facecolor": "#fbfcfd", "edgecolor": "none", "pad": 1.5},
        zorder=4,
    )

    # 先画边，使箭头自然收在节点边框下方。
    top_y = 8.48
    row_top_y = 7.20
    theta_targets = {
        ("c",): 1.55,
        ("z",): 4.90,
        ("m",): 8.35,
        ("xi",): 11.80,
        ("lambda",): 15.20,
        ("delta", "delta_surr"): 18.90,
    }
    for target_ids, x_value in theta_targets.items():
        add_arrow(
            ax,
            (x_value, top_y),
            (x_value, row_top_y),
            semantic_edges=tuple(("theta", target_id) for target_id in target_ids),
            drawn_edges=drawn_edges,
            linestyle=(0, (3, 2.4)),
            linewidth=0.95,
        )

    add_arrow(
        ax,
        (2.93, 6.62),
        (3.30, 6.62),
        semantic_edges=(("c", "z"),),
        drawn_edges=drawn_edges,
        linewidth=1.35,
    )
    add_arrow(
        ax,
        (6.50, 6.62),
        (6.75, 6.62),
        semantic_edges=(("z", "m"),),
        drawn_edges=drawn_edges,
        linewidth=1.35,
    )

    # 注册父集中的跨层依赖分别绘制；弧线避免把经过的节点误读为父节点。
    for start, end, edge, curvature in (
        ((2.70, 6.03), (7.10, 6.03), ("c", "m"), 0.34),
        ((2.55, 5.98), (10.45, 5.98), ("c", "xi"), 0.27),
        ((2.45, 5.95), (17.25, 7.08), ("c", "delta"), -0.18),
        ((2.35, 5.91), (17.25, 6.15), ("c", "delta_surr"), -0.11),
        ((6.10, 6.02), (17.25, 6.08), ("z", "delta_surr"), -0.08),
        ((9.60, 6.04), (17.25, 6.04), ("m", "delta_surr"), -0.05),
        ((13.20, 6.08), (17.25, 6.08), ("xi", "delta_surr"), -0.03),
    ):
        add_arrow(
            ax,
            start,
            end,
            semantic_edges=(edge,),
            drawn_edges=drawn_edges,
            linestyle=(0, (2.2, 2.2)),
            linewidth=0.72,
            connectionstyle=f"arc3,rad={curvature}",
        )

    factor_center = (13.00, 3.72)
    factor_half = 0.67
    for start, end, edge, curvature in (
        ((2.70, 6.00), (12.33, 3.54), ("c", "f_k"), -0.14),
        ((6.15, 6.00), (12.33, 3.68), ("z", "f_k"), -0.10),
        ((10.50, 8.48), (13.00, 4.39), ("theta", "f_k"), 0.12),
    ):
        add_arrow(
            ax,
            start,
            end,
            semantic_edges=(edge,),
            drawn_edges=drawn_edges,
            linestyle=(0, (2.2, 2.2)),
            linewidth=0.78,
            connectionstyle=f"arc3,rad={curvature}",
        )
    add_arrow(
        ax,
        (8.35, 6.03),
        (12.33, 4.12),
        semantic_edges=(("m", "f_k"),),
        drawn_edges=drawn_edges,
        connectionstyle="arc3,rad=-0.05",
    )
    add_arrow(
        ax,
        (11.80, 6.03),
        (12.80, 4.39),
        semantic_edges=(("xi", "f_k"),),
        drawn_edges=drawn_edges,
        linewidth=1.55,
    )
    add_arrow(
        ax,
        (15.20, 6.03),
        (13.46, 4.39),
        semantic_edges=(("lambda", "f_k"),),
        drawn_edges=drawn_edges,
        connectionstyle="arc3,rad=0.05",
    )
    add_arrow(
        ax,
        (18.35, 6.56),
        (factor_center[0] + factor_half, factor_center[1] + 0.22),
        semantic_edges=(("delta", "f_k"),),
        drawn_edges=drawn_edges,
        connectionstyle="angle3,angleA=-95,angleB=0",
    )
    add_arrow(
        ax,
        (19.45, 5.86),
        (factor_center[0] + factor_half, factor_center[1] - 0.24),
        semantic_edges=(("delta_surr", "f_k"),),
        drawn_edges=drawn_edges,
        connectionstyle="angle3,angleA=-90,angleB=0",
    )
    add_arrow(
        ax,
        (13.00, 3.05),
        (13.00, 2.72),
        semantic_edges=(("f_k", "d_k"),),
        drawn_edges=drawn_edges,
        linewidth=1.35,
    )

    # 顶部超参数节点横跨全部潜变量。
    theta_patch = FancyBboxPatch(
        (0.55, 8.48),
        19.90,
        0.92,
        boxstyle="round,pad=0.035,rounding_size=0.14",
        facecolor="#e7ebef",
        edgecolor="#27313b",
        linewidth=1.2,
        zorder=3,
    )
    ax.add_patch(theta_patch)
    ax.text(
        10.50,
        8.94,
        r"$\Theta$  —  hyperparameters",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="semibold",
        color="#1d252d",
        zorder=4,
    )
    ax.text(
        15.20,
        8.18,
        LAMBDA_PARENT_LABEL,
        ha="center",
        va="center",
        fontsize=7.2,
        color="#394551",
        zorder=4,
    )

    variable_patches = {
        "theta": theta_patch,
        "c": rounded_node(ax, (1.55, 6.62), 2.75, 1.18, r"$c$", "model / dimension index"),
        "z": rounded_node(ax, (4.90, 6.62), 3.20, 1.18, r"$z$", "within-model lithology labels"),
        "m": rounded_node(ax, (8.35, 6.62), 3.20, 1.18, r"$m$", "continuous property fields"),
        "xi": rounded_node(
            ax,
            (11.80, 6.62),
            3.20,
            1.18,
            r"$\xi$",
            "shared systematic nuisance",
            fill="#edf0f3",
        ),
        "lambda": rounded_node(
            ax,
            (15.20, 6.62),
            3.35,
            1.18,
            r"$\lambda$",
            "scalar precision mixing variable",
        ),
    }

    # δ 与 δ_surr 保持同一个圆角框，并用分格线保留两个独立变量入口。
    discrepancy_patch = FancyBboxPatch(
        (17.25, 5.72),
        3.30,
        1.80,
        boxstyle="round,pad=0.035,rounding_size=0.13",
        facecolor="#f5f7f9",
        edgecolor="#27313b",
        linewidth=1.15,
        zorder=3,
    )
    ax.add_patch(discrepancy_patch)
    divider = Line2D([17.29, 20.51], [6.62, 6.62], color="#7b8794", linewidth=0.9, zorder=4)
    ax.add_line(divider)
    ax.text(17.65, 7.07, r"$\delta$", ha="left", va="center", fontsize=9.6, color="#1d252d", zorder=4)
    ax.text(18.48, 7.07, "model discrepancy", ha="left", va="center", fontsize=7.1, color="#394551", zorder=4)
    ax.text(
        17.55,
        6.17,
        r"$\delta_{\mathrm{surr}}$",
        ha="left",
        va="center",
        fontsize=8.8,
        color="#1d252d",
        zorder=4,
    )
    ax.text(18.82, 6.17, "surrogate error", ha="left", va="center", fontsize=7.1, color="#394551", zorder=4)
    variable_patches["discrepancy"] = discrepancy_patch

    # 实心、无圆角的正方形是唯一因子节点。
    factor_patch = Rectangle(
        (factor_center[0] - factor_half, factor_center[1] - factor_half),
        2.0 * factor_half,
        2.0 * factor_half,
        facecolor="#303842",
        edgecolor="#171c22",
        linewidth=1.15,
        zorder=3,
    )
    ax.add_patch(factor_patch)
    ax.text(
        factor_center[0],
        factor_center[1] + 0.22,
        r"$f_k$",
        ha="center",
        va="center",
        fontsize=10.0,
        color="white",
        fontweight="semibold",
        zorder=4,
    )
    ax.text(
        factor_center[0],
        factor_center[1] - 0.25,
        "observation\nfactor",
        ha="center",
        va="center",
        fontsize=6.8,
        color="white",
        linespacing=0.95,
        zorder=4,
    )

    data_patch = rounded_node(
        ax,
        (13.00, 2.18),
        3.80,
        1.08,
        r"$d_k$",
        "observed data, method k",
        fill="#dfe4e9",
    )
    variable_patches["d_k"] = data_patch

    ax.text(
        0.56,
        0.58,
        FOOTNOTE,
        ha="left",
        va="center",
        fontsize=7.6,
        color="#394551",
        zorder=4,
    )

    # 实际箭头登记必须与冻结拓扑逐边相等，声明正确不能替代画布正确。
    validate_drawn_topology(drawn_edges)
    print(f"[画布] DRAWN_TOPOLOGY=PASS edges={len(drawn_edges)}")

    # 艺术家级验收防止未来修改绕过集中字符串表。
    require(len(fig.axes) == 1 and fig.axes[0] is ax, "Figure 必须恰含一个坐标轴。")
    require(not ax.axison, "DAG 坐标轴必须关闭，禁止生成刻度或双轴。")
    factor_shape_kind = "square-factor" if type(factor_patch) is Rectangle else "rounded"
    validate_factor_render_signature(
        factor_shape_kind,
        factor_patch.get_width(),
        factor_patch.get_height(),
        factor_patch.get_facecolor()[3],
    )
    require(
        all(isinstance(patch, FancyBboxPatch) for patch in variable_patches.values()),
        "变量节点存在非圆角框。",
    )

    artist_texts = [artist.get_text() for artist in fig.findobj(match=Text) if artist.get_text()]
    validate_display_texts(artist_texts)
    require(Counter(artist_texts) == Counter(visible_texts()), "实际图面文字与冻结文字清单不一致。")
    print("[画布] SINGLE_AXIS=PASS VARIABLE_ROUNDED=PASS FACTOR_SQUARE_SOLID=PASS")
    print("[画布] ENGLISH_ONLY=PASS CONCRETE_NUMBERS=PASS RUN_READOUTS=PASS")
    return fig


def make_temp_path(output_dir: Path, suffix: str) -> Path:
    """在最终目录同一文件系统创建唯一临时文件。"""
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{OUTPUT_STEM}-",
        suffix=suffix,
        dir=output_dir,
    )
    os.close(descriptor)
    return Path(raw_path)


def load_pdf_reader(pdf_path: Path):
    """从现有环境选择 PDF 解析器；缺失时失败关闭。"""
    if importlib.util.find_spec("pypdf") is not None:
        from pypdf import PdfReader

        return PdfReader(str(pdf_path)), "pypdf"
    if importlib.util.find_spec("PyPDF2") is not None:
        from PyPDF2 import PdfReader

        return PdfReader(str(pdf_path)), "PyPDF2"
    raise RenderError("缺少 pypdf 或 PyPDF2，无法失败关闭验收 PDF。")


def indirect_object(value):
    """兼容两个 PDF 解析器取得间接对象。"""
    return value.get_object() if hasattr(value, "get_object") else value


def check_pdf(pdf_path: Path, output_dir: Path) -> dict[str, object]:
    """验收 PDF 元数据、矢量资源、页面尺寸与图面文字。"""
    raw = pdf_path.read_bytes()
    require(raw[:5] == b"%PDF-", "PDF 文件头无效。")
    require(str(output_dir).encode("utf-8") not in raw, "PDF 嵌入了输出目录绝对路径。")

    reader, parser_name = load_pdf_reader(pdf_path)
    require(len(reader.pages) == 1, "PDF 必须恰含一页。")
    page = reader.pages[0]
    width_pt = float(page.mediabox.width)
    height_pt = float(page.mediabox.height)
    require(width_pt > 0.0 and height_pt > 0.0, "PDF 页面尺寸无效。")
    require(
        math.isclose(width_pt / 72.0, FIGURE_SIZE_IN[0], abs_tol=0.01)
        and math.isclose(height_pt / 72.0, FIGURE_SIZE_IN[1], abs_tol=0.01),
        "PDF 页面尺寸与冻结画布尺寸不一致。",
    )

    metadata = reader.metadata or {}
    raw_creation = str(metadata.get("/CreationDate", ""))
    raw_modification = str(metadata.get("/ModDate", ""))
    expected_pdf_date = "D:20260819000000Z"
    require(raw_creation == expected_pdf_date, f"PDF CreationDate 不固定：{raw_creation!r}")
    require(raw_modification == expected_pdf_date, f"PDF ModDate 不固定：{raw_modification!r}")

    page_text = page.extract_text() or ""
    require(page_text.strip(), "PDF 未提取到矢量文字。")
    require(not CJK_PATTERN.search(page_text), "PDF 页面提取文字含中文。")
    require("posterior" not in page_text.lower(), "PDF 页面出现禁用后验文字。")

    resources = indirect_object(page.get("/Resources") or {})
    xobjects = indirect_object(resources.get("/XObject") or {}) if resources else {}
    image_count = 0
    for value in xobjects.values():
        obj = indirect_object(value)
        if obj.get("/Subtype") == "/Image":
            image_count += 1
    require(image_count == 0, f"PDF 含 {image_count} 个栅格图像对象。")

    fonts = indirect_object(resources.get("/Font") or {}) if resources else {}
    require(len(fonts) > 0, "PDF 页面未声明字体资源，矢量文字验收失败。")
    contents = page.get_contents()
    require(contents is not None, "PDF 页面缺少内容流。")
    content_bytes = contents.get_data()
    require(b"BT" in content_bytes and b"ET" in content_bytes, "PDF 内容流缺少文字绘制操作。")
    vector_operator = re.search(rb"(?:^|\s)(?:m|l|c|re)(?:\s|$)", content_bytes)
    require(vector_operator is not None, "PDF 内容流缺少矢量路径操作。")

    result = {
        "parser": parser_name,
        "width_pt": width_pt,
        "height_pt": height_pt,
        "creation_date": raw_creation,
        "modification_date": raw_modification,
        "image_xobjects": image_count,
        "font_resources": len(fonts),
        "extracted_chars": len(page_text),
    }
    print(
        "[验收] PDF=PASS "
        f"size_pt={width_pt:.2f}x{height_pt:.2f} parser={parser_name} "
        f"image_xobjects={image_count} font_resources={len(fonts)} "
        f"CreationDate={raw_creation} ModDate={raw_modification}"
    )
    return result


def check_png(png_path: Path, output_dir: Path) -> dict[str, object]:
    """验收 PNG 尺寸、分辨率、灰度层次与路径洁净性。"""
    raw = png_path.read_bytes()
    require(raw[:8] == b"\x89PNG\r\n\x1a\n", "PNG 文件头无效。")
    require(str(output_dir).encode("utf-8") not in raw, "PNG 嵌入了输出目录绝对路径。")

    import numpy as np
    from PIL import Image

    with Image.open(png_path) as image:
        width, height = image.size
        dpi = tuple(float(value) for value in image.info.get("dpi", (0.0, 0.0)))
        gray = np.asarray(image.convert("L"), dtype=np.uint8)

    expected_width = int(FIGURE_SIZE_IN[0] * PNG_DPI)
    expected_height = int(FIGURE_SIZE_IN[1] * PNG_DPI)
    require(
        (width, height) == (expected_width, expected_height),
        f"PNG 像素尺寸与冻结画布不一致：期望 {expected_width}x{expected_height}，实际 {width}x{height}",
    )
    require(len(dpi) == 2 and min(dpi) >= 300.0, f"PNG 分辨率低于 300 dpi：{dpi}")

    gray_min = int(np.min(gray))
    gray_max = int(np.max(gray))
    unique_levels = int(np.unique(gray).size)
    nonwhite_fraction = float(np.mean(gray < 250))
    require(gray_min <= 55 and gray_max >= 250, "PNG 灰度预览缺少足够明暗范围。")
    require(unique_levels >= 64, "PNG 灰度预览层级过少。")
    require(0.01 <= nonwhite_fraction <= 0.45, "PNG 前景占比异常。")

    result = {
        "width_px": width,
        "height_px": height,
        "dpi": dpi,
        "gray_min": gray_min,
        "gray_max": gray_max,
        "unique_gray_levels": unique_levels,
        "nonwhite_fraction": nonwhite_fraction,
    }
    print(
        "[验收] PNG=PASS "
        f"size_px={width}x{height} dpi={dpi[0]:.3f}x{dpi[1]:.3f} "
        f"gray_range={gray_min}..{gray_max} unique_gray={unique_levels} "
        f"nonwhite_fraction={nonwhite_fraction:.6f}"
    )
    return result


def publish_pair_atomically(temp_pdf: Path, temp_png: Path, final_pdf: Path, final_png: Path) -> None:
    """成对替换输出；失败时回滚，避免留下半对文件。"""
    require(final_pdf.exists() == final_png.exists(), "现有 PDF/PNG 仅存在一个，拒绝覆盖不完整输出对。")
    token = uuid.uuid4().hex
    finals = (final_pdf, final_png)
    temps = (temp_pdf, temp_png)
    backups: list[tuple[Path, Path]] = []
    moved: list[Path] = []

    try:
        for final in finals:
            if final.exists():
                backup = final.with_name(f".{final.name}.{token}.bak")
                os.replace(final, backup)
                backups.append((backup, final))
        for temp, final in zip(temps, finals, strict=True):
            os.replace(temp, final)
            moved.append(final)
    except Exception:
        for final in moved:
            try:
                final.unlink(missing_ok=True)
            except OSError:
                pass
        for backup, final in reversed(backups):
            if backup.exists():
                os.replace(backup, final)
        raise
    else:
        for backup, _final in backups:
            backup.unlink(missing_ok=True)


def log_output(path: Path) -> None:
    """报告最终文件的字节数与 SHA-256。"""
    print(f"[输出] path={path} bytes={path.stat().st_size} sha256={sha256_file(path)}")


def main() -> int:
    """按规格门、渲染、验收、发布的固定顺序执行。"""
    paths = locate_paths()
    validate_graph_spec()
    run_negative_probes()
    configure_determinism()

    fig = None
    temp_pdf: Path | None = None
    temp_png: Path | None = None
    try:
        fig = draw_figure()
        temp_pdf = make_temp_path(paths["output_dir"], ".pdf.tmp")
        temp_png = make_temp_path(paths["output_dir"], ".png.tmp")

        fig.savefig(
            temp_pdf,
            format="pdf",
            dpi=PNG_DPI,
            metadata={
                "Title": "Probabilistic graph",
                "Creator": "GeoDeepBayes paper figure renderer",
                "CreationDate": PROJECT_FREEZE_UTC,
                "ModDate": PROJECT_FREEZE_UTC,
            },
        )
        fig.savefig(
            temp_png,
            format="png",
            dpi=PNG_DPI,
            metadata={"Software": "Matplotlib"},
        )

        import matplotlib.pyplot as plt

        plt.close(fig)
        fig = None

        require(temp_pdf.stat().st_size > 0, "临时 PDF 为空。")
        require(temp_png.stat().st_size > 0, "临时 PNG 为空。")
        check_pdf(temp_pdf, paths["output_dir"])
        check_png(temp_png, paths["output_dir"])

        publish_pair_atomically(temp_pdf, temp_png, paths["pdf"], paths["png"])
        temp_pdf = None
        temp_png = None

        log_output(paths["pdf"])
        log_output(paths["png"])
        print(
            "[元素] Θ；c→z→m；单一 ξ；λ；同框分格 δ/δ_surr；"
            "方法 plate 内方形观测因子与 d_k；disjoint-union 脚注"
        )
        print("[完成] 图 2 PDF/PNG 已成对发布；未生成图 6。")
        return 0
    finally:
        if fig is not None:
            try:
                import matplotlib.pyplot as plt

                plt.close(fig)
            except Exception:
                pass
        for temp in (temp_pdf, temp_png):
            if temp is not None:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RenderError as exc:
        print(f"[失败关闭] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
