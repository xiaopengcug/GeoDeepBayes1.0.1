#!/usr/bin/env python
"""Freeze a response-blind USGS AEM training expansion before payload access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
CATALOGUE = (
    ROOT
    / "validation/wp8/data/usgs-sciencebase-aem-catalogue-v2/catalogue.json"
)
DOC_MANIFEST = (
    ROOT
    / "validation/wp8/data/usgs-sciencebase-aem-contract-docs-v1/manifest.json"
)
AUDIT = EVIDENCE / "usgs-sciencebase-aem-contract-audit-v1.json"
GA_SPLIT = EVIDENCE / "geoscience-australia-aem-multisystem-spatial-split.json"
OUT = EVIDENCE / "usgs-aem-training-expansion-design-v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    document_manifest = json.loads(DOC_MANIFEST.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    ga_split = json.loads(GA_SPLIT.read_text(encoding="utf-8"))
    if (
        catalogue["aem_response_values_interpreted"] != 0
        or audit["response_values_interpreted"] != 0
        or ga_split["test_unseal_count"] != 0
    ):
        raise RuntimeError("input population is not response blind")

    exposed_ids = {
        Path(incident["path"]).name.split("__", 1)[0]
        for incident in document_manifest[
            "excluded_response_package_download_incidents"
        ]
    }
    records = {
        record["sciencebase_id"]: record for record in catalogue["records"]
    }
    training = []
    for survey in audit["surveys"]:
        item_id = survey["sciencebase_id"]
        if (
            not survey["provisional_observation_contract_ready"]
            or item_id in exposed_ids
        ):
            continue
        candidates = records[item_id]["candidate_data_files"]
        em_candidates = [
            file
            for file in candidates
            if any(
                cue in (file.get("name") or "").lower()
                for cue in ("em_", "aem", "skytem", "tempest")
            )
            and "rad_" not in (file.get("name") or "").lower()
        ]
        if len(em_candidates) != 1:
            raise RuntimeError(
                f"ambiguous observational payload for {item_id}: "
                f"{[file.get('name') for file in em_candidates]}"
            )
        file = em_candidates[0]
        training.append(
            {
                "sciencebase_id": item_id,
                "parent_id": survey["parent_id"],
                "title": survey["title"],
                "systems": survey["systems"],
                "role": "training",
                "selection_basis": (
                    "all unexposed provisional contract-ready time-domain "
                    "USGS surveys in frozen catalogue"
                ),
                "payload": {
                    key: file.get(key)
                    for key in (
                        "name",
                        "title",
                        "contentType",
                        "size",
                        "dateUploaded",
                        "downloadUri",
                        "checksum",
                    )
                },
            }
        )
    training.sort(key=lambda value: value["sciencebase_id"])
    output = {
        "schema_version": "wp8-usgs-aem-training-expansion-design-v1",
        "catalogue_sha256": sha(CATALOGUE),
        "contract_document_manifest_sha256": sha(DOC_MANIFEST),
        "contract_audit_sha256": sha(AUDIT),
        "ga_multisystem_spatial_split_sha256": sha(GA_SPLIT),
        "selection_frozen_before_payload_access": True,
        "excluded_response_exposed_sciencebase_ids": sorted(exposed_ids),
        "training_survey_count": len(training),
        "training_systems": sorted(
            {system for survey in training for system in survey["systems"]}
        ),
        "training_surveys": training,
        "ga_sealed_test_cluster_upper_bound": ga_split[
            "design_test_cluster_upper_bound"
        ],
        "ga_required_test_clusters": 223,
        "usgs_calibration_surveys": [],
        "usgs_test_surveys": [],
        "training_payloads_downloaded": 0,
        "training_response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_surveys": len(training),
                "systems": output["training_systems"],
                "excluded_exposed": sorted(exposed_ids),
                "ga_sealed_test_clusters": output[
                    "ga_sealed_test_cluster_upper_bound"
                ],
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
