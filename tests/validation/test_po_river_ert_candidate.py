import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1/po-river-ert-candidate.json"


def test_po_river_candidate_is_sealed_and_rejected_before_response_audit():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    archive = ROOT / payload["archive_path"]
    assert payload["schema_version"] == "wp8-po-river-ert-candidate-v1"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == payload["archive_sha256"]
    assert payload["observation_values_parsed"] is False
    assert payload["station_count"] == 518
    assert payload["electrode_position_rows"] == 518 * 13
    assert payload["contract_header_and_metadata_complete_except_topographic_elevation"]
    assert payload["maximum_nonoverlapping_footprint_units"] < 223
    assert payload["can_meet_cluster_gate_before_correlation_adjustment"] is False
    assert payload["calibration_responses_interpreted"] == 0
    assert payload["test_responses_interpreted"] == 0
    assert payload["test_unseal_count"] == 0
