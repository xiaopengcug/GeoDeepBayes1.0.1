"""论文 01 正式归档元数据和发布树形状测试。"""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPLAY_PATH = (
    REPOSITORY_ROOT
    / "papers"
    / "paper01-rasti"
    / "scripts"
    / "replay_release.py"
)


def _load_replay_module():
    spec = importlib.util.spec_from_file_location("paper01_release_metadata", REPLAY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_zenodo_metadata_requires_explicit_open_access_and_closed_reuse(tmp_path):
    """捕获 Zenodo 缺省 open/CC-BY 与 Proprietary 声明冲突的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_zenodo_metadata", None)
    assert validator is not None, "重放器必须校验 Zenodo access_right 与 license"
    metadata = tmp_path / ".zenodo.json"
    _write_json(metadata, {"title": "Paper 01", "upload_type": "software"})

    with pytest.raises(replay.VerificationError, match="access_right|license"):
        validator(metadata)


def test_zenodo_metadata_accepts_public_download_without_open_reuse(tmp_path):
    """锁定作者确认的公开下载、非开放复用组合。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_zenodo_metadata", None)
    assert validator is not None, "重放器必须校验 Zenodo access_right 与 license"
    metadata = tmp_path / ".zenodo.json"
    _write_json(
        metadata,
        {
            "title": "Paper 01",
            "upload_type": "software",
            "access_right": "open",
            "license": "other-closed",
        },
    )

    assert validator(metadata) == {
        "access_right": "open",
        "license": "other-closed",
    }


def test_release_shape_rejects_internal_bmad_tree(tmp_path):
    """捕获内部治理工件再次进入 DOI 候选树的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_release_shape", None)
    assert validator is not None, "重放器必须检查精选发布树"
    repository = tmp_path / "repository"
    (repository / "_bmad-output").mkdir(parents=True)

    with pytest.raises(replay.VerificationError, match="_bmad-output"):
        validator(repository)


def test_release_shape_reports_missing_reader_facing_assets(tmp_path):
    """捕获图件、Supplement、注册证据或诊断仪器缺失的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_release_shape", None)
    assert validator is not None, "重放器必须检查精选发布树"
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(replay.VerificationError, match="figure-1-framework-governance"):
        validator(repository)


def test_credential_scan_rejects_named_zenodo_token(tmp_path):
    """捕获发布树中以环境变量或配置键保存的访问令牌。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_no_credentials", None)
    assert validator is not None, "重放器必须执行高置信凭据扫描"
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".env").write_text(
        "ZENODO_" + "ACCESS_TOKEN=" + "abcdefghijklmnopqrstuvwxyz0123456789\n",
        encoding="utf-8",
    )

    with pytest.raises(replay.VerificationError, match="凭据|credential|token"):
        validator(repository)


def test_do27_provenance_binds_mit_source_record_and_derived_attachment(tmp_path):
    """捕获 DO27 数值附件脱离来源记录、MIT 归属或自身哈希的回归。"""
    replay = _load_replay_module()
    validator = getattr(replay, "verify_do27_provenance", None)
    assert validator is not None, "重放器必须校验 DO27 来源与许可边界"
    repository = tmp_path / "repository"
    root = repository / "validation" / "wp7" / "versions" / "do27-v4-20260724"
    root.mkdir(parents=True)
    raw = root / "raw-numerics.npz"
    raw.write_bytes(b"derived numerics")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    _write_json(
        root / "source_record.zenodo.json",
        {
            "doi": "10.5281/zenodo.3633239",
            "metadata": {
                "license": {"id": "other-open"},
                "description": "Licensed under the MIT License.",
            },
        },
    )
    (root / "UPSTREAM-LICENSE-MIT.txt").write_text(
        "MIT License\n\nPermission is hereby granted, free of charge,",
        encoding="utf-8",
    )
    (root / "PROVENANCE.md").write_text(
        f"DOI `10.5281/zenodo.3633239`\nraw SHA-256 `{digest}`\n",
        encoding="utf-8",
    )

    assert validator(repository) == {
        "doi": "10.5281/zenodo.3633239",
        "raw_numerics_sha256": digest,
        "license": "MIT",
    }
