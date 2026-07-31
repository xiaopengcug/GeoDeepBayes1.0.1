#!/usr/bin/env python
"""Resumably seal the Texas AIB CSV ZIP from a temporary ScienceBase S3 URL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/texas-aib-magnetic-v1"
TARGET = OUTPUT / "TX_AIB_mag.csv.zip"
PARTIAL = OUTPUT / "TX_AIB_mag.csv.zip.partial"
MANIFEST = OUTPUT / "response-manifest.json"
EXPECTED_BYTES = 4_236_679_294


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str) -> None:
    offset = PARTIAL.stat().st_size if PARTIAL.exists() else 0
    headers = {"User-Agent": "GeoDeepBayes-WP8 sealed public-data acquisition"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=300) as response:
        if offset and response.status != 206:
            raise RuntimeError("server did not honor resume Range; partial retained")
        if not offset and response.status != 200:
            raise RuntimeError(f"unexpected HTTP {response.status}")
        mode = "ab" if offset else "wb"
        with PARTIAL.open(mode) as stream:
            for chunk in iter(lambda: response.read(8 * 1024 * 1024), b""):
                stream.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        required=True,
        help="temporary direct S3 URL obtained after the ScienceBase CAPTCHA",
    )
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if TARGET.exists() and TARGET.stat().st_size == EXPECTED_BYTES:
        pass
    else:
        download(args.url)
        if PARTIAL.stat().st_size != EXPECTED_BYTES:
            raise RuntimeError(
                f"incomplete archive: {PARTIAL.stat().st_size}/{EXPECTED_BYTES} bytes; "
                "rerun with a fresh signed URL to resume"
            )
        PARTIAL.replace(TARGET)
    with zipfile.ZipFile(TARGET) as archive:
        members = [
            {
                "name": item.filename,
                "bytes": item.file_size,
                "compressed_bytes": item.compress_size,
                "crc32": f"{item.CRC:08x}",
            }
            for item in archive.infolist()
        ]
        bad_member = archive.testzip()
    if bad_member is not None:
        raise RuntimeError(f"corrupt ZIP member: {bad_member}")
    os.chmod(TARGET, 0o444)
    payload = {
        "schema_version": "wp8-texas-aib-magnetic-response-manifest-v1",
        "sciencebase_item_id": "69ab5a87b66b01cd2fd12813",
        "doi": "10.5066/P1EOKG6I",
        "archive": {
            "name": TARGET.name,
            "bytes": TARGET.stat().st_size,
            "sha256": sha256(TARGET),
        },
        "members": members,
        "signed_url_persisted": False,
        "member_contents_interpreted": False,
        "response_values_interpreted": False,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"bytes": TARGET.stat().st_size, "members": len(members)}, indent=2))


if __name__ == "__main__":
    main()
