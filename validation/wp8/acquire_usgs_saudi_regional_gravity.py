#!/usr/bin/env python
"""Freeze USGS OFR 85-254 and its provider checksum."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-saudi-regional-gravity-v1"
BASE = "https://pubs.usgs.gov/of/1985/0254/"
RESOURCES = {
    "directory-index.html": BASE,
    "report.pdf": BASE + "report.pdf",
    "report.pdf.md5": BASE + "report.pdf.md5",
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for name, url in RESOURCES.items():
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
        path = DATA / name
        path.write_bytes(payload)
        members.append(
            {"path": name, "bytes": len(payload), "sha256": sha256(path), "source_url": url}
        )
    expected_md5 = (DATA / "report.pdf.md5").read_text(encoding="ascii").split()[0].lower()
    actual_md5 = hashlib.md5((DATA / "report.pdf").read_bytes()).hexdigest()
    if actual_md5 != expected_md5:
        raise RuntimeError("provider MD5 mismatch")
    manifest = {
        "dataset": "USGS OFR 85-254 southwestern Saudi Arabia gravity",
        "doi": "10.3133/ofr85254",
        "publication_url": "https://pubs.usgs.gov/publication/ofr85254",
        "provider_md5": expected_md5,
        "members": members,
        "response_values_interpreted_during_acquisition": 0,
    }
    (DATA / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
