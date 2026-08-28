"""论文 01 发布包重放器的行为测试。"""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


PAPER_RELATIVE = Path("papers") / "paper01-rasti"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPLAY_PATH = (
    REPOSITORY_ROOT
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


def _load_path_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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
    contract_path = repository / "validation" / "wp2-toy" / "diagnostic-contract.json"
    thresholds = {
        "max_rhat": 1.01,
        "min_bulk_ess": 400,
        "min_tail_ess": 400,
        "max_relative_mcse": 0.05,
        "min_mode_visits_per_chain": None,
        "max_failed_replicate_rate": None,
    }
    _write_json(
        config_path,
        {"thresholds": thresholds},
    )
    _write_json(
        contract_path,
        {
            "thresholds": {
                "rank_normalized_split_rhat_max": 1.01,
                "bulk_ess_min": 400,
                "tail_ess_min": 400,
                "relative_mcse_max": 0.05,
                "required_mode_visits_per_chain": None,
                "failed_replicate_rate_max": None,
            }
        },
    )
    code_paths = {
        "rhat.py": repository / "src" / "geodeepbayes" / "diagnostics" / "rhat.py",
        "ess.py": repository / "src" / "geodeepbayes" / "diagnostics" / "ess.py",
        "mcse.py": repository / "src" / "geodeepbayes" / "diagnostics" / "mcse.py",
        "joint_block.py": repository / "src" / "geodeepbayes" / "benchmarks" / "joint_block.py",
        "diagnostic-contract.json": contract_path,
    }
    for name, path in code_paths.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture {name}\n", encoding="utf-8")
    code_hashes = {
        name: hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name, path in code_paths.items()
    }
    algorithm_source = (
        repository / "validation" / "wp7" / "versions" / "synthetic-block-v6-20260724"
    )
    raw_path = algorithm_source / "raw-chains.npz"
    metrics_path = algorithm_source / "metrics.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"fixture raw chains")
    metrics_path.write_bytes(b'{"status":"Synthetic-run"}\n')
    algorithm_source_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (raw_path, metrics_path)
    }
    _write_json(
        verification / "joint-replay-summary.json",
        {
            "source_label": "historical/evd-joint-001-v1-20260819",
            "source_count": 65,
            "code_and_contract_sha256": code_hashes,
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
                        "diagnostic_stop_reason": "nonfinite_diagnostic",
                        "degenerate_channel_count": (
                            1 if index < 57 else 2 if index < 60 else 6
                        ),
                    },
                }
                for index in range(65)
            ],
        },
    )
    _write_json(
        verification / "algorithm-replay.json",
        {
            "source_label": "validation/wp7/versions/synthetic-block-v6-20260724",
            "all_four_thresholds_pass": True,
            "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "code_sha256": {
                name: code_hashes[name] for name in ("rhat.py", "ess.py", "mcse.py")
            },
            "source_sha256_before": algorithm_source_hashes,
            "source_sha256_after": algorithm_source_hashes,
            "threshold_checks": {
                "rhat": True,
                "bulk_ess": True,
                "tail_ess": True,
                "relative_mcse": True,
            },
            "source_integrity_preserved": True,
            "manuscript_conservative_values": {
                "max_rhat_ceiling_5dp": 1.00374,
                "min_bulk_ess_floor_integer": 2496,
                "min_tail_ess_floor_integer": 1963,
                "max_relative_mcse_ceiling_4dp": 0.0202,
            },
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
            "pilot_label": "historical/evd-joint-001-v1-20260819/pilot",
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


def _write_release_figure_inventory(repository: Path) -> None:
    figures = repository / PAPER_RELATIVE / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    for number, stem in {
        1: "framework-governance",
        2: "probabilistic-dag",
        3: "multiscale-parameterisation",
        4: "evd-joint-scene",
        5: "algo-diagnostics",
    }.items():
        for suffix in (".py", ".pdf", ".png"):
            (figures / f"figure-{number}-{stem}{suffix}").write_bytes(b"asset\n")


def test_figure_inventory_rejects_unreferenced_c1_family(tmp_path):
    """捕获 Figures 1–5 之外的图族逃逸精确清单门。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_figure_inventory", None)
    assert validator is not None, "重放器必须验证 Figures 1–5 的精确 py/pdf/png 集合"
    repository = tmp_path / "repository"
    _write_release_figure_inventory(repository)
    assert validator(repository) == {"figure_families": 5, "figure_members": 15}

    extra = repository / PAPER_RELATIVE / "figures" / "figure-c1-prisma-flow.py"
    extra.write_text("print('withdrawn')\n", encoding="utf-8")
    with pytest.raises(replay.VerificationError, match="Figure|图件|额外|C1"):
        validator(repository)


def test_verify_evidence_rejects_stale_joint_code_hash(tmp_path):
    """捕获联合重放摘要仍绑定旧诊断实现的回归。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    joint_path = root / "evidence" / "verification-final" / "joint-replay-summary.json"
    joint = json.loads(joint_path.read_text(encoding="utf-8"))
    assert set(joint["code_and_contract_sha256"]) == {
        "rhat.py", "ess.py", "mcse.py", "joint_block.py", "diagnostic-contract.json"
    }
    joint["code_and_contract_sha256"]["ess.py"] = "0" * 64
    _write_json(joint_path, joint)

    with pytest.raises(replay.VerificationError, match="代码|ess.py|SHA-256"):
        replay.verify_evidence(root)


def test_verify_evidence_rejects_stale_algorithm_code_hash(tmp_path):
    """捕获算法摘要保留完整代码键集、但单个诊断源码摘要陈旧。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    algorithm_path = root / "evidence" / "verification-final" / "algorithm-replay.json"
    algorithm = json.loads(algorithm_path.read_text(encoding="utf-8"))
    assert set(algorithm["code_sha256"]) == {"rhat.py", "ess.py", "mcse.py"}
    algorithm["code_sha256"]["rhat.py"] = "0" * 64
    _write_json(algorithm_path, algorithm)

    with pytest.raises(replay.VerificationError, match="算法重放.*rhat.py|代码 SHA-256"):
        replay.verify_evidence(root)


def test_verify_evidence_rejects_stale_algorithm_source_hash(tmp_path):
    """捕获算法重放记录的 raw/metrics 当前字节绑定漂移。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    repository = root.parents[1]
    source_root = repository / "validation" / "wp7" / "versions" / "synthetic-block-v6-20260724"
    raw = source_root / "raw-chains.npz"
    metrics = source_root / "metrics.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"raw")
    metrics.write_bytes(b'{"status":"ok"}\n')
    algorithm_path = root / "evidence" / "verification-final" / "algorithm-replay.json"
    algorithm = json.loads(algorithm_path.read_text(encoding="utf-8"))
    algorithm["source_label"] = "validation/wp7/versions/synthetic-block-v6-20260724"
    algorithm["source_sha256_before"] = {
        "raw-chains.npz": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "metrics.json": "0" * 64,
    }
    algorithm["source_sha256_after"] = dict(algorithm["source_sha256_before"])
    _write_json(algorithm_path, algorithm)

    with pytest.raises(replay.VerificationError, match="metrics.json|源.*SHA-256|字节"):
        replay.verify_evidence(root)


def test_verify_evidence_rejects_absolute_source_roots(tmp_path):
    """捕获新重放工件泄漏本机盘符绝对路径。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    joint_path = root / "evidence" / "verification-final" / "joint-replay-summary.json"
    joint = json.loads(joint_path.read_text(encoding="utf-8"))
    joint["source_root"] = "H:/private/historical-chains"
    _write_json(joint_path, joint)

    with pytest.raises(replay.VerificationError, match="绝对|source_root|盘符"):
        replay.verify_evidence(root)


def test_render_submission_rejects_unpaired_evidence_note_marker():
    """捕获未闭合证据注记吞掉后续正文的回归。"""
    replay = _load_replay_module()

    with pytest.raises(replay.VerificationError, match="注记|配对|闭合"):
        replay.render_submission_text("Visible claim. ⟦unclosed\nNext claim.\n")


def test_validation_compatibility_rejects_unclassified_resolvable_mismatch(tmp_path):
    """捕获可解析历史 path/hash 漂移未进入兼容侧车的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_validation_link_compatibility", None)
    assert validator is not None, "重放器必须校验 validation 历史链接兼容侧车"
    repository = tmp_path / "repository"
    current = repository / "src" / "geodeepbayes" / "diagnostics" / "ess.py"
    current.parent.mkdir(parents=True)
    current.write_text("current\n", encoding="utf-8")
    record = repository / "validation" / "wp7" / "record.json"
    _write_json(
        record,
        {"code": {"path": "src/geodeepbayes/diagnostics/ess.py", "sha256": "0" * 64}},
    )
    _write_json(
        repository / PAPER_RELATIVE / "provenance" / "validation-link-compatibility.json",
        {
            "schema_version": "paper01-validation-link-compatibility/1.0",
            "entries": [],
        },
    )

    with pytest.raises(replay.VerificationError, match="兼容|未分类|历史链接"):
        validator(repository)


@pytest.mark.parametrize(
    ("document", "key"),
    (
        ("config", "min_mode_visits_per_chain"),
        ("contract", "required_mode_visits_per_chain"),
    ),
)
def test_threshold_contract_rejects_missing_mapped_key(tmp_path, document, key):
    """捕获映射两侧缺键被误当成显式 None 等值。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    repository = root.parents[1]
    path = (
        repository / "validation" / "wp7" / "synthetic-v6-config.json"
        if document == "config"
        else repository / "validation" / "wp2-toy" / "diagnostic-contract.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["thresholds"][key]
    _write_json(path, payload)

    with pytest.raises(replay.VerificationError, match="缺少|缺失|键"):
        replay.verify_threshold_contract(repository)


def test_collect_hash_references_supports_files_sha256_map():
    """捕获 files_sha256 路径→摘要映射被历史链接扫描遗漏。"""
    replay = _load_replay_module()
    digest = "a" * 64

    assert replay._collect_hash_references(
        {"files_sha256": {"src/geodeepbayes/diagnostics/ess.py": digest}}
    ) == [
        (
            '$.files_sha256["src/geodeepbayes/diagnostics/ess.py"]',
            "src/geodeepbayes/diagnostics/ess.py",
            digest,
        )
    ]


def _valid_compatibility_repository(tmp_path: Path, replay) -> Path:
    repository = tmp_path / "repository"
    current = repository / "src" / "example.py"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"VALUE = 1\n")
    _write_json(
        repository / "validation" / "record.json",
        {
            "member": {
                "path": "src/example.py",
                "sha256": hashlib.sha256(current.read_bytes()).hexdigest(),
            }
        },
    )
    replay.write_validation_link_compatibility(repository)
    return repository


@pytest.mark.parametrize("mutation", ("delete", "tamper"))
def test_validation_compatibility_rejects_sidecar_entry_drift(tmp_path, mutation):
    """有效侧车删除或篡改单条后，完整重算比较必须失败。"""
    replay = _load_replay_module()
    repository = _valid_compatibility_repository(tmp_path, replay)
    sidecar_path = (
        repository / PAPER_RELATIVE / "provenance" / "validation-link-compatibility.json"
    )
    assert replay.verify_validation_link_compatibility(repository) == {
        "resolvable_links": 1,
        "unclassified_mismatches": 0,
    }
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if mutation == "delete":
        sidecar["entries"].pop()
    else:
        sidecar["entries"][0]["current_sha256"] = "0" * 64
    _write_json(sidecar_path, sidecar)

    with pytest.raises(replay.VerificationError, match="兼容侧车|历史链接"):
        replay.verify_validation_link_compatibility(repository)


def test_code_evolution_allowlist_binds_approved_current_sha256(tmp_path):
    """历史摘要获准不代表未来任意当前字节都可继续放行。"""
    replay = _load_replay_module()
    repository = tmp_path / "repository"
    current = repository / "src" / "geodeepbayes" / "diagnostics" / "ess.py"
    current.parent.mkdir(parents=True)
    shutil.copy2(REPOSITORY_ROOT / current.relative_to(repository), current)
    _write_json(
        repository / "validation" / "record.json",
        {
            "code": {
                "path": "src/geodeepbayes/diagnostics/ess.py",
                "sha256": "9d7669ed361ee0aa09faeba18f77940516d7fe3812a78885752b610eb28bb683",
            }
        },
    )
    payload = replay.build_validation_link_compatibility(repository)
    assert payload["entries"][0]["classification"] == "historical_code_evolution"

    current.write_text(current.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    with pytest.raises(replay.VerificationError, match="未分类失配|current"):
        replay.build_validation_link_compatibility(repository)


def test_environment_evolution_allowlist_binds_authorized_uv_lock_transition(tmp_path):
    """仅放行作者明确授权的 pypdf 发布验收锁文件演进。"""
    replay = _load_replay_module()
    repository = tmp_path / "repository"
    current = repository / "uv.lock"
    current.parent.mkdir(parents=True)
    shutil.copy2(REPOSITORY_ROOT / "uv.lock", current)
    _write_json(
        repository / "validation" / "record.json",
        {
            "provenance_bindings": {
                "files_sha256": {
                    "uv.lock": "c71791cc6cda23ea4ba563821a4235261374e5268d8cfd9a595799c552834026"
                }
            }
        },
    )

    payload = replay.build_validation_link_compatibility(repository)

    assert payload["entries"][0]["classification"] == "historical_environment_evolution"
    assert payload["entries"][0]["current_sha256"] == (
        "819f311f710d9e9265858c4dd004060333b6360313598cf3e5b7a57ff05b7c6f"
    )
    assert "pypdf 6.16.2" in payload["entries"][0]["classification_reason"]

    current.write_text(current.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    with pytest.raises(replay.VerificationError, match="未分类失配|current"):
        replay.build_validation_link_compatibility(repository)


def test_verify_evidence_rejects_joint_degenerate_distribution_drift(tmp_path):
    """捕获 57+3+5 退化通道分布发生单条漂移。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    joint_path = root / "evidence" / "verification-final" / "joint-replay-summary.json"
    joint = json.loads(joint_path.read_text(encoding="utf-8"))
    joint["records"][0]["replayed_diagnostics"]["degenerate_channel_count"] = 2
    _write_json(joint_path, joint)

    with pytest.raises(replay.VerificationError, match=r"57\+3\+5|退化通道"):
        replay.verify_evidence(root)


def test_verify_evidence_rejects_conservative_value_drift(tmp_path):
    """捕获算法四个保守报告值中任一值漂移。"""
    replay = _load_replay_module()
    root = _evidence_root(tmp_path)
    path = root / "evidence" / "verification-final" / "algorithm-replay.json"
    algorithm = json.loads(path.read_text(encoding="utf-8"))
    algorithm["manuscript_conservative_values"]["min_tail_ess_floor_integer"] = 1964
    _write_json(path, algorithm)

    with pytest.raises(replay.VerificationError, match="保守报告值|漂移"):
        replay.verify_evidence(root)


def _copy_manuscript_contract_fixture(tmp_path: Path) -> Path:
    source_root = REPLAY_PATH.parents[1]
    root = tmp_path / "repository" / PAPER_RELATIVE
    for relative in (
        Path("manuscript/manuscript-anchored.md"),
        Path("manuscript/manuscript-clean.md"),
        Path("provenance/release-manuscript-patch-r4-application.json"),
        Path("provenance/release-r5-patch-application.json"),
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, target)
    return root


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("after_manuscript_sha256", "0" * 64),
        ("after_clean_sha256", "0" * 64),
        ("historical_records_byte_preserved", False),
        ("formal_release_locked", False),
        ("requires_new_candidate_manual_review", False),
    ),
)
def test_manuscript_contract_rejects_r5_record_drift(tmp_path, field, bad_value):
    """R5 after-hash 与三项人工发布锁均必须逐项失败关闭。"""
    replay = _load_replay_module()
    root = _copy_manuscript_contract_fixture(tmp_path)
    path = root / "provenance" / "release-r5-patch-application.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record[field] = bad_value
    _write_json(path, record)

    with pytest.raises(replay.VerificationError, match="R5.*发布锁|R5.*不一致"):
        replay.verify_manuscript_contract(root)


