#!/usr/bin/env python
"""Freeze an outcome-blind TDIP date split from ZIP member names only."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "_bmad-output/planning-artifacts/research/open-data/dc_ip/Zenodo_Reykjanes_ERT_IP_monitoring_2025/ERT_IP_Reykjanes.zip"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/tdip-date-split.json"
EXPOSED = {"20221023"}
UNPAIRED = {"20230705"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    pattern = re.compile(r"/([NR])_(\d{8})\.csv$", re.I)
    by_date: dict[str, dict[str, dict[str, object]]] = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for info in archive.infolist():
            match = pattern.search(info.filename)
            if match:
                kind, date = match.groups()
                by_date.setdefault(date, {})[kind.upper()] = {
                    "path": info.filename,
                    "bytes": info.file_size,
                    "crc32": f"{info.CRC:08x}",
                }
    paired = sorted(date for date, members in by_date.items() if set(members) == {"N", "R"})
    eligible = [date for date in paired if date not in EXPOSED]
    # Chronological, outcome-blind allocation. The ten-day buffer separates
    # training from calibration; the formal test is the final 223 paired dates.
    # The initial training-only diagnostic estimated a 17-day temporal
    # correlation length. Preserve the date seal but enlarge the outcome-blind
    # buffer to at least that length before deriving independent time blocks.
    counts = {"train": 79, "buffer": 17, "calibration": 50, "test": 223}
    assert sum(counts.values()) == len(eligible) == 369
    cursor = 0
    partitions = {}
    for name, count in counts.items():
        selected = eligible[cursor : cursor + count]
        partitions[name] = selected
        cursor += count
    payload = {
        "schema_version": "wp8-tdip-date-split-v1",
        "selection_inputs": "ZIP member names, sizes and CRC only; no observation values",
        "archive_sha256": sha256(ARCHIVE),
        "cluster_unit": "acquisition_date",
        "observation_unit": "acquisition_date",
        "power_cluster_unit": "non-overlapping temporal block derived from the training-only correlation length",
        "normal_and_reciprocal_are_repeated_measurements_not_clusters": True,
        "time_windows_are_repeated_channels_not_clusters": True,
        "buffer_policy": "at least the 17-day training-only temporal correlation length",
        "all_named_dates": len(by_date),
        "paired_dates": len(paired),
        "excluded": {
            "endpoint_exposed": sorted(EXPOSED),
            "missing_reciprocal": sorted(UNPAIRED),
        },
        "counts": counts,
        "partitions": partitions,
        "members": by_date,
        "calibration_members_interpreted": 0,
        "test_members_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "excluded": payload["excluded"]}))


if __name__ == "__main__":
    main()
