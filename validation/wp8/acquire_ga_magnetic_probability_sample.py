#!/usr/bin/env python
"""Acquire the preregistered GA cell-weighted probability sample."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-probability-sample.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-probability-sample-v1"
REUSE_DIRS = (
    ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-survey-v1",
    ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-consortium-v1",
    ROOT / "validation/wp8/data/geoscience-australia-magnetic-training-expansion-v1",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reusable_members() -> dict[int, tuple[Path, dict]]:
    result = {}
    for directory in REUSE_DIRS:
        manifest_path = directory / "raw-manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "members" in manifest:
            members = manifest["members"]
        else:
            members = [dict(manifest["member"], dataset_no=manifest["dataset_no"])]
        for member in members:
            source = directory / member["path"]
            if (
                source.is_file()
                and source.stat().st_size == member["bytes"]
                and sha(source) == member["sha256"]
            ):
                result[int(member["dataset_no"])] = (source, member)
    return result


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        sample["selection_is_design_metadata_only"] is not True
        or sample["magnetic_response_values_interpreted"] != 0
        or sample["test_unseal_count"] != 0
    ):
        raise RuntimeError("probability sample is not response blind")
    DATA.mkdir(parents=True, exist_ok=True)
    reusable = reusable_members()
    members = []
    for product in sample["products"]:
        dataset_no = int(product["dataset_no"])
        target = DATA / Path(product["provider_url"]).name
        reused_from = None
        expected_sha = None
        expected_bytes = None
        if dataset_no in reusable:
            source, old_member = reusable[dataset_no]
            expected_sha = old_member["sha256"]
            expected_bytes = old_member["bytes"]
            if not target.exists():
                try:
                    os.link(source, target)
                except OSError:
                    shutil.copy2(source, target)
            reused_from = str(source.relative_to(ROOT))
        if not target.is_file():
            partial = target.with_suffix(target.suffix + ".part")
            request = urllib.request.Request(
                product["provider_url"],
                headers={
                    "User-Agent": (
                        "GeoDeepBayes-WP8 preregistered GA probability sample"
                    )
                },
            )
            with urllib.request.urlopen(request, timeout=300) as response, partial.open(
                "wb"
            ) as output:
                for block in iter(lambda: response.read(8 * 1024 * 1024), b""):
                    output.write(block)
            partial.replace(target)
        actual_sha = sha(target)
        actual_bytes = target.stat().st_size
        if (
            expected_sha is not None
            and (actual_sha != expected_sha or actual_bytes != expected_bytes)
        ):
            raise RuntimeError(f"reused dataset integrity drift: {dataset_no}")
        members.append(
            {
                "dataset_no": dataset_no,
                "survey_id": product["survey_id"],
                "survey_name": product["survey_name"],
                "state": product["state"],
                "survey_start_date": product["survey_start_date"],
                "sampled_cells": product["sampled_cells"],
                "covered_design_cells": [
                    {"cell": cell["cell"], "role": cell["role"]}
                    for cell in design["cells"]
                    if dataset_no in cell["covering_dataset_numbers"]
                ],
                "path": target.name,
                "bytes": actual_bytes,
                "sha256": actual_sha,
                "provider_url": product["provider_url"],
                "catalogue_file_size": product["catalogue_file_size"],
                "reused_from": reused_from,
            }
        )
        print(
            json.dumps(
                {
                    "dataset_no": dataset_no,
                    "bytes": actual_bytes,
                    "reused": reused_from is not None,
                }
            ),
            flush=True,
        )
    manifest = {
        "schema_version": "wp8-ga-magnetic-probability-sample-freeze-v1",
        "sample_sha256": sha(SAMPLE),
        "design_sha256": sample["design_sha256"],
        "dds_contract_sha256": sample["dds_contract_sha256"],
        "dataset_numbers": sample["selected_dataset_numbers"],
        "states": sorted({member["state"] for member in members}),
        "sampled_cells": sample["sampled_cells"],
        "acquisition_interpreted_response_values": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "members": members,
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
                "bytes": sum(member["bytes"] for member in members),
                "reused": sum(member["reused_from"] is not None for member in members),
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
