#!/usr/bin/env python3
"""按 Figure C1 规格失败关闭地渲染 PRISMA 流程图。"""

from __future__ import annotations

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
import textwrap
import unicodedata
import uuid

# 该图必须以 ``python -B``（或等价环境变量）运行，且不得生成 __pycache__。
STARTED_WITHOUT_BYTECODE = bool(sys.flags.dont_write_bytecode)
sys.dont_write_bytecode = True

FIXED_PDF_TIME = datetime(2026, 8, 22, 0, 0, 0, tzinfo=timezone.utc)
FIXED_SOURCE_DATE_EPOCH = int(FIXED_PDF_TIME.timestamp())
os.environ["SOURCE_DATE_EPOCH"] = str(FIXED_SOURCE_DATE_EPOCH)

OUTPUT_STEM = "figure-c1-prisma-flow"
FIGURE_SIZE_INCHES = (8.5, 13.2)
PNG_DPI = 360
EXPECTED_PDF_DATE = "D:20260822000000Z"

# 图面只使用中性灰，避免任何颜色感知成为信息通道。
INK = "#262626"
MID_INK = "#5c5c5c"
RULE = "#8a8a8a"
LIGHT_RULE = "#d9d9d9"
MAIN_FILL = "#ffffff"
EXCLUSION_FILL = "#f2f2f2"
CAPTION_FILL = "#f7f7f7"


class FigureC1Error(RuntimeError):
    """源件、算术、渲染或验收失败。"""


def require(condition: bool, message: str) -> None:
    """统一执行失败关闭断言。"""
    if not condition:
        raise FigureC1Error(message)


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_once(text: str, fragment: str, label: str) -> None:
    """要求源件中的承重片段恰好出现一次。"""
    count = text.count(fragment)
    require(count == 1, f"{label} 承重片段出现次数应为 1，实际为 {count}。")


def capture_ints(text: str, pattern: str, label: str) -> tuple[int, ...]:
    """用唯一正则命中提取整数；重复或缺失均失败。"""
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    require(len(matches) == 1, f"{label} 应唯一命中，实际命中 {len(matches)} 次。")
    raw = matches[0]
    if isinstance(raw, str):
        raw = (raw,)
    return tuple(int(value) for value in raw)


def read_source(path: Path, label: str) -> str:
    """只读加载源件。"""
    require(path.is_file(), f"{label} 不存在：{path.name}")
    return path.read_text(encoding="utf-8")


def slice_section(text: str, heading: str, next_marker: str, label: str) -> str:
    """按唯一标题切出源件章节。"""
    require_once(text, heading, f"{label} 标题")
    section = text.split(heading, 1)[1]
    require(next_marker in section, f"{label} 缺少章节终止标记。")
    return section.split(next_marker, 1)[0]


@dataclass(frozen=True)
class FlowCounts:
    """Figure C1 冻结流程数；相同值仍保持不同字段身份。"""

    identified: int = 458
    internal_pool: int = 380
    targeted_external: int = 78
    r1_removed: int = 23
    r1_placeholders: int = 14
    r1_duplicate_pairs: int = 9
    screened: int = 435
    r2_excluded: int = 294
    assessed: int = 141
    r3_failures: int = 27
    r3_recovered: int = 4
    r3_excluded: int = 23
    r4_rejected: int = 21
    included: int = 97
    included_internal: int = 41
    included_external: int = 56
    errata_base: int = 111
    registration_unique: int = 24
    spot_examined: int = 41
    spot_collisions: int = 17
    spot_not_found: int = 6
    spot_distorted: int = 23


COUNTS = FlowCounts()


@dataclass(frozen=True)
class CountIdentity:
    """三个数值相同但语义不同的 23 的来源身份。"""

    key: str
    value: int
    equation: str
    meaning: str
    primary_region: str
    source_chain: tuple[str, ...]


IDENTITIES_23 = (
    CountIdentity(
        key="R1_REMOVAL",
        value=COUNTS.r1_removed,
        equation="14 + 9 = 23",
        meaning="cross-reference placeholders plus duplicate pairs removed",
        primary_region="flow box R1",
        source_chain=("Figure C1 specification", "Appendix C.6", "Annotated bibliography 1.1"),
    ),
    CountIdentity(
        key="R3_SCREENING",
        value=COUNTS.r3_excluded,
        equation="27 - 4 = 23",
        meaning="verification failures minus recovered records, leaving exclusions",
        primary_region="flow box R3 and caption convention ii",
        source_chain=("Figure C1 specification", "Appendix C.6", "Research report 2.4"),
    ),
    CountIdentity(
        key="SPOT_CHECK",
        value=COUNTS.spot_distorted,
        equation="17 + 6 = 23",
        meaning="DOI collisions plus nonexistent identifiers among 41 examined",
        primary_region="caption convention iii",
        source_chain=("Figure C1 specification", "Research report 5.1", "Annotated bibliography 1.2"),
    ),
)


@dataclass(frozen=True)
class SourcePaths:
    """全部检索、筛选与口径源件路径。"""

    script: Path
    output_dir: Path
    spec: Path
    appendix_c: Path
    section_8_4: Path
    research_report: Path
    annotated_bibliography: Path
    lit_coverage_matrix: Path


