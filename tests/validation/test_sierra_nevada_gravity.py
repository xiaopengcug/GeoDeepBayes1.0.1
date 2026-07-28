from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/sierra-nevada-gravity-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sierra_nevada_gravity_freeze_and_design_are_response_blind() -> None:
    manifest_path = DATA / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = json.loads(
        (EVIDENCE / "sierra-nevada-gravity-design.json").read_text(encoding="utf-8")
    )
    assert manifest["license"] == "CC0 1.0 Universal"
    assert manifest["response_values_interpreted_during_acquisition"] == 0
    for member in manifest["members"]:
        path = DATA / member["path"]
        assert path.stat().st_size == member["bytes"]
        assert sha(path) == member["sha256"]
    assert design["raw_manifest_sha256"] == sha(manifest_path)
    assert design["formal_excluded_ids"] == ["CH75"]
    assert design["response_fields_interpreted"] == 0
    assert design["station_count"] == 28_895
    assert design["source_count"] == 21
    assert design["partition_block_counts"] == {
        "train": 107,
        "buffer": 48,
        "calibration": 59,
        "test": 320,
    }
    assert design["design_power_gate_possible"] is True
    assert design["test_unseal_count"] == 0


def test_sierra_nevada_training_audit_rejects_formal_qualification() -> None:
    audit = json.loads(
        (
            EVIDENCE / "sierra-nevada-gravity-train-diagnostics.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["training_response_rows_interpreted"] == 5_585
    assert audit["response_rows_interpreted"] == {
        "train": 5_585,
        "buffer": 0,
        "calibration": 0,
        "test": 0,
    }
    assert audit["correlation_range_km"] == 62.5
    assert audit["range_censored_at_200km"] is False
    assert audit["design_test_cluster_upper_bound"] == 320
    assert audit["correlation_adjusted_test_cluster_upper_bound"] == 42
    assert audit["cluster_power_gate_passes"] is False
    assert audit["per_observation_uncertainty_contract_ready"] is False
    assert audit["test_unseal_count"] == 0
