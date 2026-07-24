"""WP6契约、成熟度、历史冻结、worker边界与GC回归测试。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = (
    PROJECT_ROOT
    / "_bmad-output"
    / "planning-artifacts"
    / "research"
    / "贝叶斯思想与重磁电电磁深度融合技术体系"
)
CONTRACTS = RESEARCH_ROOT / "contracts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_module("wp6_contract_validator", CONTRACTS / "validate_contracts.py")
governance = _load_module("wp6_governance", CONTRACTS / "wp6_governance.py")


def test_contract_matrix_and_self_test_pass():
    result = contracts.run_validation(self_test=True)
    assert result["status"] == "passed", result["failures"]
    assert result["methods"] == 9


def test_evidence_run_rejects_time_exit_seed_hash_and_claim_mutations():
    run = contracts.load("examples/valid-evidence-run-v2.json")
    assert contracts.evidence_semantic_errors(run) == []

    mutations = []
    broken = deepcopy(run)
    broken["execution"]["ended_at"] = "2026-07-23T23:59:59Z"
    mutations.append(broken)
    broken = deepcopy(run)
    broken["execution"]["exit_code"] = 3
    mutations.append(broken)
    broken = deepcopy(run)
    broken["randomness"]["seeds"] = []
    mutations.append(broken)
    broken = deepcopy(run)
    broken["code"]["sha256"] = "0" * 64
    mutations.append(broken)
    broken = deepcopy(run)
    broken["claims"][0].update(scope="field", max_maturity="Unit-verified")
    mutations.append(broken)
    for item in mutations:
        assert contracts.evidence_semantic_errors(item)


def test_placeholder_cannot_upgrade_to_implemented():
    capabilities = contracts.load("operator-capabilities.json")
    placeholder = deepcopy(next(item for item in capabilities if item["method"] == "dc"))
    placeholder["maturity"] = "Implemented"
    assert contracts.capability_semantic_errors(placeholder)


def test_legacy_index_is_hash_frozen():
    index = RESEARCH_ROOT / "validation" / "wp6-governance" / "legacy-index.json"
    assert governance.validate_legacy_index(RESEARCH_ROOT, index) == []


def test_worker_boundary_requires_distinct_identity_and_direct_stage(tmp_path):
    versions = tmp_path / "versions"
    versions.mkdir()
    stage = versions / (".stage-" + "a" * 32)
    stage.mkdir()
    governance.validate_worker_boundary(versions, stage, "worker", "supervisor")
    with pytest.raises(ValueError, match="不同身份"):
        governance.validate_worker_boundary(versions, stage, "same", "same")
    outside = tmp_path / (".stage-" + "b" * 32)
    outside.mkdir()
    with pytest.raises(ValueError, match="直属子目录"):
        governance.validate_worker_boundary(versions, outside, "worker", "supervisor")


def test_worker_boundary_rejects_symlink_when_supported(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows无开发者模式时创建符号链接不稳定，ACL集成脚本覆盖该平台")
    versions = tmp_path / "versions"
    versions.mkdir()
    target = versions / (".stage-" + "c" * 32)
    target.mkdir()
    link = versions / (".stage-" + "d" * 32)
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="符号链接"):
        governance.validate_worker_boundary(versions, link, "worker", "supervisor")


def test_gc_protects_referenced_versions_and_reports_old_or_quota(tmp_path):
    versions = tmp_path / "versions"
    versions.mkdir()
    protected = "20260701T000000000Z-" + "a" * 32
    orphan = "20260701T000000001Z-" + "b" * 32
    for name in (protected, orphan):
        directory = versions / name
        directory.mkdir()
        (directory / "artifact.bin").write_bytes(b"x" * 20)
        old = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()
        os.utime(directory, (old, old))
    report = governance.gc_report(
        versions,
        [protected],
        retention_days=30,
        quota_bytes=1,
        now=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    names = [item["path"] for item in report["candidates"]]
    assert protected not in names
    assert names == [orphan]


def test_gc_quota_stops_after_enough_space_is_reclaimed(tmp_path):
    versions = tmp_path / "versions"
    versions.mkdir()
    names = [
        f"20260701T00000000{i}Z-" + character * 32
        for i, character in enumerate(("a", "b", "c"))
    ]
    for index, name in enumerate(names):
        directory = versions / name
        directory.mkdir()
        (directory / "artifact.bin").write_bytes(b"x" * 10)
        modified = datetime(2026, 7, 20 + index, tzinfo=timezone.utc).timestamp()
        os.utime(directory, (modified, modified))
    report = governance.gc_report(
        versions,
        [],
        retention_days=30,
        quota_bytes=20,
        now=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    assert [item["path"] for item in report["candidates"]] == [names[0]]


def test_legacy_index_and_evidence_root_reject_path_escape(tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    index = research / "legacy-index.json"
    index.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": "../outside.txt",
                        "bytes": outside.stat().st_size,
                        "sha256": governance.file_sha256(outside),
                        "migration_state": "Legacy-frozen",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert any(
        "路径越界" in error
        for error in governance.validate_legacy_index(research, index)
    )
    with pytest.raises(ValueError, match="受控根目录"):
        governance.build_evidence_root(
            research, ["../outside.txt"], commit_sha="a" * 40
        )


def test_evidence_root_detects_content_change(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("v1", encoding="utf-8")
    first = governance.build_evidence_root(tmp_path, ["artifact.txt"], commit_sha="a" * 40)
    artifact.write_text("v2", encoding="utf-8")
    second = governance.build_evidence_root(tmp_path, ["artifact.txt"], commit_sha="a" * 40)
    assert first["root_sha256"] != second["root_sha256"]
