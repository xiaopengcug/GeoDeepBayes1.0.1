#!/usr/bin/env python
"""Acquire the preselected train-only GA Gilmore TEMPEST AEM package."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-aem-training-probe-v1"
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/geoscience-australia-aem-design.json"
)
PACKAGE_ID = "97e28bf9-dfb0-4e29-9834-e14857508f7c"
METADATA_URL = f"https://data.gov.au/data/api/3/action/package_show?id={PACKAGE_ID}"
DATA_URL = "https://d28rz98at9flks.cloudfront.net/60847/60847.zip"
EXPECTED_BYTES = 216_209_877
EXPECTED_ETAG_MD5 = "764b6e7788d5a2269fbedd9257b1c5ce"
DATASET_NO = 22153


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def md5(path: Path) -> str:
    value = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 GA AEM training probe"}
    )
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(request, timeout=300) as response, temporary.open(
        "wb"
    ) as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
    temporary.replace(path)


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    covered_roles = {
        cell["role"]
        for cell in design["cells"]
        if DATASET_NO in cell["covering_dataset_numbers"]
    }
    if covered_roles != {"train"} or design["test_unseal_count"] != 0:
        raise RuntimeError("preselected AEM probe is no longer train-only")
    DATA.mkdir(parents=True, exist_ok=True)
    metadata_path = DATA / "data-gov-au-package.json"
    archive_path = DATA / "60847.zip"
    if not metadata_path.exists():
        download(METADATA_URL, metadata_path)
    if not archive_path.exists():
        download(DATA_URL, archive_path)
    if archive_path.stat().st_size != EXPECTED_BYTES:
        raise RuntimeError("GA AEM training archive byte-length drift")
    if md5(archive_path) != EXPECTED_ETAG_MD5:
        raise RuntimeError("GA AEM training archive ETag/MD5 drift")
    manifest = {
        "schema_version": "wp8-geoscience-australia-aem-training-probe-v1",
        "selection_design_sha256": sha256(DESIGN),
        "dataset_number": DATASET_NO,
        "survey_id": "729",
        "record_id": 60847,
        "package_id": PACKAGE_ID,
        "selection_was_response_blind": True,
        "covered_design_roles": sorted(covered_roles),
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "source": {
            "metadata_url": METADATA_URL,
            "download_url": DATA_URL,
            "provider_etag_md5": EXPECTED_ETAG_MD5,
        },
        "members": [
            {
                "path": metadata_path.name,
                "bytes": metadata_path.stat().st_size,
                "sha256": sha256(metadata_path),
            },
            {
                "path": archive_path.name,
                "bytes": archive_path.stat().st_size,
                "sha256": sha256(archive_path),
                "md5": md5(archive_path),
            },
        ],
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (metadata_path, archive_path, manifest_path):
        os.chmod(path, 0o444)
    print(
        json.dumps(
            {
                "archive_bytes": archive_path.stat().st_size,
                "archive_sha256": sha256(archive_path),
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