def test_figure2_rejects_each_missing_registered_parent_edge():
    """捕获 Figure 2 漏画 Eq. (3.1)/Table 1 任一注册父边。"""
    path = REPLAY_PATH.parents[1] / "figures" / "figure-2-probabilistic-dag.py"
    figure = _load_path_module(path, "paper01_figure2")
    required = frozenset(
        {
            ("theta", "c"), ("theta", "z"), ("theta", "m"),
            ("theta", "xi"), ("theta", "lambda"), ("theta", "delta"),
            ("theta", "delta_surr"), ("c", "z"), ("c", "m"),
            ("c", "xi"), ("c", "delta"), ("c", "delta_surr"),
            ("c", "f_k"), ("z", "m"), ("z", "delta_surr"),
            ("z", "f_k"), ("m", "delta_surr"), ("m", "f_k"),
            ("xi", "delta_surr"), ("xi", "f_k"), ("lambda", "f_k"),
            ("delta", "f_k"), ("delta_surr", "f_k"),
            ("theta", "f_k"), ("f_k", "d_k"),
        }
    )
    figure.validate_graph_spec(edges=required)
    for edge in required:
        with pytest.raises(figure.RenderError, match="边集合|拓扑"):
            figure.validate_graph_spec(edges=required - {edge})


def test_figure4_station_grid_is_exactly_six_by_six():
    """捕获名义 36 站场景被缩成 6×3 示意网。"""
    path = REPLAY_PATH.parents[1] / "figures" / "figure-4-evd-joint-scene.py"
    figure = _load_path_module(path, "paper01_figure4")
    validator = getattr(figure, "validate_station_grid", None)
    assert validator is not None, "Figure 4 必须公开名义站网失败关闭校验"
    assert validator(figure.STATION_GRID) == {"x_count": 6, "y_count": 6, "stations": 36}
    with pytest.raises(figure.Figure4Error, match="36|6 × 6|站"):
        validator(figure.STATION_GRID[:-1])


