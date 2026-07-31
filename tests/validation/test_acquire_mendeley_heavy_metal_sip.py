from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "validation"
    / "wp8"
    / "acquire_mendeley_heavy_metal_sip.py"
)
SPEC = importlib.util.spec_from_file_location("acquire_mendeley_heavy_metal_sip", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
sys.path.insert(0, str(MODULE_PATH.parent))
AUDIT_PATH = MODULE_PATH.parent / "audit_mendeley_heavy_metal_sip_training.py"
AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_mendeley_heavy_metal_sip_training", AUDIT_PATH
)
assert AUDIT_SPEC and AUDIT_SPEC.loader
audit_module = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(audit_module)


def make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)


def test_audit_archive_hashes_every_member_without_extracting(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    members = {"survey/header.txt": b"AB=5 m\nM0-M8\n", "survey/raw.bin": b"\x00\x01\x02"}
    make_zip(archive, members)

    result = module.audit_archive(archive)

    assert result["member_count"] == 2
    assert result["expanded_bytes"] == sum(map(len, members.values()))
    indexed = {item["path"]: item for item in result["members"]}
    assert indexed["survey/header.txt"]["sha256"] == hashlib.sha256(members["survey/header.txt"]).hexdigest()
    assert indexed["survey/raw.bin"]["sha256"] == hashlib.sha256(members["survey/raw.bin"]).hexdigest()
    assert not (tmp_path / "survey").exists()


@pytest.mark.parametrize("name", ["../escape.txt", "/absolute.txt", "C:/drive.txt"])
def test_audit_archive_rejects_unsafe_member_paths(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "unsafe.zip"
    make_zip(archive, {name: b"payload"})

    with pytest.raises(RuntimeError, match="unsafe ZIP member path"):
        module.audit_archive(archive)


def test_audit_archive_rejects_duplicate_member_paths(tmp_path: Path) -> None:
    archive = tmp_path / "duplicate.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("same.dat", b"a")
            package.writestr("same.dat", b"b")
    with pytest.raises(RuntimeError, match="duplicate ZIP member"):
        module.audit_archive(archive)


def test_download_verified_is_atomic_and_rejects_bad_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "archive.zip"
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"bad"))

    with pytest.raises(RuntimeError, match="does not match"):
        module.download_verified("https://example.invalid/file", target, 4, "0" * 64)

    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))


