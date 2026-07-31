#!/usr/bin/env python
"""Freeze the USGS Upper San Pedro Valley gravity principal facts."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-upper-san-pedro-gravity-v1"
RESOURCES = {
    "landing.html": "https://pubs.usgs.gov/of/2000/of00-138/",
    "appendix-4.html": "https://pubs.usgs.gov/of/2000/of00-138/append_4.htm",
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
            {
                "path": name,
                "bytes": len(payload),
                "sha256": sha256(path),
                "source_url": url,
            }
        )
    manifest = {
        "dataset": "USGS Upper San Pedro Valley gravity principal facts",
        "publication": "USGS Open-File Report 00-138",
        "landing_page": RESOURCES["landing.html"],
        "reuse_basis": "U.S. Geological Survey authored federal government work",
        "members": members,
    }
    (DATA / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
