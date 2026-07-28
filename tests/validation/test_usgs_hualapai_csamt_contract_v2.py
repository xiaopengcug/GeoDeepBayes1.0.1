import importlib.util
import json
import re
import io
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


audit = load("hualapai_audit", "validation/wp8/audit_usgs_hualapai_csamt_contract.py")
acquire = load("hualapai_acquire", "validation/wp8/acquire_usgs_hualapai_csamt.py")


def valid_mtm():
    return """
TxLength(1)=1000,TxAzimuth(1)=90,TxGridE(1)=241960,TxGridN(1)=3972019
DpLength=100,DpAzimuth=90
ARerrFloor=7.5
ZPerrFloor=4.5
"""


@pytest.mark.parametrize(
    "replacement,match",
    [
        ("", "missing or duplicate"),
        ("TxLength(1)=0", "non-positive TxLength"),
        ("TxGridE(1)=0", "outside UTM"),
        ("TxGridN(1)=0", "outside UTM"),
        ("DpLength=0", "non-positive DpLength"),
        ("TxAzimuth(1)=360", "invalid TxAzimuth"),
    ],
)
def test_mtm_missing_zero_and_invalid_fields(replacement, match):
    text = valid_mtm()
    if not replacement:
        text = text.replace("ARerrFloor=7.5", "")
    else:
        field = replacement.split("=")[0]
        text = re.sub(rf"{re.escape(field)}=[^,\n]+", replacement, text)
    with pytest.raises(RuntimeError, match=match):
        audit.parse_mtm(text, "A1")


def test_mtm_rejects_nonfinite_and_duplicate():
    with pytest.raises(RuntimeError, match="missing or duplicate"):
        audit.parse_mtm(valid_mtm() + "\nARerrFloor=2\n", "A1")
    # NaN is deliberately outside the accepted numeric grammar and therefore fails closed.
    with pytest.raises(RuntimeError, match="missing or duplicate"):
        audit.parse_mtm(valid_mtm().replace("ZPerrFloor=4.5", "ZPerrFloor=NaN"), "A1")


def test_line_inventory_rejects_missing_duplicate_and_wrong():
    good = sorted(audit.EXPECTED_LINES)
    audit.require_exact_lines(good, "test")
    for bad in (good[:-1], good + ["A1"], good[:-1] + ["BAD"]):
        with pytest.raises(RuntimeError, match="inventory drift"):
            audit.require_exact_lines(bad, "test")


def test_provider_synchronized_replacement_still_fails_fixed_anchor(tmp_path):
    path = tmp_path / "provider.bin"
    path.write_bytes(b"replacement")
    replacement_hash = acquire.sha256(path)
    # A synchronized mutable manifest could accept this digest; the code anchor cannot.
    assert replacement_hash != "80d68dfab36b77824474dba9bba9eda972eaa39caecc073cbb30476dcf9cacbb"
    with pytest.raises(RuntimeError, match="provider anchor drift"):
        acquire.verify(path, len(b"replacement"), "80d68dfab36b77824474dba9bba9eda972eaa39caecc073cbb30476dcf9cacbb")


def test_all_nine_anchors_and_resource_classes_are_frozen():
    manifest = json.loads((acquire.DATA / "raw-manifest.json").read_text())
    assert len(acquire.ANCHORS) == 9
    assert manifest["provider_member_count"] == 7
    assert manifest["metadata_snapshot_count"] == 2
    assert manifest["total_resource_count"] == 9
    assert sum(row["resource_kind"] == "provider_file" for row in manifest["members"]) == 7


def test_bad_fetch_never_publishes_target(monkeypatch, tmp_path):
    class Response(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(acquire.urllib.request, "urlopen", lambda *a, **k: Response(b"bad"))
    target = tmp_path / "member.bin"
    with pytest.raises(RuntimeError, match="provider anchor drift"):
        acquire.fetch_atomic("https://invalid.example", target, 4, "0" * 64)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_immutable_writers_reject_drift(tmp_path):
    target = tmp_path / "evidence.json"
    acquire.write_immutable(target, {"a": 1})
    with pytest.raises(RuntimeError, match="immutable"):
        acquire.write_immutable(target, {"a": 2})
    other = tmp_path / "contract.json"
    audit.write_immutable_atomic(other, {"a": 1})
    with pytest.raises(RuntimeError, match="immutable"):
        audit.write_immutable_atomic(other, {"a": 2})


def test_real_contract_is_conservative_and_aligned():
    result = audit.audit()
    assert result["line_ids"] == sorted(audit.EXPECTED_LINES)
    assert result["site_mapping"]["status"] == "unsupported_by_anchored_official_evidence"
    assert result["site_mapping"]["requested_three_site_mapping_accepted"] is False
    assert result["site_mapping"]["lines_are_sites"] is False
    assert result["field_validation_eligible"] is False
    assert result["formal_cluster_power_gate_passes"] is False
    assert all(row["TxGridE"] and row["TxGridN"] for row in result["mtm_source_and_error_contract_by_line"].values())


def test_site_mapping_and_central_contract_tamper_are_detectable(tmp_path):
    result = audit.audit()
    result["site_mapping"]["status"] = "proved_three_sites"
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(result), encoding="utf-8")
    validator = load("wp8_validator_hualapai", "validation/wp8/validate_wp8.py")
    validator.HUALAPAI_CSAMT_CONTRACT = target
    with pytest.raises(RuntimeError, match="Hualapai CSAMT conservative contract"):
        validator.audit_controlled_source_paths()


def test_reconciliation_tamper_and_legacy_sealed_role_are_rejected(tmp_path):
    validator = load("wp8_validator_hualapai_reconciliation", "validation/wp8/validate_wp8.py")
    source = validator.HUALAPAI_CSAMT_RECONCILIATION
    value = json.loads(source.read_text(encoding="utf-8"))
    value["hualapai_sealed_test_eligible"] = True
    target = tmp_path / "reconciliation.json"
    target.write_text(json.dumps(value), encoding="utf-8")
    validator.HUALAPAI_CSAMT_RECONCILIATION = target
    with pytest.raises(RuntimeError, match="role reconciliation drift"):
        validator.audit_controlled_source_paths()
