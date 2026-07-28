#!/usr/bin/env python
"""Acquire the USGS Wisconsin statewide gravity archive without parsing values."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/wisconsin-gravity-v1"
ARCHIVE = OUTPUT / "wi_gravity_state.zip"
MANIFEST = OUTPUT / "raw-manifest.json"
URL = "https://pubs.usgs.gov/of/2003/of03-157/Data/wi_gravity_state.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not ARCHIVE.exists():
        request = urllib.request.Request(
            URL,
            headers={"User-Agent": "GeoDeepBayes-WP8 feasibility audit (public USGS data)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, ARCHIVE.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
    with zipfile.ZipFile(ARCHIVE) as archive:
        members = [
            {
                "name": item.filename,
                "uncompressed_bytes": item.file_size,
                "compressed_bytes": item.compress_size,
                "crc32": f"{item.CRC:08x}",
            }
            for item in archive.infolist()
            if not item.is_dir()
        ]
    result = {
        "schema_version": "wp8-wisconsin-gravity-raw-manifest-v1",
        "source_url": URL,
        "license": "United States Government work; source page distribution terms apply",
        "archive": {
            "path": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
            "bytes": ARCHIVE.stat().st_size,
            "sha256": sha256(ARCHIVE),
            "members": members,
        },
        "response_values_interpreted": False,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.chmod(ARCHIVE, 0o444)
    print(json.dumps(result["archive"], indent=2))


if __name__ == "__main__":
    main()
