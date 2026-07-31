from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_western_arkansas_split_is_response_blind_and_spatially_grouped() -> None:
    split_path = EVIDENCE / "western-arkansas-magnetic-design-split.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    assert split["schema_version"] == "wp8-western-arkansas-magnetic-design-split-v1"
    assert split["magnetic_response_values_interpreted"] == 0
    assert split["calibration_responses_interpreted"] == 0
    assert split["test_responses_interpreted"] == 0
    assert split["partition_macroblock_m"] == 20_000.0
    assert split["partition_cell_counts"] == {
        "train": 913,
        "buffer": 710,
        "calibration": 228,
        "test": 366,
    }
    roles: dict[str, set[str]] = {}
    for cell in split["cells"]:
        roles.setdefault(cell["macroblock"], set()).add(cell["partition"])
    assert all(len(values) == 1 for values in roles.values())


def test_western_arkansas_training_audit_fails_closed_without_heldout_reads() -> None:
    split_path = EVIDENCE / "western-arkansas-magnetic-design-split.json"
    diagnostic = json.loads(
        (EVIDENCE / "western-arkansas-magnetic-train-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    assert diagnostic["split_sha256"] == sha(split_path)
    assert diagnostic["response_policy"]["buffer_rows_interpreted"] == 0
    assert diagnostic["response_policy"]["calibration_rows_interpreted"] == 0
    assert diagnostic["response_policy"]["test_rows_interpreted"] == 0
    assert diagnostic["conservative_spatial_correlation_range_m"] == 21_000.0
    assert diagnostic["correlation_adjusted_test_clusters"] == 0
    assert diagnostic["cluster_gate_passed"] is False
    assert diagnostic["power_gate_passed"] is False


def test_western_arkansas_contract_preserves_remanence_boundary() -> None:
    contract = json.loads(
        (EVIDENCE / "western-arkansas-magnetic-contract-readiness.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["observation_contract_passed"] is True
    assert contract["formal_uncertainty_model_ready"] is False
    assert contract["vector_measurement_channels_present"] is True
    assert "not treated as a rock-remanence direction prior" in contract["remanence_boundary"]
