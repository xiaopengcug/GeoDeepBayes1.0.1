#!/usr/bin/env python
"""Freeze OPeNDAP DDS schemas for every design-eligible GA magnetic product."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-design.json"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-dds-v1"
WORKERS = 12


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dds_url(download: str) -> str:
    if "/thredds/fileServer/" not in download:
        raise ValueError(f"unexpected THREDDS file URL: {download}")
    return download.replace("/thredds/fileServer/", "/thredds/dodsC/") + ".dds"


def acquire(product: dict) -> dict:
    dataset_no = int(product["DATASET_NO"])
    url = dds_url(product["FILE_DOWNLOAD"])
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 response-blind DDS freeze"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    text = content.decode("utf-8", errors="strict")
    if not text.startswith("Dataset {") or "} " not in text:
        raise RuntimeError(f"invalid DDS response for dataset {dataset_no}")
    path = DATA / f"{dataset_no}.dds"
    path.write_bytes(content)
    return {
        "dataset_no": dataset_no,
        "survey_id": product["SURVEY_ID"],
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "provider_url": url,
    }


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        design["selection_is_design_metadata_only"] is not True
        or design["magnetic_response_values_interpreted"] != 0
        or design["test_unseal_count"] != 0
    ):
        raise RuntimeError("GA magnetic design evidence drift")
    DATA.mkdir(parents=True, exist_ok=True)
    members = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(acquire, product): int(product["DATASET_NO"])
            for product in design["products"]
        }
        for future in concurrent.futures.as_completed(futures):
            dataset_no = futures[future]
            try:
                members.append(future.result())
            except Exception as error:
                failures.append({"dataset_no": dataset_no, "error": str(error)})
    members.sort(key=lambda item: item["dataset_no"])
    failures.sort(key=lambda item: item["dataset_no"])
    manifest = {
        "schema_version": "wp8-ga-magnetic-dds-freeze-v1",
        "design_sha256": sha(DESIGN),
        "requested_products": len(design["products"]),
        "successful_products": len(members),
        "failed_products": failures,
        "dds_contains_declarations_only": True,
        "variable_attributes_requested": False,
        "magnetic_response_values_interpreted": 0,
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
                "requested": len(design["products"]),
                "successful": len(members),
                "failed": len(failures),
            }
        )
    )


if __name__ == "__main__":
    main()
