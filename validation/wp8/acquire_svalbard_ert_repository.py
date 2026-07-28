#!/usr/bin/env python
"""Freeze the Ny-Ålesund ERT repository and Zenodo metadata."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/svalbard-ert-repository-v1"
API = "https://zenodo.org/api/records/10260056"


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str) -> tuple[bytes, dict[str, str | None]]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 Svalbard ERT freeze"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read(), {
            "last_modified": response.headers.get("Last-Modified"),
            "etag": response.headers.get("ETag"),
        }


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    metadata_payload, metadata_headers = fetch(API)
    record = json.loads(metadata_payload)
    if len(record["files"]) != 1:
        raise RuntimeError("Zenodo file inventory drift")
    remote = record["files"][0]
    archive_payload, archive_headers = fetch(remote["links"]["self"])
    if len(archive_payload) != remote["size"]:
        raise RuntimeError("Zenodo archive size drift")

    resources = [
        ("zenodo-record.json", API, metadata_payload, metadata_headers),
        ("Repository.zip", remote["links"]["self"], archive_payload, archive_headers),
    ]
    members = []
    for name, url, payload, headers in resources:
        path = DATA / name
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(payload)
        members.append(
            {
                "path": name,
                "bytes": len(payload),
                "sha256": digest(path),
                "source_url": url,
                **headers,
            }
        )
    archive_path = DATA / "Repository.zip"
    provider_md5 = remote["checksum"].split(":", 1)[1]
    if digest(archive_path, "md5") != provider_md5:
        raise RuntimeError("Zenodo provider MD5 mismatch")
    manifest = {
        "schema_version": "wp8-svalbard-ert-repository-raw-v1",
        "doi": "10.5281/zenodo.10260056",
        "resolved_record_id": record["id"],
        "license": record["metadata"]["license"]["id"],
        "provider_md5": provider_md5,
        "selection_is_response_blind": True,
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
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
