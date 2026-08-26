"""论文 01 发布包重放器的行为测试。"""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


PAPER_RELATIVE = Path("papers") / "paper01-rasti"
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


def _m2_run_ids() -> list[str]:
    run_ids = [
        f"s{scene:02d}__lam-{lam}__da"
        for scene in range(5)
        for lam in ("0", "1", "10", "100", "1000", "10000")
    ]
    run_ids.extend(["s00__lam-1000__am", "s01__lam-1000__am"])
    run_ids.extend(
        run_id
        for scene in range(5)
        for run_id in (
            f"s{scene:02d}__lam-1000__w__da",
            f"s{scene:02d}__lam-1000__w-xifrozen__da",
        )
    )
    return run_ids


def _evidence_root(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    root = repository / PAPER_RELATIVE
    verification = root / "evidence" / "verification-final"
    config_path = repository / "validation" / "wp7" / "synthetic-v6-config.json"
    _write_json(
        config_path,
        {
            "thresholds": {
                "max_rhat": 1.01,
                "min_bulk_ess": 400,
                "min_tail_ess": 400,
                "max_relative_mcse": 0.05,
            }
        },
    )
    _write_json(
        verification / "joint-replay-summary.json",
        {
            "source_count": 65,
            "summary": {
                "all_source_integrity_preserved": True,
                "status_transition_counts": {"Failed->Failed": 65},
                "diagnostic_stop_reason_counts": {"nonfinite_diagnostic": 65},
            },
            "records": [
                {
                    "source_relative_path": f"runs/run-{index:02d}/raw-chains.npz",
                    "source_integrity_preserved": True,
                    "status_transition": {"from": "Failed", "to": "Failed"},
                    "replayed_diagnostics": {
                        "diagnostic_stop_reason": "nonfinite_diagnostic"
                    },
                }
                for index in range(65)
            ],
        },
    )
    _write_json(
        verification / "algorithm-replay.json",
        {
            "all_four_thresholds_pass": True,
            "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "threshold_checks": {
                "rhat": True,
                "bulk_ess": True,
                "tail_ess": True,
                "relative_mcse": True,
            },
            "source_integrity_preserved": True,
            "replayed_diagnostics": {
                "max_rhat": 1.003,
                "min_bulk_ess": 500.0,
                "min_tail_ess": 450.0,
                "max_relative_mcse": 0.02,
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
            },
            "records": [
                {"run_id": run_id, "ledger_row_exact_match": True}
                for run_id in _m2_run_ids()
            ],
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


def test_verify_evidence_rejects_record_drift_hidden_by_joint_summary(tmp_path):
    """捕获逐条记录已漂移、冻结 summary 仍声称 65/65 的辖域错觉。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    path = root / "evidence" / "verification-final" / "joint-replay-summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["status_transition"]["to"] = "Passed"
    _write_json(path, payload)

    with pytest.raises(replay.VerificationError, match="逐条记录|记录层"):
        replay.verify_evidence(root)


def test_verify_evidence_rejects_m2_record_hidden_by_summary(tmp_path):
    """捕获 42/42 summary 未反映单行 lineage 失败的回归。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    path = root / "evidence" / "verification-final" / "m2-reconstruction-lineage.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["ledger_row_exact_match"] = False
    _write_json(path, payload)

    with pytest.raises(replay.VerificationError, match="逐条记录|记录层"):
        replay.verify_evidence(root)


def test_verify_evidence_recomputes_algorithm_thresholds(tmp_path):
    """捕获阈值布尔值为真、实际重放值却越界的回归。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    path = root / "evidence" / "verification-final" / "algorithm-replay.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["replayed_diagnostics"]["max_rhat"] = 1.02
    _write_json(path, payload)

    with pytest.raises(replay.VerificationError, match="阈值|rhat"):
        replay.verify_evidence(root)


def test_verify_manifest_rejects_member_hash_drift(tmp_path):
    """捕获发布成员在清单生成后被改写的回归。"""
    replay = _load_replay_module()
    root = tmp_path / "repository" / PAPER_RELATIVE
    member = root / "manuscript" / "paper.md"
    member.parent.mkdir(parents=True)
    member.write_text("frozen candidate\n", encoding="utf-8")
    digest = hashlib.sha256(member.read_bytes()).hexdigest()
    _write_json(
        root / "release-manifest.json",
        {
            "schema_version": "paper01-release-manifest/1.2",
            "scope": "repository_tag_tree_excluding_declared_self_and_runtime_outputs",
            "excluded_paths": [
                "papers/paper01-rasti/release-manifest.json",
                "papers/paper01-rasti/replay-result.json",
            ],
            "members": [
                {
                    "path": "papers/paper01-rasti/manuscript/paper.md",
                    "bytes": member.stat().st_size,
                    "sha256": digest,
                }
            ],
        },
    )
    assert replay.verify_manifest(root) == 1

    member.write_text("drifted candidate\n", encoding="utf-8")
    with pytest.raises(replay.VerificationError, match="字节数|SHA-256"):
        replay.verify_manifest(root)


def test_verify_manifest_rejects_unlisted_extra_member(tmp_path):
    """捕获 tag 树出现清单未登记成员、外层清单仍全绿的回归。"""
    replay = _load_replay_module()
    root = tmp_path / "repository" / PAPER_RELATIVE
    member = root / "manuscript" / "paper.md"
    member.parent.mkdir(parents=True)
    member.write_text("frozen candidate\n", encoding="utf-8")
    replay.write_manifest(root)
    (root.parents[1] / "unlisted.txt").write_text("not declared\n", encoding="utf-8")

    with pytest.raises(replay.VerificationError, match="未登记|成员集合"):
        replay.verify_manifest(root)


def test_build_manifest_is_sorted_and_excludes_generated_outputs(tmp_path):
    """捕获成员顺序不确定或把自引用/重放输出收入清单的回归。"""
    replay = _load_replay_module()
    root = tmp_path / "repository" / PAPER_RELATIVE
    (root / "z").mkdir(parents=True)
    (root / "z" / "last.txt").write_text("z\n", encoding="utf-8")
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    (root / "release-manifest.json").write_text("stale", encoding="utf-8")
    (root / "replay-result.json").write_text("generated", encoding="utf-8")
    egg_info = root.parents[1] / "src" / "package.egg-info"
    egg_info.mkdir(parents=True)
    (egg_info / "PKG-INFO").write_text("generated metadata\n", encoding="utf-8")

    manifest = replay.build_manifest(root)

    assert manifest["schema_version"] == "paper01-release-manifest/1.2"
    assert manifest["scope"] == "repository_tag_tree_excluding_declared_self_and_runtime_outputs"
    assert manifest["excluded_paths"] == [
        "papers/paper01-rasti/release-manifest.json",
        "papers/paper01-rasti/replay-result.json",
    ]
    assert [row["path"] for row in manifest["members"]] == [
        "papers/paper01-rasti/a.txt",
        "papers/paper01-rasti/z/last.txt",
    ]
    assert [row["bytes"] for row in manifest["members"]] == [
        (root / "a.txt").stat().st_size,
        (root / "z" / "last.txt").stat().st_size,
    ]


def test_verify_revision_bundle_rejects_eol_hash_drift(tmp_path):
    """捕获 CRLF→LF 改写造成的证据束内部哈希断链。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_revision_bundle", None)
    assert validator is not None, "重放器必须遍历 revision evidence bundle 内链"
    root = tmp_path / "repository" / PAPER_RELATIVE
    bundle_root = root / "evidence" / "revision-bundle-r2"
    member = bundle_root / "source.md"
    member.parent.mkdir(parents=True)
    member.write_bytes(b"line one\n")
    crlf_digest = hashlib.sha256(b"line one\r\n").hexdigest()
    _write_json(
        bundle_root / "revision-evidence-bundle-r2.json",
        {
            "schema_version": "revision-evidence-bundle/1.0",
            "chain_start": {
                "draft": {"path": "source.md", "sha256": crlf_digest}
            },
            "rounds": [],
            "final_draft": {"path": "source.md", "sha256": crlf_digest},
        },
    )

    with pytest.raises(replay.VerificationError, match="证据束.*SHA-256|内部.*SHA-256"):
        validator(root)


def test_verify_revision_bundle_rejects_redundant_outer_copy(tmp_path):
    """精选包只保留自包含证据束，避免两个权威副本发生漂移。"""
    replay = _load_replay_module()
    root = tmp_path / "repository" / PAPER_RELATIVE
    bundle_root = root / "evidence" / "revision-bundle-r2"
    member = bundle_root / "source.md"
    member.parent.mkdir(parents=True)
    member.write_bytes(b"line one\n")
    digest = hashlib.sha256(member.read_bytes()).hexdigest()
    bundle = {
        "schema_version": "revision-evidence-bundle/1.0",
        "chain_start": {"draft": {"path": "source.md", "sha256": digest}},
        "rounds": [],
        "final_draft": {"path": "source.md", "sha256": digest},
    }
    _write_json(bundle_root / "revision-evidence-bundle-r2.json", bundle)
    _write_json(root / "evidence" / "revision-evidence-bundle-r2.json", bundle)

    with pytest.raises(replay.VerificationError, match="外层副本|重复"):
        replay.verify_revision_bundle(root)


def test_current_revision_bundle_binds_refreeze_report():
    """当前精选包必须把重冻结原因和结果绑定到自包含证据束。"""
    replay = _load_replay_module()

    result = replay.verify_revision_bundle(REPLAY_PATH.parents[1])

    assert result == {"links_verified": 19, "refreeze_report_verified": 1}


def test_verify_submission_rejects_reference_pipeline_notes(tmp_path):
    """捕获 clean 稿参考文献仍携带内部著录与 LIT 标签的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_submission_hygiene", None)
    assert validator is not None, "重放器必须检查投稿稿件内部注记"
    root = tmp_path / "repository" / PAPER_RELATIVE
    manuscript = root / "manuscript"
    manuscript.mkdir(parents=True)
    (manuscript / "manuscript-clean.md").write_text(
        "## References\n\n> **著录说明**：内部记录。\n\nA. (2026). Title. `[LIT:1 · A]`\n",
        encoding="utf-8",
    )
    (manuscript / "response-to-reviewers-r1.md").write_text(
        "# SIMULATED INTERNAL REVIEW RESPONSE\n", encoding="utf-8"
    )

    with pytest.raises(replay.VerificationError, match="著录说明|LIT|内部注记"):
        validator(root)


def test_render_submission_removes_compact_no_doi_reference_note():
    """覆盖无空格紧贴 LIT 标签的中文无 DOI 著录注记。"""
    replay = _load_replay_module()
    renderer = getattr(replay, "render_submission_text", None)
    assert renderer is not None, "重放器必须公开确定性 clean 渲染函数"
    anchored = (
        "## References\n\n"
        "Tarantola, A., & Valette, B. (1982b). Inverse problems = quest for "
        "information. *Journal of Geophysics, 50*, 159–170. "
        "（无 DOI；OpenAlex: https://openalex.org/W1574224119）"
        "`[LIT:1 · A]`（内部核验说明）\n"
    )

    clean = renderer(anchored)

    assert "[LIT:" not in clean
    assert "无 DOI" not in clean
    assert "OpenAlex" not in clean
    assert clean.endswith("159–170.\n")


def test_write_submission_render_binds_source_output_and_allowed_transformations(tmp_path):
    """clean 稿与报告必须由同一确定性渲染操作共同生成。"""
    replay = _load_replay_module()
    writer = getattr(replay, "write_submission_render", None)
    assert writer is not None, "重放器必须公开 clean 稿原子生成函数"
    root = tmp_path / "repository" / PAPER_RELATIVE
    manuscript = root / "manuscript"
    manuscript.mkdir(parents=True)
    anchored = manuscript / "manuscript-anchored.md"
    anchored.write_text(
        "<!--block:B0001-->\nSupported claim. ⟦EVD-1⟧\n",
        encoding="utf-8",
        newline="\n",
    )

    clean_path, report_path = writer(root)

    assert clean_path.read_text(encoding="utf-8") == "Supported claim.\n"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "ars-clean-manuscript-render/1.1"
    assert report["source"]["sha256"] == hashlib.sha256(anchored.read_bytes()).hexdigest()
    assert report["output"]["sha256"] == hashlib.sha256(clean_path.read_bytes()).hexdigest()
    assert set(report["allowed_transformations"]) == replay.ALLOWED_TRANSFORMATIONS
    assert report["semantic_edits"] == 0


def test_current_release_manuscript_contract_covers_r4_repairs():
    """把 R4 的事实、编号与文风修复纳入发布机器门。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_manuscript_contract", None)
    assert validator is not None, "重放器必须验证 R4 稿件契约"

    result = validator(REPLAY_PATH.parents[1])

    assert result["table_order"] == ["1", "2", "3", "4", "5", "5a"]
    assert result["figure_order"] == ["1", "2", "3", "4", "5"]
    assert result["paragraph_order"] == ["1", "2", "3", "4", "5", "6"]
    assert result["section_6_equations"] == ["6.1", "6.2"]
    assert result["required_repairs_verified"] == 13
    assert result["forbidden_regressions"] == 0
    assert result["patch_record_verified"] == 1
    assert result["style_metrics"] == {
        "em_dash": 101,
        "rather_than": 56,
        "block_leading_bold": 0,
        "travel_with": 0,
        "generalized_bayes": 0,
    }


def test_verify_submission_requires_simulated_review_label(tmp_path):
    """捕获内部模拟 response-to-reviewers 被误呈现为真实期刊往来的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_submission_hygiene", None)
    assert validator is not None, "重放器必须检查模拟评审标识"
    root = tmp_path / "repository" / PAPER_RELATIVE
    manuscript = root / "manuscript"
    manuscript.mkdir(parents=True)
    (manuscript / "manuscript-clean.md").write_text("Clean manuscript.\n", encoding="utf-8")
    (manuscript / "response-to-reviewers-r1.md").write_text(
        "# Response to Reviewers\n", encoding="utf-8"
    )

    with pytest.raises(replay.VerificationError, match="模拟|SIMULATED"):
        validator(root)


def test_verify_submission_render_rejects_semantic_drift_with_updated_hashes(tmp_path):
    """捕获 clean 稿和报告哈希一起改写、但不再是允许渲染结果的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_submission_render", None)
    assert validator is not None, "重放器必须重做 anchored→clean 允许变换"
    root = tmp_path / "repository" / PAPER_RELATIVE
    manuscript = root / "manuscript"
    provenance = root / "provenance"
    manuscript.mkdir(parents=True)
    anchored = manuscript / "manuscript-anchored.md"
    clean = manuscript / "manuscript-clean.md"
    anchored.write_text(
        "<!--block:B0001-->\nSupported claim. ⟦EVD-1⟧\n",
        encoding="utf-8",
    )
    clean.write_text("Different claim.\n", encoding="utf-8")
    _write_json(
        provenance / "clean-render-report.json",
        {
            "schema_version": "ars-clean-manuscript-render/1.1",
            "source": {"sha256": hashlib.sha256(anchored.read_bytes()).hexdigest()},
            "output": {"sha256": hashlib.sha256(clean.read_bytes()).hexdigest()},
            "semantic_edits": 0,
            "allowed_transformations": [
                "block_marker_lines",
                "evidence_note_spans",
                "reference_pipeline_notes",
            ],
        },
    )

    with pytest.raises(replay.VerificationError, match="允许渲染|语义漂移"):
        validator(root)