def locate_paths() -> SourcePaths:
    """从论文目录或显式仓根解析源件，不把绝对路径写入图件。"""
    script = Path(__file__).resolve()
    output_dir = script.parent
    if output_dir.name == "figures" and output_dir.parent.name == "stage2-writing":
        stage2_root = output_dir.parent
        paper_root = stage2_root.parent
    else:
        repo_root_text = os.environ.get("GEODEEPBAYES_REPO_ROOT", "").strip()
        require(bool(repo_root_text), "脚本位于审查目录时必须设置 GEODEEPBAYES_REPO_ROOT。")
        repo_root = Path(repo_root_text).resolve()
        require(repo_root.is_absolute() and repo_root.is_dir(), "GEODEEPBAYES_REPO_ROOT 不是有效绝对目录。")
        paper_root = (
            repo_root
            / "_bmad-output"
            / "planning-artifacts"
            / "research"
            / "papers"
            / "paper01-multi-scale-physics-informed-bayesian-fusion"
        )
        stage2_root = paper_root / "stage2-writing"
    phase2_root = paper_root / "stage1-research" / "phase2-investigation"
    return SourcePaths(
        script=script,
        output_dir=output_dir,
        spec=stage2_root / "drafts" / "figure-c1-prisma-spec.md",
        appendix_c=stage2_root / "drafts" / "appendix-c-search-and-verification-protocol.md",
        section_8_4=stage2_root / "drafts" / "sec8-4-governance-motivation.md",
        research_report=paper_root / "stage1-research" / "research-report.md",
        annotated_bibliography=phase2_root / "annotated-bibliography.md",
        lit_coverage_matrix=phase2_root / "lit-coverage-matrix.md",
    )


def expected_graph_tuple() -> tuple[int, ...]:
    """按规格表顺序返回全部节点与分解计数。"""
    return (
        COUNTS.identified,
        COUNTS.internal_pool,
        COUNTS.targeted_external,
        COUNTS.r1_removed,
        COUNTS.r1_placeholders,
        COUNTS.r1_duplicate_pairs,
        COUNTS.screened,
        COUNTS.r2_excluded,
        COUNTS.assessed,
        COUNTS.r3_excluded,
        COUNTS.r4_rejected,
        COUNTS.included,
        COUNTS.included_internal,
        COUNTS.included_external,
        COUNTS.errata_base,
    )


def extract_spec_graph_counts(spec: str) -> tuple[int, ...]:
    """从 C1 规格的九框表逐行提取数字。"""
    s1 = capture_ints(spec, r"^\| S1 \| .*? \| \*\*(\d+)\*\* / (\d+) / (\d+) \|.*$", "规格 S1")
    r1 = capture_ints(spec, r"^\| R1 \| .*? \| \*\*(\d+)\*\* / (\d+) / (\d+) \|.*$", "规格 R1")
    s2 = capture_ints(spec, r"^\| S2 \| .*? \| \*\*(\d+)\*\* \|.*$", "规格 S2")
    r2 = capture_ints(spec, r"^\| R2 \| .*? \| \*\*(\d+)\*\* \|.*$", "规格 R2")
    s3 = capture_ints(spec, r"^\| S3 \| .*? \| \*\*(\d+)\*\* \|.*$", "规格 S3")
    r3 = capture_ints(spec, r"^\| R3 \| .*? \| \*\*(\d+)\*\* \|.*$", "规格 R3")
    r4 = capture_ints(spec, r"^\| R4 \| .*? \| \*\*(\d+)\*\* \|.*$", "规格 R4")
    s4 = capture_ints(spec, r"^\| S4 \| .*? \| \*\*(\d+)\*\* / (\d+) / (\d+) \|.*$", "规格 S4")
    s5 = capture_ints(spec, r"^\| S5 \| .*? \| \*\*(\d+)\*\* \|.*$", "规格 S5")
    return (*s1, *r1, *s2, *r2, *s3, *r3, *r4, *s4, *s5)


def extract_appendix_graph_counts(appendix: str) -> tuple[tuple[int, ...], tuple[int, int, int]]:
    """从 Appendix C.6 表与算术说明独立提取流程数。"""
    c6 = slice_section(appendix, "## C.6 PRISMA flow", "\n---", "Appendix C.6")
    s1 = capture_ints(c6, r"^\| Records identified \| \*\*(\d+)\*\* \|$", "C.6 S1")
    internal = capture_ints(c6, r"^\| — internal pool \| (\d+) \|$", "C.6 internal")
    external = capture_ints(c6, r"^\| — targeted external candidates \| (\d+) \|$", "C.6 external")
    r1 = capture_ints(
        c6,
        r"^\| Duplicates and cross-reference placeholders removed \| \*\*(\d+)\*\* \((\d+) placeholders, (\d+) duplicate pairs\) \|$",
        "C.6 R1",
    )
    s2 = capture_ints(
        c6,
        r"^\| Records screened on title and abstract against the 20 evidence slots \| \*\*(\d+)\*\* \|$",
        "C.6 S2",
    )
    r2 = capture_ints(c6, r"^\| — excluded as not supporting any slot \| \*\*(\d+)\*\* \|$", "C.6 R2")
    s3 = capture_ints(
        c6,
        r"^\| Records assessed for eligibility by metadata verification \| \*\*(\d+)\*\* \|$",
        "C.6 S3",
    )
    r3 = capture_ints(
        c6,
        r"^\| — internal records excluded to the distortion registry \| \*\*(\d+)\*\* \|$",
        "C.6 R3",
    )
    r4 = capture_ints(c6, r"^\| — external candidates rejected \| \*\*(\d+)\*\* \|$", "C.6 R4")
    s4 = capture_ints(c6, r"^\| Entries included \| \*\*(\d+)\*\* \((\d+) internal, (\d+) external\) \|$", "C.6 S4")
    s5 = capture_ints(c6, r"base was subsequently extended by registered errata to \*\*(\d+)\*\* entries", "C.6 S5")
    r3_detail = capture_ints(
        c6,
        r"metadata verification failed on \*\*(\d+)\*\* internal records, of which (\d+) were excluded and \*\*(\d+)\*\* were traced",
        "C.6 R3 构成",
    )
    graph = (*s1, *internal, *external, *r1, *s2, *r2, *s3, *r3, *r4, *s4, *s5)
    return graph, r3_detail


