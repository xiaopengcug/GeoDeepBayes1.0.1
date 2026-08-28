#!/usr/bin/env python3
"""校验论文 01 发布清单及已登记的只读重放摘要。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
import re
import tempfile
import sys
from pathlib import Path
from typing import Any


PAPER_RELATIVE = Path("papers") / "paper01-rasti"
MANIFEST_RELATIVE = PAPER_RELATIVE / "release-manifest.json"
REPLAY_RESULT_RELATIVE = PAPER_RELATIVE / "replay-result.json"
MANIFEST_EXCLUDED_PATHS = (
    MANIFEST_RELATIVE.as_posix(),
    REPLAY_RESULT_RELATIVE.as_posix(),
)
EXCLUDED_DIRECTORY_NAMES = {
    ".codegraph",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    "__pycache__",
}
BLOCK_MARKER = re.compile(r"(?m)^<!--block:B[0-9]+-->\r?\n?")
EVIDENCE_NOTE = re.compile(r"\s*⟦.*?⟧", re.DOTALL)
REFERENCE_PIPELINE_NOTE = re.compile(
    r"(?m)\s+(?:（[^`\r\n]*）)?`\[LIT:[^\r\n]*$"
)
REFERENCE_NOTE_HEADER = re.compile(r"(?m)^> \*\*著录说明\*\*[^\r\n]*(?:\r?\n)?")
ANCHORED_BLOCK_RE = re.compile(
    r"(?ms)^<!--block:(B\d+)-->\r?\n(.*?)(?=^<!--block:B\d+-->\r?\n|\Z)"
)
BLOCK_LEADING_BOLD = re.compile(r"^\*\*([^*\r\n]+)\*\*")
CAPTION_OR_FRONT_MATTER = re.compile(
    r"^\*\*(?:Table|Figure|Keywords|Li Xiao Peng)", re.IGNORECASE
)
ALLOWED_TRANSFORMATIONS = {
    "block_marker_lines",
    "evidence_note_spans",
    "reference_pipeline_notes",
}
FIGURE_STEMS = (
    "figure-1-framework-governance",
    "figure-2-probabilistic-dag",
    "figure-3-multiscale-parameterisation",
    "figure-4-evd-joint-scene",
    "figure-5-algo-diagnostics",
)
EXPECTED_FIGURE_SCRIPTS = frozenset(f"{stem}.py" for stem in FIGURE_STEMS)
EXPECTED_FIGURE_IMAGES = frozenset(
    f"{stem}{suffix}" for stem in FIGURE_STEMS for suffix in (".pdf", ".png")
)
DRIVE_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[/\\]")
JOINT_CODE_PATHS = {
    "rhat.py": Path("src/geodeepbayes/diagnostics/rhat.py"),
    "ess.py": Path("src/geodeepbayes/diagnostics/ess.py"),
    "mcse.py": Path("src/geodeepbayes/diagnostics/mcse.py"),
    "joint_block.py": Path("src/geodeepbayes/benchmarks/joint_block.py"),
    "diagnostic-contract.json": Path("validation/wp2-toy/diagnostic-contract.json"),
}
ALGORITHM_CODE_PATHS = {
    name: relative
    for name, relative in JOINT_CODE_PATHS.items()
    if name in {"rhat.py", "ess.py", "mcse.py"}
}

REQUIRED_RELEASE_MEMBERS = (
    "papers/paper01-rasti/manuscript/figure-1-framework-governance.pdf",
    "papers/paper01-rasti/manuscript/figure-1-framework-governance.png",
    "papers/paper01-rasti/manuscript/figure-2-probabilistic-dag.pdf",
    "papers/paper01-rasti/manuscript/figure-2-probabilistic-dag.png",
    "papers/paper01-rasti/manuscript/figure-3-multiscale-parameterisation.pdf",
    "papers/paper01-rasti/manuscript/figure-3-multiscale-parameterisation.png",
    "papers/paper01-rasti/manuscript/figure-4-evd-joint-scene.pdf",
    "papers/paper01-rasti/manuscript/figure-4-evd-joint-scene.png",
    "papers/paper01-rasti/manuscript/figure-5-algo-diagnostics.pdf",
    "papers/paper01-rasti/manuscript/figure-5-algo-diagnostics.png",
    "papers/paper01-rasti/supplement/reproducibility-and-adoption-checklist-r1.md",
    "papers/paper01-rasti/evidence/positive-control/joint-diagnostics-input.npz",
    "papers/paper01-rasti/evidence/positive-control/joint-diagnostics-expected.json",
    "src/geodeepbayes/benchmarks/joint_block.py",
    "validation/wp2-toy/diagnostic-contract.json",
    "validation/wp7/synthetic-v6-config.json",
    "validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json",
    "validation/wp7/versions/synthetic-block-v6-20260724/run-manifest.json",
    "validation/wp7/versions/synthetic-block-v6-20260724/metrics.json",
    "validation/wp7/versions/synthetic-block-v6-20260724/raw-chains.npz",
    "validation/wp7/versions/do27-v4-20260724/run-manifest.json",
    "validation/wp7/versions/do27-v4-20260724/PROVENANCE.md",
    "validation/wp7/versions/do27-v4-20260724/raw-numerics.npz",
    "validation/wp7/versions/do27-v4-20260724/source_record.zenodo.json",
    "validation/wp7/versions/do27-v4-20260724/UPSTREAM-LICENSE-MIT.txt",
    "validation/runs/open-data-20260717-03/run-manifest.json",
)
CREDENTIAL_PATTERNS = (
    (
        "named_token_or_key",
        re.compile(
            r"(?i)(?:ZENODO(?:_ACCESS)?_TOKEN|GITHUB_TOKEN|GH_TOKEN|"
            r"OPENAI_API_KEY|S2_API_KEY|OPENALEX_API_KEY|API_KEY|ACCESS_TOKEN)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{16,}"
        ),
    ),
    ("github_classic_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("github_fine_grained_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "bearer_credential",
        re.compile(r"(?i)Authorization\s*[:=]\s*[\"']?Bearer\s+[A-Za-z0-9._~+\-/]{20,}"),
    ),
)


class VerificationError(RuntimeError):
    """发布包或登记结果不满足冻结契约。"""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"无法读取 JSON：{path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_lf_normalized(path: Path) -> str:
    """对文本按发布树 LF 字节计算哈希；二进制保持原字节。"""
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".md", ".py", ".txt", ".yml", ".yaml"}:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def _verify_stable_source_label(
    payload: dict,
    *,
    label_field: str,
    forbidden_field: str,
) -> None:
    """要求新生成工件仅携带稳定相对/历史标签。"""
    if forbidden_field in payload:
        raise VerificationError(f"重放工件不得包含本机绝对字段 {forbidden_field}")
    label = payload.get(label_field)
    if (
        not isinstance(label, str)
        or not label
        or DRIVE_ABSOLUTE_PATH.match(label)
        or label.startswith(("/", "\\"))
        or ".." in Path(label).parts
    ):
        raise VerificationError(f"{label_field} 必须是稳定相对或历史标签，禁止盘符绝对路径")


def _verify_hash_map(
    repository: Path,
    recorded: object,
    expected_paths: dict[str, Path],
    label: str,
) -> None:
    if not isinstance(recorded, dict) or set(recorded) != set(expected_paths):
        raise VerificationError(f"{label}代码 SHA-256 字段集合不完整")
    for name, relative in expected_paths.items():
        path = repository / relative
        actual = _sha256_lf_normalized(path)
        if recorded.get(name) != actual:
            raise VerificationError(
                f"{label}代码 SHA-256 不一致：{name}，"
                f"expected={recorded.get(name)}，actual={actual}"
            )


def verify_threshold_contract(repository: Path) -> dict[str, int]:
    """锁定 WP2 合同与 WP7 算法配置的同名门槛等值。"""
    repository = Path(repository).resolve()
    contract = _read_json(repository / "validation" / "wp2-toy" / "diagnostic-contract.json")
    config = _read_json(repository / "validation" / "wp7" / "synthetic-v6-config.json")
    contract_thresholds = contract.get("thresholds", {})
    config_thresholds = config.get("thresholds", {})
    mappings = {
        "max_rhat": "rank_normalized_split_rhat_max",
        "min_bulk_ess": "bulk_ess_min",
        "min_tail_ess": "tail_ess_min",
        "max_relative_mcse": "relative_mcse_max",
        "min_mode_visits_per_chain": "required_mode_visits_per_chain",
        "max_failed_replicate_rate": "failed_replicate_rate_max",
    }
    missing_config = [name for name in mappings if name not in config_thresholds]
    missing_contract = [name for name in mappings.values() if name not in contract_thresholds]
    if missing_config or missing_contract:
        raise VerificationError(
            "WP2/WP7 诊断阈值缺少显式映射键："
            f"config={missing_config}，contract={missing_contract}"
        )
    mismatches = {
        config_name: (config_thresholds[config_name], contract_thresholds[contract_name])
        for config_name, contract_name in mappings.items()
        if config_thresholds[config_name] != contract_thresholds[contract_name]
    }
    if mismatches:
        raise VerificationError(f"WP2/WP7 诊断阈值不等值：{mismatches}")
    return {"threshold_equalities_verified": len(mappings)}


def _repository_root(paper_root: Path) -> Path:
    paper_root = Path(paper_root).resolve()
    if paper_root.name != "paper01-rasti" or paper_root.parent.name != "papers":
        raise VerificationError(
            f"发布包根目录必须是 <repository>/papers/paper01-rasti：{paper_root}"
        )
    return paper_root.parents[1]


def _resolve_within(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise VerificationError(f"{label}路径越界：{relative}") from exc
    return candidate


def _manifest_files(repository: Path) -> list[Path]:
    repository = Path(repository).resolve()
    members: list[Path] = []
    for path in repository.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repository)
        if EXCLUDED_DIRECTORY_NAMES.intersection(relative.parts):
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        if relative in {MANIFEST_RELATIVE, REPLAY_RESULT_RELATIVE}:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        members.append(path)
    return sorted(members, key=lambda item: item.relative_to(repository).as_posix())


def build_manifest(root: Path) -> dict:
    """确定性生成候选树中除自引用清单与运行时输出外的成员清单。"""
    root = Path(root).resolve()
    repository = _repository_root(root)
    members = []
    for path in _manifest_files(repository):
        relative = path.relative_to(repository)
        members.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema_version": "paper01-release-manifest/1.2",
        "scope": "repository_tag_tree_excluding_declared_self_and_runtime_outputs",
        "excluded_paths": list(MANIFEST_EXCLUDED_PATHS),
        "package_status": "release_candidate_pending_human_verification",
        "members": members,
    }


def write_manifest(root: Path) -> Path:
    """以 UTF-8/LF 写入当前候选的确定性发布清单。"""
    root = Path(root).resolve()
    target = root / "release-manifest.json"
    target.write_text(
        json.dumps(build_manifest(root), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def verify_manifest(root: Path) -> int:
    """按显式排除边界重算候选树成员集合、字节数和 SHA-256。"""
    root = Path(root).resolve()
    repository = _repository_root(root)
    manifest = _read_json(root / "release-manifest.json")
    if manifest.get("schema_version") != "paper01-release-manifest/1.2":
        raise VerificationError("发布清单 schema_version 不受支持")
    if (
        manifest.get("scope")
        != "repository_tag_tree_excluding_declared_self_and_runtime_outputs"
        or manifest.get("excluded_paths") != list(MANIFEST_EXCLUDED_PATHS)
    ):
        raise VerificationError("发布清单未精确声明自引用与运行时输出排除边界")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise VerificationError("发布清单没有成员")

    seen: set[str] = set()
    declared: dict[str, dict[str, Any]] = {}
    for row in members:
        relative = row.get("path")
        expected = row.get("sha256")
        expected_bytes = row.get("bytes")
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or not isinstance(expected_bytes, int)
        ):
            raise VerificationError("发布清单成员字段不完整")
        if relative in seen:
            raise VerificationError(f"发布清单含重复路径：{relative}")
        seen.add(relative)
        declared[relative] = row
        member = _resolve_within(repository, relative, "发布清单")
        if not member.is_file():
            raise VerificationError(f"发布清单成员不存在：{relative}")
        if member.stat().st_size != expected_bytes:
            raise VerificationError(
                f"发布清单成员字节数不一致：{relative}，"
                f"expected={expected_bytes}，actual={member.stat().st_size}"
            )
        actual = _sha256(member)
        if actual != expected:
            raise VerificationError(
                f"发布清单成员 SHA-256 不一致：{relative}，expected={expected}，actual={actual}"
            )

    actual_paths = {
        path.relative_to(repository).as_posix() for path in _manifest_files(repository)
    }
    declared_paths = set(declared)
    missing = sorted(declared_paths - actual_paths)
    unlisted = sorted(actual_paths - declared_paths)
    if missing or unlisted:
        raise VerificationError(
            "发布清单成员集合不一致："
            f"缺失={missing or []}；未登记={unlisted or []}"
        )
    return len(members)


def verify_evidence(root: Path) -> dict[str, int]:
    """从记录层重算 Stage 4 冻结摘要，不重跑原始实验。"""
    root = Path(root).resolve()
    repository = _repository_root(root)
    verification = Path(root) / "evidence" / "verification-final"
    joint = _read_json(verification / "joint-replay-summary.json")
    algorithm = _read_json(verification / "algorithm-replay.json")
    m2 = _read_json(verification / "m2-reconstruction-lineage.json")

    _verify_stable_source_label(
        joint,
        label_field="source_label",
        forbidden_field="source_root",
    )
    _verify_stable_source_label(
        algorithm,
        label_field="source_label",
        forbidden_field="source_root",
    )
    _verify_stable_source_label(
        m2,
        label_field="pilot_label",
        forbidden_field="pilot_root",
    )
    _verify_hash_map(
        repository,
        joint.get("code_and_contract_sha256"),
        JOINT_CODE_PATHS,
        "联合重放",
    )
    _verify_hash_map(
        repository,
        algorithm.get("code_sha256"),
        ALGORITHM_CODE_PATHS,
        "算法重放",
    )
    verify_threshold_contract(repository)

    algorithm_source = (
        repository
        / "validation"
        / "wp7"
        / "versions"
        / "synthetic-block-v6-20260724"
    )
    source_paths = {
        name: algorithm_source / name for name in ("raw-chains.npz", "metrics.json")
    }
    actual_source_hashes = {
        name: _sha256_lf_normalized(path) for name, path in source_paths.items()
    }
    source_before = algorithm.get("source_sha256_before")
    source_after = algorithm.get("source_sha256_after")
    if source_before != actual_source_hashes or source_after != actual_source_hashes:
        raise VerificationError(
            "算法重放源字节 SHA-256 不一致："
            f"expected={actual_source_hashes}，before={source_before}，after={source_after}"
        )

    joint_records = joint.get("records")
    if not isinstance(joint_records, list) or len(joint_records) != 65:
        raise VerificationError("联合历史记录层必须恰含 65 条记录")
    joint_paths = [row.get("source_relative_path") for row in joint_records]
    if any(not isinstance(path, str) for path in joint_paths) or len(set(joint_paths)) != 65:
        raise VerificationError("联合历史逐条记录的源路径必须完整且唯一")
    record_transition_count = sum(
        row.get("status_transition") == {"from": "Failed", "to": "Failed"}
        for row in joint_records
    )
    record_stop_count = sum(
        row.get("replayed_diagnostics", {}).get("diagnostic_stop_reason")
        == "nonfinite_diagnostic"
        for row in joint_records
    )
    record_integrity_count = sum(
        row.get("source_integrity_preserved") is True for row in joint_records
    )
    degenerate_counts = Counter(
        row.get("replayed_diagnostics", {}).get("degenerate_channel_count")
        for row in joint_records
    )
    if (
        record_transition_count != 65
        or record_stop_count != 65
        or record_integrity_count != 65
    ):
        raise VerificationError(
            "联合历史逐条记录层不满足 65 个 Failed->Failed、"
            "nonfinite_diagnostic 与完整性保持"
        )
    if degenerate_counts != Counter({1: 57, 2: 3, 6: 5}):
        raise VerificationError(
            f"联合历史退化通道分布必须保持 57+3+5；实际={dict(degenerate_counts)}"
        )

    joint_sources = joint.get("source_count")
    joint_summary = joint.get("summary", {})
    transition_count = joint_summary.get("status_transition_counts", {}).get(
        "Failed->Failed"
    )
    stop_count = joint_summary.get("diagnostic_stop_reason_counts", {}).get(
        "nonfinite_diagnostic"
    )
    if joint_sources != len(joint_records) or transition_count != record_transition_count:
        raise VerificationError(
            "联合历史状态必须保持 65 个 Failed->Failed 记录"
        )
    if (
        stop_count != record_stop_count
        or joint_summary.get("all_source_integrity_preserved")
        is not (record_integrity_count == len(joint_records))
    ):
        raise VerificationError("联合历史摘要的完整性或 fail-closed 原因不一致")

    config_path = repository / "validation" / "wp7" / "synthetic-v6-config.json"
    config = _read_json(config_path)
    if algorithm.get("config_sha256") != _sha256(config_path):
        raise VerificationError("算法阈值配置 SHA-256 与发布树文件不一致")
    thresholds = config.get("thresholds", {})
    replayed = algorithm.get("replayed_diagnostics", {})

    def finite_number(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )

    threshold_inputs = {
        "rhat": (replayed.get("max_rhat"), thresholds.get("max_rhat"), "max"),
        "bulk_ess": (
            replayed.get("min_bulk_ess"),
            thresholds.get("min_bulk_ess"),
            "min",
        ),
        "tail_ess": (
            replayed.get("min_tail_ess"),
            thresholds.get("min_tail_ess"),
            "min",
        ),
        "relative_mcse": (
            replayed.get("max_relative_mcse"),
            thresholds.get("max_relative_mcse"),
            "max",
        ),
    }
    computed_checks: dict[str, bool] = {}
    for name, (value, threshold, direction) in threshold_inputs.items():
        if not finite_number(value) or not finite_number(threshold):
            raise VerificationError(f"算法阈值重算输入非有限或缺失：{name}")
        computed_checks[name] = (
            float(value) <= float(threshold)
            if direction == "max"
            else float(value) >= float(threshold)
        )

    checks = algorithm.get("threshold_checks", {})
    required_checks = ("rhat", "bulk_ess", "tail_ess", "relative_mcse")
    if checks != computed_checks:
        changed = [name for name in required_checks if checks.get(name) != computed_checks[name]]
        raise VerificationError(f"算法阈值布尔摘要与重算不一致：{changed}")
    if (
        algorithm.get("source_integrity_preserved") is not True
        or algorithm.get("all_four_thresholds_pass") is not all(computed_checks.values())
        or not all(computed_checks.values())
    ):
        raise VerificationError("算法组件的四项登记阈值未全部通过")
    expected_conservative_values = {
        "max_rhat_ceiling_5dp": 1.00374,
        "min_bulk_ess_floor_integer": 2496,
        "min_tail_ess_floor_integer": 1963,
        "max_relative_mcse_ceiling_4dp": 0.0202,
    }
    if algorithm.get("manuscript_conservative_values") != expected_conservative_values:
        raise VerificationError("算法组件四个保守报告值发生漂移")

    m2_summary = m2.get("summary", {})
    m2_records = m2.get("records")
    if not isinstance(m2_records, list) or len(m2_records) != 42:
        raise VerificationError("M2 逐条记录层必须恰含 42 条记录")
    run_ids = [row.get("run_id") for row in m2_records]
    if any(not isinstance(run_id, str) for run_id in run_ids) or len(set(run_ids)) != 42:
        raise VerificationError("M2 逐条记录的 run_id 必须完整且唯一")
    record_exact = sum(
        row.get("ledger_row_exact_match") is True for row in m2_records
    )
    if record_exact != 42:
        raise VerificationError("M2 逐条记录层未保持 42/42 精确匹配")

    lambda_grid_pattern = re.compile(
        r"^s0[0-4]__lam-(?:0|1|10|100|1000|10000)__da$"
    )
    am_pattern = re.compile(r"^s0[01]__lam-1000__am$")
    weighted_pattern = re.compile(
        r"^s0[0-4]__lam-1000__w(?:-xifrozen)?__da$"
    )
    decomposition = (
        sum(bool(lambda_grid_pattern.fullmatch(run_id)) for run_id in run_ids),
        sum(bool(am_pattern.fullmatch(run_id)) for run_id in run_ids),
        sum(bool(weighted_pattern.fullmatch(run_id)) for run_id in run_ids),
    )
    if decomposition != (30, 2, 10):
        raise VerificationError(
            f"M2 的 42 条记录必须分解为 30 个 λ 网格、2 个 AM 和 10 个加权臂；实际={decomposition}"
        )

    exact = m2_summary.get("exact_match_count")
    total = m2_summary.get("run_count")
    if (
        exact != record_exact
        or total != len(m2_records)
        or m2_summary.get("all_rows_exact") is not True
        or m2_summary.get("unbound_ledger_run_ids") != []
    ):
        raise VerificationError("M2 重建谱系必须保持 42/42 且无未绑定 run id")

    return {
        "joint_sources": joint_sources,
        "joint_failed_to_failed": transition_count,
        "algorithm_checks_passed": len(required_checks),
        "m2_exact": exact,
        "m2_total": total,
    }


def _collect_hash_references(value: object, locator: str = "$") -> list[tuple[str, str, str]]:
    references: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        path = value.get("path")
        digest = value.get("sha256")
        if isinstance(path, str) and isinstance(digest, str):
            references.append((locator, path, digest))
        files_sha256 = value.get("files_sha256")
        if isinstance(files_sha256, dict):
            for mapped_path in sorted(files_sha256):
                mapped_digest = files_sha256[mapped_path]
                if isinstance(mapped_path, str) and isinstance(mapped_digest, str):
                    mapped_locator = (
                        f"{locator}.files_sha256["
                        f"{json.dumps(mapped_path, ensure_ascii=False)}]"
                    )
                    references.append((mapped_locator, mapped_path, mapped_digest))
        for key, child in value.items():
            references.extend(_collect_hash_references(child, f"{locator}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            references.extend(_collect_hash_references(child, f"{locator}[{index}]"))
    return references


HISTORICAL_CODE_EVOLUTION_ALLOWLIST = {
    (
        "src/geodeepbayes/diagnostics/ess.py",
        "9d7669ed361ee0aa09faeba18f77940516d7fe3812a78885752b610eb28bb683",
        "111fc44474ad6a22f618b66e5e87ddbf79511b06714f266e9205e8b80fff5292",
    ),
    (
        "src/geodeepbayes/diagnostics/rhat.py",
        "bfe187a7507f3bd6e36bd9bbbee6ab1d5fff9c24879d8a2f2a8e47fe8c98010c",
        "2a4408976cf8cfca2fae67e76138dbbb439a9cb16709384bd97d798753d24523",
    ),
}

HISTORICAL_ENVIRONMENT_EVOLUTION_ALLOWLIST = {
    (
        "uv.lock",
        "c71791cc6cda23ea4ba563821a4235261374e5268d8cfd9a595799c552834026",
        "819f311f710d9e9265858c4dd004060333b6360313598cf3e5b7a57ff05b7c6f",
    ),
}


def _resolve_historical_member(repository: Path, record_path: Path, raw_path: str) -> Path | None:
    """把旧治理根路径映射到精选发布树中的唯一现行成员。"""
    normalized = raw_path.replace("\\", "/")
    rooted = "/" + normalized.lstrip("/")
    relative_candidates: list[str] = []
    for marker in ("/src/", "/validation/"):
        if marker in rooted:
            relative_candidates.append(
                f"{marker.strip('/')}/{rooted.split(marker, 1)[1]}"
            )
    relative_candidates.extend((normalized, f"validation/{normalized}"))
    candidates = [repository / candidate for candidate in relative_candidates]
    candidates.extend((record_path.parent / normalized, record_path.parent.parent / normalized))
    existing = {candidate.resolve() for candidate in candidates if candidate.is_file()}
    if not existing and normalized:
        suffix = "/" + normalized.lstrip("/")
        existing = {
            candidate.resolve()
            for candidate in repository.rglob(Path(normalized).name)
            if candidate.is_file()
            and ("/" + candidate.relative_to(repository).as_posix()).endswith(suffix)
        }
    if len(existing) > 1:
        raise VerificationError(f"历史路径映射不唯一：{raw_path} -> {sorted(map(str, existing))}")
    return next(iter(existing)) if existing else None


def _crlf_variant_sha256(path: Path) -> str | None:
    content = path.read_bytes()
    if b"\x00" in content:
        return None
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    lf = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(lf.replace("\n", "\r\n").encode("utf-8")).hexdigest()


def _build_validation_compatibility_entries(repository: Path) -> list[dict[str, Any]]:
    repository = Path(repository).resolve()
    validation_root = repository / "validation"
    entries: list[dict[str, Any]] = []
    for record_path in sorted(validation_root.rglob("*.json")):
        record = _read_json(record_path)
        record_relative = record_path.relative_to(repository).as_posix()
        for locator, original_path, original_sha256 in _collect_hash_references(record):
            current = _resolve_historical_member(repository, record_path, original_path)
            if current is None:
                continue
            current_relative = current.relative_to(repository).as_posix()
            current_sha256 = _sha256_lf_normalized(current)
            if original_sha256 == current_sha256:
                classification = "exact"
                reason = "历史 SHA-256 与当前发布字节一致"
            elif original_sha256 == _crlf_variant_sha256(current):
                classification = "historical_eol_normalization"
                reason = "历史 SHA-256 对应 CRLF，当前发布成员按 LF 固定"
            elif (
                current_relative,
                original_sha256,
                current_sha256,
            ) in HISTORICAL_CODE_EVOLUTION_ALLOWLIST:
                classification = "historical_code_evolution"
                reason = "显式 allowlist：诊断实现演进，历史记录保持不变"
            elif (
                current_relative,
                original_sha256,
                current_sha256,
            ) in HISTORICAL_ENVIRONMENT_EVOLUTION_ALLOWLIST:
                classification = "historical_environment_evolution"
                reason = (
                    "作者显式授权：加入 pypdf 6.16.2 dev 依赖用于发布图件 PDF 验收；"
                    "历史证据记录保持不变"
                )
            else:
                raise VerificationError(
                    "可解析历史链接存在未分类失配："
                    f"{record_relative} {locator} -> {original_path}，"
                    f"historical={original_sha256}，current={current_sha256}"
                )
            entries.append(
                {
                    "record_path": record_relative,
                    "locator": locator,
                    "original_path": original_path,
                    "original_sha256": original_sha256,
                    "classification": classification,
                    "classification_reason": reason,
                    "current_path": current_relative,
                    "current_bytes": current.stat().st_size,
                    "current_sha256": current_sha256,
                }
            )
    return sorted(
        entries,
        key=lambda row: (
            row["record_path"],
            row["locator"],
            row["original_path"],
            row["original_sha256"],
        ),
    )


def build_validation_link_compatibility(repository: Path) -> dict[str, Any]:
    """建立历史 path/hash 到当前发布字节的只读分类侧车。"""
    entries = _build_validation_compatibility_entries(repository)
    counts: dict[str, int] = {}
    for row in entries:
        classification = row["classification"]
        counts[classification] = counts.get(classification, 0) + 1
    return {
        "schema_version": "paper01-validation-link-compatibility/1.0",
        "policy": "historical_records_byte_preserved_current_release_bytes_bound",
        "summary": {
            "resolvable_links": len(entries),
            "classification_counts": dict(sorted(counts.items())),
        },
        "entries": entries,
    }


def write_validation_link_compatibility(repository: Path) -> Path:
    repository = Path(repository).resolve()
    target = repository / PAPER_RELATIVE / "provenance" / "validation-link-compatibility.json"
    payload = build_validation_link_compatibility(repository)
    _atomic_write_bytes(
        target,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return target


def verify_validation_link_compatibility(repository: Path) -> dict[str, int]:
    """重算全部可解析历史链接并逐字段核对兼容侧车。"""
    repository = Path(repository).resolve()
    sidecar = _read_json(
        repository / PAPER_RELATIVE / "provenance" / "validation-link-compatibility.json"
    )
    expected = build_validation_link_compatibility(repository)
    if sidecar != expected:
        raise VerificationError("validation 历史链接兼容侧车与当前可解析链接不一致")
    return {
        "resolvable_links": expected["summary"]["resolvable_links"],
        "unclassified_mismatches": 0,
    }


def verify_revision_bundle(root: Path) -> dict[str, int]:
    """遍历并验证 revision-evidence bundle 的全部内部哈希链接。"""
    root = Path(root).resolve()
    bundle_root = root / "evidence" / "revision-bundle-r2"
    bundle_path = bundle_root / "revision-evidence-bundle-r2.json"
    bundle = _read_json(bundle_path)
    if bundle.get("schema_version") != "revision-evidence-bundle/1.0":
        raise VerificationError("revision evidence bundle schema_version 不受支持")
    references = _collect_hash_references(bundle)
    if not references:
        raise VerificationError("revision evidence bundle 没有内部哈希链接")
    for locator, relative, expected in references:
        member = _resolve_within(bundle_root, relative, "证据束内部")
        if not member.is_file():
            raise VerificationError(f"证据束内部成员不存在：{locator} -> {relative}")
        actual = _sha256(member)
        if actual != expected:
            raise VerificationError(
                "证据束内部 SHA-256 不一致："
                f"{locator} -> {relative}，expected={expected}，actual={actual}"
            )
    if not isinstance(bundle.get("rounds"), list):
        raise VerificationError("revision evidence bundle 的 rounds 字段无效")
    outer = root / "evidence" / "revision-evidence-bundle-r2.json"
    if outer.exists():
        raise VerificationError("revision evidence bundle 存在冗余外层副本")
    refreeze_report = _read_json(
        root / "provenance" / "revision-bundle-r2-refreeze-report.json"
    )
    changes = refreeze_report.get("changes")
    if (
        refreeze_report.get("schema_version")
        != "ars-revision-bundle-refreeze/1.0"
        or refreeze_report.get("status") != "passed"
        or refreeze_report.get("bundle_sha256_after") != _sha256(bundle_path)
        or refreeze_report.get("links_verified") != len(references)
        or refreeze_report.get("links_updated") != 2
        or refreeze_report.get("redundant_outer_copy_removed") is not True
        or not isinstance(changes, list)
        or len(changes) != 2
    ):
        raise VerificationError("revision bundle 重冻结报告与当前证据束不一致")
    for change in changes:
        relative = change.get("path")
        current_sha256 = change.get("current_sha256")
        if not isinstance(relative, str) or not isinstance(current_sha256, str):
            raise VerificationError("revision bundle 重冻结变更记录字段不完整")
        member = _resolve_within(bundle_root, relative, "重冻结报告")
        if not member.is_file() or _sha256(member) != current_sha256:
            raise VerificationError(f"revision bundle 重冻结成员漂移：{relative}")
    return {"links_verified": len(references), "refreeze_report_verified": 1}


def render_submission_text(anchored: str) -> str:
    """仅执行登记过的非语义清洁变换。"""
    without_notes = EVIDENCE_NOTE.sub("", anchored)
    if "⟦" in without_notes or "⟧" in without_notes:
        raise VerificationError("可见正文中的证据注记开启与闭合标记未配对")
    clean = BLOCK_MARKER.sub("", anchored)
    clean = EVIDENCE_NOTE.sub("", clean)
    clean = REFERENCE_NOTE_HEADER.sub("", clean)
    clean = REFERENCE_PIPELINE_NOTE.sub("", clean)
    clean = re.sub(r"[ \t]+(?=\r?$)", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"(?:\r?\n){3,}", "\n\n", clean).strip() + "\n"
    return clean


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """在同一目录落盘并原子替换，避免发布工件出现半写状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def write_submission_render(root: Path) -> tuple[Path, Path]:
    """由 anchored 稿确定性重建 clean 稿及其哈希绑定报告。"""
    root = Path(root).resolve()
    anchored_path = root / "manuscript" / "manuscript-anchored.md"
    clean_path = root / "manuscript" / "manuscript-clean.md"
    report_path = root / "provenance" / "clean-render-report.json"
    anchored_bytes = anchored_path.read_bytes()
    try:
        anchored = anchored_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"anchored 稿不是 UTF-8：{exc}") from exc
    clean_bytes = render_submission_text(anchored).encode("utf-8")
    _atomic_write_bytes(clean_path, clean_bytes)
    report = {
        "schema_version": "ars-clean-manuscript-render/1.1",
        "source": {
            "path": "manuscript/manuscript-anchored.md",
            "bytes": len(anchored_bytes),
            "sha256": hashlib.sha256(anchored_bytes).hexdigest(),
        },
        "output": {
            "path": "manuscript/manuscript-clean.md",
            "bytes": len(clean_bytes),
            "sha256": hashlib.sha256(clean_bytes).hexdigest(),
        },
        "removed": {
            "block_marker_lines": len(BLOCK_MARKER.findall(anchored)),
            "evidence_note_spans": len(EVIDENCE_NOTE.findall(anchored)),
            "reference_pipeline_notes": (
                len(REFERENCE_NOTE_HEADER.findall(anchored))
                + len(REFERENCE_PIPELINE_NOTE.findall(anchored))
            ),
        },
        "allowed_transformations": sorted(ALLOWED_TRANSFORMATIONS),
        "semantic_edits": 0,
        "status": "release_candidate_pending_human_verification",
    }
    _atomic_write_bytes(
        report_path,
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return clean_path, report_path


def verify_submission_render(root: Path) -> dict[str, int]:
    """重做 anchored→clean 变换，拒绝报告与稿件共同漂移。"""
    root = Path(root).resolve()
    anchored_path = root / "manuscript" / "manuscript-anchored.md"
    clean_path = root / "manuscript" / "manuscript-clean.md"
    report = _read_json(root / "provenance" / "clean-render-report.json")
    if report.get("schema_version") != "ars-clean-manuscript-render/1.1":
        raise VerificationError("clean render report schema_version 不受支持")
    if set(report.get("allowed_transformations", [])) != ALLOWED_TRANSFORMATIONS:
        raise VerificationError("clean render report 的允许变换集合不完整")
    if report.get("semantic_edits") != 0:
        raise VerificationError("clean render report 声称发生语义编辑")
    if report.get("source", {}).get("sha256") != _sha256(anchored_path):
        raise VerificationError("clean render source SHA-256 不一致")
    if report.get("output", {}).get("sha256") != _sha256(clean_path):
        raise VerificationError("clean render output SHA-256 不一致")
    expected = render_submission_text(anchored_path.read_text(encoding="utf-8"))
    actual = clean_path.read_text(encoding="utf-8")
    if actual != expected:
        raise VerificationError("clean 稿不等于允许渲染结果，存在语义漂移")
    return {
        "anchored_bytes": anchored_path.stat().st_size,
        "clean_bytes": clean_path.stat().st_size,
    }


def verify_manuscript_contract(root: Path) -> dict[str, Any]:
    """验证 R4–R6 的事实修复、编号顺序与可见正文文风上限。"""
    root = Path(root).resolve()
    anchored = (root / "manuscript" / "manuscript-anchored.md").read_text(
        encoding="utf-8"
    )
    clean = (root / "manuscript" / "manuscript-clean.md").read_text(
        encoding="utf-8"
    )
    response = (root / "manuscript" / "response-to-reviewers-r1.md").read_text(
        encoding="utf-8"
    )
    human_verification = (root / "HUMAN-VERIFICATION.md").read_text(
        encoding="utf-8"
    )
    table_order = re.findall(r"(?m)^\*\*Table ([1-9][0-9]*a?)\.", clean)
    figure_order = re.findall(r"(?m)^\*\*Figure ([1-9][0-9]*)\.", clean)
    paragraph_order = re.findall(r"(?m)^(?:\*\*)?P([1-6])\.", clean)
    equation_six = re.findall(r"\\tag\{(6\.[0-9]+)\}", clean)
    if table_order != ["1", "2", "3", "4", "5", "5a"]:
        raise VerificationError(f"主文表号顺序错误：{table_order}")
    if figure_order != ["1", "2", "3", "4", "5"]:
        raise VerificationError(f"图号顺序错误：{figure_order}")
    if paragraph_order != ["1", "2", "3", "4", "5", "6"]:
        raise VerificationError(f"引言段号顺序错误：{paragraph_order}")
    if equation_six != ["6.1", "6.2"]:
        raise VerificationError(f"第 6 节方程号错误：{equation_six}")

    required = (
        "Cauchy priors over reflectivity or AVO coefficients",
        "Two rows carry Synthetic-run support",
        "all five pilot scenes",
        "30 $\\lambda_{gm}$-grid runs",
        "two adaptive-Metropolis arms",
        "ten weighted arms",
        "did not adjudicate that priority",
        "Appendix D",
        "item-by-item review",
        "Li Xiao Peng made substantive revisions and accepts responsibility",
        "author-managed clean-environment replay",
        "independent-team replay has not been completed",
        "| $K$ | number of methods | 3.2 |",
    )
    missing = [value for value in required if value not in clean]
    if missing:
        raise VerificationError(f"R4 必需修订缺失：{missing}")
    forbidden = (
        "correlated heavy-tailed likelihood within a single method",
        "Only one row",
        "all three scenario families",
        "Table 6.",
        "Table 4a.",
        "Eq. (6.3)",
        r"\tag{6.3}",
        "Referenced from §6.1, Eq. (6.2)",
        "generalized-Bayes",
        "multiscale unstructured",
        "preregistration Appendix",
        "spatio-temporal holdout",
        "have not been pushed",
        "no immutable public commit",
        "著录说明",
        "[LIT:",
        "依 team lead",
    )
    hits = [value for value in forbidden if value in clean]
    if hits:
        raise VerificationError(f"R4 禁止文本仍存在：{hits}")

    if 'The "multi-scale" of the title refers' in clean:
        raise VerificationError("R6 标题残留仍存在：multi-scale of the title")
    if "joint-pilot registration and failure records" in clean:
        raise VerificationError("R6 含混 failure records 措辞仍存在")
    r6_required = (
        (clean, "carried once in Table A.1"),
        (clean, "All four boundaries carry a mandatory co-disclosure"),
        (clean, "distinct planned redesign batch"),
        (clean, "Appendix E.1 of the pre-registration document"),
        (clean, "25 discrepancies between downloaded byte sizes and upstream metadata"),
        (clean, "failure summaries and reconstructed gate ledger"),
        (clean, "superseded DO-27 v2 failure package are excluded"),
        (clean, "*Bayesian Analysis, 12*(4), 1069–1103."),
        (clean, "*Geophysical Journal International, 215*(3), 1540–1557."),
        (clean, "… Mons, B. (2016)."),
        (response, "§2.2 text now points to Table A.1"),
        (response, "Addressed with Table 5a, immediately following Table 5."),
        (response, "**Location:** immediately following Table 5."),
        (human_verification, "superseded DO-27 v2 failure package"),
    )
    r6_missing = [value for corpus, value in r6_required if value not in corpus]
    if r6_missing:
        raise VerificationError(f"R6 必需修订缺失：{r6_missing}")
    if clean.count("**Table A.1.") != 1:
        raise VerificationError("R6 Table A.1 必须恰保留一份")
    if clean.count(
        "| Nearest neighbour | Auditable priors | Shared-error likelihood |"
    ) != 1:
        raise VerificationError("R6 最近邻清单表必须恰保留一份")
    r6_forbidden = (
        (clean, "Three of the four boundaries carry"),
        (response, "Table 5 now assigns every element cell"),
        (response, "Addressed with Table 4a."),
        (response, "**Location:** immediately after Table 4."),
        (anchored, "Crossref 未返回卷期页"),
    )
    r6_hits = [value for corpus, value in r6_forbidden if value in corpus]
    if r6_hits:
        raise VerificationError(f"R6 禁止文本仍存在：{r6_hits}")

    visible_blocks: list[str] = []
    block_leading_bold = 0
    for match in ANCHORED_BLOCK_RE.finditer(anchored):
        if int(match.group(1)[1:]) >= 533:
            continue
        visible = match.group(2).split("⟦", 1)[0]
        visible_blocks.append(visible)
        if BLOCK_LEADING_BOLD.match(visible) and not CAPTION_OR_FRONT_MATTER.match(
            visible
        ):
            block_leading_bold += 1
    corpus = "\n".join(visible_blocks)
    style_metrics = {
        "em_dash": corpus.count("—"),
        "rather_than": len(re.findall(r"\brather than\b", corpus, re.IGNORECASE)),
        "block_leading_bold": block_leading_bold,
        "travel_with": len(re.findall(r"\btravels? with\b", corpus, re.IGNORECASE)),
        "generalized_bayes": corpus.count("generalized-Bayes"),
    }
    expected_style = {
        "em_dash": 101,
        "rather_than": 56,
        "block_leading_bold": 0,
        "travel_with": 0,
        "generalized_bayes": 0,
    }
    if style_metrics != expected_style:
        raise VerificationError(
            f"R4 可见正文文风指标漂移：expected={expected_style}，actual={style_metrics}"
        )
    patch_record = _read_json(
        root / "provenance" / "release-manuscript-patch-r4-application.json"
    )
    structural_operations = patch_record.get("structural_operations")
    authorization = patch_record.get("authorization", {})
    if (
        patch_record.get("schema_version")
        != "ars-authorized-patch-application/1.0"
        or patch_record.get("patch_sha256")
        != "9487ebda98c7b1c2c29a9e27215592f211fdd5d44184594513d98600d2be0ca6"
        or patch_record.get("after_sha256")
        != "ef03aa58ee5e6fbaa3f21874ba6d2cb8728b43b3fba32d90d0f57df8b5df3361"
        or patch_record.get("operations_applied") != 193
        or not authorization.get("all_listed_targets_and_operations_authorized")
        or not authorization.get("structural_changes_acknowledged")
        or not authorization.get("formal_release_separately_blocked_on_human_verification")
        or not isinstance(structural_operations, list)
        or len(structural_operations) != 3
        or any(row.get("status") != "completed" for row in structural_operations)
    ):
        raise VerificationError("R4 授权补丁应用记录与当前稿件或结构状态不一致")
    r5_record = _read_json(root / "provenance" / "release-r5-patch-application.json")
    if (
        r5_record.get("schema_version") != "ars-release-r5-patch-application/1.0"
        or r5_record.get("base_candidate")
        != "7a9d06f27a0a21b7ee93bb01091c5b853e164b95"
        or r5_record.get("base_manuscript_sha256")
        != "ef03aa58ee5e6fbaa3f21874ba6d2cb8728b43b3fba32d90d0f57df8b5df3361"
        or r5_record.get("patch_sha256")
        != "dd71c7c147a066d65321432d51efd5fac50b581635343254031f4c35358c98c0"
        or r5_record.get("after_manuscript_sha256")
        != "95570a979e39ffca75d5cfde21115d8f346b1469fb3de32852345f7d8f252b7e"
        or r5_record.get("after_clean_sha256")
        != "48a53ab7b97155461252adaa2459917d9c6fc028beb3c01c9fba71e28aa6702d"
        or r5_record.get("historical_records_byte_preserved") is not True
        or r5_record.get("formal_release_locked") is not True
        or r5_record.get("requires_new_candidate_manual_review") is not True
    ):
        raise VerificationError("R5 授权补丁应用记录与当前稿件或发布锁不一致")
    r6_record = _read_json(root / "provenance" / "release-r6-patch-application.json")
    if (
        r6_record.get("schema_version") != "ars-release-r6-patch-application/1.0"
        or r6_record.get("base_candidate")
        != "a2050c8345dfc614c9acf67d48f2ee1b9b4071ff"
        or r6_record.get("base_manuscript_sha256")
        != "95570a979e39ffca75d5cfde21115d8f346b1469fb3de32852345f7d8f252b7e"
        or r6_record.get("base_response_sha256")
        != "3668ad1e72b3988823d4159a8472f0e1411f92b24842d7ab1758599b86892982"
        or r6_record.get("base_human_verification_sha256")
        != "7492066b97eee678b1a74a5c0a5a284b96917450e912ab12432f46956e2ff576"
        or r6_record.get("patch_sha256")
        != "94b2bc0702b10290fe46f006c75e94ae0a9ca768a3d6ce2a413af232e47cc847"
        or r6_record.get("operation_counts")
        != {
            "manuscript_blocks": 12,
            "text_replacements": 3,
            "code_specs": 3,
            "structural_operations": 4,
        }
        or r6_record.get("after_manuscript_sha256")
        != "6339aa01a47f6b5da5f870f4ea1981bfeee9b136f1e60461631ae2f6ea7ec1c2"
        or r6_record.get("after_clean_sha256")
        != "801cd2a692b8110877a9de07747494b37804f329542b579443c5d751b57923c7"
        or r6_record.get("after_response_sha256")
        != "26b619e6d7295cbf662251b751d2a84d6c4029ade954587ae27feee604b0c856"
        or r6_record.get("after_human_verification_sha256")
        != "b08b92ee65d3511e299076a2cf43cabf9c0ab7b43edfd05795b77f90ae8dcdf2"
        or _sha256(root / "manuscript" / "manuscript-anchored.md")
        != "6339aa01a47f6b5da5f870f4ea1981bfeee9b136f1e60461631ae2f6ea7ec1c2"
        or _sha256(root / "manuscript" / "manuscript-clean.md")
        != "801cd2a692b8110877a9de07747494b37804f329542b579443c5d751b57923c7"
        or _sha256(root / "manuscript" / "response-to-reviewers-r1.md")
        != "26b619e6d7295cbf662251b751d2a84d6c4029ade954587ae27feee604b0c856"
        or _sha256(root / "HUMAN-VERIFICATION.md")
        != "b08b92ee65d3511e299076a2cf43cabf9c0ab7b43edfd05795b77f90ae8dcdf2"
        or r6_record.get("historical_records_byte_preserved") is not True
        or r6_record.get("formal_release_locked") is not True
        or r6_record.get("requires_new_candidate_full_release_review") is not True
        or r6_record.get("requires_new_full_sha_release_authorization") is not True
        or r6_record.get("status")
        != "applied_pending_machine_and_human_verification"
    ):
        raise VerificationError("R6 授权补丁应用记录与当前稿件或发布锁不一致")
    return {
        "table_order": table_order,
        "figure_order": figure_order,
        "paragraph_order": paragraph_order,
        "section_6_equations": equation_six,
        "required_repairs_verified": len(required),
        "forbidden_regressions": len(hits),
        "patch_record_verified": 1,
        "r5_patch_record_verified": 1,
        "r6_repairs_verified": len(r6_required),
        "r6_forbidden_regressions": len(r6_hits),
        "r6_patch_record_verified": 1,
        "style_metrics": style_metrics,
    }


def verify_submission_hygiene(root: Path) -> dict[str, int]:
    """拒绝投稿稿件中的内部生产注记和未标记模拟评审材料。"""
    root = Path(root).resolve()
    clean_path = root / "manuscript" / "manuscript-clean.md"
    response_path = root / "manuscript" / "response-to-reviewers-r1.md"
    try:
        clean = clean_path.read_text(encoding="utf-8")
        response = response_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"无法读取投稿稿件：{exc}") from exc
    forbidden = ("著录说明", "[LIT:", "依 team lead", "team lead 裁定")
    hits = [token for token in forbidden if token in clean]
    if hits:
        raise VerificationError(f"clean 稿仍含参考文献内部注记：{hits}")
    response_header = response[:1000].upper()
    if "SIMULATED" not in response_header or "INTERNAL" not in response_header:
        raise VerificationError("response-to-reviewers 必须标注 SIMULATED INTERNAL 模拟评审")
    return {"forbidden_note_hits": 0, "simulated_review_label": 1}


