#!/usr/bin/env python
"""Freeze one small GA located-line NetCDF for training-side schema inspection."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-probe-v1"
DATASET_NO = 17638


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    product = next(
        item for item in design["products"] if int(item["DATASET_NO"]) == DATASET_NO
    )
    covered_roles = {
        cell["role"]
        for cell in design["cells"]
        if DATASET_NO in cell["covering_dataset_numbers"]
    }
    if "train" not in covered_roles:
        raise RuntimeError("probe product no longer covers a training design cell")
    DATA.mkdir(parents=True, exist_ok=True)
    name = Path(product["FILE_DOWNLOAD"]).name
    target = DATA / name
    request = urllib.request.Request(
        product["FILE_DOWNLOAD"],
        headers={"User-Agent": "GeoDeepBayes-WP8 training schema probe"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        content = response.read()
    target.write_bytes(content)
    manifest = {
        "schema_version": "wp8-ga-magnetic-training-probe-freeze-v1",
        "design_sha256": sha(DESIGN),
        "dataset_no": DATASET_NO,
        "survey_id": product["SURVEY_ID"],
        "survey_name": product["SURVEY_NAME"],
        "license": product["LICENCE"],
        "covered_design_roles": sorted(covered_roles),
        "acquisition_interpreted_response_values": 0,
        "member": {
            "path": name,
            "bytes": target.stat().st_size,
            "sha256": sha(target),
            "provider_url": product["FILE_DOWNLOAD"],
            "catalogue_file_size": product["FILE_SIZE"],
        },
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (target, manifest_path):
        os.chmod(path, 0o444)
    print(
        json.dumps(
            {
                "dataset_no": DATASET_NO,
                "bytes": target.stat().st_size,
                "covered_roles": sorted(covered_roles),
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