def validate_sources(paths: SourcePaths) -> None:
    """逐件追溯数字并拒绝规格、源件或上游口径冲突。"""
    spec = read_source(paths.spec, "Figure C1 规格")
    appendix = read_source(paths.appendix_c, "Appendix C")
    report = read_source(paths.research_report, "研究报告")
    section_8_4 = read_source(paths.section_8_4, "§8.4 草稿")
    bibliography = read_source(paths.annotated_bibliography, "注释书目")
    coverage = read_source(paths.lit_coverage_matrix, "覆盖矩阵")

    expected = expected_graph_tuple()
    spec_graph = extract_spec_graph_counts(spec)
    appendix_graph, r3_detail = extract_appendix_graph_counts(appendix)
    require(spec_graph == expected, f"C1 规格九框数字与冻结图模不一致：{spec_graph}")
    require(appendix_graph == expected, f"Appendix C.6 九框数字与冻结图模不一致：{appendix_graph}")
    require(spec_graph == appendix_graph, "C1 规格与 Appendix C.6 的九框数字冲突。")
    require(
        r3_detail == (COUNTS.r3_failures, COUNTS.r3_excluded, COUNTS.r3_recovered),
        f"Appendix C.6 的 R3 构成冲突：{r3_detail}",
    )

    # 规格必须明确保留三个 23 的独立算式与图注身份。
    for fragment, label in (
        ("**14 + 9**", "规格 R1 公式"),
        ("**27 − 4**", "规格 R3 公式"),
        ("**17 + 6**", "规格抽查公式"),
        (
            "Three figures describe the same underlying finding and are **not three measurements of one quantity**; each answers a differently posed question and only one of them is a box in this diagram.",
            "规格三口径声明",
        ),
        ("图注必须显式写出「(i) 与 (iii) 不是本图的框」", "规格非框声明"),
        ("**闭合式（须印在图注内）**：$458-23=435$；$435-294-23-21=97$", "规格闭合式"),
    ):
        require_once(spec, fragment, label)

    # Appendix C.6 必须同时披露 294 为精确闭合值、上游约 290 为豁免口径，禁止伪装成重数值。
    require_once(appendix, "294 是残差，不是重新点算的计数", "C.6 的 294 来源定性")
    require_once(appendix, "the rounded figure carried in the pipeline's internal report", "C.6 的约数披露")
    require_once(appendix, "$435-294-23-21=97$", "C.6 闭合式")

    # 注释书目分别承载 R1 原始分解与抽查口径；两者不能因值同为 23 而合并。
    require_once(bibliography, "Duplicates removed: 23（池内 14 占位 + 9 对重复）", "注释书目 R1 分解")
    require_once(
        bibliography,
        "重点抽查的 41 条英文条目有 23 条元数据失真**（DOI 撞车 17、DOI 不存在 6）",
        "注释书目抽查口径",
    )
    require_once(bibliography, "Records excluded（与 20 个 LIT 标记无直接语义）: 约 290", "注释书目约数")

    # 研究报告给出抽查 17+6 与 PRISMA 27-4，两者必须同时在场。
    require_once(
        report,
        "重点抽查的 41 条英文条目中 **23 条**失真（抽查口径，`annotated-bibliography.md` §1.2：DOI 撞车 17——DOI 解析到完全不相干的论文，最强伪造信号；DOI 不存在 6——Crossref 404）",
        "研究报告抽查口径",
    )
    require_once(report, "PRISMA 口径为 27 次核验失败、4 条找回后 23 条排除", "研究报告 R3 口径")

    # §8.4 为三口径互不等价的正文约束；覆盖矩阵为登记 24 的逐条来源。
    require_once(section_8_4, "they are not three measurements of one quantity", "§8.4 三口径声明")
    require_once(section_8_4, "24 unique", "§8.4 登记口径")
    require_once(
        section_8_4,
        "of **41** English entries selected for focused re-checking, **23** were found distorted, of which 17 were DOI collisions and 6 were DOIs that do not exist",
        "§8.4 抽查口径",
    )
    require_once(coverage, "## 4. 池内元数据失真清单（移交 source_verification；24 条唯一失真）", "覆盖矩阵登记 24")

    print("[来源 1/6] SPEC_VS_APPENDIX=PASS 九框数字逐项一致")
    print("[来源 2/6] R1_SOURCE=PASS 14+9=23（占位 + 重复对）")
    print("[来源 3/6] R3_SOURCE=PASS 27-4=23（失败 - 找回 = 排除）")
    print("[来源 4/6] SPOT_SOURCE=PASS 17+6=23 of 41（抽查口径）")
    print("[来源 5/6] REGISTRATION_SOURCE=PASS 24 unique（登记口径，非流程框）")
    print("[来源 6/6] R2_PROVENANCE=PASS 294 为 C.6 残差；上游约 290 已显式披露")


def validate_arithmetic() -> None:
    """逐个复算图中全部流程加减关系，不生成任何配平数。"""
    checks = (
        (COUNTS.internal_pool + COUNTS.targeted_external, COUNTS.identified, "380 + 78 = 458"),
        (COUNTS.r1_placeholders + COUNTS.r1_duplicate_pairs, COUNTS.r1_removed, "14 + 9 = 23 [R1]"),
        (COUNTS.identified - COUNTS.r1_removed, COUNTS.screened, "458 - 23 = 435"),
        (COUNTS.screened - COUNTS.r2_excluded, COUNTS.assessed, "435 - 294 = 141"),
        (COUNTS.r3_failures - COUNTS.r3_recovered, COUNTS.r3_excluded, "27 - 4 = 23 [R3]"),
        (COUNTS.assessed - COUNTS.r3_excluded - COUNTS.r4_rejected, COUNTS.included, "141 - 23 - 21 = 97"),
        (
            COUNTS.screened - COUNTS.r2_excluded - COUNTS.r3_excluded - COUNTS.r4_rejected,
            COUNTS.included,
            "435 - 294 - 23 - 21 = 97",
        ),
        (COUNTS.included_internal + COUNTS.included_external, COUNTS.included, "41 + 56 = 97"),
        (COUNTS.spot_collisions + COUNTS.spot_not_found, COUNTS.spot_distorted, "17 + 6 = 23 [spot-check]"),
    )
    for actual, expected, equation in checks:
        require(actual == expected, f"流程算术不闭合：{equation}，实际左侧为 {actual}。")
        print(f"[算术] PASS {equation}")

    # S5 是后续扩容注记，不得伪造为本次检索的一条加法关系。
    require(COUNTS.errata_base == 111 and COUNTS.errata_base != COUNTS.included, "S5 身份无效。")
    print("[算术] PASS S5=111 仅作后续 registered errata 注记；未作为检索流程等式")


