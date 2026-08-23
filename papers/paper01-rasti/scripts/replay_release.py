#!/usr/bin/env python3
"""校验论文 01 发布清单及已登记的只读重放摘要。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class VerificationError(RuntimeError):
    """发布包或登记结果不满足冻结契约。"""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"无法读取 JSON：{path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(root: Path) -> dict:
    """确定性生成发布成员清单，不包含自引用或运行时输出。"""
    root = Path(root).resolve()
    excluded_names = {"release-manifest.json", "replay-result.json"}
    members = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if path.name in excluded_names or "__pycache__" in relative.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        members.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema_version": "paper01-release-manifest/1.0",
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
    """逐项重算 `release-manifest.json` 成员 SHA-256。"""
    root = Path(root).resolve()
    manifest = _read_json(root / "release-manifest.json")
    if manifest.get("schema_version") != "paper01-release-manifest/1.0":
        raise VerificationError("发布清单 schema_version 不受支持")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise VerificationError("发布清单没有成员")

    seen: set[str] = set()
    for row in members:
        relative = row.get("path")
        expected = row.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise VerificationError("发布清单成员字段不完整")
        if relative in seen:
            raise VerificationError(f"发布清单含重复路径：{relative}")
        seen.add(relative)
        member = (root / relative).resolve()
        try:
            member.relative_to(root)
        except ValueError as exc:
            raise VerificationError(f"发布清单路径越界：{relative}") from exc
        if not member.is_file():
            raise VerificationError(f"发布清单成员不存在：{relative}")
        actual = _sha256(member)
        if actual != expected:
            raise VerificationError(
                f"发布清单成员 SHA-256 不一致：{relative}，expected={expected}，actual={actual}"
            )
    return len(members)


def verify_evidence(root: Path) -> dict[str, int]:
    """验证 Stage 4 冻结摘要，不把摘要升级为原始链的独立重算。"""
    verification = Path(root) / "evidence" / "verification-final"
    joint = _read_json(verification / "joint-replay-summary.json")
    algorithm = _read_json(verification / "algorithm-replay.json")
    m2 = _read_json(verification / "m2-reconstruction-lineage.json")

    joint_sources = joint.get("source_count")
    joint_summary = joint.get("summary", {})
    transition_count = joint_summary.get("status_transition_counts", {}).get(
        "Failed->Failed"
    )
    stop_count = joint_summary.get("diagnostic_stop_reason_counts", {}).get(
        "nonfinite_diagnostic"
    )
    if joint_sources != 65 or transition_count != 65:
        raise VerificationError(
            "联合历史状态必须保持 65 个 Failed->Failed 记录"
        )
    if stop_count != 65 or joint_summary.get("all_source_integrity_preserved") is not True:
        raise VerificationError("联合历史摘要的完整性或 fail-closed 原因不一致")

    checks = algorithm.get("threshold_checks", {})
    required_checks = ("rhat", "bulk_ess", "tail_ess", "relative_mcse")
    if algorithm.get("all_four_thresholds_pass") is not True or not all(
        checks.get(name) is True for name in required_checks
    ):
        raise VerificationError("算法组件的四项登记阈值未全部通过")

    m2_summary = m2.get("summary", {})
    exact = m2_summary.get("exact_match_count")
    total = m2_summary.get("run_count")
    if (
        exact != 42
        or total != 42
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="paper01-rasti 发布包根目录",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="先按当前候选成员重建 release-manifest.json",
    )
    args = parser.parse_args(argv)
    try:
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
        }
    except VerificationError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
