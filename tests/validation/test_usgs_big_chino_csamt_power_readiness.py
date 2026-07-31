from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "validation/wp8/audit_usgs_big_chino_csamt_training_power_readiness_v1.py"
spec = importlib.util.spec_from_file_location("big_chino_power_readiness", PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_real_readiness_is_line_level_and_power_blocked() -> None:
    result = module.build_audit()
    assert result["partition"]["authorized_training_lines"] == [
        "CG", "CH", "EW2", "FMW", "NS1", "NS3"
    ]
    assert result["partition"]["response_content_members_opened_by_this_audit"] == []
    assert result["partition"]["archive_member_leakage_by_this_audit"] == []
    assert result["inference_hierarchy"]["training_observations_reported"] == 342
    assert result["inference_hierarchy"]["training_lines"] == 6
    assert result["inference_hierarchy"]["training_sites"] == 1
    assert result["design_reconciliation"]["claimed_257_station_clusters"] == 257
    assert result["design_reconciliation"]["claim_status"] == "superseded_for_formal_gate"
    assert result["design_reconciliation"]["formal_independent_cluster_proven_upper_bound"] == 1
    assert result["design_reconciliation"]["sealed_packaged_line_upper_bound_not_independence_evidence"] == 15
    assert result["design_reconciliation"]["formal_cluster_gate_passes"] is False
    assert result["paired_power_inputs"]["validated_registry_count"] == 0
    assert result["paired_power_inputs"]["registry_present"] is False
    assert result["paired_crps_computed"] is False
    assert result["formal_power_gate_passes"] is False
    assert result["field_validation_eligible"] is False


def test_training_line_authorization_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    design = json.loads(module.DESIGN.read_text())
    design["split"]["training_lines"][0] = "AX"
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design))
    monkeypatch.setattr(module, "DESIGN", path)
    result = module.build_audit()
    assert {"approved_anchor_drift", "partition_contract"} <= set(result["errors"])
    assert result["structure_audit_passed"] is False


@pytest.mark.parametrize("target_name", ["TRAINING", "INVERSION"])
def test_training_or_inversion_anchor_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_name: str
) -> None:
    source = getattr(module, target_name)
    path = tmp_path / source.name
    path.write_bytes(source.read_bytes() + b" ")
    monkeypatch.setattr(module, target_name, path)
    assert "approved_anchor_drift" in module.build_audit()["errors"]


def test_missing_registry_and_power_model_keep_power_noncomputable() -> None:
    result = module.build_audit()
    conditions = result["paired_power_inputs"]["minimum_computable_conditions"]
    assert conditions["cluster_and_correlation_model_frozen"] is False
    assert conditions["required_independent_cluster_count_derived_by_frozen_power_method"] is False
    assert conditions["two_frozen_methods_named_and_versioned"] is False
    assert conditions["paired_out_of_sample_predictions_cover_all_training_lines"] is False
    assert any("derive required independent N" in row for row in result["exact_unblockers"])


def test_production_zip_wrapper_uses_namelist_and_never_open_or_read(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"namelist": 0, "open": 0, "read": 0}
    real_zip = module.ZipFile
    class SpyZip:
        def __init__(self, path):
            self.inner = real_zip(path)
        def __enter__(self): return self
        def __exit__(self, *args): self.inner.close()
        def namelist(self):
            calls["namelist"] += 1
            return self.inner.namelist()
        def open(self, *args):
            calls["open"] += 1
            raise AssertionError
        def read(self, *args):
            calls["read"] += 1
            raise AssertionError
    monkeypatch.setattr(module, "ZipFile", SpyZip)
    result = module.build_audit()
    assert calls == {"namelist": 2, "open": 0, "read": 0}
    assert result["partition"]["response_content_members_opened_by_this_audit"] == []
    assert result["partition"]["archive_member_leakage_by_this_audit"] == []


def test_missing_archive_member_is_rejected() -> None:
    lines = sorted(module.APPROVED_LINES - {"CG"})
    result = module._build_audit_from_test_inventories(
        [f"{line}.raw" for line in lines], [f"{line}.mtm" for line in lines]
    )
    assert "archive_line_inventory" in result["errors"]
    assert "training_member_missing" in result["errors"]


def test_forged_archive_line_is_rejected() -> None:
    assert "archive_line_inventory" in module._build_audit_from_test_inventories(
        [f"{line}.raw" for line in module.APPROVED_LINES] + ["FORGED.raw"],
        [f"{line}.mtm" for line in module.APPROVED_LINES] + ["FORGED.mtm"],
    )["errors"]


def test_duplicate_partition_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    design = json.loads(module.DESIGN.read_text())
    design["split"]["training_lines"].append("CG")
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design))
    monkeypatch.setattr(module, "DESIGN", path)
    assert "partition_contract" in module.build_audit()["errors"]


def test_immutable_output_rejects_drift_and_preserves_bytes(tmp_path: Path) -> None:
    path = tmp_path / "readiness.json"
    value = {"status": "blocked"}
    module.write_immutable(path, value)
    original = path.read_bytes()
    module.write_immutable(path, value)
    with pytest.raises(RuntimeError, match="immutable"):
        module.write_immutable(path, {"status": "passed"})
    assert path.read_bytes() == original


def _valid_registry(tmp_path: Path) -> tuple[Path, dict]:
    artifact = tmp_path / "scores.json"
    artifact.write_text("{}")
    value = {
        "schema_version": "usgs-big-chino-csamt-paired-score-registry-v1",
        "dataset_doi": "10.5066/P9KGKWNL",
        "method_versions": ["baseline@1", "candidate@1"],
        "line_coverage": sorted(module.AUTHORIZED_TRAINING_LINES),
        "artifact_path": "scores.json",
        "artifact_sha256": module.sha256(artifact),
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(value))
    return path, value


def test_valid_paired_registry_counts_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = _valid_registry(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    registry, errors = module.load_registry(path)
    assert registry is not None and errors == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "bad"),
        ("dataset_doi", "bad"),
        ("method_versions", ["one"]),
        ("line_coverage", ["CG"]),
        ("artifact_sha256", "0" * 64),
        ("artifact_path", "../escape.json"),
    ],
)
def test_invalid_paired_registry_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value
) -> None:
    path, registry = _valid_registry(tmp_path)
    registry[field] = value
    path.write_text(json.dumps(registry))
    monkeypatch.setattr(module, "ROOT", tmp_path)
    _, errors = module.load_registry(path)
    assert errors == ["paired_registry_contract"]