def test_figure5_resolves_only_distributed_release_sources():
    """捕获 Figure 5 再次解析到包外治理档案或旧诊断源码。"""
    path = REPLAY_PATH.parents[1] / "figures" / "figure-5-algo-diagnostics.py"
    figure = _load_path_module(path, "paper01_figure5")
    paths = figure.locate_paths()

    assert paths["repository_root"] == REPOSITORY_ROOT
    assert paths["npz"].is_relative_to(REPOSITORY_ROOT / "validation" / "wp7")
    assert paths["contract"].is_relative_to(REPOSITORY_ROOT / "validation" / "wp2-toy")
    assert paths["diagnostics"] == REPOSITORY_ROOT / "src" / "geodeepbayes" / "diagnostics"
    figure.check_diagnostic_source_hashes(paths["diagnostics"])


def test_figure5_accepts_code_evolution_only_when_conservative_values_hold(tmp_path):
    """捕获把允许的逐位演进误当漂移，或放过保守报告值漂移。"""
    import numpy as np

    path = REPLAY_PATH.parents[1] / "figures" / "figure-5-algo-diagnostics.py"
    figure = _load_path_module(path, "paper01_figure5_values")
    metrics = tmp_path / "metrics.json"
    _write_json(
        metrics,
        {
            "max_rhat": 1.003739821507544,
            "min_bulk_ess": 2496.461999015852,
            "min_tail_ess": 1963.6080886746252,
            "max_relative_mcse": 0.020122173198390787,
        },
    )
    arrays = {
        "rhat": np.array([1.0037388341264455]),
        "bulk_ess": np.array([2496.5476048670203]),
        "tail_ess": np.array([1963.6080886746252]),
        "relative_mcse": np.array([0.020122173198390787]),
    }
    assert figure.load_metrics_and_check_extrema(np, metrics, arrays)["max_rhat"] == 1.003739821507544

    arrays["tail_ess"] = np.array([1962.9])
    with pytest.raises(figure.ReproductionError, match="保守报告值|tail_ess"):
        figure.load_metrics_and_check_extrema(np, metrics, arrays)
