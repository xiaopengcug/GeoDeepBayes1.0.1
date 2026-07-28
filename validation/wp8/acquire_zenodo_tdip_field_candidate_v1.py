#!/usr/bin/env python
"""Freeze and acquire the unopened Zenodo TDIP field archive candidate."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/wp8/data/zenodo-tdip-field-candidate-v1"
METADATA = OUT / "zenodo-record-13329326.json"
ARCHIVE = OUT / "field_survey.rar"
MANIFEST = OUT / "candidate-manifest.json"
URL = "https://zenodo.org/api/records/13329326"


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        URL, headers={"User-Agent": "GeoDeepBayes-WP8 TDIP-candidate/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    METADATA.write_bytes(raw)
    record = json.loads(raw)
    file = next(item for item in record["files"] if item["key"] == "field_survey.rar")
    request = urllib.request.Request(
        file["links"]["self"],
        headers={"User-Agent": "GeoDeepBayes-WP8 TDIP-candidate/1.0"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        with ARCHIVE.open("wb") as stream:
            for block in iter(lambda: response.read(8 * 1024 * 1024), b""):
                stream.write(block)
    expected_md5 = file["checksum"].split(":", 1)[1]
    if ARCHIVE.stat().st_size != file["size"] or digest(ARCHIVE, "md5") != expected_md5:
        raise RuntimeError("TDIP candidate archive integrity failure")
    result = {
        "schema_version": "wp8-zenodo-tdip-field-candidate-v1",
        "source": "Zenodo record 13329326",
        "doi": "10.5281/zenodo.13329326",
        "title": record["metadata"]["title"],
        "access_right": record["metadata"]["access_right"],
        "license": record["metadata"]["license"]["id"],
        "metadata_path": METADATA.relative_to(OUT).as_posix(),
        "metadata_sha256": digest(METADATA),
        "archive_path": ARCHIVE.relative_to(OUT).as_posix(),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": digest(ARCHIVE),
        "archive_members_listed": False,
        "archive_members_extracted": False,
        "response_payloads_opened": 0,
        "response_values_interpreted": 0,
        "candidate_role": "unassigned",
        "test_unseal_count": 0,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "archive_bytes": result["archive_bytes"],
                "archive_sha256": result["archive_sha256"],
                "response_values_interpreted": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
