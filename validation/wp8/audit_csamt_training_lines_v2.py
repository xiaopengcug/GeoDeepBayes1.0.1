#!/usr/bin/env python
"""Audit source/receiver fields in whole-line CSAMT training members."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/csamt-consortium-line-split-v2/training-only"
MANIFEST = DATA / "training-manifest.json"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
OUT = EVIDENCE / "csamt-training-line-contract-v2.json"

MEASUREMENT = re.compile(
    r"^\s*(?P<frequency>[0-9.]+)\s+Hz\s+"
    r"(?P<cycles>\d+)\s+Cyc\s+Tx Curr\s+(?P<current>[0-9.]+)\s*$"
)
TX_ID = re.compile(r"\bTX ID\s+(?P<id>\S+)")
COMPONENT = re.compile(r"^\s*\d+\s+(?P<component>Ex|Hy)\b")


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["extracted_roles"] != ["train"]:
        raise RuntimeError("CSAMT extraction is not training-only")
    records = []
    all_frequencies = set()
    all_currents = []
    all_components = set()
    for member in manifest["members"]:
        path = DATA / member["path"]
        if sha(path) != member["sha256"]:
            raise RuntimeError(f"training member integrity drift: {path}")
        frequencies = set()
        currents = []
        cycles = set()
        source_ids = set()
        components = set()
        measurement_blocks = 0
        for line in path.read_text(encoding="latin-1", errors="replace").splitlines():
            match = MEASUREMENT.match(line)
            if match:
                measurement_blocks += 1
                frequencies.add(float(match["frequency"]))
                currents.append(float(match["current"]))
                cycles.add(int(match["cycles"]))
            identifier = TX_ID.search(line)
            if identifier:
                source_ids.add(identifier["id"])
            component = COMPONENT.match(line)
            if component:
                components.add(component["component"])
        all_frequencies.update(frequencies)
        all_currents.extend(currents)
        all_components.update(components)
        records.append(
            {
                "provider": member["provider"],
                "path": member["path"],
                "sha256": member["sha256"],
                "measurement_blocks": measurement_blocks,
                "frequencies_hz": sorted(frequencies),
                "cycle_counts": sorted(cycles),
                "transmitter_current_range": (
                    [min(currents), max(currents)] if currents else None
                ),
                "transmitter_ids": sorted(source_ids),
                "components": sorted(components),
            }
        )
    result = {
        "schema_version": "wp8-csamt-training-line-contract-v2",
        "training_manifest_sha256": sha(MANIFEST),
        "training_line_count": len(records),
        "records": records,
        "frequency_count": len(all_frequencies),
        "frequency_range_hz": [
            min(all_frequencies),
            max(all_frequencies),
        ],
        "transmitter_current_range": [min(all_currents), max(all_currents)],
        "components": sorted(all_components),
        "receiver_electric_dipole_length_m": 100,
        "receiver_channel_contract": "five Ex channels plus one Hy channel",
        "transmitter_identifier_present": True,
        "transmitter_current_present": True,
        "frequency_and_cycle_count_present": True,
        "exact_transmitter_endpoints_present": False,
        "transmitter_orientation_present": False,
        "transmitter_waveform_samples_present": False,
        "official_report_declared_transmitter_dipole_length_m": 1000,
        "official_report_declared_source_receiver_distance_km": [5, 15],
        "formal_finite_source_observation_contract_ready": False,
        "line_level_test_cluster_upper_bound": 14,
        "required_test_clusters": 223,
        "cluster_gate_passed": False,
        "paired_crps_effect_size_available": False,
        "power_gate_passed": False,
        "buffer_response_members_opened": 0,
        "calibration_response_members_opened": 0,
        "test_response_members_opened": 0,
        "test_unseal_count": 0,
        "conclusion": (
            "Training raw lines provide transmitter IDs/current, frequency, "
            "cycle count and Ex/Hy receiver observations. Exact transmitter "
            "endpoints, orientation and waveform samples remain absent, and "
            "only 14 whole-line test candidates exist."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_lines": len(records),
                "frequency_count": len(all_frequencies),
                "frequency_range_hz": result["frequency_range_hz"],
                "transmitter_current_range": result[
                    "transmitter_current_range"
                ],
                "components": result["components"],
                "formal_contract_ready": False,
                "cluster_gate_passed": False,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
