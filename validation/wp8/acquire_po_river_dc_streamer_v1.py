#!/usr/bin/env python
# /// script
# dependencies = ["py7zr==1.0.0"]
# ///
"""Acquire the preregistered Po River DC archive without reading responses."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

import py7zr

ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "po-river-dc-streamer-design-v1.json"
)
OUT = ROOT / "validation/wp8/data/po-river-dc-streamer-v1"
ARCHIVE = OUT / "Electrical_Tomography_Data.7z"
EXTRACTED = OUT / "extracted"
MANIFEST = OUT / "raw-manifest.json"


def file_digest(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        not design["selection_frozen_before_response_access"]
        or design["test_unseal_count"] != 0
    ):
        raise RuntimeError("Po River DC design is not sealed")
    OUT.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        design["archive"]["download_url"],
        headers={"User-Agent": "GeoDeepBayes-WP8 PoRiver-DC/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        ARCHIVE.write_bytes(response.read())
    expected_md5 = design["archive"]["checksum"].split(":", 1)[1]
    if (
        ARCHIVE.stat().st_size != design["archive"]["size"]
        or file_digest(ARCHIVE, "md5") != expected_md5
    ):
        raise RuntimeError("Po River DC archive integrity failure")
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(ARCHIVE, mode="r") as archive:
        names = archive.getnames()
        archive.extractall(path=EXTRACTED)
    members = []
    for path in sorted(EXTRACTED.rglob("*")):
        if not path.is_file():
            continue
        members.append(
            {
                "path": path.relative_to(OUT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_digest(path),
            }
        )
    result = {
        "schema_version": "wp8-po-river-dc-streamer-raw-manifest-v1",
        "design_sha256": file_digest(DESIGN),
        "archive_path": ARCHIVE.relative_to(OUT).as_posix(),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": file_digest(ARCHIVE),
        "declared_archive_members": names,
        "members": members,
        "member_payloads_read": 0,
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "archive_bytes": result["archive_bytes"],
                "members": len(members),
                "response_values_interpreted": 0,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
