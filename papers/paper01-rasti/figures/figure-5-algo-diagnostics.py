#!/usr/bin/env python3
"""重放并生成论文图 5；任何注册复现检查失败时均不产生图件。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

# 防止导入主工作树中的注册诊断实现时生成 __pycache__。
sys.dont_write_bytecode = True

EXPECTED_NPZ_SHA256 = "15d340931a0cbff92adb50a27ecf967cb05bc302d319e7cddcfd179d5c53e3b4"
EXPECTED_SOURCE_SHA256 = {
    "rhat.py": "bfe187a7507f3bd6e36bd9bbbee6ab1d5fff9c24879d8a2f2a8e47fe8c98010c",
    "ess.py": "9d7669ed361ee0aa09faeba18f77940516d7fe3812a78885752b610eb28bb683",
    "mcse.py": "ecc6efabb7702a469bdd47d1b302525600796cf6f8d57477a30fb3b2b6c5d65f",
}
EXPECTED_DRAWS_SHAPE = (4, 4000, 48)


class ReproductionError(RuntimeError):
    """注册复现或图件验收失败。"""


def sha256_file(path: Path) -> str:
    """以流式读取计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    """以统一异常类型执行失败关闭检查。"""
    if not condition:
        raise ReproductionError(message)


def locate_paths() -> dict[str, Path]:
    """从脚本的主工作树位置解析注册输入与输出路径。"""
    script_path = Path(__file__).resolve()
    try:
        repo_root = script_path.parents[7]
    except IndexError as exc:
        raise ReproductionError("无法从脚本位置解析仓库根目录。") from exc

    governance_root = (
        repo_root
        / "_bmad-output"
        / "planning-artifacts"
        / "research"
        / "贝叶斯思想与重磁电电磁深度融合技术体系-治理与验证档案"
    )
    run_root = (
        governance_root
        / "validation"
        / "wp7"
        / "versions"
        / "synthetic-block-v6-20260724"
    )
    return {
        "script": script_path,
        "repo_root": repo_root,
        "governance_root": governance_root,
        "run_root": run_root,
        "npz": run_root / "raw-chains.npz",
        "metrics": run_root / "metrics.json",
        "run_manifest": run_root / "run-manifest.json",
        "contract": governance_root / "validation" / "wp2-toy" / "diagnostic-contract.json",
        "diagnostics": governance_root / "src" / "geodeepbayes" / "diagnostics",
        "package_src": governance_root / "src",
        "output_dir": script_path.parent,
    }


def check_npz_hash(npz_path: Path) -> None:
    """第一道门：核对注册 NPZ 的完整哈希。"""
    require(npz_path.is_file(), f"注册 NPZ 不存在：{npz_path}")
    actual = sha256_file(npz_path)
    require(
        actual == EXPECTED_NPZ_SHA256,
        f"注册 NPZ 哈希不一致：期望 {EXPECTED_NPZ_SHA256}，实际 {actual}",
    )
    print(f"[门 1/5] NPZ_SHA256=PASS {actual}")


def load_and_check_draws(npz_path: Path):
    """第二道门：读取 draws，并核对形状与有限性。"""
    import numpy as np

    with np.load(npz_path, allow_pickle=False) as archive:
        require("draws" in archive.files, "注册 NPZ 缺少 draws 键。")
        draws = np.asarray(archive["draws"], dtype=np.float64)

    require(
        draws.shape == EXPECTED_DRAWS_SHAPE,
        f"draws 形状不一致：期望 {EXPECTED_DRAWS_SHAPE}，实际 {draws.shape}",
    )
    require(bool(np.isfinite(draws).all()), "draws 含 NaN 或 Inf。")
    print(f"[门 2/5] DRAWS_SHAPE_FINITE=PASS shape={draws.shape}")
    return np, draws


