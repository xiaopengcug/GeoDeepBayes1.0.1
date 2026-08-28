#!/usr/bin/env python3
"""生成论文 Figure 3 的多尺度参数化设计图；静态门未通过时不渲染。"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# 本脚本兼容 ``python -B``，不依赖或主动创建字节码缓存。
FIXED_SOURCE_DATE_EPOCH = 946684800
OUTPUT_STEM = "figure-3-multiscale-parameterisation"
BOUNDARY_TEXT = "parameterisation design; no multi-scale demonstration is claimed"

TITLE_TEXT = "Multi-scale parameterisation"
DEPTH_HEADING = "Depth-band organisation"
POD_HEADING = "Per-scale POD and reduced coordinates"
TRANSFER_HEADING = "Change of support"
OBSERVATION_HEADING = "Observation support"
DEPTH_ARROW_TEXT = "Increasing depth"

SCALE_ORDER = ("shallow", "intermediate", "deep", "regional")
DISPLAY_ROLES = (
    "depth_band",
    "reduced_coordinates",
    "change_of_support",
    "observation_support",
)
FORBIDDEN_EDGE_RELATIONS = (
    "contains",
    "refines",
    "nested_in",
    "parent_of",
    "child_of",
)
FORBIDDEN_VISIBLE_TERMS = (
    "pyramid",
    "refinement",
    "refines",
    "nested",
    "contains",
    "runtime",
    "result",
    "performance",
    "accuracy",
    "speedup",
    "outperform",
    "improvement",
    "effectiveness",
    "novel",
    "novelty",
    "validated",
)
REQUIRED_VISIBLE_FRAGMENTS = (
    "depth-band organisation",
    "pod basis",
    "reduced coordinates",
    "change-of-support",
    "observation support",
)


class FigureDesignError(RuntimeError):
    """图件设计或失败关闭探针未满足约束。"""


@dataclass(frozen=True)
class NodeSpec:
    """纯内存节点规格；坐标均为画布归一化坐标。"""

    key: str
    role: str
    scale: str | None
    label: str
    center_x: float
    center_y: float
    width: float
    height: float


@dataclass(frozen=True)
class EdgeSpec:
    """纯内存语义边规格。"""

    source: str
    target: str
    relation: str


@dataclass(frozen=True)
class StyleSpec:
    """颜色、灰度顺序、形状和线型的冗余编码。"""

    role: str
    face_color: str
    gray_rank: int
    shape: str
    line_style: str
    hatch: str


@dataclass(frozen=True)
class DesignSpec:
    """渲染前可完整验证的不可变图件规格。"""

    nodes: tuple[NodeSpec, ...]
    edges: tuple[EdgeSpec, ...]
    styles: tuple[StyleSpec, ...]
    fixed_texts: tuple[str, ...]


def require(condition: bool, message: str) -> None:
    """以统一异常执行失败关闭检查。"""
    if not condition:
        raise FigureDesignError(message)


def build_design() -> DesignSpec:
    """构造并列深度带及其逐尺度 POD、变支撑和观测支撑。"""
    scale_rows = (
        ("shallow", "Shallow band", "POD basis\nshallow reduced coordinates", 0.72),
        (
            "intermediate",
            "Intermediate band",
            "POD basis\nintermediate reduced coordinates",
            0.58,
        ),
        ("deep", "Deep band", "POD basis\ndeep reduced coordinates", 0.44),
        (
            "regional",
            "Regional long-wavelength band",
            "POD basis\nregional reduced coordinates",
            0.30,
        ),
    )

    nodes: list[NodeSpec] = []
    edges: list[EdgeSpec] = []
    for scale, band_label, pod_label, center_y in scale_rows:
        band_key = f"band_{scale}"
        pod_key = f"pod_{scale}"
        nodes.append(
            NodeSpec(
                key=band_key,
                role="depth_band",
                scale=scale,
                label=band_label,
                center_x=0.17,
                center_y=center_y,
                width=0.22,
                height=0.09,
            )
        )
        nodes.append(
            NodeSpec(
                key=pod_key,
                role="reduced_coordinates",
                scale=scale,
                label=pod_label,
                center_x=0.49,
                center_y=center_y,
                width=0.26,
                height=0.09,
            )
        )
        edges.append(EdgeSpec(band_key, pod_key, "parameterises"))
        edges.append(EdgeSpec(pod_key, "support_operator", "support_transfer_input"))

    nodes.extend(
        (
            NodeSpec(
                key="support_operator",
                role="change_of_support",
                scale=None,
                label="Change-of-support\noperator",
                center_x=0.73,
                center_y=0.51,
                width=0.19,
                height=0.25,
            ),
            NodeSpec(
                key="observation_field",
                role="observation_support",
                scale=None,
                label="Field on\nobservation support",
                center_x=0.91,
                center_y=0.51,
                width=0.15,
                height=0.13,
            ),
        )
    )
    edges.append(
        EdgeSpec(
            "support_operator",
            "observation_field",
            "projects_to_observation_support",
        )
    )

    styles = (
        StyleSpec("depth_band", "#E8F1F8", 4, "rectangle", "solid", ""),
        StyleSpec("reduced_coordinates", "#E9C46A", 3, "hexagon", "dashed", ""),
        StyleSpec("change_of_support", "#79B791", 2, "diamond", "dashdot", ""),
        StyleSpec("observation_support", "#9B7EAC", 1, "ellipse", "dotted", ""),
    )
    fixed_texts = (
        TITLE_TEXT,
        DEPTH_HEADING,
        POD_HEADING,
        TRANSFER_HEADING,
        OBSERVATION_HEADING,
        DEPTH_ARROW_TEXT,
        BOUNDARY_TEXT,
    )
    return DesignSpec(tuple(nodes), tuple(edges), styles, fixed_texts)


def _all_visible_texts(design: DesignSpec) -> tuple[str, ...]:
    """返回所有可能烙入画布的文字。"""
    return design.fixed_texts + tuple(node.label for node in design.nodes)


def _validate_visible_texts(texts: Iterable[str]) -> None:
    """拒绝中文、数字、结果性措辞及边界声明缺失。"""
    materialized = tuple(texts)
    require(bool(materialized), "图面文字集合为空。")
    require(all(isinstance(text, str) and text.strip() for text in materialized), "图面含空文字。")
    combined = "\n".join(materialized)
    lowered = combined.lower()

    require(
        re.search(r"[㐀-䶿一-鿿豈-﫿]", combined) is None,
        "图面文字含中文字符；图面必须全英文。",
    )
    require(
        re.search(r"[0-9０-９]", combined) is None,
        "图面文字含非法数字字符。",
    )
    for term in FORBIDDEN_VISIBLE_TERMS:
        require(term not in lowered, f"图面含禁止措辞：{term}")
    for fragment in REQUIRED_VISIBLE_FRAGMENTS:
        require(fragment in lowered, f"图面缺少必要机制文字：{fragment}")
    boundary_count = sum(text.count(BOUNDARY_TEXT) for text in materialized)
    require(boundary_count == 1, "图面边界声明必须逐字出现且仅出现一次。")


def _hex_luminance(color: str) -> float:
    """计算十六进制颜色的相对亮度，用于静态灰度顺序检查。"""
    require(bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", color)), f"颜色格式无效：{color}")
    channels = [int(color[index : index + 2], 16) / 255.0 for index in (1, 3, 5)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _rectangle_contains(outer: NodeSpec, inner: NodeSpec) -> bool:
    """判断一个节点包围盒是否包含另一个节点包围盒。"""
    outer_left = outer.center_x - outer.width / 2.0
    outer_right = outer.center_x + outer.width / 2.0
    outer_bottom = outer.center_y - outer.height / 2.0
    outer_top = outer.center_y + outer.height / 2.0
    inner_left = inner.center_x - inner.width / 2.0
    inner_right = inner.center_x + inner.width / 2.0
    inner_bottom = inner.center_y - inner.height / 2.0
    inner_top = inner.center_y + inner.height / 2.0
    return (
        outer_left <= inner_left
        and outer_right >= inner_right
        and outer_bottom <= inner_bottom
        and outer_top >= inner_top
    )


def validate_design(design: DesignSpec) -> None:
    """验证机制完备性、并列几何、禁边、文字和冗余编码。"""
    require(isinstance(design, DesignSpec), "图件规格类型无效。")
    node_by_key = {node.key: node for node in design.nodes}
    require(len(node_by_key) == len(design.nodes), "节点键重复。")

    for node in design.nodes:
        require(node.width > 0.0 and node.height > 0.0, f"节点尺寸非正：{node.key}")
        require(
            0.0 <= node.center_x - node.width / 2.0
            and node.center_x + node.width / 2.0 <= 1.0
            and 0.0 <= node.center_y - node.height / 2.0
            and node.center_y + node.height / 2.0 <= 1.0,
            f"节点越出归一化画布：{node.key}",
        )

    role_set = {node.role for node in design.nodes}
    for role in DISPLAY_ROLES:
        require(role in role_set, f"缺少必要机制角色：{role}")

    bands = {node.scale: node for node in design.nodes if node.role == "depth_band"}
    pods = {
        node.scale: node
        for node in design.nodes
        if node.role == "reduced_coordinates"
    }
    require(set(bands) == set(SCALE_ORDER), "深度带集合不完整或含未知尺度。")
    require(set(pods) == set(SCALE_ORDER), "逐尺度 POD 集合不完整或含未知尺度。")
    require(len(bands) == len(SCALE_ORDER), "每个尺度必须恰有一个深度带。")
    require(len(pods) == len(SCALE_ORDER), "每个尺度必须恰有一个 POD 坐标节点。")

    ordered_bands = [bands[scale] for scale in SCALE_ORDER]
    first_band = ordered_bands[0]
    for band in ordered_bands[1:]:
        require(
            abs(band.center_x - first_band.center_x) <= 1e-12
            and abs(band.width - first_band.width) <= 1e-12
            and abs(band.height - first_band.height) <= 1e-12,
            "深度带必须同宽、同高并列，禁止金字塔或逐级细化几何。",
        )
    require(
        all(
            ordered_bands[index].center_y > ordered_bands[index + 1].center_y
            for index in range(len(ordered_bands) - 1)
        ),
        "深度带顺序必须沿深度方向单调排列。",
    )
    for left_index, left_band in enumerate(ordered_bands):
        for right_band in ordered_bands[left_index + 1 :]:
            require(
                not _rectangle_contains(left_band, right_band)
                and not _rectangle_contains(right_band, left_band),
                "深度带之间禁止几何包含关系。",
            )
            vertical_gap = abs(left_band.center_y - right_band.center_y)
            require(
                vertical_gap > (left_band.height + right_band.height) / 2.0,
                "并列深度带不得重叠。",
            )

    for scale in SCALE_ORDER:
        require(
            abs(bands[scale].center_y - pods[scale].center_y) <= 1e-12,
            f"深度带与其 POD 节点未按尺度对齐：{scale}",
        )
        require("POD basis" in pods[scale].label, f"POD 节点缺少基底标识：{scale}")
        require(
            "reduced coordinates" in pods[scale].label,
            f"POD 节点缺少降阶坐标标识：{scale}",
        )

    support_nodes = [node for node in design.nodes if node.role == "change_of_support"]
    observation_nodes = [node for node in design.nodes if node.role == "observation_support"]
    require(len(support_nodes) == 1, "变支撑算子必须恰有一个。")
    require(len(observation_nodes) == 1, "观测支撑节点必须恰有一个。")

    edge_tuples = {(edge.source, edge.target, edge.relation) for edge in design.edges}
    require(len(edge_tuples) == len(design.edges), "语义边重复。")
    for edge in design.edges:
        require(edge.source in node_by_key, f"边源节点不存在：{edge.source}")
        require(edge.target in node_by_key, f"边目标节点不存在：{edge.target}")
        require(edge.source != edge.target, f"禁止自环边：{edge.source}")
        require(
            edge.relation not in FORBIDDEN_EDGE_RELATIONS,
            f"检测到禁止的包含或细化边：{edge.relation}",
        )
        source_role = node_by_key[edge.source].role
        target_role = node_by_key[edge.target].role
        require(
            not (source_role == "depth_band" and target_role == "depth_band"),
            "深度带之间禁止任何语义边。",
        )

    expected_edges: set[tuple[str, str, str]] = set()
    for scale in SCALE_ORDER:
        expected_edges.add((f"band_{scale}", f"pod_{scale}", "parameterises"))
        expected_edges.add(
            (f"pod_{scale}", "support_operator", "support_transfer_input")
        )
    expected_edges.add(
        (
            "support_operator",
            "observation_field",
            "projects_to_observation_support",
        )
    )
    require(edge_tuples == expected_edges, "语义边集合偏离冻结机制图。")

    styles = {style.role: style for style in design.styles}
    require(len(styles) == len(design.styles), "样式角色重复。")
    require(set(styles) == set(DISPLAY_ROLES), "样式角色集合不完整。")
    selected = [styles[role] for role in DISPLAY_ROLES]
    require(len({style.face_color for style in selected}) == len(selected), "颜色编码未区分角色。")
    require(len({style.gray_rank for style in selected}) == len(selected), "灰度顺序未区分角色。")
    require(len({style.shape for style in selected}) == len(selected), "形状编码未区分角色。")
    require(len({style.line_style for style in selected}) == len(selected), "线型编码未区分角色。")
    require(
        all(not style.hatch for style in selected),
        "文字节点下方禁止 hatch；角色区分由灰度、形状和线型共同承担。",
    )

    luminance_by_rank = sorted(
        ((style.gray_rank, _hex_luminance(style.face_color)) for style in selected),
        key=lambda item: item[0],
    )
    require(
        all(
            luminance_by_rank[index + 1][1] - luminance_by_rank[index][1] >= 0.05
            for index in range(len(luminance_by_rank) - 1)
        ),
        "颜色转灰度后的亮度间隔不足。",
    )
    _validate_visible_texts(_all_visible_texts(design))


def _without_role(design: DesignSpec, role: str) -> DesignSpec:
    """构造缺失指定机制的纯内存变异体。"""
    removed = {node.key for node in design.nodes if node.role == role}
    return replace(
        design,
        nodes=tuple(node for node in design.nodes if node.key not in removed),
        edges=tuple(
            edge
            for edge in design.edges
            if edge.source not in removed and edge.target not in removed
        ),
    )


def _expect_rejected(name: str, candidate: DesignSpec) -> str:
    """要求变异体被静态门拒绝，否则探针本身失败。"""
    try:
        validate_design(candidate)
    except FigureDesignError:
        return f"{name}=PASS"
    raise FigureDesignError(f"失败关闭探针未拒绝变异体：{name}")


def _expect_canvas_design_rejected(name: str, candidate: DesignSpec) -> str:
    """要求只在真实排版后暴露的几何变异被画布门拒绝。"""
    try:
        fig = render_figure(candidate)
    except FigureDesignError:
        return f"{name}=PASS"
    import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

    plt.close(fig)
    raise FigureDesignError(f"失败关闭探针未拒绝画布变异体：{name}")


def _probe_real_artist_empty_text() -> str:
    """第 9 号探针：真实非空标签变异为空串必须被检出（0→1）。

    在内存中构建真实 Figure（不保存任何输出），先确认基线检查 0 检出，再把
    一个真实的非空文本 artist 置为空串，同一检查必须翻为失败；同时枚举运行时
    被豁免的空文本 Annotation 计数，期望恰为 10。
    """
    design = build_design()
    validate_design(design)
    fig = render_figure(design)
    try:
        ax = fig.axes[0]
        from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

        exempted = [
            text
            for text in ax.texts
            if isinstance(text, Annotation) and not text.get_text().strip()
        ]
        require(
            len(exempted) == 10,
            f"被豁免的空文本 Annotation 计数异常：{len(exempted)}（期望 10）。",
        )
        _validate_visible_texts(_collect_canvas_texts(ax))

        real_label = next(
            text
            for text in ax.texts
            if text.get_visible()
            and not isinstance(text, Annotation)
            and text.get_text().strip()
        )
        real_label.set_text("")
        try:
            _validate_visible_texts(_collect_canvas_texts(ax))
        except FigureDesignError:
            return (
                "PROBE_REAL_ARTIST_EMPTY_TEXT=PASS "
                f"exempted_annotations={len(exempted)}"
            )
        raise FigureDesignError("失败关闭探针未拒绝变异体：PROBE_REAL_ARTIST_EMPTY_TEXT")
    finally:
        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

        plt.close(fig)


def selfcheck(verbose: bool = False) -> tuple[str, ...]:
    """做纯内存静态检查与失败构造；画布探针绝不保存任何输出。"""
    design = build_design()
    validate_design(design)
    reports = ["STATIC_BASE=PASS"]

    restored_texture = replace(
        design,
        styles=tuple(
            replace(style, hatch="///")
            if style.role == "reduced_coordinates"
            else style
            for style in design.styles
        ),
    )
    reports.append(
        _expect_rejected("PROBE_TEXT_TEXTURE_RESTORED", restored_texture)
    )

    small_diamond = replace(
        design,
        nodes=tuple(
            replace(node, width=0.13, height=0.18)
            if node.key == "support_operator"
            else node
            for node in design.nodes
        ),
    )
    reports.append(
        _expect_canvas_design_rejected(
            "PROBE_SUPPORT_DIAMOND_TOO_SMALL", small_diamond
        )
    )

    forbidden_edge = replace(
        design,
        edges=design.edges
        + (EdgeSpec("band_shallow", "band_deep", "contains"),),
    )
    reports.append(_expect_rejected("PROBE_FORBIDDEN_EDGE", forbidden_edge))

    tapered_nodes = []
    for node in design.nodes:
        if node.role == "depth_band":
            scale_index = SCALE_ORDER.index(node.scale or "")
            tapered_nodes.append(replace(node, width=node.width - 0.025 * scale_index))
        else:
            tapered_nodes.append(node)
    reports.append(
        _expect_rejected(
            "PROBE_PYRAMID_GEOMETRY",
            replace(design, nodes=tuple(tapered_nodes)),
        )
    )

    reports.append(
        _expect_rejected(
            "PROBE_MISSING_DEPTH_BANDS",
            _without_role(design, "depth_band"),
        )
    )
    reports.append(
        _expect_rejected(
            "PROBE_MISSING_POD_COORDINATES",
            _without_role(design, "reduced_coordinates"),
        )
    )
    reports.append(
        _expect_rejected(
            "PROBE_MISSING_CHANGE_OF_SUPPORT",
            _without_role(design, "change_of_support"),
        )
    )

    missing_boundary = replace(
        design,
        fixed_texts=tuple(text for text in design.fixed_texts if text != BOUNDARY_TEXT),
    )
    reports.append(_expect_rejected("PROBE_MISSING_BOUNDARY", missing_boundary))

    cjk_text = replace(design, fixed_texts=design.fixed_texts + ("中文图面",))
    reports.append(_expect_rejected("PROBE_CJK_VISIBLE_TEXT", cjk_text))

    numeric_text = replace(design, fixed_texts=design.fixed_texts + ("Band 1",))
    reports.append(_expect_rejected("PROBE_NUMERIC_VISIBLE_TEXT", numeric_text))

    reports.append(_probe_real_artist_empty_text())
    reports.append("STATIC_SELFCHECK=PASS probes=11")
    result = tuple(reports)
    if verbose:
        for report in result:
            print(report)
    return result


def _style_map(design: DesignSpec) -> dict[str, StyleSpec]:
    """按角色索引已验证样式。"""
    return {style.role: style for style in design.styles}


def _draw_node(ax, node: NodeSpec, style: StyleSpec) -> None:
    """按角色形状绘制单个节点；仅由渲染路径调用。"""
    from matplotlib.patches import Ellipse, Polygon, Rectangle

    left = node.center_x - node.width / 2.0
    bottom = node.center_y - node.height / 2.0
    common = {
        "facecolor": style.face_color,
        "edgecolor": "#1F2933",
        "linewidth": 1.5,
        "linestyle": style.line_style,
        "hatch": style.hatch,
        "zorder": 3,
    }

    if style.shape == "rectangle":
        patch = Rectangle((left, bottom), node.width, node.height, **common)
    elif style.shape == "hexagon":
        inset = node.width * 0.10
        points = (
            (left + inset, bottom),
            (left + node.width - inset, bottom),
            (left + node.width, node.center_y),
            (left + node.width - inset, bottom + node.height),
            (left + inset, bottom + node.height),
            (left, node.center_y),
        )
        patch = Polygon(points, closed=True, **common)
    elif style.shape == "diamond":
        points = (
            (node.center_x, bottom + node.height),
            (left + node.width, node.center_y),
            (node.center_x, bottom),
            (left, node.center_y),
        )
        patch = Polygon(points, closed=True, **common)
    elif style.shape == "ellipse":
        patch = Ellipse(
            (node.center_x, node.center_y),
            node.width,
            node.height,
            **common,
        )
    else:
        raise FigureDesignError(f"未知节点形状：{style.shape}")

    ax.add_patch(patch)
    patch.set_gid(f"node:{node.key}")
    label = ax.text(
        node.center_x,
        node.center_y,
        node.label,
        ha="center",
        va="center",
        fontsize=8.4 if node.role != "depth_band" else 9.0,
        color="#111827",
        linespacing=1.15,
        zorder=4,
    )
    label.set_gid(f"node:{node.key}")


def _draw_edges(ax, design: DesignSpec) -> None:
    """绘制三类有向边；深度带之间永不连边。"""
    nodes = {node.key: node for node in design.nodes}
    target_offsets = {
        "shallow": 0.060,
        "intermediate": 0.020,
        "deep": -0.020,
        "regional": -0.060,
    }
    relation_styles = {
        "parameterises": "solid",
        "support_transfer_input": "dashed",
        "projects_to_observation_support": "dashdot",
    }

    for edge in design.edges:
        source = nodes[edge.source]
        target = nodes[edge.target]
        start = (source.center_x + source.width / 2.0, source.center_y)
        end = (target.center_x - target.width / 2.0, target.center_y)
        connection = "arc3,rad=0"
        if edge.relation == "support_transfer_input":
            end = (
                target.center_x - target.width / 2.0,
                target.center_y + target_offsets[source.scale or "shallow"],
            )
            connection = "arc3,rad=0.08" if source.center_y >= target.center_y else "arc3,rad=-0.08"
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#334155",
                "linewidth": 1.35,
                "linestyle": relation_styles[edge.relation],
                "shrinkA": 2.0,
                "shrinkB": 2.0,
                "connectionstyle": connection,
            },
            zorder=2,
        )


def _configure_determinism() -> datetime:
    """在导入 Matplotlib 前固定 SOURCE_DATE_EPOCH 与 PDF 日期。"""
    os.environ["SOURCE_DATE_EPOCH"] = str(FIXED_SOURCE_DATE_EPOCH)
    return datetime.fromtimestamp(FIXED_SOURCE_DATE_EPOCH, tz=timezone.utc)


def _collect_canvas_texts(ax) -> tuple[str, ...]:
    """收集画布可见文字；仅豁免「Annotation 且文本为空」的纯箭头。

    Matplotlib 的 ``ax.annotate("", arrowprops=...)`` 惯用法会创建文本为空串的
    Annotation artist，其上只渲染箭头、不渲染任何字形；该机制性空文本不构成
    图面文字，故在收集时豁免。其余任何空文本（例如真实标签漏赋值）仍交由
    _validate_visible_texts 失败关闭。
    """
    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    return tuple(
        text.get_text()
        for text in ax.texts
        if text.get_visible()
        and not (isinstance(text, Annotation) and not text.get_text().strip())
    )


def _validate_canvas(fig, design: DesignSpec) -> None:
    """按真实 renderer 检查文字完全内含且与纹理分离。"""
    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    require(len(fig.axes) == 1, "禁双轴：整图必须只有单一 Axes。")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax = fig.axes[0]
    _validate_visible_texts(_collect_canvas_texts(ax))

    patches = {
        patch.get_gid().split(":", 1)[1]: patch
        for patch in ax.patches
        if isinstance(patch.get_gid(), str) and patch.get_gid().startswith("node:")
    }
    labels = {
        artist.get_gid().split(":", 1)[1]: artist
        for artist in ax.texts
        if isinstance(artist.get_gid(), str) and artist.get_gid().startswith("node:")
    }
    expected = {node.key for node in design.nodes}
    require(set(patches) == expected, "画布节点 patch 集合与设计规格不一致。")
    require(set(labels) == expected, "画布节点文字集合与设计规格不一致。")

    for key in sorted(expected):
        patch = patches[key]
        label = labels[key]
        require(not patch.get_hatch(), f"文字节点下方存在 hatch：{key}")
        require(
            patch.get_facecolor()[3] >= 0.99,
            f"文字节点缺少不透明底：{key}",
        )
        bbox = label.get_window_extent(renderer)
        clearance = 3.0
        corners = (
            (bbox.x0 - clearance, bbox.y0 - clearance),
            (bbox.x0 - clearance, bbox.y1 + clearance),
            (bbox.x1 + clearance, bbox.y0 - clearance),
            (bbox.x1 + clearance, bbox.y1 + clearance),
        )
        shape = patch.get_path().transformed(patch.get_transform())
        require(
            all(shape.contains_points(corners, radius=-2.0)),
            f"节点文字越出形状或未保留清晰间隔：{key}；"
            f"shape={tuple(round(value, 1) for value in shape.get_extents().extents)}；"
            f"text={tuple(round(value, 1) for value in bbox.extents)}",
        )

    arrows = [
        artist.arrow_patch
        for artist in ax.texts
        if isinstance(artist, Annotation) and artist.arrow_patch is not None
    ]
    require(len(arrows) == 10, f"真实连接线计数异常：{len(arrows)}（期望 10）。")
    node_zorder = min(patch.get_zorder() for patch in patches.values())
    require(
        all(arrow.get_zorder() < node_zorder for arrow in arrows),
        "连接线必须位于不透明文字节点下层，禁止穿字。",
    )


def render_figure(design: DesignSpec):
    """渲染已通过静态门的设计；本函数不会在 import 或 selfcheck 时调用。"""
    validate_design(design)
    _configure_determinism()

    import matplotlib

    matplotlib.use("Agg", force=True)
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.0,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(13.5, 6.2))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_axis_off()

    ax.text(0.5, 0.965, TITLE_TEXT, ha="center", va="top", fontsize=15, fontweight="bold")
    ax.text(0.17, 0.855, DEPTH_HEADING, ha="center", va="center", fontsize=10, fontweight="bold")
    ax.text(0.49, 0.855, POD_HEADING, ha="center", va="center", fontsize=10, fontweight="bold")
    ax.text(0.73, 0.855, TRANSFER_HEADING, ha="center", va="center", fontsize=10, fontweight="bold")
    ax.text(0.91, 0.855, OBSERVATION_HEADING, ha="center", va="center", fontsize=10, fontweight="bold")

    ax.annotate(
        "",
        xy=(0.025, 0.255),
        xytext=(0.025, 0.775),
        arrowprops={"arrowstyle": "-|>", "color": "#334155", "linewidth": 1.4},
    )
    ax.text(0.011, 0.515, DEPTH_ARROW_TEXT, rotation=90, ha="center", va="center", fontsize=8.5, color="#334155")

    styles = _style_map(design)
    for node in design.nodes:
        _draw_node(ax, node, styles[node.role])
    _draw_edges(ax, design)

    boundary_box = FancyBboxPatch(
        (0.18, 0.065),
        0.64,
        0.075,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        facecolor="#F8FAFC",
        edgecolor="#475569",
        linewidth=1.2,
        linestyle=(0, (4, 2)),
        zorder=1,
    )
    ax.add_patch(boundary_box)
    ax.text(0.50, 0.1025, BOUNDARY_TEXT, ha="center", va="center", fontsize=9.3, color="#1F2933", zorder=4)

    try:
        _validate_canvas(fig, design)
    except FigureDesignError:
        plt.close(fig)
        raise
    return fig


def output_paths() -> tuple[Path, Path]:
    """将 PDF/PNG 固定到与论文正文相同的 manuscript 目录。"""
    output_dir = Path(__file__).resolve().parent.parent / "manuscript"
    require(output_dir.is_dir(), f"脚本输出目录不存在：{output_dir}")
    return output_dir / f"{OUTPUT_STEM}.pdf", output_dir / f"{OUTPUT_STEM}.png"


def save_outputs(fig) -> tuple[Path, Path]:
    """保存固定日期元数据的 PDF 与 PNG；仅由 main 的渲染路径调用。"""
    pdf_path, png_path = output_paths()
    fixed_pdf_date = datetime.fromtimestamp(FIXED_SOURCE_DATE_EPOCH, tz=timezone.utc)
    fig.savefig(
        pdf_path,
        format="pdf",
        bbox_inches="tight",
        metadata={
            "Creator": "GeoDeepBayes paper figure",
            "CreationDate": fixed_pdf_date,
            "ModDate": fixed_pdf_date,
        },
    )
    fig.savefig(
        png_path,
        format="png",
        dpi=450,
        bbox_inches="tight",
        metadata={"Software": "Matplotlib"},
    )
    return pdf_path, png_path


def main() -> int:
    """先执行纯静态门，再显式渲染并输出到脚本目录。"""
    selfcheck(verbose=True)
    design = build_design()
    fig = render_figure(design)
    try:
        pdf_path, png_path = save_outputs(fig)
    finally:
        import matplotlib.pyplot as plt

        plt.close(fig)
    print(f"[完成] PDF：{pdf_path}")
    print(f"[完成] PNG：{png_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FigureDesignError as exc:
        print(f"[失败关闭] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
