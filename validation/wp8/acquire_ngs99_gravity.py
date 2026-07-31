#!/usr/bin/env python
"""Acquire NOAA/NCEI NGS99 gravity bytes and design documentation."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/ngs99-gravity-v1"
BASE = "https://www.ngdc.noaa.gov/mgg/gravity/1999/data/regional/ngs99"
FILES = ("ngs99_ascii.zip", "ngs99.fmt", "ngs99.hdr", "ngs99.txt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str) -> Path:
    destination = OUTPUT / name
    if destination.exists() and destination.stat().st_size:
        return destination
    request = urllib.request.Request(
        f"{BASE}/{name}",
        headers={"User-Agent": "GeoDeepBayes-WP8 feasibility audit (public NOAA data)"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    return destination


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paths = [download(name) for name in FILES]
    entries = []
    for path in paths:
        entry = {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                entry["members"] = [
                    {
                        "name": item.filename,
                        "uncompressed_bytes": item.file_size,
                        "compressed_bytes": item.compress_size,
                        "crc32": f"{item.CRC:08x}",
                    }
                    for item in archive.infolist()
                    if not item.is_dir()
                ]
        entries.append(entry)
        os.chmod(path, 0o444)
    manifest = {
        "schema_version": "wp8-ngs99-gravity-raw-manifest-v1",
        "source_base_url": BASE,
        "publisher": "NOAA National Centers for Environmental Information",
        "record_count_catalogued": 1_633_499,
        "files": entries,
        "response_values_interpreted": False,
    }
    (OUTPUT / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(entries, indent=2))


if __name__ == "__main__":
    main()
