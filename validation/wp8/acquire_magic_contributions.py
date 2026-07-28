#!/usr/bin/env python
"""Acquire a sealed batch of public MagIC contributions without reading response tables."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/magic-contributions-v1"
URL = (
    "https://api.earthref.org/v1/MagIC/download"
    "?query=%2A&n_max_contributions=100&only_latest=true"
)
ARCHIVE = OUTPUT / "magic-latest-100.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def acquire() -> None:
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "GeoDeepBayes-WP8 public-data feasibility audit"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        if response.status != 200:
            raise RuntimeError(f"MagIC API returned HTTP {response.status}")
        ARCHIVE.write_bytes(response.read())


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not ARCHIVE.exists() or ARCHIVE.stat().st_size == 0:
        acquire()
    with zipfile.ZipFile(ARCHIVE) as archive:
        members = [
            {
                "name": item.filename,
                "bytes": item.file_size,
                "compressed_bytes": item.compress_size,
                "crc32": f"{item.CRC:08x}",
                "is_directory": item.is_dir(),
            }
            for item in archive.infolist()
        ]
        bad_member = archive.testzip()
    if bad_member is not None:
        raise RuntimeError(f"corrupt ZIP member: {bad_member}")
    os.chmod(ARCHIVE, 0o444)
    manifest = {
        "schema_version": "wp8-magic-raw-manifest-v1",
        "source_url": URL,
        "archive": {
            "name": ARCHIVE.name,
            "bytes": ARCHIVE.stat().st_size,
            "sha256": sha256(ARCHIVE),
        },
        "members": members,
        "excluded_contribution_ids": [20710],
        "exclusion_reason": (
            "response measurement values were exposed before contribution-level split"
        ),
        "member_contents_interpreted": False,
        "response_values_interpreted": False,
    }
    (OUTPUT / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "archive_bytes": ARCHIVE.stat().st_size,
                "members": len(members),
                "excluded_contribution_ids": [20710],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