def validate_23_identities() -> None:
    """确认三个 23 的来源、公式、语义与主要布局区域均独立。"""
    require(len(IDENTITIES_23) == 3, "三个 23 的身份登记数量不为 3。")
    require(all(identity.value == 23 for identity in IDENTITIES_23), "三个身份的冻结值不全为 23。")
    require(len({identity.key for identity in IDENTITIES_23}) == 3, "三个 23 的身份键发生合并。")
    require(len({identity.equation for identity in IDENTITIES_23}) == 3, "三个 23 的算式发生合并。")
    require(len({identity.meaning for identity in IDENTITIES_23}) == 3, "三个 23 的语义发生合并。")
    require(len({identity.primary_region for identity in IDENTITIES_23}) == 3, "三个 23 的主要布局区域发生合并。")
    require(all(len(identity.source_chain) >= 3 for identity in IDENTITIES_23), "三个 23 存在未闭合的来源链。")
    for identity in IDENTITIES_23:
        print(
            f"[身份] PASS {identity.key}: {identity.equation}; "
            f"region={identity.primary_region}; sources={' > '.join(identity.source_chain)}"
        )


@dataclass(frozen=True)
class NodeSpec:
    """单个流程框的固定几何与文本。"""

    node_id: str
    x: float
    y: float
    width: float
    height: float
    header: str
    body: tuple[str, ...]
    kind: str


NODES = (
    NodeSpec("S1", 0.065, 0.855, 0.46, 0.082, "(S1)  Records identified   458", ("from internal pool   380", "from targeted external search   78"), "main"),
    NodeSpec("R1", 0.57, 0.7855, 0.365, 0.083, "(R1)  Removed before screening   23", ("cross-reference placeholders   14", "duplicate pairs   9", "14 + 9 = 23"), "exclusion"),
    NodeSpec("S2", 0.065, 0.726, 0.46, 0.062, "(S2)  Records screened on title and abstract   435", ("against the 20 evidence slots",), "main"),
    NodeSpec("R2", 0.57, 0.67, 0.365, 0.052, "(R2)  Excluded — supports no evidence slot   294", (), "exclusion"),
    NodeSpec("S3", 0.065, 0.604, 0.46, 0.062, "(S3)  Assessed for eligibility by   141", ("metadata verification",), "main"),
    NodeSpec("R3", 0.57, 0.5365, 0.365, 0.073, "(R3)  Internal records excluded to   23", ("the distortion registry", "27 failed, 4 recovered", "27 - 4 = 23 excluded"), "exclusion"),
    NodeSpec("R4", 0.57, 0.4925, 0.365, 0.043, "(R4)  External candidates rejected   21", (), "exclusion"),
    NodeSpec("S4", 0.065, 0.418, 0.46, 0.080, "(S4)  Entries included   97", ("internal   41", "external   56"), "main"),
    NodeSpec("S5", 0.065, 0.3105, 0.46, 0.063, "(S5)  Base after registered errata   111", ("(not part of this search execution)",), "extension"),
)


class FigureTextRegistry:
    """集中登记全部图面文字，供字符与身份验收。"""

    def __init__(self) -> None:
        self.by_region: dict[str, list[str]] = {}

    def add(self, region: str, text: str) -> None:
        self.by_region.setdefault(region, []).append(text)

    def joined(self, region: str) -> str:
        return "\n".join(self.by_region.get(region, []))

    def all_text(self) -> str:
        return "\n".join(text for values in self.by_region.values() for text in values)


def add_figure_text(fig, registry: FigureTextRegistry, region: str, x: float, y: float, text: str, **kwargs):
    """写入 Figure 文字并同步登记。"""
    registry.add(region, text)
    return fig.text(x, y, text, transform=fig.transFigure, **kwargs)


def draw_node(fig, patches, registry: FigureTextRegistry, node: NodeSpec) -> None:
    """按节点类型绘制圆角主干、方角排除或虚线扩容框。"""
    if node.kind in {"main", "extension"}:
        box = patches.FancyBboxPatch(
            (node.x, node.y), node.width, node.height,
            boxstyle="round,pad=0.005,rounding_size=0.010", transform=fig.transFigure,
            facecolor=MAIN_FILL, edgecolor=INK, linewidth=1.15,
            linestyle="--" if node.kind == "extension" else "-", zorder=2,
        )
    else:
        box = patches.Rectangle(
            (node.x, node.y), node.width, node.height, transform=fig.transFigure,
            facecolor=EXCLUSION_FILL, edgecolor=INK, linewidth=1.05, linestyle="-", zorder=2,
        )
    fig.add_artist(box)

    center_x = node.x + node.width / 2.0
    body_text = "\n".join(node.body)
    if node.body:
        header_y = node.y + node.height * 0.69
        body_y = node.y + node.height * 0.39
    else:
        header_y = node.y + node.height * 0.50
        body_y = node.y

    add_figure_text(
        fig, registry, f"node-{node.node_id}", center_x, header_y, node.header,
        ha="center", va="center", fontsize=7.8 if node.node_id not in {"R1", "R3"} else 7.25,
        fontweight="semibold", color=INK, zorder=3,
    )
    if node.body:
        add_figure_text(
            fig, registry, f"node-{node.node_id}", center_x, body_y, body_text,
            ha="center", va="center", fontsize=7.35 if node.node_id not in {"R1", "R3"} else 7.1,
            linespacing=1.24, color=INK, zorder=3,
        )


