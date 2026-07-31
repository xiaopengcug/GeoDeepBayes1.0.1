from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/texas-aib-magnetic-v1"
EVIDENCE = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/texas-aib-magnetic-contract-readiness.json"
)


def test_texas_aib_metadata_members_are_hash_verified() -> None:
    manifest_path = RAW / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["response_archives_downloaded"] is False
    assert manifest["response_values_interpreted"] is False
    for member in manifest["files"]:
        path = RAW / member["name"]
        assert path.stat().st_size == member["bytes"] == member["expected_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == member["sha256"]
    excluded = {member["name"]: member["bytes"] for member in manifest["excluded_response_members"]}
    assert excluded["TX_AIB_mag.csv.zip"] == 4236679294


def test_texas_aib_contract_passes_without_response_access() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["passed"] is True
    assert evidence["errors"] == []
    assert evidence["flight_plan"]["dbf"]["records"] == 1522
    assert evidence["flight_plan"]["shapefile"]["records"] == 1522
    assert evidence["survey_contract"]["primary_lines"] == 1306
    assert evidence["survey_contract"]["tie_lines"] == 141
    assert evidence["survey_contract"]["line_kilometers"] == 166594
    assert evidence["survey_contract"]["missing_attributes"] == []
    assert evidence["response_archives_downloaded"] is False
    assert evidence["response_values_interpreted"] is False
    assert evidence["selection_decision"].startswith("eligible")


def test_texas_aib_large_response_access_is_fail_closed() -> None:
    access = json.loads(
        (
            ROOT
            / "validation/wp8/evidence/feasibility-v1/texas-aib-response-access.json"
        ).read_text(encoding="utf-8")
    )
    assert access["expected_bytes"] == 4236679294
    assert access["manager_probe"]["content_type"].startswith("text/html")
    assert access["unsigned_s3_probe"]["status"] == 403
    assert access["captcha_required_for_presigned_url"] is True
    assert access["direct_archive_available_without_human_challenge"] is False
    assert access["response_bytes_read"] == 0
    assert access["status"] == "human_captcha_required_for_temporary_presigned_url"
