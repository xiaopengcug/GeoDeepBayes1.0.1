from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT / "validation/wp8/evidence/feasibility-v1/sip-fdip-public-data-audit.json"
)


def test_sip_search_distinguishes_lab_spectra_from_field_validation() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert payload["formal_test_endpoints_inspected"] is False
    assert payload["conclusions"]["complex_response_sources_exist"] is True
    assert payload["conclusions"]["contract_complete_field_replacement_found"] is False
    assert payload["conclusions"]["minimum_independent_test_clusters"] == 223
    assert payload["conclusions"]["method_substitution_allowed"] is False
    assert all(
        item.get("complex_conductivity")
        or item.get("complex_response")
        or item.get("phase_and_complex_conductivity")
        or item.get("raw_time_series")
        or item.get("complex_observations", 0) > 0
        for item in payload["candidates"]
    )
    assert all(item.get("decision") for item in payload["candidates"])
    assert any(
        item.get("field_profile_link") is False
        for item in payload["candidates"]
    )
    assert any(
        item.get("field_profiles", 0) > 0
        or item.get("field_sites", 0) > 0
        or item.get("field_site_count", 0) > 0
        for item in payload["candidates"]
    )
