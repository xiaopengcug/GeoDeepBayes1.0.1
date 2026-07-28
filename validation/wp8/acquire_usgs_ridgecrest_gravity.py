#!/usr/bin/env python
"""Freeze the CC0 USGS Ridgecrest gravity and property data release."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-ridgecrest-gravity-v1"
ITEM = "67d454efd34e1acf3979d73f"
ITEM_URL = f"https://www.sciencebase.gov/catalog/item/{ITEM}?format=json"


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    value.update(path.read_bytes())
    return value.hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 Ridgecrest audit"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    item_bytes = fetch(ITEM_URL)
    (DATA / "sciencebase-item.json").write_bytes(item_bytes)
    item = json.loads(item_bytes)
    members = []
    for resource in item["files"]:
        path = DATA / resource["name"]
        path.write_bytes(fetch(resource["url"]))
        checksum = resource.get("checksum", {})
        if checksum.get("type", "").lower() == "md5":
            if digest(path, "md5") != checksum["value"]:
                raise RuntimeError(f"provider checksum mismatch: {path.name}")
        members.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest(path),
                "provider_checksum": checksum,
                "source_url": resource["url"],
            }
        )
    manifest = {
        "dataset": "USGS Ridgecrest gravity and physical property data",
        "sciencebase_item": ITEM,
        "doi": "10.5066/P1VG6MPK",
        "license": "CC0-1.0",
        "members": members,
        "response_values_interpreted_during_acquisition": 0,
    }
    (DATA / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
