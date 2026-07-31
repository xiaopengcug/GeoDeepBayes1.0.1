#!/usr/bin/env python
"""Freeze the USGS Sierra Nevada gravity table without interpreting values."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/sierra-nevada-gravity-v1"
ITEM_ID = "65b2a230d34e36a390452f13"
ITEM_URL = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
NAMES = {"sierra_nevada_gravity.csv", "sierra_nevada_metadata.xml"}


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str, target: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 public-data freeze"}
    )
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(request, timeout=120) as response, partial.open(
        "wb"
    ) as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            output.write(block)
    partial.replace(target)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ITEM_URL, timeout=60) as response:
        item_bytes = response.read()
    item_path = DATA / "sciencebase-item.json"
    item_path.write_bytes(item_bytes)
    item = json.loads(item_bytes)
    selected = {member["name"]: member for member in item["files"] if member["name"] in NAMES}
    if set(selected) != NAMES:
        raise RuntimeError("Sierra Nevada ScienceBase member set drift")
    members = []
    for name in sorted(NAMES):
        declaration = selected[name]
        target = DATA / name
        if not target.is_file():
            fetch(declaration["downloadUri"], target)
        expected_md5 = declaration["checksum"]["value"]
        if (
            target.stat().st_size != declaration["size"]
            or digest(target, "md5") != expected_md5
        ):
            raise RuntimeError(f"Sierra Nevada integrity drift: {name}")
        members.append(
            {
                "path": name,
                "bytes": target.stat().st_size,
                "md5": expected_md5,
                "sha256": digest(target, "sha256"),
                "provider_url": declaration["downloadUri"],
            }
        )
    manifest = {
        "schema_version": "wp8-sierra-nevada-gravity-raw-freeze-v1",
        "sciencebase_item_id": ITEM_ID,
        "sciencebase_item_url": ITEM_URL,
        "doi": "10.5066/P13KZVHQ",
        "license": "CC0 1.0 Universal",
        "selection_basis": (
            "official metadata reports nearly 29,000 gravity stations, complete "
            "Bouguer/isostatic anomalies, 2012-2023 USGS measurements and 21 "
            "documented legacy sources"
        ),
        "response_values_interpreted_during_acquisition": 0,
        "members": members,
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for member in members:
        os.chmod(DATA / member["path"], 0o444)
    os.chmod(item_path, 0o444)
    os.chmod(manifest_path, 0o444)
    print(
        json.dumps(
            {
                "members": len(members),
                "bytes": sum(member["bytes"] for member in members),
                "response_values_interpreted": 0,
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