def check_diagnostic_source_hashes(diagnostics_root: Path) -> None:
    """第三道门：核对三份注册诊断源码哈希。"""
    for filename, expected in EXPECTED_SOURCE_SHA256.items():
        path = diagnostics_root / filename
        require(path.is_file(), f"注册诊断源码不存在：{path}")
        actual = sha256_file(path)
        require(
            actual == expected,
            f"诊断源码哈希不一致：{filename}，期望 {expected}，实际 {actual}",
        )
        print(f"[门 3/5] SOURCE_SHA256=PASS {filename} {actual}")


def compute_registered_diagnostics(np, draws, package_src: Path) -> dict[str, object]:
    """第四道门：用注册实现重算四组逐参数诊断数组。"""
    package_src_text = str(package_src)
    if package_src_text not in sys.path:
        sys.path.insert(0, package_src_text)

    from geodeepbayes.diagnostics import (  # pylint: disable=import-outside-toplevel
        bulk_ess,
        monte_carlo_standard_error,
        rank_normalized_split_rhat,
        tail_ess,
    )

    rhat = np.asarray(rank_normalized_split_rhat(draws), dtype=np.float64)
    bulk = np.asarray(bulk_ess(draws), dtype=np.float64)
    tail = np.asarray(tail_ess(draws), dtype=np.float64)
    mcse = np.asarray(monte_carlo_standard_error(draws), dtype=np.float64)
    sample_sd = np.std(draws, axis=(0, 1), ddof=1)
    require(bool(np.isfinite(sample_sd).all()), "逐参数样本标准差含 NaN 或 Inf。")
    require(bool((sample_sd > 0.0).all()), "逐参数样本标准差含非正值。")
    relative_mcse = mcse / sample_sd

    arrays = {
        "rhat": rhat,
        "bulk_ess": bulk,
        "tail_ess": tail,
        "relative_mcse": relative_mcse,
    }
    for name, values in arrays.items():
        require(values.shape == (48,), f"{name} 形状不一致：实际 {values.shape}")
        require(bool(np.isfinite(values).all()), f"{name} 含 NaN 或 Inf。")

    print("[门 4/5] REGISTERED_ARRAYS=PASS 每组均为 48 个逐参数值")
    return arrays


def load_metrics_and_check_extrema(np, metrics_path: Path, arrays: dict[str, object]) -> dict:
    """第五道门：将四个重算极值与注册 JSON 逐位比较。"""
    require(metrics_path.is_file(), f"注册 metrics JSON 不存在：{metrics_path}")
    with metrics_path.open("r", encoding="utf-8") as stream:
        metrics = json.load(stream)

    actual = {
        "max_rhat": np.max(arrays["rhat"]),
        "min_bulk_ess": np.min(arrays["bulk_ess"]),
        "min_tail_ess": np.min(arrays["tail_ess"]),
        "max_relative_mcse": np.max(arrays["relative_mcse"]),
    }
    indices = {
        "max_rhat": int(np.argmax(arrays["rhat"])),
        "min_bulk_ess": int(np.argmin(arrays["bulk_ess"])),
        "min_tail_ess": int(np.argmin(arrays["tail_ess"])),
        "max_relative_mcse": int(np.argmax(arrays["relative_mcse"])),
    }

    for key, value in actual.items():
        require(key in metrics, f"metrics JSON 缺少 {key}。")
        actual_scalar = np.float64(value)
        expected_scalar = np.float64(metrics[key])
        require(
            actual_scalar.tobytes() == expected_scalar.tobytes(),
            f"{key} 未逐位复现：期望 {expected_scalar!r}，实际 {actual_scalar!r}",
        )
        print(
            f"[复现日志] {key}={repr(float(actual_scalar))} "
            f"parameter_index_0_based={indices[key]} float_hex={float(actual_scalar).hex()}"
        )

    print("[门 5/5] FROZEN_EXTREMA_BITWISE=PASS")
    return metrics


