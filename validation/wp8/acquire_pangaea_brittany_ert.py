#!/usr/bin/env python
"""Freeze the response-blind PANGAEA Brittany ERT/possible-TDIP candidate."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/pangaea-brittany-ert-v1"
MANIFEST = DATA / "raw-manifest.json"
DOI = "10.1594/PANGAEA.983365"
METADATA_URL = f"https://doi.pangaea.de/{DOI}?format=textfile"
DOWNLOAD_ROOT = "https://download.pangaea.de/dataset/983365/files"
PROFILES = [f"{valley}_C{number}" for valley in ("TRU", "ANE") for number in range(1, 5)]


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 PANGAEA response-blind freeze"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    path.write_bytes(payload)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    metadata = DATA / "pangaea-metadata.txt"
    fetch(METADATA_URL, metadata)
    metadata_text = metadata.read_text(encoding="utf-8")
    names = []
    for profile in PROFILES:
        names.extend(
            (f"ERT_{profile}_raw_data.dat", f"ERT_{profile}_topo.csv")
        )
    missing = [name for name in names if name not in metadata_text]
    if missing:
        raise RuntimeError(f"PANGAEA member inventory drift: {missing}")

    members = []
    for name in names:
        path = DATA / name
        if not path.exists():
            fetch(f"{DOWNLOAD_ROOT}/{name}", path)
        members.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": f"{DOWNLOAD_ROOT}/{name}",
            }
        )
    manifest = {
        "schema_version": "wp8-pangaea-brittany-ert-raw-v1",
        "doi": DOI,
        "license": "CC BY 4.0",
        "profiles": PROFILES,
        "valleys": ["Trunvel (TRU)", "Kernic/Plouescat (ANE)"],
        "selection_basis": (
            "metadata-only search for anonymously downloadable field ERT/possible "
            "TDIP observations with ABMN geometry, precise electrode coordinates, "
            "and multiple geographically separated acquisition areas"
        ),
        "partition_assignment": "training-only",
        "partition_assignment_precedes_response_read": True,
        "selection_is_response_blind": True,
        "metadata_sha256": sha256(metadata),
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    if MANIFEST.exists():
        os.chmod(MANIFEST, 0o644)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for frozen in (metadata, *[DATA / name for name in names], MANIFEST):
        os.chmod(frozen, 0o444)
    print(json.dumps({"profiles": 8, "members": 16, "bytes": manifest["total_bytes"]}))


if __name__ == "__main__":
    main()