def add_arrow(fig, patches, start: tuple[float, float], end: tuple[float, float], dashed: bool = False) -> None:
    """添加单向流程箭头；虚线仅用于 S4 到 S5 的非流程扩容注记。"""
    arrow = patches.FancyArrowPatch(
        start, end, transform=fig.transFigure, arrowstyle="-|>", mutation_scale=10.0,
        linewidth=1.05, linestyle="--" if dashed else "-", edgecolor=INK,
        facecolor=MAIN_FILL if dashed else INK, shrinkA=0.0, shrinkB=1.5, zorder=1,
    )
    fig.add_artist(arrow)


def wrap(text: str, width: int) -> str:
    """以固定列宽确定性换行。"""
    return textwrap.fill(text, width=width, break_long_words=False, break_on_hyphens=False)


def draw_convention_panel(fig, patches, registry: FigureTextRegistry, region: str, x: float, width: float, header: str, body: str, linestyle: str | tuple) -> None:
    """在图注区绘制三个互不合并的计数口径面板。"""
    y = 0.074
    height = 0.139
    panel = patches.FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0.004,rounding_size=0.006",
        transform=fig.transFigure, facecolor=CAPTION_FILL, edgecolor=RULE,
        linewidth=0.9, linestyle=linestyle, zorder=1,
    )
    fig.add_artist(panel)
    add_figure_text(
        fig, registry, region, x + 0.012, y + height - 0.014, header,
        ha="left", va="top", fontsize=6.75, fontweight="bold", color=INK, zorder=2,
    )
    add_figure_text(
        fig, registry, region, x + 0.012, y + height - 0.035, wrap(body, 39),
        ha="left", va="top", fontsize=6.05, linespacing=1.20, color=INK, zorder=2,
    )


def draw_figure():
    """建立无坐标轴、单向且纯灰度的 Figure C1。"""
    import matplotlib

    matplotlib.use("Agg", force=True)
    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "font.size": 8.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "pdf.compression": 6,
            "text.usetex": False,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )

    import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel
    from matplotlib import patches  # pylint: disable=import-outside-toplevel

    fig = plt.figure(figsize=FIGURE_SIZE_INCHES, facecolor="white")
    registry = FigureTextRegistry()

    add_figure_text(fig, registry, "title", 0.065, 0.977, "Selection flow for the verified base", ha="left", va="top", fontsize=11.5, fontweight="bold", color=INK)
    add_figure_text(fig, registry, "title", 0.065, 0.959, "Original search execution: main flow downward; exclusions branch right", ha="left", va="top", fontsize=7.1, color=MID_INK)

    for node in NODES:
        draw_node(fig, patches, registry, node)

    main_center_x = 0.295
    # 主干 S1 -> S2 -> S3 -> S4；箭头全向下。
    add_arrow(fig, patches, (main_center_x, 0.855), (main_center_x, 0.788))
    add_arrow(fig, patches, (main_center_x, 0.726), (main_center_x, 0.666))
    add_arrow(fig, patches, (main_center_x, 0.604), (main_center_x, 0.498))

    # 排除分支全向右并指入 R1-R4。
    branch_specs = ((0.827, 0.57), (0.696, 0.57), (0.573, 0.57), (0.514, 0.57))
    for branch_y, right_x in branch_specs:
        add_arrow(fig, patches, (main_center_x, branch_y), (right_x, branch_y))
        fig.add_artist(
            patches.Circle(
                (main_center_x, branch_y), radius=0.0025, transform=fig.transFigure,
                facecolor=INK, edgecolor=INK, linewidth=0.0, zorder=2,
            )
        )

    # S5 使用虚线框、虚线开放箭头与显式非流程标签。
    add_arrow(fig, patches, (main_center_x, 0.418), (main_center_x, 0.3735), dashed=True)
    add_figure_text(
        fig, registry, "extension-label", 0.310, 0.397,
        "Subsequent registered errata; outside this search execution",
        ha="left", va="center", fontsize=6.25, color=MID_INK,
    )

    # 图注与流程图区用实线分隔；三口径只在分隔线下出现。
    fig.add_artist(
        patches.FancyArrowPatch(
            (0.065, 0.293), (0.935, 0.293), transform=fig.transFigure,
            arrowstyle="-", linewidth=0.8, color=LIGHT_RULE, zorder=1,
        )
    )
    caption_lead = "Figure C1. Selection flow for the verified base. The flow closes: 458 - 23 = 435; 435 - 294 - 23 - 21 = 97."
    caption_intro = (
        "Counting conventions. Three figures describe the same underlying finding and are not three "
        "measurements of one quantity; each answers a differently posed question and only one is a box "
        "in this diagram."
    )
    add_figure_text(fig, registry, "caption-lead", 0.065, 0.281, caption_lead, ha="left", va="top", fontsize=7.0, fontweight="semibold", color=INK)
    add_figure_text(fig, registry, "caption-intro", 0.065, 0.264, wrap(caption_intro, 119), ha="left", va="top", fontsize=6.55, linespacing=1.16, color=INK)
    add_figure_text(
        fig, registry, "caption-heading", 0.065, 0.226,
        "COUNTING CONVENTIONS — CAPTION, NOT ADDITIONAL FLOW STAGES",
        ha="left", va="bottom", fontsize=6.35, fontweight="bold", color=MID_INK,
    )

    panel_i = (
        "24 unique entries. The distortion registry's individually identifiable rows. "
        "This is the figure the paper reports, and it is not a box in this diagram."
    )
    panel_ii = (
        "23 excluded of 27 failures. Metadata verification failed on 27 internal records; 4 were traced "
        "to a real record, corrected and retained, leaving 23 excluded. This is box R3. The four are not "
        "added back at the end, because they were never removed. 27 - 4 = 23."
    )
    panel_iii = (
        "23 distorted of 41 examined. Of 41 English-language entries examined closely, 17 carried "
        "identifiers resolving to unrelated papers and 6 carried identifiers that do not exist. This is "
        "a rate over a defined subset, not a pool-wide rate, and it is not a box in this diagram. "
        "17 + 6 = 23."
    )
    draw_convention_panel(fig, patches, registry, "caption-i-registration", 0.065, 0.275, "(i) REGISTRATION — NOT A BOX", panel_i, (0, (1, 2)))
    draw_convention_panel(fig, patches, registry, "caption-ii-screening", 0.3625, 0.275, "(ii) SCREENING — THIS IS BOX R3", panel_ii, "-")
    draw_convention_panel(fig, patches, registry, "caption-iii-spot", 0.660, 0.275, "(iii) SPOT-CHECK — NOT A BOX", panel_iii, "-.")

    coincidence = (
        "Arithmetic coincidence only: (ii) 27 - 4 = 23 and (iii) 17 + 6 = 23 are different sets; "
        "R1's 23 is 14 + 9, a third unrelated quantity."
    )
    add_figure_text(fig, registry, "caption-coincidence", 0.065, 0.058, coincidence, ha="left", va="top", fontsize=6.4, fontweight="semibold", color=INK)

    # 纯 Figure 坐标绘制，不创建任何轴或孪生轴。
    require(len(fig.axes) == 0, "Figure C1 禁止出现坐标轴或双轴对象。")
    return fig, registry


