#!/usr/bin/env python
"""Acquire the CC0 USGS Great Basin pluton-property dataset as sealed bytes."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/usgs-pluton-properties-v1"
ITEM_ID = "5e4db643e4b0ff554f6eab30"
API = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
NAMES = {"readme.txt", "pluton_data.csv", "data_dictionary.csv", "rock_dictionary.csv", "metadata.xml"}


def request(url: str) -> bytes:
    query = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 feasibility audit (public USGS data)"}
    )
    with urllib.request.urlopen(query, timeout=60) as response:
        return response.read()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    record = json.loads(request(API))
    selected = [item for item in record["files"] if item["name"] in NAMES]
    if {item["name"] for item in selected} != NAMES:
        raise RuntimeError("ScienceBase member inventory drift")
    files = []
    for item in selected:
        path = OUTPUT / item["name"]
        if not path.exists() or path.stat().st_size != item["size"]:
            path.write_bytes(request(item["url"]))
        files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest(path)})
        os.chmod(path, 0o444)
    manifest = {
        "schema_version": "wp8-usgs-pluton-properties-raw-manifest-v1",
        "sciencebase_item_id": ITEM_ID,
        "doi": "10.5066/P927X64D",
        "license": "CC0-1.0",
        "files": files,
        "response_values_interpreted": False,
    }
    (OUTPUT / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"files": len(files), "bytes": sum(x["bytes"] for x in files)}, indent=2))


if __name__ == "__main__":
    main()
