#!/usr/bin/env python
"""Acquire the USGS western U.S./Alaska rock-property database as sealed bytes."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/usgs-rock-properties-v1"
ITEM_ID = "60356a96d34eb120311748e8"
API = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
NAMES = {
    "readme.txt",
    "rock_property_data.csv",
    "data_dictionary.csv",
    "rock_dictionary.csv",
    "metadata.xml",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 feasibility audit (public USGS data)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    record = json.loads(get(API))
    selected = [item for item in record["files"] if item["name"] in NAMES]
    if {item["name"] for item in selected} != NAMES:
        raise RuntimeError("ScienceBase member inventory drift")
    files = []
    for item in selected:
        path = OUTPUT / item["name"]
        if not path.exists() or path.stat().st_size != item["size"]:
            path.write_bytes(get(item["url"]))
        files.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "expected_bytes": item["size"],
                "sha256": sha256(path),
                "source_url": item["url"],
            }
        )
        os.chmod(path, 0o444)
    manifest = {
        "schema_version": "wp8-usgs-rock-properties-raw-manifest-v1",
        "sciencebase_item_id": ITEM_ID,
        "title": record["title"],
        "files": files,
        "response_values_interpreted": False,
    }
    (OUTPUT / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"files": len(files), "bytes": sum(x["bytes"] for x in files)}, indent=2))


if __name__ == "__main__":
    main()
