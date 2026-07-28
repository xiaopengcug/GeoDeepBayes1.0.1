#!/usr/bin/env python
"""Freeze CPERS v2 catalogue and data-policy pages without response downloads."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/cpers-public-catalogue-v2"
RESOURCES = {
    "nordicana-d121-v2.html": (
        "https://nordicana.cen.ulaval.ca/en/publication?"
        "doi=10.5885%2F45855XD-DC9883ABD609428B"
    ),
    "cpers-data-policy-v1.3.html": (
        "https://data.permafrostnet.ca/cpers/data_policy.html"
    ),
    "cpers-data-use.html": "https://data.permafrostnet.ca/cpers/data_use.html",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for name, url in RESOURCES.items():
        request = urllib.request.Request(
            url, headers={"User-Agent": "GeoDeepBayes-WP8 CPERS catalogue freeze"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            headers = {
                "last_modified": response.headers.get("Last-Modified"),
                "etag": response.headers.get("ETag"),
            }
        path = DATA / name
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(payload)
        members.append(
            {
                "path": name,
                "bytes": len(payload),
                "sha256": sha256(path),
                "source_url": url,
                **headers,
            }
        )
    manifest = {
        "schema_version": "wp8-cpers-public-catalogue-v2",
        "doi": "10.5885/45855XD-DC9883ABD609428B",
        "selection_is_response_blind": True,
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "measurement_payloads_downloaded": 0,
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    manifest_path = DATA / "raw-manifest.json"
    if manifest_path.exists():
        os.chmod(manifest_path, 0o644)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in [manifest_path, *(DATA / member["path"] for member in members)]:
        os.chmod(path, 0o444)
    print(json.dumps({"members": len(members), "bytes": manifest["total_bytes"]}))


if __name__ == "__main__":
    main()
