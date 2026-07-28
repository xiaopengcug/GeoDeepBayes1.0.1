#!/usr/bin/env python
"""Quarantine the whole macroblock affected by an accidental two-row preview."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
V1 = EVIDENCE / "po-river-dc-streamer-design-v1.json"
OUT = EVIDENCE / "po-river-dc-streamer-design-v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    design = json.loads(V1.read_text(encoding="utf-8"))
    affected_macroblock = 0
    affected_stations = list(range(1, 9))
    roles = dict(design["station_roles"])
    if any(roles[str(station)] != "test" for station in affected_stations):
        raise RuntimeError("exposure quarantine does not match frozen v1 roles")
    for station in affected_stations:
        roles[str(station)] = "quarantine_response_exposed"
    blocks = [dict(block) for block in design["macroblocks"]]
    blocks[affected_macroblock]["role"] = "quarantine_response_exposed"
    counts = {
        role: sum(value == role for value in roles.values())
        for role in (
            "train",
            "buffer",
            "calibration",
            "test",
            "quarantine_response_exposed",
        )
    }
    output = {
        **design,
        "schema_version": "wp8-po-river-dc-streamer-design-v2",
        "supersedes_design_sha256": sha(V1),
        "supersession_reason": (
            "A header-inspection command printed the header plus the first "
            "two observation rows. The entire containing macroblock is "
            "quarantined without using either value for selection."
        ),
        "exposure_incident": {
            "affected_macroblock": affected_macroblock,
            "affected_stations": affected_stations,
            "observed_row_numbers": [1, 2],
            "response_values_interpreted": 2,
            "values_retained_in_evidence": False,
            "selection_influenced_by_values": False,
            "disposition": "entire_macroblock_quarantined",
        },
        "macroblocks": blocks,
        "station_roles": roles,
        "partition_counts": counts,
        "design_test_cluster_upper_bound": counts["test"],
        "design_power_gate_possible": counts["test"] >= 223,
        "response_values_interpreted": 2,
        "test_responses_interpreted": 2,
        "test_unseal_count": 1,
        "remaining_test_population_sealed": True,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "quarantined_stations": len(affected_stations),
                "remaining_test_stations": counts["test"],
                "required_test_clusters": 223,
                "remaining_test_population_sealed": True,
                "test_unseal_count": 1,
            }
        )
    )


if __name__ == "__main__":
    main()
