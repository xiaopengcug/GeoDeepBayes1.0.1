#!/usr/bin/env python
"""Freeze USGS Data Series 901 Mount St. Helens CSAMT EDI/GPS files."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-mount-st-helens-csamt-v1"
BASE = "https://pubs.usgs.gov/ds/0901/"
STATIONS = [
    "MSH-1001", "MSH-1002", "MSH-1003", "MSH-1004", "MSH-1102",
    "MSH-1103", "MSH-1104", "MSH-1105", "MSH-1106", "MSH-1107",
    "MSH-1108", "MSH-1109", "MSH-1110",
]
RESOURCES = {
    "data_acquisition.html": BASE + "data_acquisition.html",
    "gps_data.html": BASE + "gps_data.html",
    "ds901_GPScoordinates.xls": BASE + "ds901_GPScoordinates.xls",
    **{
        f"{station}.edi": BASE
        + urllib.parse.quote(f"edi data/{station}.edi", safe="/:")
        for station in STATIONS
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for name, url in RESOURCES.items():
        path = DATA / name
        request = urllib.request.Request(
            url, headers={"User-Agent": "GeoDeepBayes-WP8 USGS DS901 freeze"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            last_modified = response.headers.get("Last-Modified")
            etag = response.headers.get("ETag")
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(payload)
        members.append(
            {
                "path": name,
                "bytes": len(payload),
                "sha256": sha256(path),
                "source_url": url,
                "last_modified": last_modified,
                "etag": etag,
            }
        )
    manifest = {
        "schema_version": "wp8-usgs-mount-st-helens-csamt-raw-v1",
        "record": "USGS Data Series 901",
        "title": "Mount St. Helens CSAMT Data and Inversions",
        "license": "U.S. Geological Survey public domain",
        "selection_is_response_blind": True,
        "station_count": len(STATIONS),
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    manifest_path = DATA / "raw-manifest.json"
    if manifest_path.exists():
        os.chmod(manifest_path, 0o644)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    for path in [manifest_path, *(DATA / name for name in RESOURCES)]:
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(members), "bytes": manifest["total_bytes"]}))


if __name__ == "__main__":
    main()
