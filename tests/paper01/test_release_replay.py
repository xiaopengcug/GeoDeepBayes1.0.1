"""论文 01 发布包重放器的行为测试。"""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


REPLAY_PATH = (
    Path(__file__).resolve().parents[2]
    / "papers"
    / "paper01-rasti"
    / "scripts"
    / "replay_release.py"
)


def _load_replay_module():
    spec = importlib.util.spec_from_file_location("paper01_release_replay", REPLAY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _evidence_root(tmp_path: Path) -> Path:
    root = tmp_path / "paper01-rasti"
    verification = root / "evidence" / "verification-final"
    _write_json(
        verification / "joint-replay-summary.json",
        {
            "source_count": 65,
            "summary": {
                "all_source_integrity_preserved": True,
                "status_transition_counts": {"Failed->Failed": 65},
                "diagnostic_stop_reason_counts": {"nonfinite_diagnostic": 65},
            },
        },
    )
    _write_json(
        verification / "algorithm-replay.json",
        {
            "all_four_thresholds_pass": True,
            "threshold_checks": {
                "rhat": True,
                "bulk_ess": True,
                "tail_ess": True,
                "relative_mcse": True,
            },
        },
    )
    _write_json(
        verification / "m2-reconstruction-lineage.json",
        {
            "summary": {
                "run_count": 42,
                "exact_match_count": 42,
                "unbound_ledger_run_ids": [],
                "all_rows_exact": True,
            }
        },
    )
    return root


def test_verify_evidence_accepts_registered_summary(tmp_path):
    """捕获三个注册结果被遗漏或错误解释的回归。"""
    replay = _load_replay_module()
    result = replay.verify_evidence(_evidence_root(tmp_path))

    assert result == {
        "joint_sources": 65,
        "joint_failed_to_failed": 65,
        "algorithm_checks_passed": 4,
        "m2_exact": 42,
        "m2_total": 42,
    }


def test_verify_evidence_rejects_joint_status_drift(tmp_path):
    """捕获 Failed→Failed 历史状态被静默改写的回归。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    path = root / "evidence" / "verification-final" / "joint-replay-summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"]["status_transition_counts"] = {"Failed->Passed": 65}
    _write_json(path, payload)

    with pytest.raises(replay.VerificationError, match="Failed->Failed"):
        replay.verify_evidence(root)


def test_verify_manifest_rejects_member_hash_drift(tmp_path):
    """捕获发布成员在清单生成后被改写的回归。"""
    replay = _load_replay_module()
    root = tmp_path / "paper01-rasti"
    member = root / "manuscript" / "paper.md"
    member.parent.mkdir(parents=True)
    member.write_text("frozen candidate\n", encoding="utf-8")
    digest = hashlib.sha256(member.read_bytes()).hexdigest()
    _write_json(
        root / "release-manifest.json",
        {
            "schema_version": "paper01-release-manifest/1.0",
            "members": [{"path": "manuscript/paper.md", "sha256": digest}],
        },
    )
    assert replay.verify_manifest(root) == 1

    member.write_text("drifted candidate\n", encoding="utf-8")
    with pytest.raises(replay.VerificationError, match="SHA-256"):
        replay.verify_manifest(root)


def test_build_manifest_is_sorted_and_excludes_generated_outputs(tmp_path):
    """捕获成员顺序不确定或把自引用/重放输出收入清单的回归。"""
    replay = _load_replay_module()
    root = tmp_path / "paper01-rasti"
    (root / "z").mkdir(parents=True)
    (root / "z" / "last.txt").write_text("z\n", encoding="utf-8")
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    (root / "release-manifest.json").write_text("stale", encoding="utf-8")
    (root / "replay-result.json").write_text("generated", encoding="utf-8")

    manifest = replay.build_manifest(root)

    assert [row["path"] for row in manifest["members"]] == ["a.txt", "z/last.txt"]
    assert [row["bytes"] for row in manifest["members"]] == [
        (root / "a.txt").stat().st_size,
        (root / "z" / "last.txt").stat().st_size,
    ]
