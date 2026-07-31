#!/usr/bin/env python
"""Response-blind contract audit for USGS DS901 Mount St. Helens CSAMT."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-mount-st-helens-csamt-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "usgs-mount-st-helens-csamt-contract.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def section_names(text: str) -> set[str]:
    return {
        match.group(1).upper()
        for match in re.finditer(r"(?m)^>\s*([A-Z][A-Z0-9.]+)", text)
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["selection_is_response_blind"] is not True
        or manifest["response_values_interpreted_during_acquisition"] != 0
        or manifest["test_unseal_count"] != 0
    ):
        raise RuntimeError("Mount St. Helens CSAMT acquisition drift")
    station_evidence = []
    for member in manifest["members"]:
        path = RAW / member["path"]
        if (
            path.stat().st_size != member["bytes"]
            or sha256(path) != member["sha256"]
        ):
            raise RuntimeError(f"DS901 member drift: {member['path']}")
        if path.suffix.lower() != ".edi":
            continue
        text = path.read_text(encoding="latin1")
        sections = section_names(text)
        nfreq_match = re.search(r"(?m)^NFREQ=(\d+)", text)
        lat_match = re.search(r"(?m)^LAT=([^\r\n]+)", text)
        lon_match = re.search(r"(?m)^LONG=([^\r\n]+)", text)
        station_evidence.append(
            {
                "station": path.stem,
                "frequency_count_declared": (
                    int(nfreq_match.group(1)) if nfreq_match else None
                ),
                "latitude_declared": lat_match.group(1).strip() if lat_match else None,
                "longitude_declared": lon_match.group(1).strip() if lon_match else None,
                "rho_components_present": all(
                    name in sections for name in ("RHOXY", "RHOYX", "RHOXX", "RHOYY")
                ),
                "phase_components_present": all(
                    name in sections for name in ("PHSXY", "PHSYX", "PHSXX", "PHSYY")
                ),
                "rho_error_arrays_present": all(
                    name in sections
                    for name in ("RHOXY.ERR", "RHOYX.ERR", "RHOXX.ERR", "RHOYY.ERR")
                ),
                "phase_error_arrays_present": all(
                    name in sections
                    for name in ("PHSXY.ERR", "PHSYX.ERR", "PHSXX.ERR", "PHSYY.ERR")
                ),
                "response_values_interpreted": 0,
            }
        )
    controlled = [
        item for item in station_evidence if item["station"] != "MSH-1102"
    ]
    result = {
        "schema_version": "wp8-usgs-mount-st-helens-csamt-contract-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "license_gate_passes": True,
        "station_count": len(station_evidence),
        "controlled_source_station_upper_bound": len(controlled),
        "natural_source_station": "MSH-1102",
        "repeat_station_pairs": [["MSH-1001", "MSH-1002"], ["MSH-1003", "MSH-1004"]],
        "station_edi_contracts": station_evidence,
        "all_edi_have_rho_phase_and_error_arrays": all(
            item["rho_components_present"]
            and item["phase_components_present"]
            and item["rho_error_arrays_present"]
            and item["phase_error_arrays_present"]
            for item in station_evidence
        ),
        "receiver_geometry": {
            "electric_dipoles": "orthogonal 25 m",
            "magnetic_receiver": "high-sensitivity EMI magnetic coils",
            "gps_and_elevation": True,
        },
        "source_contract": {
            "type": "controlled-source inductive transmitter",
            "augmentation_band_hz": [450, 2700],
            "documented_offset": "approximately 250 m west of receiver",
            "exact_source_coordinates_present": False,
            "source_orientation_present": False,
            "source_moment_or_current_present": False,
            "waveform_present": False,
        },
        "available_grounded_finite_line_solver_compatible": False,
        "near_transition_far_classification_possible": False,
        "observation_contract_ready": False,
        "formal_cluster_power_gate_passes": False,
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
        "warning": (
            "The EDI response/error contract is strong, but the approximate "
            "inductive-source placement lacks source moment/orientation/waveform "
            "and is incompatible with the frozen grounded finite-line CSAMT "
            "operator. Twelve controlled-source stations are also far below 223."
        ),
    }
    if len(station_evidence) != 13:
        raise RuntimeError("DS901 EDI station count drift")
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stations": len(station_evidence),
        "controlled": len(controlled),
        "edi_error_contract": result["all_edi_have_rho_phase_and_error_arrays"],
        "source_contract_ready": result["observation_contract_ready"],
    }))


if __name__ == "__main__":
    main()
