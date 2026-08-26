#!/usr/bin/env python3
"""生成论文 Figure 1（框架-治理双层架构）渲染脚本；静态门未通过时不渲染。

依据 stage2-writing/drafts/figures-1-6-specs.md 图 2 节（几何骨架与 F2-1..F2-4）：
- 上层 LAYER 1 · FRAMEWORK：priors (source-disciplined) -> joint posterior
  (shared-error likelihood) -> decision-layer interface；
- 层间注记 "every claim must cite" 自 LAYER 1 下指 LAYER 2；
- 下层 LAYER 2 · GOVERNANCE：恰四个构件——hash-bound evidence registry、
  pre-registered diagnostics contract、gate-item admission rule 横向衔接，
  三者汇入 mandatory failure co-disclosure；每项只有名称加一句功能，
  不展开内部结构；
- 回路必须闭合：co-disclosure 以 "feeds back as a claim boundary" 回指
  decision-layer interface（治理层约束框架层能主张什么，非单向注释）。

制图纪律全部写成失败关闭断言（默认拒绝，例外仅限显式冻结项）：
- F2-1 治理层恰四个构件（缺 gate-item admission rule 或加第五项均 FAIL）；
- F2-2 回路闭合（删回指边或改单向均 FAIL，画布级再按真实 Annotation 的
  箭头端点方向复核）；
- F2-3 图面零 evidence_id、零读数、零数字（仅两个层标题含序号词且整串冻结）；
- F2-4 不展开任何构件内部结构（每构件恰两行：名称+一句功能；构件内部
  词汇表 criterion/criteria/column/schema/field 一律禁现）；
- 灰度可读（亮度间隔门）、形状/线型/纹理冗余编码（不靠颜色单独区分）、
  禁双轴（画布必须恰一个 Axes）、图上文字全英文、无运行读数与新颖性主张。

selfcheck 自带纯内存变异探针：探针改写真实绘图规格（build_design 的输出）
或真实 artist 文字，再要求对应静态门翻为 FAIL；在内存中构建 Figure 验证
门的行为，但绝不保存任何输出。确定性：SOURCE_DATE_EPOCH=1787356800，PDF
/CreationDate 与 /ModDate 固定 D:20260822000000Z，输出到脚本所在目录。
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

# 本脚本兼容 ``python -B``，不依赖或主动创建字节码缓存。
FIXED_SOURCE_DATE_EPOCH = 1787356800
PDF_DATE_PIN = "D:20260822000000Z"
OUTPUT_STEM = "figure-1-framework-governance"

TITLE_TEXT = "Framework-governance two-layer architecture"
LAYER1_TITLE = "LAYER 1 · FRAMEWORK"
LAYER2_TITLE = "LAYER 2 · GOVERNANCE"
CITE_TEXT = "every claim must cite"
RETURN_TEXT = "feeds back as a claim boundary"

# F2-1：当前四项紧凑正典（P5 与摘要）；gate-item admission rule 最易漏画。
FROZEN_GOVERNANCE_NAMES = (
    "Hash-bound evidence registry",
    "Pre-registered diagnostics contract",
    "Gate-item admission rule",
    "Mandatory failure co-disclosure",
)
GOVERNANCE_NODE_KEYS = (
    "evidence_registry",
    "diagnostics_contract",
    "admission_rule",
    "co_disclosure",
)
FRAMEWORK_NODE_KEYS = ("priors", "joint_posterior", "decision_interface")

# F2-3 唯一允许含数字的文字：两个层标题，整串冻结、各恰出现一次。
SANCTIONED_DIGIT_TEXTS = (LAYER1_TITLE, LAYER2_TITLE)

FORBIDDEN_VISIBLE_TERMS = (
    "evidence_id",
    "evidence-id",
    "r-hat",
    "misfit",
    "acceptance",
    "seed",
    "run-id",
    "novel",
    "novelty",
    "state-of-the-art",
    "outperform",
    "improvement",
    "superior",
    "validated",
    "performance",
    "accuracy",
    "speedup",
    "result",
    "criterion",
    "criteria",
    "column",
    "schema",
    "field",
)
REQUIRED_VISIBLE_FRAGMENTS = (
    "priors",
    "source-disciplined",
    "joint posterior",
    "shared-error likelihood",
    "decision-layer",
    "hash-bound evidence registry",
    "pre-registered diagnostics contract",
    "gate-item admission rule",
    "mandatory failure co-disclosure",
    "every claim must cite",
    "feeds back as a claim boundary",
    "framework",
    "governance",
)

# 冻结语义边集：(source, target, relation, label)。label 非空仅限两条层间边。
EXPECTED_EDGE_TUPLES = frozenset(
    (
        ("priors", "joint_posterior", "informs", ""),
        ("joint_posterior", "decision_interface", "informs", ""),
        ("decision_interface", "evidence_registry", "must_cite", CITE_TEXT),
        ("evidence_registry", "diagnostics_contract", "chains_to", ""),
        ("diagnostics_contract", "admission_rule", "chains_to", ""),
        ("evidence_registry", "co_disclosure", "converges", ""),
        ("diagnostics_contract", "co_disclosure", "converges", ""),
        ("admission_rule", "co_disclosure", "converges", ""),
        ("co_disclosure", "decision_interface", "feeds_back", RETURN_TEXT),
    )
)

# 边类-线型映射：五个边类五种线型，颜色不是任何边类的唯一区分通道。
RELATION_LINE_STYLES = {
    "informs": "solid",
    "chains_to": "dashed",
    "converges": "dotted",
    "must_cite": "dashdot",
    "feeds_back": (0, (5, 1.5)),
}

# 无标签纯箭头（ax.annotate("", arrowprops=...)）的期望计数：
# informs 两条 + chains_to 两条 + converges 三条。
EXPECTED_PURE_ARROW_ANNOTATIONS = 7

TEXT_COLOR = "#1F2933"
EDGE_COLOR = "#334155"
BAND_BORDER_COLOR = "#475569"
CJK_PATTERN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
DIGIT_PATTERN = re.compile(r"[0-9０-９]")


class FigureDesignError(RuntimeError):
    """图件设计或失败关闭探针未满足约束。"""


@dataclass(frozen=True)
class NodeSpec:
    """纯内存节点规格；坐标为画布归一化坐标。"""

    key: str
    role: str
    label: str
    center_x: float
    center_y: float
    width: float
    height: float


@dataclass(frozen=True)
class EdgeSpec:
    """纯内存语义边规格；label 为空串表示无标签纯箭头。"""

    source: str
    target: str
    relation: str
    label: str = ""


@dataclass(frozen=True)
class BandSpec:
    """层带矩形：标题冻结、灰度填充与边框线型双重区分。"""

    key: str
    title: str
    x0: float
    x1: float
    y0: float
    y1: float
    fill_color: str
    border_linestyle: str


@dataclass(frozen=True)
class StyleSpec:
    """颜色、灰度顺序、形状、线型与纹理的冗余编码。"""

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
    bands: tuple[BandSpec, ...]
    styles: tuple[StyleSpec, ...]
    fixed_texts: tuple[str, ...]


def require(condition: bool, message: str) -> None:
    """以统一异常执行失败关闭检查。"""
    if not condition:
        raise FigureDesignError(message)


def build_design() -> DesignSpec:
    """构造框架-治理双层机制的冻结规格。"""
    nodes = (
        NodeSpec(
            "priors",
            "framework_node",
            "Priors\n(source-disciplined)",
            0.20,
            0.745,
            0.20,
            0.13,
        ),
        NodeSpec(
            "joint_posterior",
            "framework_node",
            "Joint posterior\n(shared-error likelihood)",
            0.50,
            0.745,
            0.24,
            0.13,
        ),
        NodeSpec(
            "decision_interface",
            "framework_node",
            "Decision-layer\ninterface",
            0.80,
            0.745,
            0.20,
            0.13,
        ),
        NodeSpec(
            "evidence_registry",
            "governance_component",
            "Hash-bound evidence registry\nbinds every artifact to its source commit",
            0.20,
            0.295,
            0.21,
            0.125,
        ),
        NodeSpec(
            "diagnostics_contract",
            "governance_component",
            "Pre-registered diagnostics contract\nfixes checks before outcomes are read",
            0.50,
            0.295,
            0.23,
            0.125,
        ),
        NodeSpec(
            "admission_rule",
            "governance_component",
            "Gate-item admission rule\nrequires a registered failing construction",
            0.80,
            0.295,
            0.21,
            0.125,
        ),
        NodeSpec(
            "co_disclosure",
            "governance_component",
            "Mandatory failure co-disclosure\npublishes registered failures beside successes",
            0.50,
            0.140,
            0.27,
            0.10,
        ),
    )
    edges = tuple(EdgeSpec(*tup) for tup in sorted(EXPECTED_EDGE_TUPLES))
    bands = (
        BandSpec("layer1", LAYER1_TITLE, 0.03, 0.97, 0.585, 0.905, "#FBFBFB", "solid"),
        BandSpec(
            "layer2", LAYER2_TITLE, 0.03, 0.97, 0.075, 0.420, "#EFEFEF", (0, (6, 3))
        ),
    )
    styles = (
        StyleSpec("framework_node", "#E8F1F8", 2, "sharp_box", "solid", ""),
        StyleSpec("governance_component", "#E9C46A", 1, "rounded_box", "dashed", ".."),
    )
    return DesignSpec(nodes, edges, bands, styles, (TITLE_TEXT,))


def _all_visible_texts(design: DesignSpec) -> tuple[str, ...]:
    """返回规格层面所有可能烙入画布的文字。"""
    return (
        design.fixed_texts
        + tuple(band.title for band in design.bands)
        + tuple(node.label for node in design.nodes)
        + tuple(edge.label for edge in design.edges if edge.label)
    )


def _validate_visible_texts(texts: Iterable[str]) -> None:
    """F2-3 与文字纪律：默认拒绝，例外仅限整串冻结的两个层标题。"""
    materialized = tuple(texts)
    require(bool(materialized), "图面文字集合为空。")
    require(
        all(isinstance(text, str) and text.strip() for text in materialized),
        "图面含空文本（豁免仅限纯箭头 Annotation）。",
    )
    combined = "\n".join(materialized)
    lowered = combined.lower()

    require(
        CJK_PATTERN.search(combined) is None,
        "图面文字含中文字符；图面必须全英文。",
    )
    for title in SANCTIONED_DIGIT_TEXTS:
        require(
            sum(1 for text in materialized if text == title) == 1,
            f"层标题必须整串冻结且恰出现一次：{title}",
        )
    for text in materialized:
        if text in SANCTIONED_DIGIT_TEXTS:
            continue
        require(
            DIGIT_PATTERN.search(text) is None,
            f"图面文字含非法数字（evidence_id/读数/计数）：{text!r}",
        )
    for term in FORBIDDEN_VISIBLE_TERMS:
        require(term not in lowered, f"图面含禁止措辞：{term}")
    for fragment in REQUIRED_VISIBLE_FRAGMENTS:
        require(fragment in lowered, f"图面缺少必要机制文字：{fragment}")
    require(
        sum(text.count(CITE_TEXT) for text in materialized) == 1,
        "层间注记必须逐字出现且仅出现一次：every claim must cite。",
    )
    require(
        sum(text.count(RETURN_TEXT) for text in materialized) == 1,
        "回指文字必须逐字出现且仅出现一次：feeds back as a claim boundary。",
    )


def _hex_luminance(color: str) -> float:
    """计算十六进制颜色的相对亮度，用于灰度可读性检查。"""
    require(bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", color)), f"颜色格式无效：{color}")
    channels = [int(color[index : index + 2], 16) / 255.0 for index in (1, 3, 5)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _rect_inside_band(node: NodeSpec, band: BandSpec) -> bool:
    """判断节点包围盒是否完整位于层带矩形内。"""
    left = node.center_x - node.width / 2.0
    right = node.center_x + node.width / 2.0
    bottom = node.center_y - node.height / 2.0
    top = node.center_y + node.height / 2.0
    return (
        band.x0 <= left
        and right <= band.x1
        and band.y0 <= bottom
        and top <= band.y1
    )


def _nodes_overlap(first: NodeSpec, second: NodeSpec) -> bool:
    """判断同层带内两节点包围盒是否重叠。"""
    return (
        abs(first.center_x - second.center_x) < (first.width + second.width) / 2.0
        and abs(first.center_y - second.center_y) < (first.height + second.height) / 2.0
    )


def validate_design(design: DesignSpec) -> None:
    """验证 F2-1/F2-2/F2-3/F2-4、几何、灰度冗余与文字纪律。"""
    require(isinstance(design, DesignSpec), "图件规格类型无效。")
    node_by_key = {node.key: node for node in design.nodes}
    require(len(node_by_key) == len(design.nodes), "节点键重复。")

    band_by_key = {band.key: band for band in design.bands}
    require(
        len(design.bands) == 2 and set(band_by_key) == {"layer1", "layer2"},
        "必须恰有 LAYER 1 与 LAYER 2 两个层带。",
    )
    band1 = band_by_key["layer1"]
    band2 = band_by_key["layer2"]
    require(
        band1.title == LAYER1_TITLE and band2.title == LAYER2_TITLE,
        "层带标题必须整串冻结。",
    )
    for band in design.bands:
        require(
            0.0 <= band.x0 < band.x1 <= 1.0 and 0.0 <= band.y0 < band.y1 <= 1.0,
            f"层带越出归一化画布：{band.key}",
        )
    require(band1.y0 >= band2.y1, "LAYER 1 必须整体位于 LAYER 2 上方且互不重叠。")
    require(
        _hex_luminance(band1.fill_color) - _hex_luminance(band2.fill_color) >= 0.05,
        "两层的灰度亮度间隔不足，灰度打印下不可分。",
    )
    require(
        band1.border_linestyle != band2.border_linestyle,
        "层带边框线型必须不同（不得仅靠颜色区分层）。",
    )

    styles = {style.role: style for style in design.styles}
    require(len(styles) == len(design.styles), "样式角色重复。")
    require(
        set(styles) == {"framework_node", "governance_component"},
        "样式角色集合不完整。",
    )
    selected = tuple(styles.values())
    require(
        len({style.face_color for style in selected}) == len(selected),
        "颜色编码未区分角色。",
    )
    require(
        len({style.gray_rank for style in selected}) == len(selected),
        "灰度顺序未区分角色。",
    )
    require(len({style.shape for style in selected}) == len(selected), "形状编码未区分角色。")
    require(
        len({style.line_style for style in selected}) == len(selected),
        "线型编码未区分角色。",
    )
    require(len({style.hatch for style in selected}) == len(selected), "纹理编码未区分角色。")
    luminance_by_rank = sorted(
        ((style.gray_rank, _hex_luminance(style.face_color)) for style in selected),
        key=lambda item: item[0],
    )
    require(
        all(
            luminance_by_rank[index + 1][1] - luminance_by_rank[index][1] >= 0.05
            for index in range(len(luminance_by_rank) - 1)
        ),
        "角色填充色转灰度后的亮度间隔不足。",
    )
    fill_colors = [style.face_color for style in selected] + [
        band.fill_color for band in design.bands
    ]
    require(
        min(_hex_luminance(color) for color in fill_colors) - _hex_luminance(TEXT_COLOR)
        >= 0.40,
        "文字与最浅填充的灰度对比不足。",
    )

    role_band = {"framework_node": "layer1", "governance_component": "layer2"}
    for node in design.nodes:
        require(node.width > 0.0 and node.height > 0.0, f"节点尺寸非正：{node.key}")
        require(node.role in role_band, f"未知节点角色：{node.key}")
        require(
            _rect_inside_band(node, band_by_key[role_band[node.role]]),
            f"节点必须完整位于所属层带内：{node.key}",
        )
    for group in (FRAMEWORK_NODE_KEYS, GOVERNANCE_NODE_KEYS):
        # 最小守卫：含缺键的分组跳过几何检查，交还下方键集合等值门与
        # F2-1 计数门以 FigureDesignError 干净拒绝，避免 KeyError 先于设计门逃逸。
        if not set(group) <= set(node_by_key):
            continue
        members = [node_by_key[key] for key in group]
        for left_index, first in enumerate(members):
            for second in members[left_index + 1 :]:
                require(not _nodes_overlap(first, second), f"同层节点不得重叠：{first.key} 与 {second.key}")

    framework_nodes = [node for node in design.nodes if node.role == "framework_node"]
    require(
        {node.key for node in framework_nodes} == set(FRAMEWORK_NODE_KEYS)
        and len(framework_nodes) == len(FRAMEWORK_NODE_KEYS),
        "框架层必须恰为 priors、joint posterior、decision-layer interface 三节点。",
    )
    for node in framework_nodes:
        require(
            node.label.count("\n") <= 1,
            f"框架层节点至多两行：{node.key}",
        )

    governance_nodes = [
        node for node in design.nodes if node.role == "governance_component"
    ]
    require(
        len(governance_nodes) == 4,
        "F2-1：治理层必须恰有四个构件（不是三个，也不是五个）。",
    )
    require(
        {node.key for node in governance_nodes} == set(GOVERNANCE_NODE_KEYS),
        "F2-1：治理构件键集合偏离冻结四项。",
    )
    require(
        {node.label.split("\n")[0] for node in governance_nodes}
        == set(FROZEN_GOVERNANCE_NAMES),
        "F2-1：构件名集合必须等于冻结四项正典（缺 gate-item admission rule 或加第五项均拒绝）。",
    )
    for node in governance_nodes:
        require(
            node.label.count("\n") == 1,
            f"F2-4：治理构件只许名称加一句功能（恰两行）：{node.key}",
        )
        require(
            all(line.strip() for line in node.label.split("\n")),
            f"F2-4：构件名称行与功能行均不得为空：{node.key}",
        )

    edge_tuples = {
        (edge.source, edge.target, edge.relation, edge.label) for edge in design.edges
    }
    require(len(edge_tuples) == len(design.edges), "语义边重复。")
    require(
        edge_tuples == EXPECTED_EDGE_TUPLES,
        "语义边集合偏离冻结机制图（F2-1/F2-2 结构被改动）。",
    )
    for edge in design.edges:
        require(edge.source in node_by_key, f"边源节点不存在：{edge.source}")
        require(edge.target in node_by_key, f"边目标节点不存在：{edge.target}")
        require(edge.source != edge.target, f"禁止自环边：{edge.source}")

    feedback = [edge for edge in design.edges if edge.relation == "feeds_back"]
    require(len(feedback) == 1, "F2-2：回指边必须恰有一条。")
    loop_edge = feedback[0]
    require(
        loop_edge.source == "co_disclosure"
        and node_by_key[loop_edge.source].role == "governance_component",
        "F2-2：回指边必须由 mandatory failure co-disclosure 发出。",
    )
    require(
        loop_edge.target == "decision_interface"
        and node_by_key[loop_edge.target].role == "framework_node",
        "F2-2：回指边必须指向 decision-layer interface（LAYER 2 回指 LAYER 1）。",
    )
    require(loop_edge.label == RETURN_TEXT, "F2-2：回指边文字必须逐字冻结。")
    cite_edges = [edge for edge in design.edges if edge.relation == "must_cite"]
    require(
        len(cite_edges) == 1
        and node_by_key[cite_edges[0].source].role == "framework_node"
        and node_by_key[cite_edges[0].target].role == "governance_component"
        and cite_edges[0].label == CITE_TEXT,
        "F2-2：层间注记边必须恰一条且方向为 LAYER 1 下指 LAYER 2。",
    )

    require(
        set(RELATION_LINE_STYLES) == {tup[2] for tup in EXPECTED_EDGE_TUPLES},
        "边类-线型映射与冻结边集不一致。",
    )
    require(
        len({str(value) for value in RELATION_LINE_STYLES.values()})
        == len(RELATION_LINE_STYLES),
        "各边类线型必须互不相同（不得仅靠颜色区分边类）。",
    )

    _validate_visible_texts(_all_visible_texts(design))


def _without_node(design: DesignSpec, key: str) -> DesignSpec:
    """构造缺失指定构件（连同其关联边）的纯内存变异体。"""
    return replace(
        design,
        nodes=tuple(node for node in design.nodes if node.key != key),
        edges=tuple(
            edge
            for edge in design.edges
            if edge.source != key and edge.target != key
        ),
    )


def _with_relabel(design: DesignSpec, key: str, new_label: str) -> DesignSpec:
    """构造替换指定节点文字的纯内存变异体。"""
    return replace(
        design,
        nodes=tuple(
            replace(node, label=new_label) if node.key == key else node
            for node in design.nodes
        ),
    )


def _expect_rejected(name: str, candidate: DesignSpec) -> str:
    """要求规格级变异体被静态门拒绝，否则探针本身失败。"""
    try:
        validate_design(candidate)
    except FigureDesignError:
        return f"{name}=PASS"
    raise FigureDesignError(f"失败关闭探针未拒绝变异体：{name}")


def _point_in_rect(point: tuple[float, float], band: BandSpec) -> bool:
    """判断点是否位于层带矩形内（含边界）。"""
    return (
        band.x0 <= point[0] <= band.x1 and band.y0 <= point[1] <= band.y1
    )


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
    """在真实画布对象上复跑文字纪律与 F2-2/F2-4 的方向与结构门。"""
    require(len(fig.axes) == 1, "禁双轴：整图必须只有单一 Axes。")
    ax = fig.axes[0]
    texts = _collect_canvas_texts(ax)
    _validate_visible_texts(texts)

    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    exempted = [
        text
        for text in ax.texts
        if isinstance(text, Annotation) and not text.get_text().strip()
    ]
    require(
        len(exempted) == EXPECTED_PURE_ARROW_ANNOTATIONS,
        f"纯箭头（空文本 Annotation）计数异常：{len(exempted)}"
        f"（期望 {EXPECTED_PURE_ARROW_ANNOTATIONS}）。",
    )
    labeled: dict[str, list] = {}
    for artist in ax.texts:
        if isinstance(artist, Annotation) and artist.get_text().strip():
            labeled.setdefault(artist.get_text().strip(), []).append(artist)
    require(
        set(labeled) == {CITE_TEXT, RETURN_TEXT}
        and len(labeled[CITE_TEXT]) == 1
        and len(labeled[RETURN_TEXT]) == 1,
        "带文字的箭头必须恰为层间注记与回指两条，且各只一条。",
    )

    band_by_key = {band.key: band for band in design.bands}
    cite_ann = labeled[CITE_TEXT][0]
    return_ann = labeled[RETURN_TEXT][0]
    cite_tip = tuple(float(value) for value in cite_ann.xy[:2])
    cite_tail = tuple(float(value) for value in cite_ann.get_position()[:2])
    return_tip = tuple(float(value) for value in return_ann.xy[:2])
    return_tail = tuple(float(value) for value in return_ann.get_position()[:2])
    require(
        _point_in_rect(cite_tail, band_by_key["layer1"])
        and _point_in_rect(cite_tip, band_by_key["layer2"])
        and cite_tip[1] < cite_tail[1],
        "F2-2：层间注记箭头必须自 LAYER 1 起笔、指向 LAYER 2（向下）。",
    )
    require(
        _point_in_rect(return_tail, band_by_key["layer2"])
        and _point_in_rect(return_tip, band_by_key["layer1"])
        and return_tip[1] > return_tail[1],
        "F2-2：回指箭头必须自 LAYER 2 起笔、指回 LAYER 1（回路闭合，非单向注释）。",
    )

    for name in FROZEN_GOVERNANCE_NAMES:
        matches = [text for text in texts if name.lower() in text.lower()]
        require(len(matches) == 1, f"治理构件必须恰出现一次：{name}")
        require(
            matches[0].count("\n") == 1,
            f"F2-4：构件只许名称加一句功能（恰两行）：{name}",
        )


def _configure_determinism() -> None:
    """固定 SOURCE_DATE_EPOCH；PDF 日期另由字面量 D:20260822000000Z 钉死。"""
    os.environ["SOURCE_DATE_EPOCH"] = str(FIXED_SOURCE_DATE_EPOCH)


def _draw_band(ax, band: BandSpec) -> None:
    """绘制层带矩形与冻结标题。"""
    from matplotlib.patches import Rectangle  # pylint: disable=import-outside-toplevel

    ax.add_patch(
        Rectangle(
            (band.x0, band.y0),
            band.x1 - band.x0,
            band.y1 - band.y0,
            facecolor=band.fill_color,
            edgecolor=BAND_BORDER_COLOR,
            linewidth=1.4,
            linestyle=band.border_linestyle,
            zorder=1,
        )
    )
    ax.text(
        band.x0 + 0.015,
        band.y1 - 0.028,
        band.title,
        ha="left",
        va="center",
        fontsize=10.5,
        fontweight="semibold",
        color=TEXT_COLOR,
        zorder=2,
    )


def _draw_node(ax, node: NodeSpec, style: StyleSpec) -> None:
    """按角色形状绘制单个节点；仅由渲染路径调用。"""
    from matplotlib.patches import (  # pylint: disable=import-outside-toplevel
        FancyBboxPatch,
        Rectangle,
    )

    left = node.center_x - node.width / 2.0
    bottom = node.center_y - node.height / 2.0
    common = {
        "facecolor": style.face_color,
        "edgecolor": TEXT_COLOR,
        "linewidth": 1.6,
        "linestyle": style.line_style,
        "hatch": style.hatch,
        "zorder": 3,
    }
    if style.shape == "sharp_box":
        patch = Rectangle((left, bottom), node.width, node.height, **common)
    elif style.shape == "rounded_box":
        patch = FancyBboxPatch(
            (left, bottom),
            node.width,
            node.height,
            boxstyle="round,pad=0.006,rounding_size=0.010",
            **common,
        )
    else:
        raise FigureDesignError(f"未知节点形状：{style.shape}")
    ax.add_patch(patch)
    ax.text(
        node.center_x,
        node.center_y,
        node.label,
        ha="center",
        va="center",
        fontsize=8.2 if node.role == "framework_node" else 7.4,
        color=TEXT_COLOR,
        linespacing=1.18,
        zorder=4,
    )


def _edge_geometry(edge: EdgeSpec, nodes: dict[str, NodeSpec]):
    """返回 (起笔点, 箭头端点, 弧度, 文字样式)；方向由冻结边集语义决定。"""
    source = nodes[edge.source]
    target = nodes[edge.target]
    if edge.relation in ("informs", "chains_to"):
        return (
            (source.center_x + source.width / 2.0, source.center_y),
            (target.center_x - target.width / 2.0, target.center_y),
            0.0,
            {},
        )
    if edge.relation == "converges":
        sink = nodes["co_disclosure"]
        offset = {
            "evidence_registry": -0.08,
            "diagnostics_contract": 0.0,
            "admission_rule": 0.08,
        }[edge.source]
        return (
            (source.center_x, source.center_y - source.height / 2.0),
            (sink.center_x + offset, sink.center_y + sink.height / 2.0),
            0.0,
            {},
        )
    if edge.relation == "must_cite":
        tail = (
            source.center_x - 0.065,
            source.center_y - source.height / 2.0 - 0.02,
        )
        tip = (target.center_x + 0.04, target.center_y + target.height / 2.0)
        return tail, tip, -0.15, {"ha": "left", "va": "top", "fontsize": 7.6}
    if edge.relation == "feeds_back":
        tail = (
            source.center_x + source.width / 2.0 + 0.015,
            source.center_y,
        )
        tip = (target.center_x + 0.04, target.center_y - target.height / 2.0)
        return (
            tail,
            tip,
            0.12,
            {
                "ha": "left",
                "va": "bottom",
                "rotation": 90,
                "rotation_mode": "anchor",
                "fontsize": 7.6,
            },
        )
    raise FigureDesignError(f"未知边类：{edge.relation}")


def _draw_edges(ax, design: DesignSpec) -> None:
    """按冻结线型绘制有向边；无标签边即纯箭头。"""
    nodes = {node.key: node for node in design.nodes}
    for edge in design.edges:
        tail, tip, rad, text_kwargs = _edge_geometry(edge, nodes)
        ax.annotate(
            edge.label,
            xy=tip,
            xytext=tail,
            arrowprops={
                "arrowstyle": "-|>",
                "color": EDGE_COLOR,
                "linewidth": 1.35,
                "linestyle": RELATION_LINE_STYLES[edge.relation],
                "shrinkA": 3.0,
                "shrinkB": 1.0,
                "connectionstyle": f"arc3,rad={rad}",
            },
            color=TEXT_COLOR,
            zorder=2,
            **text_kwargs,
        )


def render_figure(design: DesignSpec, validate: bool = True):
    """渲染已通过静态门的设计；selfcheck 仅在内存构建，绝不保存输出。"""
    if validate:
        validate_design(design)
    _configure_determinism()

    import matplotlib  # pylint: disable=import-outside-toplevel

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
    import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

    fig, ax = plt.subplots(figsize=(13.5, 7.0))
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_axis_off()

    ax.text(
        0.5,
        0.965,
        TITLE_TEXT,
        ha="center",
        va="top",
        fontsize=15,
        fontweight="semibold",
        color=TEXT_COLOR,
    )
    for band in design.bands:
        _draw_band(ax, band)
    styles = {style.role: style for style in design.styles}
    for node in design.nodes:
        _draw_node(ax, node, styles[node.role])
    _draw_edges(ax, design)

    _validate_canvas(fig, design)
    return fig


def output_paths() -> tuple[Path, Path]:
    """将 PDF/PNG 最终路径固定在脚本自身目录。"""
    output_dir = Path(__file__).resolve().parent
    require(output_dir.is_dir(), f"脚本输出目录不存在：{output_dir}")
    return output_dir / f"{OUTPUT_STEM}.pdf", output_dir / f"{OUTPUT_STEM}.png"


def save_outputs(fig) -> tuple[Path, Path]:
    """保存固定日期元数据的 PDF 与 PNG；仅由 main 的渲染路径调用。"""
    pdf_path, png_path = output_paths()
    os.environ["SOURCE_DATE_EPOCH"] = str(FIXED_SOURCE_DATE_EPOCH)
    fig.savefig(
        pdf_path,
        format="pdf",
        bbox_inches="tight",
        metadata={
            "Creator": "GeoDeepBayes paper figure",
            "CreationDate": PDF_DATE_PIN,
            "ModDate": PDF_DATE_PIN,
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


def _mutator_remove_return_annotation(fig) -> None:
    """画布级断回路：删除真实回指 Annotation。"""
    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    ax = fig.axes[0]
    targets = [
        artist
        for artist in ax.texts
        if isinstance(artist, Annotation) and artist.get_text().strip() == RETURN_TEXT
    ]
    require(len(targets) == 1, "回指箭头定位失败，探针前置条件不成立。")
    targets[0].remove()


def _mutator_inject_evidence_id(fig) -> None:
    """画布级 F2-3：把真实 Priors 标签改为 evidence_id 读数。"""
    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    ax = fig.axes[0]
    target = next(
        artist
        for artist in ax.texts
        if artist.get_visible()
        and not isinstance(artist, Annotation)
        and "Priors" in artist.get_text()
    )
    target.set_text("evidence_id E-017")


def _mutator_expand_contract_artist(fig) -> None:
    """画布级 F2-4：把真实诊断契约标签追加一行内部判据。"""
    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    ax = fig.axes[0]
    target = next(
        artist
        for artist in ax.texts
        if artist.get_visible()
        and not isinstance(artist, Annotation)
        and "Pre-registered diagnostics contract" in artist.get_text()
    )
    target.set_text(target.get_text() + "\nConvergence criterion")


def _mutator_blank_real_label(fig) -> None:
    """画布级空文本：真实非 Annotation 标签置空必须失败关闭。"""
    from matplotlib.text import Annotation  # pylint: disable=import-outside-toplevel

    ax = fig.axes[0]
    exempted = [
        artist
        for artist in ax.texts
        if isinstance(artist, Annotation) and not artist.get_text().strip()
    ]
    require(
        len(exempted) == EXPECTED_PURE_ARROW_ANNOTATIONS,
        f"被豁免空文本 Annotation 计数异常：{len(exempted)}"
        f"（期望 {EXPECTED_PURE_ARROW_ANNOTATIONS}）。",
    )
    target = next(
        artist
        for artist in ax.texts
        if artist.get_visible()
        and not isinstance(artist, Annotation)
        and "Gate-item admission rule" in artist.get_text()
    )
    target.set_text("")


def _expect_canvas_rejected(name: str, mutate: Callable) -> str:
    """要求画布级变异被真实画布门拒绝；变异步骤独立于期望步骤，不得互相吞错。"""
    design = build_design()
    validate_design(design)
    fig = render_figure(design)
    try:
        mutate(fig)
        try:
            _validate_canvas(fig, design)
        except FigureDesignError:
            return f"{name}=PASS"
    finally:
        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

        plt.close(fig)
    raise FigureDesignError(f"失败关闭探针未拒绝画布变异体：{name}")


def selfcheck(verbose: bool = False) -> tuple[str, ...]:
    """纯内存静态门与五类变异探针；构建真实 Figure 但绝不保存任何输出。

    探针清单（16 项 = 规格级 12 + 画布级 4）：
    - F2-1 删构件 x4：PROBE_F2_1_DROP_COMPONENT:{key}（四个构件逐一删除）；
    - F2-1 加第五构件：PROBE_F2_1_FIFTH_COMPONENT；
    - F2-2 断回路：PROBE_F2_2_BREAK_LOOP（删回指边）；
    - F2-2 改单向：PROBE_F2_2_ONE_WAY_FLIP（回指边反向，仅剩下指）；
    - F2-3 注入 evidence_id：PROBE_F2_3_EVIDENCE_ID；
    - F2-3 注入读数：PROBE_F2_3_READING（acceptance rate 0.27）；
    - F2-3 注入计数数字：PROBE_F2_3_NUMERIC（"4 components" 式计数）；
    - F2-4 展开诊断契约内部：PROBE_F2_4_EXPAND_CONTRACT（四项判据入图）；
    - F2-4 展开注册表字段：PROBE_F2_4_EXPAND_REGISTRY；
    - 画布级四探针：删真实回指箭头、真实标签改 evidence_id、真实契约标签
      追加判据行、真实标签置空串（并核纯箭头豁免计数恰为 7）；
    - 确定性钉子：DETERMINISM_PIN。
    """
    design = build_design()
    validate_design(design)
    reports = ["STATIC_BASE=PASS"]

    _configure_determinism()
    require(
        os.environ.get("SOURCE_DATE_EPOCH") == "1787356800",
        "SOURCE_DATE_EPOCH 未按固定值 1787356800 设置。",
    )
    require(PDF_DATE_PIN == "D:20260822000000Z", "PDF 日期钉死值错误。")
    require(
        datetime.fromtimestamp(FIXED_SOURCE_DATE_EPOCH, tz=timezone.utc).strftime(
            "%Y%m%d%H%M%S"
        )
        == "20260822000000",
        "SOURCE_DATE_EPOCH 与 PDF 日期钉死值不一致。",
    )
    reports.append("DETERMINISM_PIN=PASS")

    for key in GOVERNANCE_NODE_KEYS:
        reports.append(
            _expect_rejected(f"PROBE_F2_1_DROP_COMPONENT:{key}", _without_node(design, key))
        )

    fifth = replace(
        design,
        nodes=design.nodes
        + (
            NodeSpec(
                "failure_ledger",
                "governance_component",
                "Public failure ledger\ncollects every blocked run",
                0.20,
                0.14,
                0.20,
                0.10,
            ),
        ),
    )
    reports.append(_expect_rejected("PROBE_F2_1_FIFTH_COMPONENT", fifth))

    broken_loop = replace(
        design,
        edges=tuple(edge for edge in design.edges if edge.relation != "feeds_back"),
    )
    reports.append(_expect_rejected("PROBE_F2_2_BREAK_LOOP", broken_loop))

    one_way = replace(
        design,
        edges=tuple(
            EdgeSpec("decision_interface", "co_disclosure", "feeds_back", RETURN_TEXT)
            if edge.relation == "feeds_back"
            else edge
            for edge in design.edges
        ),
    )
    reports.append(_expect_rejected("PROBE_F2_2_ONE_WAY_FLIP", one_way))

    reports.append(
        _expect_rejected(
            "PROBE_F2_3_EVIDENCE_ID",
            replace(
                design,
                fixed_texts=design.fixed_texts + ("evidence_id E-017 bound at intake",),
            ),
        )
    )
    reports.append(
        _expect_rejected(
            "PROBE_F2_3_READING",
            replace(
                design,
                fixed_texts=design.fixed_texts + ("acceptance rate 0.27",),
            ),
        )
    )
    reports.append(
        _expect_rejected(
            "PROBE_F2_3_NUMERIC",
            replace(
                design,
                fixed_texts=design.fixed_texts + ("governance has 4 components",),
            ),
        )
    )

    contract_label = next(
        node.label
        for node in design.nodes
        if node.key == "diagnostics_contract"
    )
    expanded_contract = _with_relabel(
        design,
        "diagnostics_contract",
        contract_label
        + "\nConvergence criterion\nCalibration criterion\nReproduction criterion\nRegistration criterion",
    )
    reports.append(_expect_rejected("PROBE_F2_4_EXPAND_CONTRACT", expanded_contract))

    registry_label = next(
        node.label
        for node in design.nodes
        if node.key == "evidence_registry"
    )
    expanded_registry = _with_relabel(
        design,
        "evidence_registry",
        registry_label + "\nArtifact column\nCommit column\nSignature column",
    )
    reports.append(_expect_rejected("PROBE_F2_4_EXPAND_REGISTRY", expanded_registry))

    reports.append(
        _expect_canvas_rejected(
            "PROBE_REAL_ARTIST_LOOP_BREAK", _mutator_remove_return_annotation
        )
    )
    reports.append(
        _expect_canvas_rejected(
            "PROBE_REAL_ARTIST_EVIDENCE_ID", _mutator_inject_evidence_id
        )
    )
    reports.append(
        _expect_canvas_rejected(
            "PROBE_REAL_ARTIST_CONTRACT_EXPANSION", _mutator_expand_contract_artist
        )
    )
    reports.append(
        _expect_canvas_rejected(
            "PROBE_REAL_ARTIST_EMPTY_TEXT", _mutator_blank_real_label
        )
    )

    reports.append("STATIC_SELFCHECK=PASS probes=16")
    result = tuple(reports)
    if verbose:
        for report in result:
            print(report)
    return result


def main() -> int:
    """先执行纯静态门与探针，再显式渲染并输出到脚本目录。"""
    selfcheck(verbose=True)
    design = build_design()
    fig = render_figure(design)
    try:
        pdf_path, png_path = save_outputs(fig)
    finally:
        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

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