def test_resolve_source_requires_one_consistent_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = tmp_path / "source.json"
    inventory.write_text(
        json.dumps(
            [
                {
                    "filename": module.ARCHIVE_NAME,
                    "id": "file-id",
                    "size": 3,
                    "content_details": {
                        "id": "content-id",
                        "download_url": "https://example.invalid/file",
                        "sha256_hash": hashlib.sha256(b"abc").hexdigest(),
                        "size": 3,
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "INVENTORY_SHA256", module.sha256_file(inventory))
    monkeypatch.setattr(module, "PROVIDER_FILE_ID", "file-id")
    monkeypatch.setattr(module, "PROVIDER_CONTENT_ID", "content-id")
    monkeypatch.setattr(module, "PROVIDER_SIZE", 3)
    monkeypatch.setattr(module, "PROVIDER_SHA256", hashlib.sha256(b"abc").hexdigest())
    assert module.resolve_source(inventory)["id"] == "file-id"


def test_contract_audit_preserves_training_boundary_and_cluster_unit(tmp_path: Path) -> None:
    archive = tmp_path / module.ARCHIVE_NAME
    members = {
        "site/acquisition-1/0.0156250Hz/channel-set/channel0.dat": b"\0" * 8,
        "site/acquisition-1/0.0156250Hz/channel-set/channel1.dat": b"\0" * 8,
        "site/acquisition-1/metadata.xls": "频率/Hz\t采样率\n0.015625\t25000\n".encode(
            "gb18030"
        ),
    }
    make_zip(archive, members)
    audited = module.audit_archive(archive)
    manifest = {
        "schema_version": module.MANIFEST_SCHEMA,
        "scope": "permanently-training-only",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "doi": module.DOI,
        "license": {"spdx": module.LICENSE},
        "archive": {
            "bytes": archive.stat().st_size,
            "sha256": module.sha256_file(archive),
        },
        "audit": audited,
        "retrieval_provenance": {
            "schema_version": "wp8-retrieval-provenance-v1",
            "status": "downloaded_verified",
            "retrieved_at_utc": "2026-07-26T00:00:00+00:00",
            "transport": "https",
            "verification": "provider-size-and-sha256",
        },
    }
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = audit_module.build_contract_audit(tmp_path, require_real_contract=False)

    assert result["structure_audit_passed"] is True
    assert result["acquisition_group_count"] == 1
    assert result["dat_member_count"] == 2
    assert result["independent_cluster_upper_bound"] == "not_assessed"
    assert result["sealed_test_accessed"] == "not_assessed"
    assert result["formal_field_gate_passes"] is False
    assert result["field_validation_eligible"] is False
    assert result["archive_contract_integrity_passed"] is True
    assert result["metadata_tables"][0]["nonempty_row_count"] == 2
    assert result["metadata_tables"][0]["maximum_tab_column_count"] == 2
    assert result["metadata_tables"][0]["content_sha256"] == hashlib.sha256(
        members["site/acquisition-1/metadata.xls"]
    ).hexdigest()


@pytest.mark.parametrize(
    ("field_value", "sealed_value", "expected"),
    [(True, False, "field_validation_eligible"), (False, True, "sealed_test_boundary")],
)
def test_contract_audit_rejects_boundary_conflicts(
    tmp_path: Path, field_value: bool, sealed_value: bool, expected: str
) -> None:
    archive = tmp_path / module.ARCHIVE_NAME
    make_zip(archive, {})
    manifest = {
        "schema_version": module.MANIFEST_SCHEMA,
        "scope": "permanently-training-only",
        "field_validation_eligible": field_value,
        "sealed_test_accessed": sealed_value,
        "doi": module.DOI,
        "license": {"spdx": module.LICENSE},
        "archive": {"bytes": archive.stat().st_size, "sha256": module.sha256_file(archive)},
        "audit": module.audit_archive(archive),
        "retrieval_provenance": {
            "schema_version": "wp8-retrieval-provenance-v1",
            "status": "downloaded_verified",
            "retrieved_at_utc": "2026-07-26T00:00:00+00:00",
            "transport": "https",
            "verification": "provider-size-and-sha256",
        },
    }
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = audit_module.build_contract_audit(tmp_path, require_real_contract=False)
    assert expected in result["errors"]
    assert result["archive_contract_integrity_passed"] is False


def test_contract_audit_rejects_manifest_audit_drift(tmp_path: Path) -> None:
    archive = tmp_path / module.ARCHIVE_NAME
    make_zip(archive, {"site/a/1Hz/set/c0.dat": b"1234"})
    audited = module.audit_archive(archive)
    audited["member_count"] = 84
    manifest = {
        "schema_version": module.MANIFEST_SCHEMA,
        "scope": "permanently-training-only",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "doi": module.DOI,
        "license": {"spdx": module.LICENSE},
        "archive": {"bytes": archive.stat().st_size, "sha256": module.sha256_file(archive)},
        "audit": audited,
        "retrieval_provenance": {
            "schema_version": "wp8-retrieval-provenance-v1",
            "status": "downloaded_verified",
            "retrieved_at_utc": "2026-07-26T00:00:00+00:00",
            "transport": "https",
            "verification": "provider-size-and-sha256",
        },
    }
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = audit_module.build_contract_audit(tmp_path, require_real_contract=False)
    assert "archive_audit_drift" in result["errors"]


def test_real_contract_rejects_empty_package_and_schema_drift(tmp_path: Path) -> None:
    archive = tmp_path / module.ARCHIVE_NAME
    make_zip(archive, {})
    manifest = {
        "schema_version": "drifted",
        "scope": "permanently-training-only",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "doi": module.DOI,
        "license": {"spdx": module.LICENSE},
        "source_inventory": {},
        "archive": {"bytes": archive.stat().st_size, "sha256": module.sha256_file(archive)},
        "audit": module.audit_archive(archive),
        "retrieval_provenance": {},
    }
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = audit_module.build_contract_audit(tmp_path)
    assert {"manifest_schema", "provider_anchor", "real_structure_contract"} <= set(
        result["errors"]
    )
    assert result["archive_contract_integrity_passed"] is False


def test_provider_inventory_hash_drift_is_rejected(tmp_path: Path) -> None:
    inventory = tmp_path / "source.json"
    inventory.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="inventory anchor drift"):
        module.resolve_source(inventory)


def test_immutable_contract_result_preserves_bytes_and_rejects_drift(
    tmp_path: Path
) -> None:
    output = tmp_path / "contract-audit.json"
    value = {
        "schema_version": "v1",
        "audit_mode": "real-provider-contract",
        "sealed_test_accessed": False,
        "structure_audit_passed": True,
    }
    audit_module.write_immutable_result(output, value)
    original = output.read_bytes()
    audit_module.write_immutable_result(output, value)
    assert output.read_bytes() == original
    with pytest.raises(RuntimeError, match="immutable"):
        audit_module.write_immutable_result(
            output, {**value, "structure_audit_passed": False}
        )
    assert output.read_bytes() == original


def test_immutable_raw_manifest_preserves_bytes_and_rejects_drift(
    tmp_path: Path
) -> None:
    output = tmp_path / "raw-manifest.json"
    value = {"schema_version": "v2", "scope": "permanently-training-only"}
    module.write_immutable_manifest(output, value)
    original = output.read_bytes()
    module.write_immutable_manifest(output, value)
    assert output.read_bytes() == original
    with pytest.raises(RuntimeError, match="immutable"):
        module.write_immutable_manifest(output, {**value, "scope": "field"})
    assert output.read_bytes() == original


def test_frozen_real_contract_has_exact_three_by_three_by_nine_mapping() -> None:
    data = module.DATA
    manifest = json.loads((data / "raw-manifest.json").read_text(encoding="utf-8"))
    contract = json.loads((data / "contract-audit.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == module.MANIFEST_SCHEMA
    assert manifest["source_inventory"]["sha256"] == module.INVENTORY_SHA256
    assert manifest["source_inventory"]["mendeley_file_id"] == module.PROVIDER_FILE_ID
    assert manifest["source_inventory"]["content_id"] == module.PROVIDER_CONTENT_ID
    assert manifest["archive"]["bytes"] == module.PROVIDER_SIZE
    assert manifest["archive"]["sha256"] == module.PROVIDER_SHA256
    assert manifest["audit"]["member_count"] == 84
    assert manifest["audit"]["extensions"] == {".dat": 81, ".xls": 3}
    assert contract["archive_contract_integrity_passed"] is True
    assert contract["acquisition_group_count"] == 3
    assert all(
        item["frequency_count"] == 3 and item["channel_count"] == 9
        for item in contract["acquisitions"].values()
    )
    assert contract["formal_status"] == "blocked"
    assert contract["formal_field_gate_passes"] is False
    assert contract["site_identity_evidence"]["provider_declared_site_count"] == 1
    assert len(contract["site_identity_evidence"]["top_level_names"]) == 1


def test_build_manifest_hard_codes_permanent_training_boundaries(tmp_path: Path) -> None:
    archive = tmp_path / module.ARCHIVE_NAME
    archive.write_bytes(b"zip")
    source = {
        "id": module.PROVIDER_FILE_ID,
        "content_details": {
            "id": module.PROVIDER_CONTENT_ID,
            "download_url": "https://example.invalid/file",
            "created_date": "2022-01-01T00:00:00Z",
            "content_type": "application/zip",
        },
    }
    result = module.build_manifest(
        source, archive, {},
        retrieval_status="downloaded_verified",
        retrieved_at_utc="2026-07-26T00:00:00+00:00",
    )
    assert result["scope"] == "permanently-training-only"
    assert result["field_validation_eligible"] is False
    assert result["sealed_test_accessed"] is False


@pytest.mark.parametrize("timestamp", ["not-a-time", "2026-07-26T08:00:00+08:00"])
def test_build_manifest_rejects_non_utc_retrieval_time(
    tmp_path: Path, timestamp: str
) -> None:
    archive = tmp_path / module.ARCHIVE_NAME
    archive.write_bytes(b"zip")
    source = {"id": "x", "content_details": {
        "id": "y", "download_url": "https://example.invalid",
        "created_date": "x", "content_type": "application/zip"}}
    with pytest.raises(RuntimeError, match="UTC ISO-8601"):
        module.build_manifest(
            source, archive, {},
            retrieval_status="downloaded_verified", retrieved_at_utc=timestamp,
        )


def test_two_acquisition_structure_maps_names_frequencies_and_channels(
    tmp_path: Path
) -> None:
    members: dict[str, bytes] = {}
    for acquisition in ("acq-a", "acq-b"):
        for frequency in ("1Hz", "2Hz"):
            for channel in ("c0", "c1"):
                members[f"site/{acquisition}/{frequency}/set/{channel}.dat"] = b"1234"
        members[f"site/{acquisition}/metadata.xls"] = b"a\tb\n"
    archive = tmp_path / module.ARCHIVE_NAME
    make_zip(archive, members)
    manifest = {
        "schema_version": module.MANIFEST_SCHEMA,
        "scope": "permanently-training-only",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "doi": module.DOI,
        "license": {"spdx": module.LICENSE},
        "archive": {"bytes": archive.stat().st_size, "sha256": module.sha256_file(archive)},
        "audit": module.audit_archive(archive),
        "retrieval_provenance": {
            "schema_version": "wp8-retrieval-provenance-v1",
            "status": "downloaded_verified",
            "retrieved_at_utc": "2026-07-26T00:00:00Z",
            "transport": "https",
            "verification": "provider-size-and-sha256",
        },
    }
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = audit_module.build_contract_audit(tmp_path, require_real_contract=False)
    assert set(result["acquisitions"]) == {"acq-a", "acq-b"}
    assert all(item["frequencies_hz"] == [1.0, 2.0] for item in result["acquisitions"].values())
    assert all(item["channel_count"] == 2 for item in result["acquisitions"].values())


def test_mains_delegate_to_immutable_writers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: list[str] = []
    fake_manifest = {
        "retrieval_provenance": {
            "schema_version": "wp8-retrieval-provenance-v1",
            "status": "downloaded_verified",
            "retrieved_at_utc": "2026-07-26T00:00:00Z",
            "transport": "https",
            "verification": "provider-size-and-sha256",
        },
        "archive": {"sha256": "x"},
    }
    monkeypatch.setattr(module, "resolve_source", lambda: {"content_details": {
        "download_url": "x", "size": 1, "sha256_hash": "x"}})
    monkeypatch.setattr(module, "download_verified", lambda *args: "downloaded_verified")
    monkeypatch.setattr(module, "audit_archive", lambda path: {"member_count": 0, "expanded_bytes": 0})
    monkeypatch.setattr(module, "build_manifest", lambda *args, **kwargs: fake_manifest)
    def record_manifest(path: Path, value: object) -> None:
        captured.append("manifest")
        path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "write_immutable_manifest", record_manifest)
    monkeypatch.setattr(module, "DATA", tmp_path)
    (tmp_path / module.ARCHIVE_NAME).write_bytes(b"x")
    module.main()
    real_result = {
        "audit_mode": "real-provider-contract",
        "sealed_test_accessed": False,
        "structure_audit_passed": True,
        "acquisition_group_count": 0,
        "dat_member_count": 0,
        "independent_cluster_upper_bound": 1,
        "formal_field_gate_passes": False,
    }
    monkeypatch.setattr(audit_module, "build_contract_audit", lambda: real_result)
    monkeypatch.setattr(audit_module, "write_immutable_result", lambda path, value: captured.append("audit"))
    audit_module.main()
    assert captured == ["manifest", "audit"]