def load_contract(contract_path: Path) -> dict:
    """在复现门通过后读取运行时诊断阈值；阈值只用于无数字参考线。"""
    require(contract_path.is_file(), f"诊断契约不存在：{contract_path}")
    with contract_path.open("r", encoding="utf-8") as stream:
        contract = json.load(stream)
    thresholds = contract.get("thresholds", {})
    required = {
        "rank_normalized_split_rhat_max",
        "bulk_ess_min",
        "tail_ess_min",
    }
    require(required.issubset(thresholds), "诊断契约缺少图 5 所需阈值。")
    return thresholds


def configure_pdf_timestamp(run_manifest_path: Path) -> datetime:
    """从注册 run 的完成时间导出固定 PDF 时间，并在导入 Matplotlib 前设置环境。"""
    require(run_manifest_path.is_file(), f"注册 run manifest 不存在：{run_manifest_path}")
    with run_manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)

    source_key = "completed_at"
    source_value = manifest.get(source_key)
    require(
        isinstance(source_value, str) and bool(source_value.strip()),
        f"注册 run manifest 缺少可用时间字段：{source_key}",
    )
    try:
        parsed = datetime.fromisoformat(source_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReproductionError(
            f"注册时间字段无法解析：{run_manifest_path}::{source_key}={source_value!r}"
        ) from exc
    require(parsed.tzinfo is not None, "注册完成时间缺少时区，不能安全导出 PDF 固定时间。")

    registered_utc = parsed.astimezone(timezone.utc)
    source_date_epoch = math.floor(registered_utc.timestamp())
    require(source_date_epoch >= 0, "注册完成时间不能转换为非负 SOURCE_DATE_EPOCH。")
    fixed_pdf_time = datetime.fromtimestamp(source_date_epoch, tz=timezone.utc)
    os.environ["SOURCE_DATE_EPOCH"] = str(source_date_epoch)
    print(
        "[确定性] PDF_TIME_SOURCE=PASS "
        f"path={run_manifest_path} key={source_key} value={source_value} "
        f"SOURCE_DATE_EPOCH={source_date_epoch} pdf_time={fixed_pdf_time.isoformat()}"
    )
    return fixed_pdf_time


def deterministic_jitter(count: int, amplitude: float):
    """生成不依赖随机数的竖向错位，仅用于避免点完全遮盖。"""
    import numpy as np

    pattern = np.arange(count, dtype=np.float64) % 9.0
    return (pattern - 4.0) * (amplitude / 4.0)


def style_axes(ax) -> None:
    """应用无数字刻度、弱化边框的共同样式。"""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#94a3b8")
    ax.spines["bottom"].set_color("#94a3b8")
    ax.tick_params(axis="both", colors="#334155", length=0)
    ax.set_xticks([])
    ax.grid(False)


def draw_figure(np, arrays: dict[str, object], metrics: dict, thresholds: dict, output_dir: Path):
    """复现门通过后才导入 Matplotlib、建立目录并创建 Figure。"""
    import matplotlib

    matplotlib.use("Agg", force=True)
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 11,
            "axes.labelsize": 9.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )

    # 输出目录的创建明确晚于全部复现门和 Matplotlib 导入。
    output_dir.mkdir(parents=True, exist_ok=True)

    import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

    # 编码先由位置、线型和标记形状承担；颜色仅使用中性灰阶。
    ink = "#1f2933"
    mid = "#64748b"
    light = "#d9e0e7"
    pale = "#eef2f6"
    threshold_color = "#475569"

    identity_styles = {
        "bulk": {"linestyle": "-", "marker": "o"},
        "tail": {"linestyle": "--", "marker": "^"},
        "coverage_lower": {"linestyle": "-", "marker": "o"},
        "coverage_higher": {"linestyle": "--", "marker": "s"},
    }
    require(
        identity_styles["bulk"] != identity_styles["tail"]
        and identity_styles["coverage_lower"] != identity_styles["coverage_higher"],
        "灰度身份编码未提供独立的线型与标记形状。",
    )

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 4.45), constrained_layout=True)
    ax_a, ax_b, ax_c = axes

    # (a) 仅画四链联合计算所得的 48 个逐参数 R-hat，绝不构造逐链 R-hat。
    rhat = arrays["rhat"]
    violin_a = ax_a.violinplot(
        [rhat], positions=[0.0], vert=False, widths=0.58, showmeans=False,
        showmedians=False, showextrema=False,
    )
    for body in violin_a["bodies"]:
        body.set_facecolor(light)
        body.set_edgecolor(ink)
        body.set_linewidth(1.25)
        body.set_alpha(1.0)
    ax_a.scatter(
        rhat,
        deterministic_jitter(rhat.size, 0.34),
        marker="|",
        s=52,
        linewidths=0.9,
        color=ink,
        zorder=3,
    )
    rhat_limit = float(thresholds["rank_normalized_split_rhat_max"])
    ax_a.axvline(rhat_limit, color=threshold_color, linewidth=1.25, linestyle=(0, (2, 3)))
    rhat_low = min(float(np.min(rhat)), rhat_limit)
    rhat_high = max(float(np.max(rhat)), rhat_limit)
    rhat_pad = max((rhat_high - rhat_low) * 0.08, np.finfo(float).eps)
    ax_a.set_xlim(rhat_low - rhat_pad, rhat_high + rhat_pad)
    ax_a.set_ylim(-0.48, 0.48)
    ax_a.set_yticks([])
    ax_a.set_title("(a) Rank-normalized split R-hat", loc="left", fontweight="semibold")
    ax_a.set_xlabel("diagnostic value  —  lower to higher")
    style_axes(ax_a)

    # (b) Bulk 与 tail ESS 以不同纵向位置、线型和标记形状编码。
    bulk = arrays["bulk_ess"]
    tail = arrays["tail_ess"]
    ess_series = [
        (bulk, 1.0, "Bulk ESS", identity_styles["bulk"], float(thresholds["bulk_ess_min"])),
        (tail, 0.0, "Tail ESS", identity_styles["tail"], float(thresholds["tail_ess_min"])),
    ]
    for values, position, label, style, limit in ess_series:
        violin = ax_b.violinplot(
            [values], positions=[position], vert=False, widths=0.58, showmeans=False,
            showmedians=False, showextrema=False,
        )
        for body in violin["bodies"]:
            body.set_facecolor(pale if position == 1.0 else light)
            body.set_edgecolor(ink)
            body.set_linewidth(1.25)
            body.set_linestyle(style["linestyle"])
            body.set_alpha(1.0)
        ax_b.scatter(
            values,
            position + deterministic_jitter(values.size, 0.28),
            marker=style["marker"],
            s=20,
            facecolors="white",
            edgecolors=ink,
            linewidths=0.8,
            zorder=3,
        )
        ax_b.vlines(
            limit,
            position - 0.34,
            position + 0.34,
            color=threshold_color,
            linewidth=1.25,
            linestyle=(0, (2, 3)),
        )
        ax_b.text(
            0.98,
            position + 0.29,
            label,
            transform=ax_b.get_yaxis_transform(),
            ha="right",
            va="bottom",
            color=mid,
        )
    ess_limits = [
        float(np.min(bulk)), float(np.max(bulk)), float(np.min(tail)), float(np.max(tail)),
        float(thresholds["bulk_ess_min"]), float(thresholds["tail_ess_min"]),
    ]
    ess_low, ess_high = min(ess_limits), max(ess_limits)
    ess_span = max(ess_high - ess_low, np.finfo(float).eps)
    ax_b.set_xlim(ess_low - ess_span * 0.06, ess_high + ess_span * 0.24)
    ax_b.set_ylim(-0.55, 1.55)
    ax_b.set_yticks([])
    ax_b.set_title("(b) Effective sample size", loc="left", fontweight="semibold")
    ax_b.set_xlabel("effective sample size  —  lower to higher")
    style_axes(ax_b)

    # (c) 点和 Wilson 区间表达位置关系；nominal 线不带标签或数字。
    coverage = metrics.get("predictive_coverage", {}).get("full", {})
    level_keys = sorted(coverage, key=float)
    require(len(level_keys) == 2, "注册 full coverage 必须恰含两个名义层级。")
    coverage_rows = [
        (level_keys[0], 1.0, "Lower nominal level", identity_styles["coverage_lower"]),
        (level_keys[1], 0.0, "Higher nominal level", identity_styles["coverage_higher"]),
    ]
    coverage_positions: list[float] = []
    for level_key, y_value, label, style in coverage_rows:
        item = coverage[level_key]
        point = float(item["rate"])
        interval = [float(value) for value in item["wilson95"]]
        nominal = float(level_key)
        require(
            len(interval) == 2
            and all(math.isfinite(value) for value in [point, nominal, *interval])
            and interval[0] <= point <= interval[1],
            "注册 coverage 点或区间无效。",
        )
        coverage_positions.extend([point, nominal, *interval])
        ax_c.plot(
            interval,
            [y_value, y_value],
            color=ink,
            linewidth=2.0,
            linestyle=style["linestyle"],
            solid_capstyle="round",
            zorder=2,
        )
        ax_c.scatter(
            [point],
            [y_value],
            marker=style["marker"],
            s=54,
            facecolors="white",
            edgecolors=ink,
            linewidths=1.45,
            zorder=3,
        )
        ax_c.vlines(
            nominal,
            y_value - 0.31,
            y_value + 0.31,
            color=threshold_color,
            linewidth=1.25,
            linestyle=(0, (2, 3)),
            zorder=1,
        )
        ax_c.text(
            0.03,
            y_value + 0.20,
            label,
            transform=ax_c.get_yaxis_transform(),
            ha="left",
            va="bottom",
            color=mid,
        )
    coverage_low, coverage_high = min(coverage_positions), max(coverage_positions)
    coverage_pad = max((coverage_high - coverage_low) * 0.10, np.finfo(float).eps)
    ax_c.set_xlim(coverage_low - coverage_pad, coverage_high + coverage_pad)
    ax_c.set_ylim(-0.55, 1.55)
    ax_c.set_yticks([])
    ax_c.set_title("(c) Same-truth coverage", loc="left", fontweight="semibold")
    ax_c.set_xlabel("same-truth coverage  —  lower to higher")
    style_axes(ax_c)

    # 强制确认三个面板都没有数值刻度文字，且不存在双轴对象。
    require(len(fig.axes) == 3, "Figure 出现额外坐标轴；禁止双轴或隐藏孪生轴。")
    for axis in fig.axes:
        numeric_tick_text = [
            label.get_text()
            for label in [*axis.get_xticklabels(), *axis.get_yticklabels()]
            if re.search(r"[0-9０-９]", label.get_text())
        ]
        require(not numeric_tick_text, f"图面残留数值刻度标签：{numeric_tick_text}")

    return fig, identity_styles


