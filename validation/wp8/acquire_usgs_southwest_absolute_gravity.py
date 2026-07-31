#!/usr/bin/env python
"""Freeze the USGS Southwest Gravity Program absolute-gravity database."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-southwest-absolute-gravity-v1"
ITEM = "60c0f325d34e86b938940a93"
ITEM_URL = f"https://www.sciencebase.gov/catalog/item/{ITEM}?format=json"


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 gravity audit"}
    )
    for delay in (0, 2, 5):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception:
            pass
    with tempfile.NamedTemporaryFile(delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        subprocess.run(
            ["curl.exe", "-L", "--fail", "--retry", "5", "-o", str(temporary_path), url],
            check=True,
        )
        return temporary_path.read_bytes()
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    item_bytes = fetch(ITEM_URL)
    (DATA / "sciencebase-item.json").write_bytes(item_bytes)
    item = json.loads(item_bytes)
    members = []
    for resource in item["files"]:
        path = DATA / resource["name"]
        path.write_bytes(fetch(resource["url"]))
        expected = resource.get("checksum", {})
        if expected.get("type", "").lower() == "md5":
            actual_md5 = digest(path, "md5")
            if actual_md5 != expected["value"]:
                raise RuntimeError(f"MD5 mismatch: {path.name}")
        members.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest(path),
                "source_url": resource["url"],
                "provider_checksum": expected,
            }
        )
    manifest = {
        "dataset": "USGS Southwest Gravity Program Absolute-Gravity Database",
        "sciencebase_item": ITEM,
        "landing_page": (
            "https://www.usgs.gov/data/southwest-gravity-program-"
            "absolute-gravity-database-updated-2025-12-19"
        ),
        "doi": "10.5066/P984HN6J",
        "license": "CC0-1.0",
        "item_snapshot": "sciencebase-item.json",
        "members": members,
    }
    (DATA / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
