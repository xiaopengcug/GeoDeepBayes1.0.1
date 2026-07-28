from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-krause-ert-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_krause_ert_contract_fails_closed_on_reciprocal_error() -> None:
    manifest_path = RAW / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = json.loads(
        (EVIDENCE / "usgs-krause-ert-contract.json").read_text(encoding="utf-8")
    )
    assert manifest["doi"] == "10.5066/P91Z1HKN"
    assert manifest["license"].startswith("CC0")
    assert manifest["selection_is_response_blind"] is True
    for member in manifest["members"]:
        path = RAW / member["path"]
        assert path.stat().st_size == member["bytes"]
        assert sha256(path) == member["sha256"]
    assert contract["raw_manifest_sha256"] == sha256(manifest_path)
    assert contract["measurement_count"] == 13_605
    assert contract["profile_count"] == 4
    assert contract["abmn_local_geometry_present"] is True
    assert contract["electrode_gps_present"] is True
    assert contract["navd88_topography_present"] is True
    assert contract["reciprocal_configuration_group_count"] == 0
    assert contract["empirical_error_model_possible"] is False
    assert contract["direct_per_observation_standard_deviation_present"] is False
    assert contract["observation_contract_ready_for_development"] is False
    assert contract["formal_cluster_power_gate_passes"] is False
    assert contract["test_unseal_count"] == 0
