#!/usr/bin/env python
"""Freeze a response-blind, acquisition-group TDIP role design."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/zenodo-tdip-field-candidate-v1"
ARCHIVE = DATA / "field_survey.rar"
MANIFEST = DATA / "candidate-manifest.json"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "zenodo-tdip-field-design-v1.json"
)

# Explicit profile-level roles are frozen before extraction or payload access.
# Keeping whole acquisition groups together prevents adjacent waveform records
# from leaking across roles.
ROLE_BY_GROUP = {
    "n12_n13": "train",
    "n7_n6_n1": "train",
    "s2": "buffer",
    "s5_s7_n10": "calibration",
    "s6_s4": "test",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    candidate = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if candidate["response_values_interpreted"] != 0:
        raise RuntimeError("candidate is no longer response-blind")
    if digest(ARCHIVE) != candidate["archive_sha256"]:
        raise RuntimeError("TDIP archive SHA-256 mismatch")

    listing = subprocess.run(
        ["tar", "-tf", str(ARCHIVE)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()
    field_prefix = "field_survey/field_full_waveform_data/"
    counts: Counter[str] = Counter()
    extensions: Counter[str] = Counter()
    for member in listing:
        suffix = member.removeprefix(field_prefix)
        if member.startswith(field_prefix) and "/" in suffix:
            group = suffix.split("/", 1)[0]
            if group in ROLE_BY_GROUP:
                counts[group] += 1
        extensions[Path(member).suffix.lower() or "<none>"] += 1

    missing = set(ROLE_BY_GROUP) - set(counts)
    if missing:
        raise RuntimeError(f"missing frozen acquisition groups: {sorted(missing)}")
    groups = [
        {
            "acquisition_group": group,
            "role": ROLE_BY_GROUP[group],
            "archive_member_count": counts[group],
        }
        for group in ROLE_BY_GROUP
    ]
    role_counts = Counter(ROLE_BY_GROUP.values())
    result = {
        "schema_version": "wp8-zenodo-tdip-field-design-v1",
        "source": candidate["source"],
        "doi": candidate["doi"],
        "license": candidate["license"],
        "archive_sha256": candidate["archive_sha256"],
        "archive_member_count": len(listing),
        "archive_extension_counts": dict(extensions.most_common()),
        "selection_unit": "whole field acquisition group",
        "selection_frozen_before_payload_extraction": True,
        "selection_frozen_before_response_access": True,
        "role_rule": "explicit immutable acquisition-group assignment in script v1",
        "groups": groups,
        "partition_group_counts": dict(role_counts),
        "required_test_clusters": 223,
        "profile_level_test_cluster_upper_bound": role_counts["test"],
        "profile_level_power_gate_possible": role_counts["test"] >= 223,
        "archive_members_listed": True,
        "archive_members_extracted": False,
        "response_payloads_opened": 0,
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "next_step": (
            "extract training group only; derive waveform schema and spatial "
            "correlation without opening buffer/calibration/test payloads"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "archive_member_count": len(listing),
                "groups": groups,
                "profile_level_power_gate_possible": False,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
