#!/usr/bin/env python
"""Freeze the response-blind Zenodo TDIP full-decay field candidate."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/zenodo-tdip-full-decay-v1"
MANIFEST = DATA / "raw-manifest.json"
RECORD_ID = "13329326"
RECORD_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
FIELD_NAME = "field_survey.rar"


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 TDIP field freeze"}
    )
    temporary = path.with_suffix(path.suffix + ".part")
    resume_at = temporary.stat().st_size if temporary.exists() else 0
    if resume_at:
        request.add_header("Range", f"bytes={resume_at}-")
    with urllib.request.urlopen(request, timeout=180) as response:
        mode = "ab" if resume_at and response.status == 206 else "wb"
        with temporary.open(mode) as target:
            while block := response.read(1024 * 1024):
                target.write(block)
    temporary.replace(path)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        RECORD_URL, headers={"User-Agent": "GeoDeepBayes-WP8 TDIP metadata freeze"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        record_bytes = response.read()
    record_path = DATA / "zenodo-record.json"
    record_path.write_bytes(record_bytes)
    record = json.loads(record_bytes)
    files = {entry["key"]: entry for entry in record["files"]}
    if FIELD_NAME not in files:
        raise RuntimeError("Zenodo TDIP field member inventory drift")
    entry = files[FIELD_NAME]
    path = DATA / FIELD_NAME
    if not path.exists():
        download(entry["links"]["self"], path)
    provider_md5 = entry["checksum"].removeprefix("md5:")
    if path.stat().st_size != entry["size"] or digest(path, "md5") != provider_md5:
        raise RuntimeError("Zenodo TDIP field member integrity drift")
    manifest = {
        "schema_version": "wp8-zenodo-tdip-full-decay-raw-v1",
        "record_id": RECORD_ID,
        "doi": "10.5281/zenodo.13329326",
        "license": "CC BY 4.0",
        "selection_basis": (
            "metadata-only search for downloadable TDIP field observations "
            "with full decay curves and a stable provider checksum"
        ),
        "selection_is_response_blind": True,
        "zenodo_record_sha256": digest(record_path, "sha256"),
        "members": [
            {
                "path": FIELD_NAME,
                "bytes": entry["size"],
                "provider_md5": provider_md5,
                "sha256": digest(path, "sha256"),
                "source_url": entry["links"]["self"],
            }
        ],
        "total_bytes": entry["size"],
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    if MANIFEST.exists():
        os.chmod(MANIFEST, 0o644)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for frozen in (record_path, path, MANIFEST):
        os.chmod(frozen, 0o444)
    print(json.dumps({"members": 1, "bytes": entry["size"]}))


if __name__ == "__main__":
    main()
