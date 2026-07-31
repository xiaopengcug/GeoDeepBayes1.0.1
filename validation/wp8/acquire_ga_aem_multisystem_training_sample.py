#!/usr/bin/env python
"""Acquire frozen response-blind GA VTEM/SkyTEM training resources."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-aem-multisystem-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
SAMPLE = EVIDENCE / "geoscience-australia-aem-multisystem-training-sample.json"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 GA AEM multisystem freeze"}
    )
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(request, timeout=300) as response, temporary.open(
        "wb"
    ) as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
    temporary.replace(path)


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if (
        sample["selection_is_response_blind"] is not True
        or sample["response_values_interpreted"] != 0
        or sample["test_unseal_count"] != 0
    ):
        raise RuntimeError("GA AEM multisystem selection drift")
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for choice in sample["choices"]:
        name = f"{choice['record_id']}-{Path(choice['url']).name}"
        path = DATA / name
        if not path.exists():
            download(choice["url"], path)
        if path.stat().st_size != choice["expected_bytes"]:
            raise RuntimeError(f"GA AEM resource byte-length drift: {name}")
        members.append(
            {
                "system": choice["system"],
                "dataset_number": choice["dataset_number"],
                "record_id": choice["record_id"],
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "provider_etag": choice["provider_etag"],
                "covered_design_roles": choice["covered_design_roles"],
            }
        )
    manifest = {
        "schema_version": "wp8-geoscience-australia-aem-multisystem-raw-v1",
        "sample_sha256": sha256(SAMPLE),
        "selection_was_response_blind": True,
        "members": members,
        "total_bytes": sum(member["bytes"] for member in members),
        "response_values_interpreted_during_acquisition": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    manifest_path = DATA / "raw-manifest.json"
    if manifest_path.exists():
        os.chmod(manifest_path, 0o644)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for member in members:
        os.chmod(DATA / member["path"], 0o444)
    os.chmod(manifest_path, 0o444)
    print(
        json.dumps(
            {
                "members": len(members),
                "total_bytes": manifest["total_bytes"],
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
