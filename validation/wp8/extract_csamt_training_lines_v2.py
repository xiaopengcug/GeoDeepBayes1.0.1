#!/usr/bin/env python
"""Extract only pre-frozen CSAMT whole-line training members."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "csamt-line-split-v2.json"
OUT = ROOT / "validation/wp8/data/csamt-consortium-line-split-v2/training-only"
MANIFEST = OUT / "training-manifest.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if not design["selection_frozen_before_response_access"]:
        raise RuntimeError("CSAMT line split is not frozen")
    selected = [row for row in design["lines"] if row["role"] == "train"]
    OUT.mkdir(parents=True, exist_ok=True)
    extracted = []
    archives = {}
    for row in selected:
        archive = ROOT / row["archive_path"]
        if row["archive_path"] not in archives:
            if sha(archive) != row["archive_sha256"]:
                raise RuntimeError(f"archive integrity drift: {archive}")
            archives[row["archive_path"]] = zipfile.ZipFile(archive)
        source = archives[row["archive_path"]]
        info = source.getinfo(row["member"])
        if (
            info.file_size != row["member_bytes"]
            or f"{info.CRC:08x}" != row["member_crc32"]
        ):
            raise RuntimeError(f"member integrity drift: {row['member']}")
        target = OUT / row["provider"] / Path(row["member"]).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read(info))
        extracted.append(
            {
                "provider": row["provider"],
                "source_member": row["member"],
                "path": target.relative_to(OUT).as_posix(),
                "bytes": target.stat().st_size,
                "sha256": sha(target),
            }
        )
    for archive in archives.values():
        archive.close()
    result = {
        "schema_version": "wp8-csamt-training-lines-manifest-v2",
        "design_sha256": sha(DESIGN),
        "extracted_roles": ["train"],
        "training_line_count": len(extracted),
        "members": extracted,
        "buffer_response_members_opened": 0,
        "calibration_response_members_opened": 0,
        "test_response_members_opened": 0,
        "test_unseal_count": 0,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
