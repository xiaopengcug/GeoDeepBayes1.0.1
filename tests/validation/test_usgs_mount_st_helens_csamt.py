from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-mount-st-helens-csamt-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_mount_st_helens_csamt_has_errors_but_fails_source_contract() -> None:
    manifest_path = RAW / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = json.loads(
        (
            EVIDENCE / "usgs-mount-st-helens-csamt-contract.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["record"] == "USGS Data Series 901"
    assert manifest["station_count"] == 13
    assert manifest["selection_is_response_blind"] is True
    for member in manifest["members"]:
        path = RAW / member["path"]
        assert path.stat().st_size == member["bytes"]
        assert sha256(path) == member["sha256"]
    assert contract["raw_manifest_sha256"] == sha256(manifest_path)
    assert contract["station_count"] == 13
    assert contract["controlled_source_station_upper_bound"] == 12
    assert contract["all_edi_have_rho_phase_and_error_arrays"] is True
    assert contract["source_contract"]["exact_source_coordinates_present"] is False
    assert contract["source_contract"]["source_moment_or_current_present"] is False
    assert contract["available_grounded_finite_line_solver_compatible"] is False
    assert contract["near_transition_far_classification_possible"] is False
    assert contract["observation_contract_ready"] is False
    assert contract["formal_cluster_power_gate_passes"] is False
    assert contract["response_values_interpreted"] == 0
    assert contract["test_unseal_count"] == 0