def contains_han(text: str) -> bool:
    """检测全部常见与扩展 CJK 统一表意文字。"""
    for character in text:
        codepoint = ord(character)
        if 0x3400 <= codepoint <= 0x4DBF or 0x4E00 <= codepoint <= 0x9FFF or 0xF900 <= codepoint <= 0xFAFF or 0x20000 <= codepoint <= 0x3134F:
            return True
        if "CJK UNIFIED IDEOGRAPH" in unicodedata.name(character, ""):
            return True
    return False


def forbidden_controls(text: str) -> list[str]:
    """允许排版换行，拒绝 TAB、CR 与其余控制字符。"""
    return sorted({f"U+{ord(ch):04X}" for ch in text if unicodedata.category(ch) == "Cc" and ch != "\n"})


def validate_figure_text(registry: FigureTextRegistry) -> None:
    """验收英文、控制字符、九节点以及三个 23 的布局隔离。"""
    all_text = registry.all_text()
    require(not contains_han(all_text), "图面文字含中文字符。")
    controls = forbidden_controls(all_text)
    require(not controls, f"图面文字含禁止控制字符：{controls}")
    require(not re.search(r"(?:[A-Za-z]:[\\/]|(?:^|\s)/(?:Users|home|tmp|mnt)/)", all_text), "图面文字含绝对路径。")

    expected_node_ids = {"S1", "S2", "S3", "S4", "S5", "R1", "R2", "R3", "R4"}
    actual_node_ids = {key.removeprefix("node-") for key in registry.by_region if key.startswith("node-")}
    require(actual_node_ids == expected_node_ids, f"流程节点集合不完整或多画：{sorted(actual_node_ids)}")
    for node_id in expected_node_ids:
        require(all_text.count(f"({node_id})") == 1, f"节点 {node_id} 的图面 ID 应恰出现一次。")

    r1_text = registry.joined("node-R1")
    r3_text = registry.joined("node-R3")
    spot_text = registry.joined("caption-iii-spot")
    require("14 + 9 = 23" in r1_text, "R1 未在框内显示 14 + 9 = 23。")
    require("27 failed, 4 recovered" in r3_text and "27 - 4 = 23 excluded" in r3_text, "R3 未在框内显示失败、找回与排除构成。")
    require("17 + 6 = 23" in spot_text and "41 examined" in spot_text, "抽查 23 未在独立图注面板显示 17 + 6 与分母 41。")
    require("27 - 4" not in r1_text and "17 + 6" not in r1_text, "R1 框合并了其他 23 的算式。")
    require("14 + 9" not in r3_text and "17 + 6" not in r3_text, "R3 框合并了其他 23 的算式。")
    require("14 + 9" not in spot_text and "27 - 4" not in spot_text, "抽查面板合并了其他 23 的算式。")
    require("NOT A BOX" in registry.joined("caption-i-registration"), "登记口径未声明不是流程框。")
    require("NOT A BOX" in spot_text, "抽查口径未声明不是流程框。")
    require("THIS IS BOX R3" in registry.joined("caption-ii-screening"), "筛选口径未绑定 R3。")
    normalized_intro = re.sub(r"\s+", " ", registry.joined("caption-intro"))
    require("not three measurements of one quantity" in normalized_intro, "三口径非同量声明缺失。")
    print("[图面] TEXT_LANGUAGE=PASS English only")
    print("[图面] CONTROL_CHARACTERS=PASS none except layout newlines")
    print("[图面] NODE_SET=PASS S1-S5 + R1-R4（无额外 PRISMA 空框）")
    print("[图面] THREE_23_REGIONS=PASS R1 / R3 / caption iii 独立，caption i/iii 均声明非框")


def make_temp_path(output_dir: Path, suffix: str) -> Path:
    """在最终目录同卷创建临时文件，以便原子发布。"""
    descriptor, raw_path = tempfile.mkstemp(prefix=f".{OUTPUT_STEM}-", suffix=suffix, dir=output_dir)
    os.close(descriptor)
    return Path(raw_path)