def verify_zenodo_metadata(path: Path) -> dict[str, str]:
    """锁定公开下载但不授予开放复用许可的 Zenodo 组合。"""
    metadata = _read_json(Path(path))
    access_right = metadata.get("access_right")
    license_id = metadata.get("license")
    if access_right != "open" or license_id != "other-closed":
        raise VerificationError(
            "Zenodo 元数据必须显式使用 access_right=open 与 license=other-closed"
        )
    return {"access_right": access_right, "license": license_id}


def verify_citation_metadata(path: Path) -> dict[str, int]:
    """要求 CFF 显式链接仓库的访问与许可边界。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"无法读取 CITATION.cff：{exc}") from exc
    match = re.search(r'(?m)^license-url:\s*["\']?([^"\'\r\n]+)', text)
    if match is None or "#access-and-licence" not in match.group(1):
        raise VerificationError("CITATION.cff 缺少指向访问与许可边界的 license-url")
    return {"license_url_verified": 1}


def verify_do27_provenance(repository: Path) -> dict[str, str]:
    """绑定 DO-27 派生数值、上游 Zenodo 记录及其 MIT 许可边界。"""
    repository = Path(repository).resolve()
    root = (
        repository
        / "validation"
        / "wp7"
        / "versions"
        / "do27-v4-20260724"
    )
    source_record = _read_json(root / "source_record.zenodo.json")
    doi = source_record.get("doi")
    metadata = source_record.get("metadata", {})
    if doi != "10.5281/zenodo.3633239":
        raise VerificationError("DO-27 来源记录 DOI 不等于冻结版本 10.5281/zenodo.3633239")
    if not isinstance(metadata, dict):
        raise VerificationError("DO-27 来源记录缺少 metadata")
    license_record = metadata.get("license", {})
    description = metadata.get("description")
    if (
        not isinstance(license_record, dict)
        or license_record.get("id") != "other-open"
        or not isinstance(description, str)
        or "mit license" not in description.lower()
    ):
        raise VerificationError("DO-27 Zenodo 来源记录未声明其上游 MIT License")

    license_path = root / "UPSTREAM-LICENSE-MIT.txt"
    try:
        license_text = license_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"无法读取 DO-27 上游许可证：{exc}") from exc
    required_license_phrases = (
        "MIT License",
        "Permission is hereby granted, free of charge",
    )
    if any(phrase not in license_text for phrase in required_license_phrases):
        raise VerificationError("DO-27 上游许可证文本不是所登记的 MIT License")

    raw_path = root / "raw-numerics.npz"
    provenance_path = root / "PROVENANCE.md"
    if not raw_path.is_file():
        raise VerificationError("DO-27 派生数值附件 raw-numerics.npz 不存在")
    digest = _sha256(raw_path)
    try:
        provenance = provenance_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"无法读取 DO-27 来源说明：{exc}") from exc
    if doi not in provenance or digest not in provenance:
        raise VerificationError("DO-27 来源说明未绑定冻结 DOI 与 raw-numerics SHA-256")
    return {
        "doi": doi,
        "raw_numerics_sha256": digest,
        "license": "MIT",
    }


def verify_figure_inventory(repository: Path) -> dict[str, int]:
    """正文目录只放 Figures 1–5 图像，figures 目录只放对应生成器。"""
    repository = Path(repository).resolve()
    figures = repository / PAPER_RELATIVE / "figures"
    manuscript = repository / PAPER_RELATIVE / "manuscript"
    if not figures.is_dir() or not manuscript.is_dir():
        raise VerificationError("图件生成器或正文目录不存在")
    actual_scripts = {
        path.name
        for path in figures.iterdir()
        if path.is_file() and path.name.lower().startswith("figure-")
    }
    actual_images = {
        path.name
        for path in manuscript.iterdir()
        if path.is_file() and path.name.lower().startswith("figure-")
    }
    missing_scripts = sorted(EXPECTED_FIGURE_SCRIPTS - actual_scripts)
    extra_scripts = sorted(actual_scripts - EXPECTED_FIGURE_SCRIPTS)
    missing_images = sorted(EXPECTED_FIGURE_IMAGES - actual_images)
    extra_images = sorted(actual_images - EXPECTED_FIGURE_IMAGES)
    if missing_scripts or extra_scripts or missing_images or extra_images:
        raise VerificationError(
            "Figure 1–5 正文同目录集合不一致："
            f"生成器缺失={missing_scripts}；生成器额外={extra_scripts}；"
            f"正文图像缺失={missing_images}；正文图像额外={extra_images}"
        )
    return {
        "figure_families": len(FIGURE_STEMS),
        "figure_images": len(actual_images),
        "figure_scripts": len(actual_scripts),
    }


def verify_figure5_source_binding(repository: Path) -> dict[str, int]:
    """执行 Figure 5 的树内路径解析与当前诊断源码哈希门。"""
    repository = Path(repository).resolve()
    script = repository / PAPER_RELATIVE / "figures" / "figure-5-algo-diagnostics.py"
    spec = importlib.util.spec_from_file_location("paper01_release_figure5", script)
    if spec is None or spec.loader is None:
        raise VerificationError("无法加载 Figure 5 生成器")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    paths = module.locate_paths()
    expected_paths = {
        "repository_root": repository,
        "run_root": repository / "validation" / "wp7" / "versions" / "synthetic-block-v6-20260724",
        "contract": repository / "validation" / "wp2-toy" / "diagnostic-contract.json",
        "diagnostics": repository / "src" / "geodeepbayes" / "diagnostics",
        "package_src": repository / "src",
        "output_dir": repository / PAPER_RELATIVE / "manuscript",
    }
    mismatches = {
        name: (paths.get(name), expected)
        for name, expected in expected_paths.items()
        if paths.get(name) != expected
    }
    if mismatches:
        raise VerificationError(f"Figure 5 未仅解析精选发布树路径：{mismatches}")
    try:
        module.check_diagnostic_source_hashes(paths["diagnostics"])
    except Exception as exc:
        raise VerificationError(f"Figure 5 当前源码钉值失败：{exc}") from exc
    return {"portable_paths_verified": len(expected_paths), "source_pins_verified": 3}


def verify_release_shape(repository: Path) -> dict[str, int]:
    """验证 DOI 候选是精选、读者可用且不含内部治理树的发布树。"""
    repository = Path(repository).resolve()
    internal = repository / "_bmad-output"
    if internal.exists():
        raise VerificationError("精选发布树不得包含 _bmad-output 内部治理工件")
    transient = [
        path.relative_to(repository).as_posix()
        for path in repository.rglob(".run.lock")
        if path.is_file()
    ]
    if transient:
        raise VerificationError(f"精选发布树含瞬时 .run.lock：{transient}")
    missing = [
        relative
        for relative in REQUIRED_RELEASE_MEMBERS
        if not (repository / relative).is_file()
    ]
    if missing:
        raise VerificationError(f"缺少发布必需成员：{missing}")
    inventory = verify_figure_inventory(repository)
    return {
        "required_members_verified": len(REQUIRED_RELEASE_MEMBERS),
        **inventory,
    }


def verify_no_credentials(repository: Path) -> dict[str, int]:
    """扫描发布成员中的高置信访问令牌、密钥和私钥标记。"""
    repository = Path(repository).resolve()
    files_scanned = 0
    bytes_scanned = 0
    findings: list[dict[str, str]] = []
    for path in _manifest_files(repository):
        content = path.read_bytes()
        if b"\x00" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        files_scanned += 1
        bytes_scanned += len(content)
        for label, pattern in CREDENTIAL_PATTERNS:
            if pattern.search(text):
                findings.append(
                    {
                        "path": path.relative_to(repository).as_posix(),
                        "pattern": label,
                    }
                )
    if findings:
        raise VerificationError(f"发布树发现高置信凭据模式：{findings}")
    return {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "high_confidence_findings": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="paper01-rasti 发布包根目录",
    )
    parser.add_argument(
        "--write-clean",
        action="store_true",
        help="先由 anchored 稿重建 clean 稿及 clean-render-report.json",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="先按当前候选成员重建 release-manifest.json",
    )
    args = parser.parse_args(argv)
    try:
        if args.write_clean:
            write_submission_render(args.root)
        if args.write_manifest:
            write_manifest(args.root)
        result = {
            "status": "passed",
            "scope": (
                "author-managed clean-environment replay of release hashes and "
                "registered summaries; not independent reproduction of raw experiments"
            ),
            "manifest_members_verified": verify_manifest(args.root),
            "evidence": verify_evidence(args.root),
            "revision_bundle": verify_revision_bundle(args.root),
            "submission_render": verify_submission_render(args.root),
            "manuscript_contract": verify_manuscript_contract(args.root),
            "submission_hygiene": verify_submission_hygiene(args.root),
            "citation_metadata": verify_citation_metadata(
                _repository_root(args.root) / "CITATION.cff"
            ),
            "zenodo_metadata": verify_zenodo_metadata(
                _repository_root(args.root) / ".zenodo.json"
            ),
            "do27_provenance": verify_do27_provenance(
                _repository_root(args.root)
            ),
            "release_shape": verify_release_shape(_repository_root(args.root)),
            "figure5_source_binding": verify_figure5_source_binding(
                _repository_root(args.root)
            ),
            "validation_link_compatibility": verify_validation_link_compatibility(
                _repository_root(args.root)
            ),
            "credential_scan": verify_no_credentials(_repository_root(args.root)),
        }
    except VerificationError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
