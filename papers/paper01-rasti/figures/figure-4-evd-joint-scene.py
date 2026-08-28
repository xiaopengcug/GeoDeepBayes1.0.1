#!/usr/bin/env python3
"""生成 Figure 4 的 EVD 联合场景与观测设计矢量图。"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping


class Figure4Error(RuntimeError):
    """Figure 4 生成或验收失败。"""


def require(condition: bool, message: str) -> None:
    """条件不成立时立即失败，避免不完整图件被发布。"""
    if not condition:
        raise Figure4Error(message)


SOURCE_DATE_EPOCH: Final[str] = "1787356800"
PDF_DATE_TEXT: Final[str] = "D:20260822000000Z"
FIXED_UTC: Final[datetime] = datetime.fromtimestamp(
    int(SOURCE_DATE_EPOCH), tz=timezone.utc
)
OUTPUT_STEM: Final[str] = "figure-4-evd-joint-scene"
FIGURE_SIZE_INCHES: Final[tuple[float, float]] = (12.0, 7.0)
PNG_DPI: Final[int] = 300
EXPECTED_PNG_SIZE: Final[tuple[int, int]] = (
    round(FIGURE_SIZE_INCHES[0] * PNG_DPI),
    round(FIGURE_SIZE_INCHES[1] * PNG_DPI),
)
CANVAS_BOUNDS: Final[tuple[float, float, float, float]] = (0.0, 12.0, 0.0, 7.0)
DIVIDER_X: Final[float] = 5.65
GRAVITY_OBSERVATION_BOUNDS: Final[tuple[float, float, float, float]] = (
    7.10,
    2.82,
    4.15,
    0.70,
)
STATION_GRID_BOUNDS: Final[tuple[float, float, float, float]] = (
    6.72,
    4.08,
    4.50,
    1.16,
)
STATION_X: Final[tuple[float, ...]] = (6.72, 7.62, 8.52, 9.42, 10.32, 11.22)
STATION_Y: Final[tuple[float, ...]] = (4.08, 4.312, 4.544, 4.776, 5.008, 5.24)
STATION_GRID: Final[tuple[tuple[float, float], ...]] = tuple(
    (x_value, y_value) for y_value in STATION_Y for x_value in STATION_X
)

_FROZEN_TEXT_ITEMS: Final[tuple[tuple[str, str], ...]] = (
    ("title", "Joint model scene and observation design"),
    ("model_side", "model side"),
    ("observation_side", "observation side"),
    ("survey_surface", "survey surface"),
    ("target_block", "target block"),
    ("decoy_lens", "decoy lens"),
    ("station_grid", "station grid"),
    ("gravity_observations", "gravity observations"),
    ("magnetic_observations", "magnetic observations"),
    (
        "systematic_term",
        "ξ_g — shared station-location geometry offset",
    ),
    ("boundary", "schematic, not to scale"),
    ("caption", "Registered scene and observation design"),
)
FROZEN_TEXT_BY_ROLE: Final[Mapping[str, str]] = MappingProxyType(
    dict(_FROZEN_TEXT_ITEMS)
)
FROZEN_FIGURE_TEXTS: Final[frozenset[str]] = frozenset(
    FROZEN_TEXT_BY_ROLE.values()
)
FROZEN_SEMANTIC_ELEMENTS: Final[frozenset[str]] = frozenset(
    {
        "target_block",
        "decoy_lens",
        "station_grid",
        "gravity_systematic_term",
    }
)
FROZEN_DRAW_ROLES: Final[frozenset[str]] = (
    frozenset(FROZEN_TEXT_BY_ROLE.keys())
    | FROZEN_SEMANTIC_ELEMENTS
    | frozenset({"xi_on_observation_side"})
)

PDF_METADATA: Final[Mapping[str, object]] = MappingProxyType(
    {
        "Title": "EVD joint scene and observation design",
        "Author": "GeoDeepBayes",
        "Subject": "Registered scene and observation design",
        "Keywords": "joint scene, observation design, schematic",
        "Creator": "GeoDeepBayes deterministic figure generator",
        "Producer": "Matplotlib PDF backend",
        "CreationDate": FIXED_UTC,
        "ModDate": FIXED_UTC,
    }
)
PNG_METADATA: Final[Mapping[str, str]] = MappingProxyType(
    {
        "Title": "EVD joint scene and observation design",
        "Author": "GeoDeepBayes",
        "Description": "Registered scene and observation design",
        "Software": "Matplotlib",
    }
)
RENDER_RC: Final[Mapping[str, object]] = MappingProxyType(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10.0,
        "axes.unicode_minus": False,
        "pdf.compression": 0,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.facecolor": "white",
        "savefig.edgecolor": "white",
        "savefig.transparent": False,
    }
)

_CJK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[㐀-䶿一-鿿豈-﫿]"
)
_FORBIDDEN_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:run|runs|running|result|results|diagnostic|diagnostics)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SceneSemantics:
    """与绘图实现绑定的冻结语义契约。"""

    elements: frozenset[str]
    visible_texts: frozenset[str]
    text_overrides: Mapping[str, str]
    xi_label_text: str
    xi_side_label: str
    xi_label_position: tuple[float, float]
    xi_arrow_target: str
    xi_arrow_tip: tuple[float, float]
    gravity_observation_bounds: tuple[float, float, float, float]
    boundary_text: str
    creation_date: str
    modification_date: str
    expected_drawn_roles: frozenset[str]


BASE_SCENE: Final[SceneSemantics] = SceneSemantics(
    elements=FROZEN_SEMANTIC_ELEMENTS,
    visible_texts=FROZEN_FIGURE_TEXTS,
    text_overrides=MappingProxyType({}),
    xi_label_text=FROZEN_TEXT_BY_ROLE["systematic_term"],
    xi_side_label=FROZEN_TEXT_BY_ROLE["observation_side"],
    xi_label_position=(5.96, 0.82),
    xi_arrow_target="station_grid",
    xi_arrow_tip=(8.52, 4.66),
    gravity_observation_bounds=GRAVITY_OBSERVATION_BOUNDS,
    boundary_text=FROZEN_TEXT_BY_ROLE["boundary"],
    creation_date=PDF_DATE_TEXT,
    modification_date=PDF_DATE_TEXT,
    expected_drawn_roles=FROZEN_DRAW_ROLES,
)


def _point_in_bounds(
    point: tuple[float, float], bounds: tuple[float, float, float, float]
) -> bool:
    """判断箭头端点是否落入指定观测对象。"""
    x_value, y_value = point
    left, bottom, width, height = bounds
    return (
        left <= x_value <= left + width
        and bottom <= y_value <= bottom + height
    )


def validate_station_grid(
    stations: tuple[tuple[float, float], ...],
) -> dict[str, int]:
    """要求名义站网恰为完整 6 × 6 笛卡尔积。"""
    x_values = tuple(sorted({point[0] for point in stations}))
    y_values = tuple(sorted({point[1] for point in stations}))
    expected = {(x_value, y_value) for y_value in y_values for x_value in x_values}
    require(len(x_values) == 6 and len(y_values) == 6, "名义站网必须为 6 × 6。")
    require(len(stations) == 36, "名义站网必须恰含 36 个站。")
    require(len(set(stations)) == 36 and set(stations) == expected, "36 站必须形成完整笛卡尔网。")
    return {"x_count": 6, "y_count": 6, "stations": 36}


def _selected_text(scene: SceneSemantics, role: str) -> str:
    """取指定文字角色的实际绘制文本；探针可通过覆盖值改写真实 artist。"""
    override = scene.text_overrides.get(role)
    if override is not None:
        return override
    return FROZEN_TEXT_BY_ROLE[role]


def validate_semantics(scene: SceneSemantics) -> None:
    """以失败关闭方式验证冻结文字、四元素和观测侧关系。"""
    validate_station_grid(STATION_GRID)
    issues: list[str] = []
    try:
        if scene.elements != FROZEN_SEMANTIC_ELEMENTS:
            issues.append("四个必需语义元素不完整或出现未冻结元素")
        if scene.expected_drawn_roles != FROZEN_DRAW_ROLES:
            issues.append("期望绘制角色集合偏离冻结版本")

        texts_are_strings = isinstance(scene.visible_texts, frozenset) and all(
            isinstance(text, str) for text in scene.visible_texts
        )
        if not texts_are_strings:
            issues.append("图面文字集合类型无效")
            texts: frozenset[str] = frozenset()
        else:
            texts = scene.visible_texts

        if texts != FROZEN_FIGURE_TEXTS:
            issues.append("图面文字集合偏离冻结版本")
        if set(scene.text_overrides) - set(FROZEN_TEXT_BY_ROLE):
            issues.append("文字覆盖表出现未冻结角色")

        xi_is_on_observation_side = (
            scene.xi_label_text == FROZEN_TEXT_BY_ROLE["systematic_term"]
            and scene.xi_label_text in texts
            and scene.xi_side_label == FROZEN_TEXT_BY_ROLE["observation_side"]
            and scene.xi_label_position[0] > DIVIDER_X
            and scene.xi_arrow_target == "station_grid"
            and _point_in_bounds(
                scene.xi_arrow_tip, STATION_GRID_BOUNDS
            )
        )
        if not xi_is_on_observation_side:
            issues.append(
                "ξ_g 未同时满足观测侧位置标签及进入共享测站的箭头关系"
            )

        boundary_is_exact = (
            scene.boundary_text == FROZEN_TEXT_BY_ROLE["boundary"]
            and scene.boundary_text in texts
        )
        if not boundary_is_exact:
            issues.append("边界句缺失或不精确")

        if any(_CJK_PATTERN.search(text) for text in texts):
            issues.append("图面出现中文字符")
        if any(any(character.isdigit() for character in text) for text in texts):
            issues.append("图面出现数字 token")
        if any(_FORBIDDEN_WORD_PATTERN.search(text) for text in texts):
            issues.append("图面出现禁用的运行、结果或诊断词")

        if (
            scene.creation_date != PDF_DATE_TEXT
            or scene.modification_date != PDF_DATE_TEXT
        ):
            issues.append("PDF 日期元数据不是冻结日期")
    except Exception as exc:
        raise Figure4Error("语义校验无法完整执行，已按失败处理。") from exc

    require(not issues, "图面语义校验失败：" + "；".join(issues))


def _semantic_failure_bit(scene: SceneSemantics) -> int:
    """把单个纯内存语义样本归约为通过或失败。"""
    try:
        validate_semantics(scene)
    except Figure4Error:
        return 1
    return 0


def _dynamic_date_probe_value() -> str:
    """仅为负向探针生成动态日期，不参与任何输出元数据。"""
    candidate = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
    if candidate == PDF_DATE_TEXT:
        return "D:20991231235959Z"
    return candidate


def _add_channel_box(
    ax: Any,
    patch_type: Any,
    bounds: tuple[float, float, float, float],
    label: str,
    *,
    linestyle: str,
    facecolor: str,
) -> None:
    """用不同线型绘制观测通道，保持灰度冗余。"""
    left, bottom, width, height = bounds
    box = patch_type(
        (left, bottom),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.45,
        linestyle=linestyle,
        edgecolor="#252525",
        facecolor=facecolor,
        zorder=3,
    )
    ax.add_patch(box)
    ax.text(
        left + width / 2.0,
        bottom + height / 2.0,
        label,
        ha="center",
        va="center",
        color="#202020",
        fontsize=10.4,
        fontweight="semibold",
        zorder=4,
    )


def _draw_figure(
    scene: SceneSemantics,
) -> tuple[Any, frozenset[str], frozenset[str]]:
    """按语义契约驱动真实 artist，并在绘制后执行 fail-closed 集合门。"""
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        from matplotlib.figure import Figure
        from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle
    except Exception as exc:
        raise Figure4Error("无法加载 matplotlib 绘图后端。") from exc

    require(
        scene.expected_drawn_roles == FROZEN_DRAW_ROLES,
        "期望绘制角色集合被改写，拒绝绘制。",
    )

    with matplotlib.rc_context(dict(RENDER_RC)):
        fig = Figure(figsize=FIGURE_SIZE_INCHES, dpi=PNG_DPI)
        fig.patch.set_facecolor("white")
        ax = fig.add_axes((0.025, 0.035, 0.96, 0.94))
        ax.set_facecolor("white")
        ax.set_xlim(CANVAS_BOUNDS[0], CANVAS_BOUNDS[1])
        ax.set_ylim(CANVAS_BOUNDS[2], CANVAS_BOUNDS[3])
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_axis_off()

        drawn_registry: set[str] = set()
        drawn_texts: set[str] = set()

        def register_text(role: str, text: str) -> None:
            drawn_registry.add(role)
            drawn_texts.add(text)

        # 日期契约参与标题 artist 的准入：日期被动态化时，真实标题调用被跳过，
        # 绘制后集合门会因缺少 title 角色而失败。
        dates_are_frozen = (
            scene.creation_date == PDF_DATE_TEXT
            and scene.modification_date == PDF_DATE_TEXT
        )
        title_text = _selected_text(scene, "title")
        if dates_are_frozen and title_text in scene.visible_texts:
            ax.text(
                6.0,
                6.66,
                title_text,
                ha="center",
                va="center",
                fontsize=18.0,
                fontweight="bold",
                color="#181818",
            )
            register_text("title", title_text)

        ax.add_patch(
            Rectangle(
                (0.42, 1.08),
                4.92,
                4.06,
                facecolor="#f1f1f1",
                edgecolor="#343434",
                linewidth=1.25,
                zorder=0,
            )
        )
        ax.plot(
            [0.42, 5.34],
            [5.14, 5.14],
            color="#242424",
            linewidth=2.0,
            solid_capstyle="round",
            zorder=2,
        )
        ax.plot(
            [0.42, 5.34],
            [4.84, 4.84],
            color="#8a8a8a",
            linewidth=0.85,
            linestyle=(0, (4, 3)),
            zorder=1,
        )

        survey_surface_text = _selected_text(scene, "survey_surface")
        if survey_surface_text in scene.visible_texts:
            ax.text(
                0.60,
                5.31,
                survey_surface_text,
                ha="left",
                va="bottom",
                fontsize=9.6,
                color="#444444",
            )
            register_text("survey_surface", survey_surface_text)

        ax.plot(
            [DIVIDER_X, DIVIDER_X],
            [0.72, 6.18],
            color="#4b4b4b",
            linewidth=1.2,
            linestyle=(0, (6, 4)),
            zorder=1,
        )

        model_side_text = _selected_text(scene, "model_side")
        if model_side_text in scene.visible_texts:
            ax.text(
                2.90,
                6.12,
                model_side_text,
                ha="center",
                va="center",
                fontsize=11.5,
                fontweight="semibold",
                color="#303030",
            )
            register_text("model_side", model_side_text)

        observation_side_text = _selected_text(scene, "observation_side")
        if observation_side_text in scene.visible_texts:
            ax.text(
                8.85,
                6.12,
                observation_side_text,
                ha="center",
                va="center",
                fontsize=11.5,
                fontweight="semibold",
                color="#303030",
            )
            register_text("observation_side", observation_side_text)

        target_block_text = _selected_text(scene, "target_block")
        if (
            "target_block" in scene.elements
            and target_block_text in scene.visible_texts
        ):
            target = Rectangle(
                (1.30, 2.22),
                1.62,
                1.06,
                facecolor="#666666",
                edgecolor="#1c1c1c",
                linewidth=2.0,
                zorder=4,
            )
            ax.add_patch(target)
            ax.annotate(
                target_block_text,
                xy=(2.11, 2.76),
                xytext=(1.18, 1.70),
                ha="left",
                va="center",
                fontsize=10.8,
                fontweight="semibold",
                color="#202020",
                arrowprops={
                    "arrowstyle": "-|>",
                    "color": "#202020",
                    "linewidth": 1.25,
                    "shrinkA": 4,
                    "shrinkB": 3,
                },
                zorder=6,
            )
            drawn_registry.add("target_block")
            register_text("target_block", target_block_text)

        decoy_lens_text = _selected_text(scene, "decoy_lens")
        if (
            "decoy_lens" in scene.elements
            and decoy_lens_text in scene.visible_texts
        ):
            decoy = Ellipse(
                (4.10, 3.58),
                width=1.86,
                height=0.90,
                angle=-8.0,
                facecolor="#fafafa",
                edgecolor="#242424",
                linewidth=1.7,
                linestyle=(0, (5, 2)),
                hatch="////",
                zorder=4,
            )
            ax.add_patch(decoy)
            ax.annotate(
                decoy_lens_text,
                xy=(4.12, 3.58),
                xytext=(3.40, 2.66),
                ha="left",
                va="center",
                fontsize=10.8,
                fontweight="semibold",
                color="#202020",
                arrowprops={
                    "arrowstyle": "->",
                    "color": "#202020",
                    "linewidth": 1.15,
                    "linestyle": (0, (3, 2)),
                    "shrinkA": 4,
                    "shrinkB": 4,
                },
                zorder=6,
            )
            drawn_registry.add("decoy_lens")
            register_text("decoy_lens", decoy_lens_text)

        station_grid_text = _selected_text(scene, "station_grid")
        if (
            "station_grid" in scene.elements
            and station_grid_text in scene.visible_texts
        ):
            validate_station_grid(STATION_GRID)
            station_x = STATION_X
            station_y = STATION_Y
            for y_value in station_y:
                ax.plot(
                    [station_x[0], station_x[-1]],
                    [y_value, y_value],
                    color="#a1a1a1",
                    linewidth=0.75,
                    linestyle=(0, (2, 3)),
                    zorder=1,
                )
            for x_value in station_x:
                ax.plot(
                    [x_value, x_value],
                    [station_y[0], station_y[-1]],
                    color="#a1a1a1",
                    linewidth=0.75,
                    linestyle=(0, (2, 3)),
                    zorder=1,
                )
            for y_value in station_y:
                ax.scatter(
                    station_x,
                    [y_value] * len(station_x),
                    marker="s",
                    s=50.0,
                    facecolors="white",
                    edgecolors="#252525",
                    linewidths=1.25,
                    zorder=4,
                )
                ax.scatter(
                    station_x,
                    [y_value] * len(station_x),
                    marker="o",
                    s=8.0,
                    facecolors="#252525",
                    edgecolors="#252525",
                    linewidths=0.0,
                    zorder=5,
                )
            ax.text(
                8.97,
                5.63,
                station_grid_text,
                ha="center",
                va="center",
                fontsize=10.8,
                fontweight="semibold",
                color="#202020",
            )
            drawn_registry.add("station_grid")
            register_text("station_grid", station_grid_text)

        ax.annotate(
            "",
            xy=(6.38, 4.72),
            xytext=(5.02, 4.72),
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#777777",
                "linewidth": 1.05,
                "linestyle": (0, (4, 3)),
            },
            zorder=2,
        )
        ax.annotate(
            "",
            xy=(6.38, 4.20),
            xytext=(4.88, 3.96),
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#777777",
                "linewidth": 1.05,
                "linestyle": (0, (2, 3)),
            },
            zorder=2,
        )

        gravity_observations_text = _selected_text(
            scene, "gravity_observations"
        )
        if gravity_observations_text in scene.visible_texts:
            _add_channel_box(
                ax,
                FancyBboxPatch,
                scene.gravity_observation_bounds,
                gravity_observations_text,
                linestyle="solid",
                facecolor="#d7d7d7",
            )
            register_text(
                "gravity_observations", gravity_observations_text
            )

        magnetic_observations_text = _selected_text(
            scene, "magnetic_observations"
        )
        if magnetic_observations_text in scene.visible_texts:
            _add_channel_box(
                ax,
                FancyBboxPatch,
                (7.10, 2.00, 4.15, 0.62),
                magnetic_observations_text,
                linestyle=(0, (6, 3)),
                facecolor="#ededed",
            )
            register_text(
                "magnetic_observations", magnetic_observations_text
            )

        if (
            "gravity_systematic_term" in scene.elements
            and scene.xi_label_text in scene.visible_texts
        ):
            # 位置和箭头端点直接来自语义字段；探针改位即改变真实 artist。
            ax.annotate(
                scene.xi_label_text,
                xy=scene.xi_arrow_tip,
                xytext=scene.xi_label_position,
                ha="left",
                va="center",
                fontsize=9.3,
                fontweight="semibold",
                color="#171717",
                arrowprops={
                    "arrowstyle": "-|>",
                    "color": "#171717",
                    "linewidth": 1.55,
                    "connectionstyle": "arc3,rad=-0.31",
                    "shrinkA": 4,
                    "shrinkB": 2,
                },
                zorder=7,
            )
            drawn_registry.add("gravity_systematic_term")
            register_text("systematic_term", scene.xi_label_text)

            xi_is_on_observation_side = (
                scene.xi_side_label
                == FROZEN_TEXT_BY_ROLE["observation_side"]
                and scene.xi_label_position[0] > DIVIDER_X
                and scene.xi_arrow_target == "station_grid"
                and _point_in_bounds(
                    scene.xi_arrow_tip, STATION_GRID_BOUNDS
                )
            )
            if xi_is_on_observation_side:
                drawn_registry.add("xi_on_observation_side")
            else:
                drawn_registry.add("xi_on_model_side")

        boundary_text = _selected_text(scene, "boundary")
        if (
            boundary_text == scene.boundary_text
            and boundary_text in scene.visible_texts
        ):
            ax.text(
                0.48,
                0.43,
                boundary_text,
                ha="left",
                va="center",
                fontsize=9.0,
                fontstyle="italic",
                color="#555555",
            )
            register_text("boundary", boundary_text)

        caption_text = _selected_text(scene, "caption")
        if caption_text in scene.visible_texts:
            ax.text(
                6.0,
                0.18,
                caption_text,
                ha="center",
                va="center",
                fontsize=9.7,
                color="#3a3a3a",
            )
            register_text("caption", caption_text)

        require(
            frozenset(drawn_registry) == scene.expected_drawn_roles,
            "真实绘制角色集合偏离期望集合。",
        )
        require(
            frozenset(drawn_texts) == FROZEN_FIGURE_TEXTS,
            "真实绘制文字集合偏离冻结集合。",
        )
        if any(_CJK_PATTERN.search(text) for text in drawn_texts):
            raise Figure4Error("真实绘制文字中出现中文字符。")
        if any(
            any(character.isdigit() for character in text)
            for text in drawn_texts
        ):
            raise Figure4Error("真实绘制文字中出现数字 token。")
        if any(_FORBIDDEN_WORD_PATTERN.search(text) for text in drawn_texts):
            raise Figure4Error("真实绘制文字中出现禁用词。")
        require(
            dates_are_frozen,
            "真实绘制通道检测到动态日期。",
        )

        return fig, frozenset(drawn_registry), frozenset(drawn_texts)


def _reserve_temp_path(directory: Path, suffix: str) -> Path:
    """在目标目录中预留同卷临时文件，供原子替换使用。"""
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{OUTPUT_STEM}-",
        suffix=suffix,
        dir=directory,
    )
    os.close(descriptor)
    return Path(raw_path)


def render_and_publish(output_directory: Path) -> tuple[Path, Path]:
    """先完整写入临时文件，再分别原子发布 PDF 与 PNG。"""
    os.environ["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH

    output_directory.mkdir(parents=True, exist_ok=True)
    pdf_path = output_directory / f"{OUTPUT_STEM}.pdf"
    png_path = output_directory / f"{OUTPUT_STEM}.png"
    temporary_paths: set[Path] = set()
    fig: Any | None = None

    try:
        import matplotlib

        fig, _, _ = _draw_figure(BASE_SCENE)
        temporary_pdf = _reserve_temp_path(output_directory, ".pdf")
        temporary_paths.add(temporary_pdf)
        temporary_png = _reserve_temp_path(output_directory, ".png")
        temporary_paths.add(temporary_png)

        with matplotlib.rc_context(dict(RENDER_RC)):
            fig.savefig(
                temporary_pdf,
                format="pdf",
                metadata=dict(PDF_METADATA),
                facecolor="white",
                edgecolor="white",
                transparent=False,
            )
            fig.savefig(
                temporary_png,
                format="png",
                dpi=PNG_DPI,
                metadata=dict(PNG_METADATA),
                facecolor="white",
                edgecolor="white",
                transparent=False,
            )

        os.replace(temporary_pdf, pdf_path)
        temporary_paths.discard(temporary_pdf)
        os.replace(temporary_png, png_path)
        temporary_paths.discard(temporary_png)
    except Exception as exc:
        for temporary_path in tuple(temporary_paths):
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, Figure4Error):
            raise
        raise Figure4Error("图件写入或原子发布失败。") from exc
    finally:
        if fig is not None:
            fig.clf()

    return pdf_path, png_path


def validate_pdf_artifact(pdf_path: Path) -> None:
    """PDF 实物验收：单页、固定日期、零位图对象和矢量路径。"""
    try:
        payload = pdf_path.read_bytes()
    except OSError as exc:
        raise Figure4Error("无法读取待验收 PDF。") from exc

    require(payload.startswith(b"%PDF-"), "PDF 文件头无效。")
    page_count = len(re.findall(rb"/Type\s*/Page\b", payload))
    require(page_count == 1, "PDF 必须且只能包含单页。")

    frozen_date = re.escape(PDF_DATE_TEXT.encode("ascii"))
    creation_pattern = rb"/CreationDate\s*\(" + frozen_date + rb"\)"
    modification_pattern = rb"/ModDate\s*\(" + frozen_date + rb"\)"
    require(
        re.search(creation_pattern, payload) is not None,
        "PDF CreationDate 未冻结。",
    )
    require(
        re.search(modification_pattern, payload) is not None,
        "PDF ModDate 未冻结。",
    )

    image_xobjects = len(re.findall(rb"/Subtype\s*/Image\b", payload))
    require(image_xobjects == 0, "PDF 含有 Image XObject。")

    streams = re.findall(
        rb"stream\r?\n(.*?)\r?\nendstream",
        payload,
        flags=re.DOTALL,
    )
    vector_operator = re.compile(
        rb"(?:^|\s)(?:m|l|c|v|y|h|re|S|s|f|f\*|B|B\*)(?:\s|$)"
    )
    require(
        any(vector_operator.search(stream) for stream in streams),
        "PDF 未检出矢量路径操作符。",
    )


def validate_png_artifact(png_path: Path) -> None:
    """PNG 实物验收：尺寸、DPI 与逐像素灰度一致性。"""
    try:
        from PIL import Image, ImageChops
    except Exception as exc:
        raise Figure4Error("无法加载 PNG 验收所需的 Pillow。") from exc

    try:
        with Image.open(png_path) as image:
            require(image.format == "PNG", "PNG 文件格式标识无效。")
            require(
                image.size == EXPECTED_PNG_SIZE,
                "PNG 像素尺寸不符合冻结规格。",
            )
            dpi_value = image.info.get("dpi")
            require(
                isinstance(dpi_value, tuple) and len(dpi_value) == 2,
                "PNG 缺少 DPI 元数据。",
            )
            require(
                abs(float(dpi_value[0]) - PNG_DPI) <= 0.1
                and abs(float(dpi_value[1]) - PNG_DPI) <= 0.1,
                "PNG DPI 不符合冻结规格。",
            )

            red, green, blue = image.convert("RGB").split()
            require(
                ImageChops.difference(red, green).getbbox() is None
                and ImageChops.difference(red, blue).getbbox() is None,
                "PNG 含有非灰度颜色像素。",
            )
            minimum, maximum = red.getextrema()
            require(minimum < maximum, "PNG 灰度动态范围退化。")
    except Figure4Error:
        raise
    except Exception as exc:
        raise Figure4Error("PNG 实物验收无法完成。") from exc


def _probe_failure_bit(scene: SceneSemantics) -> int:
    """把真实绘制通道探针归约为通过或失败。"""
    try:
        fig, _, _ = _draw_figure(scene)
        fig.clf()
    except Figure4Error:
        return 1
    return 0


def run_negative_probes() -> None:
    """逐项证明六类违规会让真实绘制通道从通过变为失败。"""
    baseline = _probe_failure_bit(BASE_SCENE)
    require(baseline == 0, "负向探针基线未通过。")

    without_boundary = frozenset(
        text
        for text in BASE_SCENE.visible_texts
        if text != FROZEN_TEXT_BY_ROLE["boundary"]
    )
    dynamic_date = _dynamic_date_probe_value()
    probes: tuple[tuple[str, SceneSemantics], ...] = (
        (
            "缺少四元素之一",
            replace(
                BASE_SCENE,
                elements=BASE_SCENE.elements - {"decoy_lens"},
            ),
        ),
        (
            "ξ_g 被改到模型侧",
            replace(
                BASE_SCENE,
                xi_side_label=FROZEN_TEXT_BY_ROLE["model_side"],
                xi_label_position=(DIVIDER_X - 0.50, 0.82),
                xi_arrow_tip=(DIVIDER_X - 0.60, 3.10),
            ),
        ),
        (
            "删除边界句",
            replace(
                BASE_SCENE,
                visible_texts=without_boundary,
                boundary_text="",
            ),
        ),
        (
            "注入运行读数",
            replace(
                BASE_SCENE,
                visible_texts=(
                    BASE_SCENE.visible_texts
                    - {FROZEN_TEXT_BY_ROLE["caption"]}
                )
                | {"run reading: 7.5"},
                text_overrides=MappingProxyType(
                    {"caption": "run reading: 7.5"}
                ),
            ),
        ),
        (
            "注入中文图面",
            replace(
                BASE_SCENE,
                visible_texts=(
                    BASE_SCENE.visible_texts
                    - {FROZEN_TEXT_BY_ROLE["caption"]}
                )
                | {"观测读数"},
                text_overrides=MappingProxyType({"caption": "观测读数"}),
            ),
        ),
        (
            "注入动态日期",
            replace(
                BASE_SCENE,
                creation_date=dynamic_date,
                modification_date=dynamic_date,
            ),
        ),
    )

    for probe_name, mutated_scene in probes:
        transition = (baseline, _probe_failure_bit(mutated_scene))
        print(f"负向探针｜{probe_name}：{transition[0]} -> {transition[1]}")
        require(
            transition == (0, 1),
            f"负向探针“{probe_name}”未从通过切换为失败。",
        )


def main() -> int:
    """执行纯内存探针并将图件写到脚本所在目录。"""
    try:
        os.environ["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
        if "--self-test" in sys.argv[1:]:
            run_negative_probes()
            print("全部负向探针均已按预期从 0 切换为 1。")
            return 0

        run_negative_probes()
        validate_semantics(BASE_SCENE)
        output_directory = Path(__file__).resolve().parent
        pdf_path, png_path = render_and_publish(output_directory)
        validate_pdf_artifact(pdf_path)
        validate_png_artifact(png_path)
    except Figure4Error as exc:
        print(f"Figure 4 生成失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Figure 4 发生未预期错误：{exc}", file=sys.stderr)
        return 1

    print(f"图件已原子发布：{pdf_path.name}、{png_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