def pdf_reader_class():
    """Figure C1 验收要求现有 PDF 解析器，不可跳过。"""
    if importlib.util.find_spec("pypdf") is not None:
        from pypdf import PdfReader  # type: ignore[import-not-found]
        return PdfReader, "pypdf"
    if importlib.util.find_spec("PyPDF2") is not None:
        from PyPDF2 import PdfReader  # type: ignore[import-not-found]
        return PdfReader, "PyPDF2"
    raise FigureC1Error("未发现 pypdf/PyPDF2，不能失败关闭地验收 PDF 元数据与矢量资源。")


def dereference_pdf_object(value):
    """兼容 pypdf/PyPDF2 的间接对象。"""
    return value.get_object() if hasattr(value, "get_object") else value


def validate_pdf(pdf_path: Path, paths: SourcePaths) -> dict[str, object]:
    """验收 PDF 元数据、文字、页面尺寸与无栅格 XObject。"""
    require(pdf_path.read_bytes()[:5] == b"%PDF-", "PDF 文件头无效。")
    reader_class, parser_name = pdf_reader_class()
    reader = reader_class(str(pdf_path))
    require(len(reader.pages) == 1, f"PDF 页数应为 1，实际为 {len(reader.pages)}。")
    metadata = reader.metadata or {}
    creation = metadata.get("/CreationDate")
    modification = metadata.get("/ModDate")
    require(creation == EXPECTED_PDF_DATE, f"PDF CreationDate 不固定：{creation!r}")
    require(modification == EXPECTED_PDF_DATE, f"PDF ModDate 不固定：{modification!r}")
    require(creation == modification, "PDF CreationDate 与 ModDate 不一致。")
    for key, value in metadata.items():
        rendered = str(value)
        require(str(paths.output_dir) not in rendered and str(paths.script) not in rendered, f"PDF 元数据 {key} 含绝对路径。")

    page = reader.pages[0]
    media_box = page.mediabox
    width_points = float(media_box.width)
    height_points = float(media_box.height)
    expected_width = FIGURE_SIZE_INCHES[0] * 72.0
    expected_height = FIGURE_SIZE_INCHES[1] * 72.0
    require(math.isclose(width_points, expected_width, abs_tol=0.02), f"PDF 宽度异常：{width_points} pt")
    require(math.isclose(height_points, expected_height, abs_tol=0.02), f"PDF 高度异常：{height_points} pt")

    resources = dereference_pdf_object(page.get("/Resources"))
    require(resources is not None, "PDF 页面缺少资源字典。")
    fonts = dereference_pdf_object(resources.get("/Font")) if resources.get("/Font") is not None else None
    require(fonts is not None and len(fonts) > 0, "PDF 未嵌入文字字体资源。")
    image_count = 0
    xobjects = resources.get("/XObject")
    if xobjects is not None:
        xobjects = dereference_pdf_object(xobjects)
        for item in xobjects.values():
            obj = dereference_pdf_object(item)
            if obj.get("/Subtype") == "/Image":
                image_count += 1
    require(image_count == 0, f"PDF 含 {image_count} 个栅格图像对象，不是全矢量。")

    extracted = page.extract_text() or ""
    require(extracted.strip(), "PDF 无法提取任何文字。")
    require(not contains_han(extracted), "PDF 提取文字含中文字符。")
    controls = forbidden_controls(extracted)
    require(not controls, f"PDF 提取文字含禁止控制字符：{controls}")
    normalized = re.sub(r"\s+", " ", extracted)
    for fragment in (
        "Records identified", "Removed before screening", "Assessed for eligibility",
        "Internal records excluded", "Entries included", "Base after registered errata",
        "REGISTRATION", "SCREENING", "SPOT-CHECK", "Arithmetic coincidence only",
    ):
        require(fragment in normalized, f"PDF 提取文字缺少承重片段：{fragment}")

    raw = pdf_path.read_bytes()
    absolute_candidates = {
        str(paths.output_dir), str(paths.output_dir).replace("\\", "/"),
        str(paths.script), str(paths.script).replace("\\", "/"),
    }
    for candidate in absolute_candidates:
        require(candidate.encode("utf-8") not in raw, "PDF 二进制中发现绝对路径。")

    print(
        "[PDF] PASS "
        f"parser={parser_name} pages=1 size_pt={width_points:.2f}x{height_points:.2f} "
        f"CreationDate={creation} ModDate={modification} image_xobjects=0 fonts={len(fonts)}"
    )
    return {"width_points": width_points, "height_points": height_points, "image_xobjects": image_count, "font_resources": len(fonts), "parser": parser_name}


