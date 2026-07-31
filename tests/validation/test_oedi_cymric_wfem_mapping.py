from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ACQUIRE_PATH = ROOT / "validation/wp8/acquire_oedi_cymric_wfem_mapping.py"
spec = importlib.util.spec_from_file_location("acquire_oedi_cymric_wfem_mapping", ACQUIRE_PATH)
assert spec and spec.loader
acquire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquire)
sys.path.insert(0, str(ACQUIRE_PATH.parent))
AUDIT_PATH = ACQUIRE_PATH.parent / "audit_oedi_cymric_wfem_mapping.py"
audit_spec = importlib.util.spec_from_file_location("audit_oedi_cymric_wfem_mapping", AUDIT_PATH)
assert audit_spec and audit_spec.loader
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)


def test_real_cymric_package_is_exact_and_formally_blocked() -> None:
    manifest = acquire.build_manifest()
    result = audit.build_audit()
    assert manifest["scope"] == "permanently-training-only"
    assert len(manifest["members"]) == 6
    assert {row["path"] for row in result["field_tables"]} == set(audit.FIELD_FILES)
    assert [row["phase_degrees_present"] for row in result["field_tables"]] == [
        False, True, True
    ]
    assert result["method_identity"] == {"observed": "FDEM", "mapped_to_wfem": False}
    assert result["missing_required_wfem_fields"] == [
        "source_current", "phase_or_complex_response_complete",
        "absolute_receiver_geometry", "absolute_source_geometry", "geometric_factor",
    ]
    assert result["independent_site_cluster_upper_bound"] == 1
    assert result["formal_status"] == "blocked"
    assert result["field_validation_eligible"] is False
    assert result["sealed_test_accessed"] is False


def test_build_manifest_hard_codes_permanent_boundaries() -> None:
    result = acquire.build_manifest()
    assert result["scope"] == "permanently-training-only"
    assert result["mapping_role"] == "FDEM-to-WFEM-contract-candidate-only"
    assert result["fdem_is_wfem"] is False
    assert result["field_validation_eligible"] is False
    assert result["sealed_test_accessed"] is False
    assert len(result["members"]) == len(acquire.ANCHORS) == 6


@pytest.mark.parametrize(
    ("field", "value"), [
        ("scope", "field"), ("field_validation_eligible", True),
        ("sealed_test_accessed", True), ("fdem_is_wfem", True),
    ],
)
def test_contract_audit_rejects_boundary_drift(
    tmp_path: Path, field: str, value: object
) -> None:
    for source in acquire.DATA.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())
    manifest_path = tmp_path / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest))
    result = audit.build_audit(tmp_path)
    assert "boundary_or_source" in result["errors"]
    assert result["structure_audit_passed"] is False


def test_manifest_member_hash_drift_is_rejected(tmp_path: Path) -> None:
    for source in acquire.DATA.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())
    manifest = json.loads((tmp_path / "raw-manifest.json").read_text())
    manifest["members"][1]["sha256"] = "0" * 64
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest))
    result = audit.build_audit(tmp_path)
    assert any(error.startswith("member:") for error in result["errors"])


def _copy_package(tmp_path: Path) -> None:
    for source in acquire.DATA.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())


def test_provider_synchronized_replacement_is_rejected(tmp_path: Path) -> None:
    _copy_package(tmp_path)
    target = tmp_path / "cymric_field_data1_5hz.txt"
    target.write_bytes(target.read_bytes() + b"\n")
    manifest = json.loads((tmp_path / "raw-manifest.json").read_text())
    row = next(item for item in manifest["members"] if item["path"] == target.name)
    row["bytes"] = target.stat().st_size
    row["sha256"] = acquire.sha256(target)
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest))
    result = audit.build_audit(tmp_path, require_real_contract=False)
    assert f"provider_member:{target.name}" in result["errors"]
    assert result["sealed_test_accessed"] == "not_assessed"


@pytest.mark.parametrize("missing", [
    "oedi-submission-7306.html", "cymric_data1_survey_configuration.PNG",
])
def test_missing_html_or_png_is_rejected(tmp_path: Path, missing: str) -> None:
    _copy_package(tmp_path)
    (tmp_path / missing).unlink()
    result = audit.build_audit(tmp_path, require_real_contract=False)
    assert f"provider_member:{missing}" in result["errors"]


@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", "drift"), ("mapping_role", "WFEM"),
])
def test_schema_or_role_drift_is_rejected(
    tmp_path: Path, field: str, value: str
) -> None:
    _copy_package(tmp_path)
    manifest = json.loads((tmp_path / "raw-manifest.json").read_text())
    manifest[field] = value
    (tmp_path / "raw-manifest.json").write_text(json.dumps(manifest))
    assert "boundary_or_source" in audit.build_audit(
        tmp_path, require_real_contract=False
    )["errors"]


@pytest.mark.parametrize("payload", [
    b"% distance amplitude\n1 NaN\n" * 16,
    b"% distance amplitude\n1 2 3\n" * 16,
])
def test_nonfinite_or_wrong_column_table_is_rejected(
    tmp_path: Path, payload: bytes
) -> None:
    with pytest.raises(ValueError, match="shape or finite"):
        audit.parse_field_table(payload.decode(), (16, 2))


def test_manifest_writer_preserves_bytes_and_rejects_drift(tmp_path: Path) -> None:
    path = tmp_path / "raw-manifest.json"
    value = {"scope": "permanently-training-only"}
    acquire.write_immutable(path, value)
    original = path.read_bytes()
    acquire.write_immutable(path, value)
    assert path.read_bytes() == original
    with pytest.raises(RuntimeError, match="immutable"):
        acquire.write_immutable(path, {"scope": "field"})
    assert path.read_bytes() == original


def test_contract_writer_rejects_test_mode_and_preserves_drift_bytes(
    tmp_path: Path
) -> None:
    path = tmp_path / "contract-audit.json"
    real = {"audit_mode": "real-provider-contract", "formal_status": "blocked"}
    audit.write_immutable_contract(path, real)
    original = path.read_bytes()
    audit.write_immutable_contract(path, real)
    with pytest.raises(RuntimeError, match="immutable"):
        audit.write_immutable_contract(path, {**real, "formal_status": "passed"})
    assert path.read_bytes() == original
    with pytest.raises(RuntimeError, match="cannot be written"):
        audit.write_immutable_contract(path, {"audit_mode": "test-structure-only"})


def test_mains_use_immutable_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_package(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(acquire, "DATA", tmp_path)
    monkeypatch.setattr(
        acquire, "write_immutable", lambda path, value: calls.append("manifest")
    )
    acquire.main()
    real = audit.build_audit()
    monkeypatch.setattr(audit, "build_audit", lambda: real)
    monkeypatch.setattr(
        audit, "write_immutable_contract", lambda path, value: calls.append("contract")
    )
    audit.main()
    assert calls == ["manifest", "contract"]
