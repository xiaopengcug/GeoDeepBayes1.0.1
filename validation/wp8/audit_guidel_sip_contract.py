#!/usr/bin/env python
"""Inventory the frozen Guidel SIP archive without reading MAT payloads."""
from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/guidel-sip-2025-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/guidel-sip-contract.json"


def main() -> None:
    manifest = json.loads((DATA / "raw-manifest.json").read_text(encoding="utf-8"))
    archive = DATA / "Guidel_SIP_DOI_2026.zip"
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
    monitoring = DATA / "guidel_sip_monitoring_data.csv.tgz"
    with tarfile.open(monitoring, "r:gz") as package:
        monitoring_members = {
            member.name: member.size for member in package.getmembers()
        }
    mat_names = [name for name in names if name.lower().endswith(".mat")]
    matlab_names = [name for name in names if name.lower().endswith(".m")]
    evidence = {
        "schema_version": "wp8-guidel-sip-contract-v1",
        "doi": manifest["doi"],
        "site": manifest["site"],
        "selection_role": "training_contract_candidate_only",
        "license": manifest["license"],
        "license_status": "resolved",
        "archive_members": len(names),
        "raw_mat_members": len(mat_names),
        "matlab_code_members": len(matlab_names),
        "monitoring_archive_members": monitoring_members,
        "monitoring_csv_bytes": monitoring_members.get(
            "guidel_sip_monitoring_data.csv", -1
        ),
        "monitoring_observations_available": False,
        "acquisition_dates_from_names": ["2025-09-18"],
        "official_metadata_contract": {
            "square_wave_periods_s": [1, 10, 100],
            "frequency_range_hz": [0.01, 100],
            "sampling_rate_hz": 2000,
            "successive_current_injection_depths": 8,
            "simultaneous_potential_dipoles_per_injection": 7,
            "raw_time_series": True,
        },
        "observation_values_read": False,
        "formal_test_endpoints_inspected": False,
        "gate_impact": {
            "observation_contract_passed": False,
            "reason": "payload geometry and uncertainty are not established by the response-blind inventory",
            "cluster_gate_passed": False,
            "power_gate_passed": False,
            "reason_power": "one site and one dated acquisition package",
        },
        "test_unseal_count": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mat": len(mat_names), "code": len(matlab_names), "values_read": False}))


if __name__ == "__main__":
    main()
