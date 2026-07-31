#!/usr/bin/env python
"""Acquire the sealed western Arkansas magnetic flight-line CSV."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEM = "6446a248d34ee8d4adec696f"
DOI = "10.5066/P9RC44VO"
DATA = ROOT / "validation/wp8/data/western-arkansas-magnetic-v1"
NAMES = (
    "AR21F1047_USGS_AR-WestCentral_MagneticLineData.csv",
    "AR21F0147_USGS_AR-WestCentral_MagneticChannelNames.csv",
)


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    api = f"https://www.sciencebase.gov/catalog/item/{ITEM}?format=json"
    with urllib.request.urlopen(api, timeout=60) as response:
        record_bytes = response.read()
    record = json.loads(record_bytes)
    selected = {item["name"]: item for item in record["files"] if item["name"] in NAMES}
    if set(selected) != set(NAMES):
        raise RuntimeError("western Arkansas files not uniquely resolved")
    members = []
    for name in NAMES:
        remote = selected[name]
        target = DATA / name
        expected_size = int(remote["size"])
        if not target.is_file() or target.stat().st_size != expected_size:
            existing = target.stat().st_size if target.is_file() else 0
            headers = {"User-Agent": "GeoDeepBayes-WP8 sealed acquisition"}
            if 0 < existing < expected_size:
                headers["Range"] = f"bytes={existing}-"
            request = urllib.request.Request(
                remote["downloadUri"],
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                resumed = existing > 0 and response.status == 206
                mode = "ab" if resumed else "wb"
                downloaded = existing if resumed else 0
                next_report = ((downloaded // (256 * 1024 * 1024)) + 1) * 256 * 1024 * 1024
                print(
                    json.dumps(
                        {
                            "file": name,
                            "existing_bytes": existing,
                            "http_status": response.status,
                            "mode": "resume" if resumed else "restart",
                        }
                    ),
                    flush=True,
                )
                output = target.open(mode)
                try:
                    while True:
                        block = response.read(8 * 1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        downloaded += len(block)
                        if downloaded >= next_report:
                            print(json.dumps({"file": name, "downloaded_bytes": downloaded}), flush=True)
                            next_report += 256 * 1024 * 1024
                finally:
                    output.close()
        expected_md5 = remote["checksum"]["value"]
        if target.stat().st_size != remote["size"] or digest(target, "md5") != expected_md5:
            raise RuntimeError(f"provider size/checksum mismatch: {name}")
        members.append(
            {
                "path": name,
                "bytes": target.stat().st_size,
                "md5": expected_md5,
                "sha256": digest(target, "sha256"),
                "provider_url": remote["downloadUri"],
            }
        )
    source = DATA / "source-record.json"
    source.write_bytes(record_bytes)
    members.append(
        {
            "path": source.name,
            "bytes": source.stat().st_size,
            "sha256": digest(source, "sha256"),
            "provider_url": api,
        }
    )
    manifest = {
        "schema_version": "wp8-western-arkansas-magnetic-raw-freeze-v1",
        "doi": DOI,
        "sciencebase_item": ITEM,
        "license": "USGS public domain",
        "response_values_interpreted_during_acquisition": 0,
        "members": members,
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (*[DATA / name for name in NAMES], source, manifest_path):
        os.chmod(path, 0o444)
    print(json.dumps({"doi": DOI, "members": len(members), "status": "frozen"}))


if __name__ == "__main__":
    main()
