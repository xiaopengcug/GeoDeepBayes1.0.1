#!/usr/bin/env python
"""Audit the TDIP field archive inventory without reading response payloads."""
from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/zenodo-tdip-full-decay-v1"
ARCHIVE = DATA / "field_survey.rar"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/zenodo-tdip-full-decay-contract.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = subprocess.run(
        ["tar", "-tf", str(ARCHIVE)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    suffix_counts = Counter(PurePosixPath(name).suffix.lower() for name in names)
    project_databases = sorted(name for name in names if name.endswith("/project.db"))
    processed_profiles = sorted(
        PurePosixPath(name).stem
        for name in names
        if "/field_processed_data/" in name and name.endswith(".dip")
    )
    acquisition_groups = sorted(
        {
            "/".join(PurePosixPath(name).parts[:3])
            for name in names
            if "/field_full_waveform_data/" in name
        }
    )
    evidence = {
        "schema_version": "wp8-zenodo-tdip-full-decay-contract-v1",
        "doi": manifest["doi"],
        "license": manifest["license"],
        "archive_sha256": manifest["members"][0]["sha256"],
        "archive_bytes": manifest["total_bytes"],
        "archive_member_names_read": True,
        "observation_values_read": False,
        "formal_test_endpoints_inspected": False,
        "selection_role": "training_contract_candidate_only",
        "inventory": {
            "members": len(names),
            "suffix_counts": dict(sorted(suffix_counts.items())),
            "project_databases": len(project_databases),
            "acquisition_groups": acquisition_groups,
            "processed_profile_ids": processed_profiles,
            "full_waveform_raw_members": suffix_counts[".raw"],
            "processed_dip_members": suffix_counts[".dip"],
            "inversion_input_members": suffix_counts[".dat"],
        },
        "contract_readiness": {
            "full_decay_waveforms_present": suffix_counts[".raw"] > 0,
            "instrument_project_databases_present": bool(project_databases),
            "processed_profiles_present": bool(processed_profiles),
            "geometry_and_time_window_fields_verified": False,
            "empirical_error_model_verified": False,
            "independent_field_sites": 1,
        },
        "gate_impact": {
            "contract_can_be_audited_training_only": True,
            "minimum_independent_test_clusters": 223,
            "power_gate_passed": False,
            "reason": (
                "the CC-BY archive provides full-waveform field TDIP and five "
                "processed profiles, but all observations belong to one "
                "contaminated site and cannot repair the 223-cluster gate"
            ),
        },
        "test_unseal_count": 0,
    }
    if OUTPUT.exists():
        os.chmod(OUTPUT, 0o644)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    os.chmod(OUTPUT, 0o444)
    print(
        json.dumps(
            {
                "members": len(names),
                "raw": suffix_counts[".raw"],
                "profiles": len(processed_profiles),
            }
        )
    )


if __name__ == "__main__":
    main()
