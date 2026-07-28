#!/usr/bin/env python
"""Freeze two directly downloadable NTGS TDIP training candidates."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ntgs-tdip-training-candidates-v1"
RESOURCES = {
    "kroda-cr2018-0418-geophysics.zip": (
        "https://geoscience.nt.gov.au/gemis/ntgsjspui/bitstream/1/93786/3/"
        "CR2018-0418_Geophysics.zip"
    ),
    "arunta-cr2024-0690-geophysics.zip": (
        "https://geoscience.nt.gov.au/gemis/ntgsjspui/bitstream/1/93651/2/"
        "CR2024-0690_Geophysics.zip"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 NTGS TDIP audit"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except Exception:
        with tempfile.NamedTemporaryFile(delete=False) as temporary:
            path = Path(temporary.name)
        try:
            subprocess.run(
                [
                    "curl.exe",
                    "-L",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "-o",
                    str(path),
                    url,
                ],
                check=True,
            )
            return path.read_bytes()
        finally:
            path.unlink(missing_ok=True)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for name, url in RESOURCES.items():
        path = DATA / name
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(download(url))
        members.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": url,
            }
        )
    manifest = {
        "schema_version": "wp8-ntgs-tdip-training-candidates-v1",
        "source_repository": "NTGS GEMIS open-file minerals exploration reports",
        "report_ids": ["CR2018-0418", "CR2024-0690"],
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "selection_role": "training_candidates_only",
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
