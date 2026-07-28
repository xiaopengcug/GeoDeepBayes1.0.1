#!/usr/bin/env python
"""Freeze the CC0 USGS Krause Springs reciprocal ERT contract candidate."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-krause-ert-v1"
MANIFEST = DATA / "raw-manifest.json"
ITEM_ID = "61804cb1d34e9f2789e01bce"
ITEM_URL = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
NAMES = {
    "Res2dinv_Input_Files.zip",
    "Electrical_Restivity_Tomography_Data.csv",
    "GPS_Data.csv",
    "Krause_Springs_Geophysics_Metadata.xml",
}


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 USGS Krause ERT freeze"}
    )
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open(
        "wb"
    ) as target:
        while block := response.read(1024 * 1024):
            target.write(block)
    temporary.replace(path)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ITEM_URL, timeout=60) as response:
        item_bytes = response.read()
    item_path = DATA / "sciencebase-item.json"
    item_path.write_bytes(item_bytes)
    item = json.loads(item_bytes)
    files = {entry["name"]: entry for entry in item["files"]}
    if not NAMES <= files.keys():
        raise RuntimeError("USGS Krause ERT file inventory drift")
    members = []
    for name in sorted(NAMES):
        entry = files[name]
        path = DATA / name
        if not path.exists():
            download(entry["downloadUri"], path)
        if (
            path.stat().st_size != entry["size"]
            or digest(path, "md5") != entry["checksum"]["value"]
        ):
            raise RuntimeError(f"USGS Krause ERT integrity drift: {name}")
        members.append(
            {
                "path": name,
                "bytes": entry["size"],
                "provider_md5": entry["checksum"]["value"],
                "sha256": digest(path, "sha256"),
                "source_url": entry["downloadUri"],
            }
        )
    manifest = {
        "schema_version": "wp8-usgs-krause-ert-raw-v1",
        "sciencebase_item_id": ITEM_ID,
        "doi": "10.5066/P91Z1HKN",
        "license": "CC0 1.0 Universal / U.S. public domain",
        "selection_basis": (
            "metadata-only contract search: reciprocal Schlumberger ERT, "
            "electrode GPS, topography and public inversion inputs"
        ),
        "selection_is_response_blind": True,
        "sciencebase_item_sha256": digest(item_path, "sha256"),
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    if MANIFEST.exists():
        os.chmod(MANIFEST, 0o644)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in [item_path, MANIFEST, *(DATA / name for name in NAMES)]:
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(members), "bytes": manifest["total_bytes"]}))


if __name__ == "__main__":
    main()
