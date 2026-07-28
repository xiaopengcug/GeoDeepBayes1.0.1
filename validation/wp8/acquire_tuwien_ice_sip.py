#!/usr/bin/env python
"""Freeze the TU Wien ice-feature SIP reference dataset response-blind."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/tuwien-ice-sip-v1"
RECORD = "2wx5q-bg153"
API = f"https://researchdata.tuwien.at/api/records/{RECORD}"
FILES = ["01_spectra.zip", "02_time_lapse.zip", "03_imaging.zip"]


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 TU Wien SIP freeze"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        path.write_bytes(response.read())


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    record_path = DATA / "record.json"
    if not record_path.exists():
        fetch(API, record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    entries = record["files"]["entries"]
    members = []
    for name in FILES:
        entry = entries[name]
        path = DATA / name
        if not path.exists():
            fetch(entry["links"]["content"], path)
        provider_md5 = entry["checksum"].removeprefix("md5:")
        if path.stat().st_size != entry["size"] or digest(path, "md5") != provider_md5:
            raise RuntimeError(f"TU Wien SIP integrity drift: {name}")
        members.append(
            {
                "path": name,
                "bytes": entry["size"],
                "provider_md5": provider_md5,
                "sha256": digest(path, "sha256"),
                "source_url": entry["links"]["content"],
            }
        )
    manifest = {
        "schema_version": "wp8-tuwien-ice-sip-raw-v1",
        "doi": "10.48436/2wx5q-bg153",
        "license": "CC BY 4.0",
        "selection_role": "laboratory_solver_reference_only",
        "selection_is_response_blind": True,
        "partition_assignment": "training-only",
        "members": members,
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    target = DATA / "raw-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (record_path, *[DATA / name for name in FILES], target):
        os.chmod(path, 0o444)
    print(json.dumps({"members": 3, "bytes": sum(x["bytes"] for x in members)}))


if __name__ == "__main__":
    main()
