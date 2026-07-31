#!/usr/bin/env python
"""Audit CPERS v2 nominal scale, response availability, and permission terms."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/cpers-public-catalogue-v2"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/cpers-public-catalogue.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["selection_is_response_blind"] is not True
        or manifest["measurement_payloads_downloaded"] != 0
        or manifest["response_values_interpreted_during_acquisition"] != 0
        or manifest["test_unseal_count"] != 0
    ):
        raise RuntimeError("CPERS acquisition protocol drift")
    for member in manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            raise RuntimeError(f"CPERS member drift: {member['path']}")

    catalogue = (RAW / "nordicana-d121-v2.html").read_text(encoding="utf-8")
    policy = (RAW / "cpers-data-policy-v1.3.html").read_text(encoding="utf-8")
    downloads = re.findall(
        r'"name":\s*"([^"]+)"\s*,\s*"contentUrl":\s*"([^"]+)"',
        catalogue,
    )
    result = {
        "schema_version": "wp8-cpers-public-catalogue-audit-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "doi": "10.5885/45855XD-DC9883ABD609428B",
        "catalogue_version": "2.0",
        "catalogue_update_date": "2025-11-05",
        "metadata_survey_count": 494,
        "distinct_profile_count": 423,
        "repeat_profile_count": 15,
        "raw_survey_count": 292,
        "embargoed_survey_count": 33,
        "survey_count_without_raw_data": 169,
        "data_year_range": [2008, 2024],
        "regional_download_member_count": len(downloads),
        "measurement_download_member_count": sum(
            "_ERT_measurements_v2.csv" in name for name, _ in downloads
        ),
        "electrode_download_member_count": sum(
            "_electrode_positions_v2.csv" in name for name, _ in downloads
        ),
        "metadata_download_member_count": sum(
            "_metadata_v2.csv" in name for name, _ in downloads
        ),
        "nominal_profile_power_threshold_exceeded": 423 >= 223,
        "nominal_raw_survey_power_threshold_exceeded": 292 >= 223,
        "permission_contract": {
            "publicly_visible_and_downloadable": True,
            "contact_contributors_required_before_use": (
                "Contact the data contributor(s) to request permission to use the data"
                in policy
            ),
            "collaboration_or_attribution_discussion_required": (
                "Discuss with the data contributor(s) the appropriate level of "
                "collaboration/attribution"
                in policy
            ),
            "permission_obtained": False,
        },
        "measurement_payloads_downloaded": 0,
        "correlation_length_frozen": False,
        "formal_contract_ready": False,
        "formal_cluster_power_gate_passes": False,
        "test_unseal_count": 0,
        "conclusion": (
            "CPERS v2 is the first public DC/ERT catalogue found whose nominal "
            "scale exceeds both thresholds: 423 distinct profiles and 292 surveys "
            "with raw data. Formal inclusion is not yet allowed because CPERS "
            "requires contributor permission and a collaboration/attribution "
            "discussion before use; no such permission is frozen. Response bytes "
            "were therefore not downloaded or interpreted, and no training-only "
            "correlation adjustment has been run."
        ),
    }
    if (
        len(downloads) != 21
        or result["measurement_download_member_count"] != 7
        or not result["permission_contract"][
            "contact_contributors_required_before_use"
        ]
        or not result["permission_contract"][
            "collaboration_or_attribution_discussion_required"
        ]
    ):
        raise RuntimeError("CPERS catalogue/policy drift")
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "profiles": 423,
                "raw_surveys": 292,
                "download_members": len(downloads),
                "permission_obtained": False,
            }
        )
    )


if __name__ == "__main__":
    main()