def validate_png(png_path: Path, paths: SourcePaths) -> dict[str, object]:
    """验收 PNG 的 DPI、像素尺寸、纯灰度编码与固定元数据。"""
    require(png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "PNG 文件头无效。")
    from PIL import Image  # pylint: disable=import-outside-toplevel
    import numpy as np  # pylint: disable=import-outside-toplevel

    with Image.open(png_path) as image:
        width, height = image.size
        info = dict(image.info)
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        gray = np.asarray(image.convert("L"), dtype=np.uint8)

    expected_size = (round(FIGURE_SIZE_INCHES[0] * PNG_DPI), round(FIGURE_SIZE_INCHES[1] * PNG_DPI))
    require((width, height) == expected_size, f"PNG 像素尺寸不固定：{width}x{height}，期望 {expected_size}")
    dpi = info.get("dpi")
    require(isinstance(dpi, tuple) and len(dpi) == 2, f"PNG 缺少 DPI 元数据：{dpi!r}")
    require(float(dpi[0]) >= 300.0 and float(dpi[1]) >= 300.0, f"PNG DPI 低于 300：{dpi}")
    require(abs(float(dpi[0]) - PNG_DPI) < 0.1 and abs(float(dpi[1]) - PNG_DPI) < 0.1, f"PNG DPI 偏离冻结值：{dpi}")
    require(info.get("Software") == "GeoDeepBayes deterministic Figure C1 renderer", "PNG Software 元数据不固定。")
    require(not any(key.lower() in {"creation time", "date", "timestamp"} for key in info), "PNG 含动态时间元数据。")
    for value in info.values():
        rendered = str(value)
        require(str(paths.output_dir) not in rendered and str(paths.script) not in rendered, "PNG 元数据含绝对路径。")

    require(bool(np.array_equal(rgb[:, :, 0], rgb[:, :, 1]) and np.array_equal(rgb[:, :, 1], rgb[:, :, 2])), "PNG 含非灰度 RGB 像素。")
    gray_min = int(gray.min())
    gray_max = int(gray.max())
    unique_levels = int(np.unique(gray).size)
    nonwhite_fraction = float(np.mean(gray < 250))
    require(gray_min <= 50 and gray_max >= 250, "PNG 灰度动态范围不足。")
    require(unique_levels >= 32, f"PNG 灰度层级不足：{unique_levels}")
    require(0.01 <= nonwhite_fraction <= 0.55, f"PNG 前景占比异常：{nonwhite_fraction:.6f}")
    print(
        "[PNG] PASS "
        f"size_px={width}x{height} dpi={dpi[0]:.3f}x{dpi[1]:.3f} "
        f"gray_min={gray_min} gray_max={gray_max} levels={unique_levels} "
        f"nonwhite_fraction={nonwhite_fraction:.6f} RGB_channels_equal=yes"
    )
    return {"width_pixels": width, "height_pixels": height, "dpi": dpi, "gray_min": gray_min, "gray_max": gray_max, "gray_levels": unique_levels, "nonwhite_fraction": nonwhite_fraction}


def publish_pair_atomically(temp_pdf: Path, temp_png: Path, final_pdf: Path, final_png: Path) -> None:
    """成对原子发布 PDF/PNG；失败时回滚旧对。"""
    finals = [final_pdf, final_png]
    temps = [temp_pdf, temp_png]
    token = uuid.uuid4().hex
    backups: list[tuple[Path, Path]] = []
    moved_finals: list[Path] = []
    try:
        for final in finals:
            if final.exists():
                backup = final.with_name(f".{final.name}.{token}.bak")
                os.replace(final, backup)
                backups.append((backup, final))
        for temp, final in zip(temps, finals, strict=True):
            os.replace(temp, final)
            moved_finals.append(final)
    except Exception:
        for final in moved_finals:
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


def assert_no_temp_residue(output_dir: Path) -> None:
    """确认最终目录不残留本脚本临时文件或备份。"""
    residue = sorted(
        path.name for path in output_dir.iterdir()
        if path.name.startswith(f".{OUTPUT_STEM}-") or path.name.startswith(f".{OUTPUT_STEM}.")
    )
    require(not residue, f"输出目录残留临时文件：{residue}")


def log_output(path: Path) -> None:
    """只打印稳定文件名、字节数与 SHA，不输出绝对路径。"""
    print(f"[输出] file={path.name} bytes={path.stat().st_size} sha256={sha256_file(path)}")


def main() -> int:
    """按源件核验、算术、绘制、验收、原子发布顺序执行。"""
    require(STARTED_WITHOUT_BYTECODE, "必须使用 python -B 运行本脚本。")
    require(os.environ.get("SOURCE_DATE_EPOCH") == str(FIXED_SOURCE_DATE_EPOCH), "SOURCE_DATE_EPOCH 未固定。")
    paths = locate_paths()
    require(paths.output_dir.is_dir(), "目标 figures 目录不存在。")

    validate_sources(paths)
    validate_arithmetic()
    validate_23_identities()

    fig = None
    temp_pdf: Path | None = None
    temp_png: Path | None = None
    final_pdf = paths.output_dir / f"{OUTPUT_STEM}.pdf"
    final_png = paths.output_dir / f"{OUTPUT_STEM}.png"
    try:
        fig, registry = draw_figure()
        validate_figure_text(registry)
        temp_pdf = make_temp_path(paths.output_dir, ".pdf.tmp")
        temp_png = make_temp_path(paths.output_dir, ".png.tmp")
        fig.savefig(
            temp_pdf,
            format="pdf",
            dpi=PNG_DPI,
            metadata={
                "Title": "Figure C1. Selection flow for the verified base",
                "Subject": "Deterministic PRISMA-style selection flow",
                "Creator": "GeoDeepBayes deterministic Figure C1 renderer",
                "CreationDate": FIXED_PDF_TIME,
                "ModDate": FIXED_PDF_TIME,
            },
        )
        fig.savefig(
            temp_png,
            format="png",
            dpi=PNG_DPI,
            metadata={
                "Software": "GeoDeepBayes deterministic Figure C1 renderer",
                "Title": "Figure C1. Selection flow for the verified base",
            },
        )

        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel
        plt.close(fig)
        fig = None
        require(temp_pdf.stat().st_size > 0, "临时 PDF 为空。")
        require(temp_png.stat().st_size > 0, "临时 PNG 为空。")
        validate_pdf(temp_pdf, paths)
        validate_png(temp_png, paths)
        publish_pair_atomically(temp_pdf, temp_png, final_pdf, final_png)
        temp_pdf = None
        temp_png = None
        assert_no_temp_residue(paths.output_dir)
        log_output(final_pdf)
        log_output(final_png)
        print(
            "[完成] Figure C1 已成对发布；SOURCE_DATE_EPOCH="
            f"{FIXED_SOURCE_DATE_EPOCH}，PDF CreationDate/ModDate={EXPECTED_PDF_DATE}。"
        )
        return 0
    finally:
        if fig is not None:
            try:
                import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel
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
    except FigureC1Error as exc:
        print(f"[失败关闭] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
