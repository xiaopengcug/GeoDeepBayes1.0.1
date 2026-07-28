#!/usr/bin/env python
"""Freeze a whole-raw-line CSAMT split before opening any response member."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
V1 = EVIDENCE / "csamt-candidate-split.json"
OUT = EVIDENCE / "csamt-line-split-v2.json"
SALT = "GeoDeepBayes-WP8-CSAMT-whole-line-v2"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def role(provider: str, member: str) -> str:
    bucket = int(
        hashlib.sha256(f"{SALT}|{provider}|{member}".encode()).hexdigest()[:12],
        16,
    ) % 10
    if bucket < 3:
        return "train"
    if bucket == 3:
        return "buffer"
    if bucket == 4:
        return "calibration"
    return "test"


def main() -> None:
    source = json.loads(V1.read_text(encoding="utf-8"))
    if source["observation_values_read"] is not False:
        raise RuntimeError("v1 CSAMT catalogue is no longer response blind")
    records = []
    for release in source["releases"]:
        provider = release["id"]
        archive_path = release.get("raw_archive_local")
        if not archive_path:
            continue
        archive = ROOT / archive_path
        if not archive.is_file() or sha(archive) != release["raw_archive_sha256"]:
            raise RuntimeError(f"raw archive integrity drift: {provider}")
        for member in release["raw_archive_members_from_central_directory"]:
            records.append(
                {
                    "provider": provider,
                    "archive_path": archive_path,
                    "archive_sha256": release["raw_archive_sha256"],
                    "member": member["path"],
                    "member_bytes": member["bytes"],
                    "member_crc32": member["crc32"],
                    "role": role(provider, member["path"]),
                }
            )
    counts = Counter(record["role"] for record in records)
    provider_counts = {
        provider: dict(
            Counter(
                record["role"]
                for record in records
                if record["provider"] == provider
            )
        )
        for provider in sorted({record["provider"] for record in records})
    }
    result = {
        "schema_version": "wp8-csamt-whole-line-split-v2",
        "source_v1_sha256": sha(V1),
        "selection_unit": "provider raw line member",
        "selection_frozen_before_response_access": True,
        "role_rule": (
            "SHA256(salt|provider|member) modulo 10: 30% train, 10% buffer, "
            "10% calibration, 50% test"
        ),
        "salt_sha256": hashlib.sha256(SALT.encode()).hexdigest(),
        "raw_line_count": len(records),
        "partition_line_counts": dict(counts),
        "provider_partition_line_counts": provider_counts,
        "lines": records,
        "required_test_clusters": 223,
        "line_level_test_cluster_upper_bound": counts["test"],
        "design_cluster_gate_possible": counts["test"] >= 223,
        "training_response_members_opened": 0,
        "calibration_response_members_opened": 0,
        "test_response_members_opened": 0,
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "raw_line_count": len(records),
                "partition_line_counts": dict(counts),
                "provider_partition_line_counts": provider_counts,
                "design_cluster_gate_possible": result[
                    "design_cluster_gate_possible"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
