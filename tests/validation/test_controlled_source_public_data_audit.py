from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/controlled-source-public-data-audit.json"
)


def test_controlled_source_public_search_does_not_change_method_contract() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert payload["formal_test_endpoints_inspected"] is False
    assert payload["conclusions"]["method_substitution_allowed"] is False
    candidates = {item["id"]: item for item in payload["candidates"]}
    assert candidates["usgs-red-knoll"]["local_pool_status"] == "already_frozen_as_red-knoll"
    assert candidates["usgs-red-knoll"]["survey_lines"] == 2
    assert candidates["usgs-red-knoll"]["per_acquisition_transmitter_endpoints"] is False
    assert candidates["usgs-mount-st-helens-ds901"]["per_acquisition_transmitter_endpoints"] is False
    assert candidates["pangaea-scanner-pockmark"]["decision"] == "do_not_substitute_for_csamt_or_wfem"
    assert candidates["wfem-literature-search"]["reusable_raw_release_found"] is False


def test_search_conclusion_preserves_fail_closed_gates() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert "223" in payload["conclusions"]["csamt"]
    assert "no public raw replacement" in payload["conclusions"]["wfem"]
