#!/usr/bin/env python
"""Acquire and freeze the Po River electric-streamer ERT package."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD_ID = "18183049"
DOI = "10.5281/zenodo.18183049"
FILENAME = "Electrical_Tomography_Data.7z"
DATA = ROOT / "validation/wp8/data/po-river-ert-v1"


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    api = f"https://zenodo.org/api/records/{RECORD_ID}"
    with urllib.request.urlopen(api, timeout=60) as response:
        record_bytes = response.read()
    record = json.loads(record_bytes)
    matches = [item for item in record["files"] if item["key"] == FILENAME]
    if len(matches) != 1:
        raise RuntimeError("ERT archive not uniquely resolved")
    remote = matches[0]
    target = DATA / FILENAME
    if not target.is_file():
        with urllib.request.urlopen(remote["links"]["self"], timeout=180) as response:
            target.write_bytes(response.read())
    expected_md5 = remote["checksum"].split(":", 1)[1]
    if target.stat().st_size != remote["size"] or digest(target, "md5") != expected_md5:
        raise RuntimeError("downloaded ERT archive does not match Zenodo")
    source_record = DATA / "source-record.json"
    source_record.write_bytes(record_bytes)
    manifest = {
        "schema_version": "wp8-po-river-ert-raw-freeze-v1",
        "record_id": RECORD_ID,
        "doi": DOI,
        "access_right": record["metadata"]["access_right"],
        "license": record["metadata"]["license"]["id"],
        "collection_description": "4-km streamer, 518 stations, March 2025, seven days",
        "observation_values_interpreted_during_acquisition": 0,
        "members": [
            {
                "path": FILENAME,
                "bytes": target.stat().st_size,
                "md5": digest(target, "md5"),
                "sha256": digest(target, "sha256"),
                "provider_url": remote["links"]["self"],
            },
            {
                "path": source_record.name,
                "bytes": source_record.stat().st_size,
                "sha256": digest(source_record, "sha256"),
                "provider_url": api,
            },
        ],
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (target, source_record, manifest_path):
        os.chmod(path, 0o444)
    print(
        json.dumps(
            {
                "doi": DOI,
                "bytes": target.stat().st_size,
                "sha256": digest(target, "sha256"),
                "license": manifest["license"],
            }
        )
    )


if __name__ == "__main__":
    main()
