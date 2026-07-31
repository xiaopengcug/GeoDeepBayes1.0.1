#!/usr/bin/env python
"""Response-blind observation-contract audit for western Arkansas magnetics."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/western-arkansas-magnetic-v1"
MANIFEST = DATA / "raw-manifest.json"
DICTIONARY = DATA / "AR21F0147_USGS_AR-WestCentral_MagneticChannelNames.csv"
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/western-arkansas-magnetic-design-split.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/western-arkansas-magnetic-contract-readiness.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    members = {item["path"]: item for item in manifest["members"]}
    checks = {}
    for name, member in members.items():
        path = DATA / name
        checks[name] = (
            path.is_file()
            and path.stat().st_size == member["bytes"]
            and sha(path) == member["sha256"]
        )
    with DICTIONARY.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        rows = list(csv.reader(stream))
    channels = {row[0]: row[1:] for row in rows if row and row[0]}
    groups = {
        "identity": {"line", "flt", "date"},
        "coordinates": {"x", "y", "z", "Lon", "Lat"},
        "height_topography": {"Radar_final", "DTM_final", "topodig"},
        "base_station": {"Baseao", "Basea", "Basebo", "Baseb"},
        "vector_fluxgate": {"mfluxX", "mfluxY", "mfluxZ"},
        "processing_corrections": {"drift_LF", "coralt", "corlvl", "cormicro", "IGRF"},
        "response": {"magres"},
    }
    group_checks = {name: required <= channels.keys() for name, required in groups.items()}
    result = {
        "schema_version": "wp8-western-arkansas-magnetic-contract-readiness-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "design_split_sha256": sha(SPLIT),
        "member_integrity": checks,
        "license": manifest["license"],
        "response_values_interpreted_by_contract_audit": 0,
        "channel_groups": {
            name: {"required": sorted(required), "present": group_checks[name]}
            for name, required in groups.items()
        },
        "line_and_flight_identity_passed": group_checks["identity"],
        "position_height_topography_passed": (
            group_checks["coordinates"] and group_checks["height_topography"]
        ),
        "field_processing_trace_passed": (
            group_checks["base_station"] and group_checks["processing_corrections"]
        ),
        "vector_measurement_channels_present": group_checks["vector_fluxgate"],
        "remanence_boundary": (
            "fluxgate X/Y/Z are measured airborne field components and are not "
            "treated as a rock-remanence direction prior; the frozen training-only "
            "MagIC NRM prior remains the remanence source"
        ),
        "per_observation_uncertainty": {
            "present": False,
            "reason": (
                "the released line-data dictionary contains corrections and raw/"
                "processed channels but no standard-deviation, crossover-error, "
                "or per-observation uncertainty column"
            ),
        },
        "observation_contract_passed": (
            all(checks.values())
            and all(group_checks.values())
            and manifest["license"] == "USGS public domain"
        ),
        "formal_uncertainty_model_ready": False,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "members_valid": all(checks.values()),
                "contract_passed": result["observation_contract_passed"],
                "uncertainty_ready": result["formal_uncertainty_model_ready"],
            }
        )
    )


if __name__ == "__main__":
    main()
