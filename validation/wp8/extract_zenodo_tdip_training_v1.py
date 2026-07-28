#!/usr/bin/env python
"""Extract only the pre-frozen TDIP training acquisition groups."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/zenodo-tdip-field-candidate-v1"
ARCHIVE = DATA / "field_survey.rar"
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "zenodo-tdip-field-design-v1.json"
)
OUT = DATA / "training-only"
MANIFEST = OUT / "training-manifest.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if not design["selection_frozen_before_payload_extraction"]:
        raise RuntimeError("TDIP role design is not frozen")
    if digest(ARCHIVE) != design["archive_sha256"]:
        raise RuntimeError("TDIP archive SHA-256 mismatch")
    groups = [
        item["acquisition_group"]
        for item in design["groups"]
        if item["role"] == "train"
    ]
    if set(groups) != {"n12_n13", "n7_n6_n1"}:
        raise RuntimeError("unexpected TDIP training groups")

    OUT.mkdir(parents=True, exist_ok=True)
    prefixes = [
        f"field_survey/field_full_waveform_data/{group}/" for group in groups
    ]
    subprocess.run(
        ["tar", "-xf", str(ARCHIVE), "-C", str(OUT), *prefixes],
        check=True,
    )
    files = sorted(path for path in OUT.rglob("*") if path.is_file())
    result = {
        "schema_version": "wp8-zenodo-tdip-training-manifest-v1",
        "design_path": DESIGN.relative_to(ROOT).as_posix(),
        "design_sha256": digest(DESIGN),
        "archive_sha256": design["archive_sha256"],
        "extracted_roles": ["train"],
        "extracted_groups": groups,
        "extracted_file_count": len(files),
        "extracted_bytes": sum(path.stat().st_size for path in files),
        "nontraining_groups_extracted": [],
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
