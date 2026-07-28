"""Response-blind central-directory inventory for NTGS CR2010-0883.

This stage reads ZIP member metadata only. It does not open observation,
inversion, AVG, EDI, RAW, or other payload members.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/wp8/data/ntgs-cr2010-0883-v1/CR20100883AC.zip"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "ntgs-cr20100883-response-blind-inventory-v1.json"
)

METHOD_TOKENS = {
    "csamt": ("csamt",),
    "pdip": ("pdip", "dipole_ip", "dipole-ip"),
    "amt": ("amt",),
}
OBSERVATION_EXTENSIONS = {
    ".avg",
    ".edi",
    ".raw",
    ".stc",
    ".z",
    ".zmm",
}
DESIGN_EXTENSIONS = {".stn", ".mde"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not ARCHIVE.is_file():
        raise SystemExit(f"missing archive: {ARCHIVE}")

    with ZipFile(ARCHIVE) as archive:
        members = archive.infolist()

    extensions = Counter()
    method_members: dict[str, list[str]] = {key: [] for key in METHOD_TOKENS}
    design_members: list[str] = []
    observation_members: list[str] = []
    top_level_trees = Counter()

    for info in members:
        name = info.filename.replace("\\", "/")
        lower = name.lower()
        suffix = PurePosixPath(lower).suffix
        if suffix:
            extensions[suffix] += 1
        parts = PurePosixPath(name).parts
        top_level_trees["/".join(parts[:6])] += 1
        for method, tokens in METHOD_TOKENS.items():
            if any(token in lower for token in tokens):
                method_members[method].append(name)
        if suffix in DESIGN_EXTENSIONS:
            design_members.append(name)
        if suffix in OBSERVATION_EXTENSIONS:
            observation_members.append(name)

    evidence = {
        "schema_version": "wp8-ntgs-cr20100883-response-blind-inventory-v1",
        "audit_date": "2026-07-25",
        "source_landing_page": (
            "https://geoscience.nt.gov.au/gemis/ntgsjspui/handle/1/90121"
        ),
        "archive_path": ARCHIVE.relative_to(ROOT).as_posix(),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": sha256_file(ARCHIVE),
        "archive_member_count": len(members),
        "response_payload_members_opened": 0,
        "test_response_members_opened": 0,
        "central_directory_only": True,
        "extension_counts": dict(sorted(extensions.items())),
        "method_name_member_counts": {
            key: len(value) for key, value in method_members.items()
        },
        "method_name_members": method_members,
        "design_member_count": len(design_members),
        "design_members": design_members,
        "observation_member_count": len(observation_members),
        "observation_member_names_frozen_only": True,
        "top_level_trees": dict(top_level_trees.most_common()),
        "next_stage": (
            "Classify survey units and freeze a geometry-only train/buffer/"
            "calibration/test design before opening any response payload."
        ),
    }
    OUTPUT.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "archive_bytes": evidence["archive_bytes"],
            "archive_member_count": evidence["archive_member_count"],
            "method_name_member_counts": evidence["method_name_member_counts"],
            "design_member_count": evidence["design_member_count"],
            "observation_member_count": evidence["observation_member_count"],
            "output": OUTPUT.relative_to(ROOT).as_posix(),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
