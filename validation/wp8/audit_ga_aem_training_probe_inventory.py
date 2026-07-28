#!/usr/bin/env python
"""Inventory train-only GA AEM ZIP members without reading member payloads."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-aem-training-probe-v1"
ARCHIVE = DATA / "60847.zip"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/geoscience-australia-aem-training-probe-inventory.json"
)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    archive_member = next(
        member for member in manifest["members"] if member["path"] == ARCHIVE.name
    )
    if (
        manifest["covered_design_roles"] != ["train"]
        or manifest["test_unseal_count"] != 0
        or archive_member["sha256"] != sha256(ARCHIVE)
    ):
        raise RuntimeError("GA AEM training probe freeze drift")
    with zipfile.ZipFile(ARCHIVE) as archive:
        members = [
            {
                "path": item.filename,
                "compressed_bytes": item.compress_size,
                "uncompressed_bytes": item.file_size,
                "crc32": f"{item.CRC:08x}",
                "is_directory": item.is_dir(),
            }
            for item in archive.infolist()
        ]
    suffix_counts: dict[str, int] = {}
    for member in members:
        suffix = Path(member["path"]).suffix.lower() or "<none>"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
    result = {
        "schema_version": "wp8-geoscience-australia-aem-training-probe-inventory-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "archive_sha256": sha256(ARCHIVE),
        "zip_central_directory_only": True,
        "member_payloads_read": 0,
        "aem_response_values_interpreted": 0,
        "member_count": len(members),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "members": members,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"members": len(members), "suffix_counts": result["suffix_counts"]}
        )
    )


if __name__ == "__main__":
    main()
