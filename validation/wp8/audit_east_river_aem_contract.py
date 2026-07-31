#!/usr/bin/env python
"""Audit the public East River AEM instrument and uncertainty contract."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/east-river-aem-v1"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/east-river-aem-contract-readiness.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    manifest_path = RAW / "raw-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["member_count"] != 10 or manifest["observation_response_interpreted"] is not False:
        raise RuntimeError("East River acquisition manifest drift")
    for member in manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha(path) != member["sha256"]:
            raise RuntimeError(f"East River raw member drift: {member['name']}")

    dictionary_path = RAW / "EastRiver2017_DataDictionary_ProcessedAEMData.csv"
    with dictionary_path.open(encoding="utf-8-sig", newline="") as stream:
        dictionary = list(csv.DictReader(stream))
    definitions = {row["Field_Name"]: row for row in dictionary}
    required = {"LINE", "TIMESTAMP", "E_UTM13N", "N_UTM13N", "ELEVATION", "ALT", "NUMDATA", "DATA[i]", "DATASTD[i]"}
    if not required <= definitions.keys():
        raise RuntimeError("processed AEM dictionary contract incomplete")
    if "Standard deviation" not in definitions["DATASTD[i]"]["Definition"]:
        raise RuntimeError("DATASTD semantics drift")
    if "z-component" not in definitions["DATA[i]"]["Definition"].lower():
        raise RuntimeError("receiver-component semantics drift")

    gate_path = RAW / "EastRiver2017_AEMGateTime.csv"
    with gate_path.open(encoding="utf-8-sig", newline="") as stream:
        gates = list(csv.DictReader(stream))
    center_times = [float(row["CENTERTIME"]) for row in gates]
    if len(center_times) != 52 or center_times != sorted(center_times):
        raise RuntimeError("AEM time-gate contract drift")

    report_path = RAW / "EastRiver2017_Geotech_DataReport.pdf"
    reader = PdfReader(report_path)
    pages = {page: reader.pages[page - 1].extract_text() or "" for page in (11, 12, 14, 15, 16, 18)}
    required_phrases = {
        11: ("full receiver-waveform", "concentric-coplanar", "Z-direction"),
        12: ("time measurement", "gates were used", "6.94 to 8254"),
        14: (
            "18.82 m",
            "556",
            "30  Hz",
            "200.58",
            "7.10  ms",
            "Bi-polar trapezoid",
            "Z-Coil diameter: 1.2 m",
            "Effective coil area: 113.04",
        ),
        15: ("complete VTEM", "transfer function"),
        16: ("TDEM 0.1 sec",),
        18: ("stacked using 15 half cycles", "system response correction", "time window binning"),
    }
    missing = {
        page: [phrase for phrase in phrases if phrase.lower() not in pages[page].lower()]
        for page, phrases in required_phrases.items()
    }
    missing = {page: phrases for page, phrases in missing.items() if phrases}
    if missing:
        raise RuntimeError(f"contract phrases missing from protected report: {missing}")

    result = {
        "schema_version": "wp8-east-river-aem-contract-readiness-v1",
        "passed": True,
        "candidate_status": "contract_ready_not_yet_selected",
        "doi": "10.5066/P949ZCZ8",
        "raw_manifest_sha256": sha(manifest_path),
        "report": {
            "path": report_path.name,
            "sha256": sha(report_path),
            "pages_checked": sorted(pages),
        },
        "survey_contract": {
            "system": "VTEM ET serial 40 full receiver-waveform TDEM",
            "geometry": "concentric-coplanar, Z-oriented transmitter and receiver",
            "transmitter_loop_diameter_m": 18.82,
            "transmitter_turns": 2,
            "effective_transmitter_area_m2": 556.0,
            "base_frequency_hz": 30.0,
            "peak_current_a": 200.58,
            "pulse_width_ms": 7.10,
            "waveform": "bipolar trapezoid",
            "peak_dipole_moment_nia": 111538,
            "receiver_coil_diameter_m": 1.2,
            "receiver_turns": 100,
            "effective_receiver_area_m2": 113.04,
            "sampling_seconds": 0.1,
            "stacked_half_cycles": 15,
        },
        "observation_contract": {
            "component": "normalized, primary-field-corrected Z receiver response",
            "units": "V/(m^4*A)",
            "time_gate_count": 52,
            "first_center_time_seconds": center_times[0],
            "last_center_time_seconds": center_times[-1],
            "per_observation_standard_deviation": True,
            "coordinates": "WGS84 UTM zone 13N",
            "altitude_above_ground_m": True,
        },
        "response_values_interpreted": False,
        "formal_cluster_gate_passed": False,
        "formal_power_gate_passed": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "gates": len(center_times), "pages": sorted(pages)}))


if __name__ == "__main__":
    main()
