#!/usr/bin/env python
"""Freeze a geographically dispersed GA training-only magnetic consortium."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-consortium-v1"
DATASET_NUMBERS = (16401, 16871, 18058, 18234, 18444, 15072)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    products = {
        int(item["DATASET_NO"]): item for item in design["products"]
    }
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    for dataset_no in DATASET_NUMBERS:
        product = products[dataset_no]
        covered = [
            {"cell": cell["cell"], "role": cell["role"]}
            for cell in design["cells"]
            if dataset_no in cell["covering_dataset_numbers"]
        ]
        if not any(cell["role"] == "train" for cell in covered):
            raise RuntimeError(f"dataset {dataset_no} no longer covers training")
        name = Path(product["FILE_DOWNLOAD"]).name
        target = DATA / name
        if not target.is_file():
            request = urllib.request.Request(
                product["FILE_DOWNLOAD"],
                headers={"User-Agent": "GeoDeepBayes-WP8 sealed GA training consortium"},
            )
            with urllib.request.urlopen(request, timeout=300) as response, target.open(
                "wb"
            ) as output:
                for block in iter(lambda: response.read(8 * 1024 * 1024), b""):
                    output.write(block)
        members.append(
            {
                "dataset_no": dataset_no,
                "survey_id": product["SURVEY_ID"],
                "survey_name": product["SURVEY_NAME"],
                "state": product["STATE"],
                "license": product["LICENCE"],
                "covered_design_cells": covered,
                "path": name,
                "bytes": target.stat().st_size,
                "sha256": sha(target),
                "provider_url": product["FILE_DOWNLOAD"],
                "catalogue_file_size": product["FILE_SIZE"],
            }
        )
        print(
            json.dumps(
                {"dataset_no": dataset_no, "bytes": target.stat().st_size}
            ),
            flush=True,
        )
    manifest = {
        "schema_version": "wp8-ga-magnetic-training-consortium-freeze-v1",
        "design_sha256": sha(DESIGN),
        "dataset_numbers": list(DATASET_NUMBERS),
        "states": sorted({member["state"] for member in members}),
        "acquisition_interpreted_response_values": 0,
        "members": members,
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for member in members:
        os.chmod(DATA / member["path"], 0o444)
    os.chmod(manifest_path, 0o444)
    print(
        json.dumps(
            {
                "members": len(members),
                "states": manifest["states"],
                "bytes": sum(member["bytes"] for member in members),
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