def make_temp_path(output_dir: Path, suffix: str) -> Path:
    """在最终目录同一文件系统创建唯一临时路径。"""
    descriptor, raw_path = tempfile.mkstemp(
        prefix=".figure-5-algo-diagnostics-",
        suffix=suffix,
        dir=output_dir,
    )
    os.close(descriptor)
    return Path(raw_path)


def extract_pdf_text(pdf_path: Path) -> tuple[str | None, str]:
    """按可用性顺序提取 PDF 页面文字，不安装任何新依赖。"""
    if importlib.util.find_spec("pypdf") is not None:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages), "pypdf"

    if importlib.util.find_spec("PyPDF2") is not None:
        from PyPDF2 import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages), "PyPDF2"

    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        result = subprocess.run(
            [pdftotext, "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout, "pdftotext"

    return None, "unavailable"


def scan_extracted_text(text: str, source: str) -> None:
    """扫描提取文字；图面出现任何数字字符即失败关闭。"""
    digits = sorted(set(re.findall(r"[0-9０-９]", text)))
    require(not digits, f"{source} 图面文字提取发现数字字符：{digits}")


def check_pdf_vector_and_text(pdf_path: Path) -> None:
    """检查 PDF 文件头、矢量资源及可行范围内的禁数扫描。"""
    require(pdf_path.read_bytes()[:5] == b"%PDF-", "PDF 文件头无效。")
    text, extractor = extract_pdf_text(pdf_path)
    if text is None:
        print("[验收] PDF_TEXT_SCAN=SKIPPED 未发现可用提取器；未安装新依赖")
        return

    scan_extracted_text(text, f"PDF/{extractor}")
    print(f"[验收] PDF_TEXT_SCAN=PASS extractor={extractor} extracted_chars={len(text)}")

    # 可用 PyPDF 系列时检查页面资源中没有栅格图像对象。
    try:
        if importlib.util.find_spec("pypdf") is not None:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        elif importlib.util.find_spec("PyPDF2") is not None:
            from PyPDF2 import PdfReader  # type: ignore[import-not-found]
        else:
            return
        reader = PdfReader(str(pdf_path))
        image_count = 0
        for page in reader.pages:
            resources = page.get("/Resources")
            if resources is None:
                continue
            resources = resources.get_object()
            xobjects = resources.get("/XObject")
            if xobjects is None:
                continue
            xobjects = xobjects.get_object()
            for item in xobjects.values():
                obj = item.get_object()
                if obj.get("/Subtype") == "/Image":
                    image_count += 1
        require(image_count == 0, f"PDF 含 {image_count} 个栅格图像对象，未保持全矢量。")
        print("[验收] PDF_VECTOR_RESOURCES=PASS image_xobjects=0")
    except ReproductionError:
        raise
    except Exception as exc:  # 资源检查不是文字扫描的替代品，但异常须如实登记。
        print(f"[验收] PDF_VECTOR_RESOURCES=SKIPPED 解析器异常：{exc}")


def check_png_and_grayscale(np, png_path: Path, identity_styles: dict[str, dict[str, str]]) -> None:
    """检查 PNG 文件头，并以内存灰度预览评估可读性。"""
    require(png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "PNG 文件头无效。")

    from PIL import Image  # pylint: disable=import-outside-toplevel

    with Image.open(png_path) as image:
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        width, height = image.size

    require(width >= 3000 and height >= 1000, f"PNG 分辨率不足：{width}x{height}")
    gray_min = int(np.min(gray))
    gray_max = int(np.max(gray))
    unique_levels = int(np.unique(gray).size)
    nonwhite_fraction = float(np.mean(gray < 250))
    require(gray_min <= 80 and gray_max >= 250, "灰度预览缺少足够的明暗范围。")
    require(unique_levels >= 32, "灰度预览层级过少。")
    require(0.005 <= nonwhite_fraction <= 0.65, "灰度预览前景占比异常。")
    require(
        identity_styles["bulk"]["linestyle"] != identity_styles["tail"]["linestyle"]
        and identity_styles["bulk"]["marker"] != identity_styles["tail"]["marker"],
        "Bulk/tail 的灰度次级编码不独立。",
    )
    print(
        "[验收] GRAYSCALE_PREVIEW=PASS "
        f"size={width}x{height} gray_min={gray_min} gray_max={gray_max} "
        f"unique_levels={unique_levels} nonwhite_fraction={nonwhite_fraction:.6f} "
        "bulk_tail=line_style+marker+position"
    )


def check_png_ocr(png_path: Path) -> None:
    """若本机已有 Tesseract，则执行 PNG OCR 禁数扫描；否则如实跳过。"""
    tesseract = shutil.which("tesseract")
    if not tesseract:
        print("[验收] PNG_OCR=SKIPPED 未发现 tesseract；按要求未安装新依赖")
        return

    result = subprocess.run(
        [tesseract, str(png_path), "stdout", "--psm", "6", "-l", "eng"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    scan_extracted_text(result.stdout, "PNG/Tesseract OCR")
    print(f"[验收] PNG_OCR=PASS extracted_chars={len(result.stdout)}")


def publish_pair_atomically(
    temp_pdf: Path,
    temp_png: Path,
    final_pdf: Path,
    final_png: Path,
) -> None:
    """先备份旧对，再逐文件原子替换；任一失败则回滚，避免留下半对输出。"""
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
            try:
                backup.unlink(missing_ok=True)
            except OSError as exc:
                print(f"[警告] 旧版备份清理失败但新 PDF/PNG 对已完整发布：{backup}：{exc}")


def log_output(path: Path) -> None:
    """打印最终输出的文件头、字节数与 SHA-256。"""
    header = path.read_bytes()[:8].hex()
    print(
        f"[输出] path={path} bytes={path.stat().st_size} "
        f"header_hex={header} sha256={sha256_file(path)}"
    )


def main() -> int:
    """按固定顺序执行注册复现、绘制、验收与原子发布。"""
    paths = locate_paths()

    # 下列五门的顺序不可改；此前不导入 Matplotlib、不创建 Figure、不写图件。
    check_npz_hash(paths["npz"])
    np, draws = load_and_check_draws(paths["npz"])
    check_diagnostic_source_hashes(paths["diagnostics"])
    arrays = compute_registered_diagnostics(np, draws, paths["package_src"])
    metrics = load_metrics_and_check_extrema(np, paths["metrics"], arrays)

    # 固定时间来自注册 run manifest；本调用必须先于 draw_figure 内的 Matplotlib 导入。
    fixed_pdf_time = configure_pdf_timestamp(paths["run_manifest"])
    thresholds = load_contract(paths["contract"])
    fig = None
    temp_pdf: Path | None = None
    temp_png: Path | None = None
    final_pdf = paths["output_dir"] / "figure-5-algo-diagnostics.pdf"
    final_png = paths["output_dir"] / "figure-5-algo-diagnostics.png"

    try:
        fig, identity_styles = draw_figure(
            np,
            arrays,
            metrics,
            thresholds,
            paths["output_dir"],
        )
        temp_pdf = make_temp_path(paths["output_dir"], ".pdf.tmp")
        temp_png = make_temp_path(paths["output_dir"], ".png.tmp")

        fig.savefig(
            temp_pdf,
            format="pdf",
            bbox_inches="tight",
            metadata={
                "Creator": "GeoDeepBayes paper figure replay",
                "CreationDate": fixed_pdf_time,
                "ModDate": fixed_pdf_time,
            },
        )
        fig.savefig(
            temp_png,
            format="png",
            dpi=450,
            bbox_inches="tight",
            metadata={"Software": "Matplotlib"},
        )

        # 先关闭 Figure，再检查完整临时文件；检查全过才发布最终名。
        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

        plt.close(fig)
        fig = None

        require(temp_pdf.stat().st_size > 0, "临时 PDF 为空。")
        require(temp_png.stat().st_size > 0, "临时 PNG 为空。")
        check_pdf_vector_and_text(temp_pdf)
        check_png_and_grayscale(np, temp_png, identity_styles)
        check_png_ocr(temp_png)

        publish_pair_atomically(temp_pdf, temp_png, final_pdf, final_png)
        temp_pdf = None
        temp_png = None

        log_output(final_pdf)
        log_output(final_png)
        print("[完成] 图 5 PDF/PNG 已成对发布；图注未烙入画布。")
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
    except ReproductionError as exc:
        print(f"[失败关闭] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
