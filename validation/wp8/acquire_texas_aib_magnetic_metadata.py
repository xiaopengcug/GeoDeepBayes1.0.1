#!/usr/bin/env python
"""Acquire Texas AIB magnetic design/contract files without the response archive."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/wp8/data/texas-aib-magnetic-v1"
PARENT_ID = "69a5c06bb66b011d83258c49"
MAGNETIC_ID = "69ab5a87b66b01cd2fd12813"
API = "https://www.sciencebase.gov/catalog/item/{item_id}?format=json"
PARENT_NAMES = {
    "TX_AIB_FlightPlan.shp.zip",
    "TX_AIB_BoundaryFinal.shp.zip",
    "Acquisition_and_Processing_Report_TX_AlkalineIgneousBelt_MAG_RAD_D24.pdf",
    "TX_AIB-LandingPage.xml",
}
MAGNETIC_NAMES = {"TX_AIB-Magnetic.xml"}


def get(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 public-data feasibility audit"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(item_id: str) -> dict:
    return json.loads(get(API.format(item_id=item_id)))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    parent = record(PARENT_ID)
    magnetic = record(MAGNETIC_ID)
    selected = [
        (PARENT_ID, item)
        for item in parent["files"]
        if item["name"] in PARENT_NAMES
    ] + [
        (MAGNETIC_ID, item)
        for item in magnetic["files"]
        if item["name"] in MAGNETIC_NAMES
    ]
    expected = PARENT_NAMES | MAGNETIC_NAMES
    if {item["name"] for _, item in selected} != expected:
        raise RuntimeError("ScienceBase metadata/contract member inventory drift")
    files = []
    for item_id, item in selected:
        path = OUTPUT / item["name"]
        if not path.exists() or path.stat().st_size != item["size"]:
            path.write_bytes(get(item["url"]))
        os.chmod(path, 0o444)
        files.append(
            {
                "sciencebase_item_id": item_id,
                "name": path.name,
                "bytes": path.stat().st_size,
                "expected_bytes": item["size"],
                "sha256": sha256(path),
                "source_url": item["url"],
            }
        )
    excluded_response_members = [
        {
            "name": item["name"],
            "bytes": item["size"],
            "source_url": item["url"],
        }
        for item in magnetic["files"]
        if item["name"]
        in {
            "TX_AIB_mag.csv.zip",
            "TX_AIB-ContractorProvidedMagneticGeosoftFiles.zip",
            "TX_AIB-Magnetic-GeoTIFF-Files.zip",
        }
    ]
    manifest = {
        "schema_version": "wp8-texas-aib-magnetic-metadata-manifest-v1",
        "doi": "10.5066/P1EOKG6I",
        "parent_sciencebase_item_id": PARENT_ID,
        "magnetic_sciencebase_item_id": MAGNETIC_ID,
        "title": parent["title"],
        "files": files,
        "excluded_response_members": excluded_response_members,
        "response_archives_downloaded": False,
        "response_values_interpreted": False,
    }
    (OUTPUT / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "files": len(files),
                "bytes": sum(item["bytes"] for item in files),
                "excluded_response_archives": len(excluded_response_members),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
