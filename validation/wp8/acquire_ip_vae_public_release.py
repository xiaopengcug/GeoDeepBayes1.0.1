#!/usr/bin/env python
"""Freeze the archival IP-VAE release and paper source without field responses."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ip-vae-public-release-v1"
RESOURCES = {
    "zenodo-record-v0.0.2.json": "https://zenodo.org/api/records/5165398",
    "ip-vae-v0.0.2.zip": (
        "https://zenodo.org/api/records/5165398/files/"
        "clberube/ip-vae-v0.0.2.zip/content"
    ),
    "arxiv-2107.14796-source.tar": "https://arxiv.org/e-print/2107.14796",
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
            url, headers={"User-Agent": "GeoDeepBayes-WP8 IP-VAE release audit"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except Exception:
            with tempfile.NamedTemporaryFile(delete=False) as temporary:
                temporary_path = Path(temporary.name)
            try:
                subprocess.run(
                    [
                        "curl.exe",
                        "-L",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "-A",
                        "GeoDeepBayes-WP8 IP-VAE release audit",
                        "-o",
                        str(temporary_path),
                        url,
                    ],
                    check=True,
                )
                payload = temporary_path.read_bytes()
            finally:
                temporary_path.unlink(missing_ok=True)
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
            }
        )
    manifest = {
        "schema_version": "wp8-ip-vae-public-release-v1",
        "paper_doi": "10.1190/geo2021-0497.1",
        "arxiv_id": "2107.14796",
        "software_doi": "10.5281/zenodo.5165398",
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "field_response_payloads_downloaded": 0,
        "formal_test_endpoints_inspected": False,
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
