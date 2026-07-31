#!/usr/bin/env python
"""Atomically freeze the official Hualapai CSAMT permanent-training package."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-hualapai-csamt-v1"
CHILD_ID = "5d1a9d8fe4b0941bde6029a9"
PARENT_ID = "5474ec49e4b04d7459a7eab2"
CHILD_API = f"https://www.sciencebase.gov/catalog/item/{CHILD_ID}?format=json"
PARENT_API = f"https://www.sciencebase.gov/catalog/item/{PARENT_ID}?format=json"
INVERSION_NAME = "Inversions-GrandCanyonWest_PlainTankFlat.zip"
INVERSION_URL = (
    "https://www.sciencebase.gov/catalog/file/get/5d1a9d8fe4b0941bde6029a9?"
    "f=__disk__f9%2Ffe%2Fcd%2Ff9fecdfd80b1f15316610b3a8d4f2cc2f904391d"
)
ANCHORS = {
    "sciencebase-item.json": (CHILD_API, 22604, "28153604f1b45277c5e79276515ede7ca4230cf7bc50b27bc2bbc9427e580ab3"),
    "sciencebase-parent.json": (PARENT_API, 3115, "d691118c8fa188dcc2ba8c894417c6688dbda70d0d624c76febf21052df06346"),
    "Grand Canyon West and Plain Tank Flat CSAMT metadata.xml": ("sciencebase-child-file", 21060, "345e2d25817a36b525f8981526fd9be831bcc0cd0c563ce85cbce49722b32da9"),
    "KMZ files for Grand Canyon West and Plain Tank Flat CSAMT.kmz": ("sciencebase-child-file", 2489978, "0548e12b591fd90c79e2bf0bfc7c963c7e215824d30d759bc010b075384b3e74"),
    "Raw-GrandCanyonWest_PlainTankFlat.zip": ("sciencebase-child-file", 644983, "cc7fb61c96d18f6e255248810bb0884cdaad42550d5ea1214131bf59033ad0db"),
    "Station-GrandCanyonWest_PlainTankFlat.zip": ("sciencebase-child-file", 6499, "e22aaf87194ca2fd06e0bfc6c01ceadaefb75c169c350a313bb5cd010f5337ad"),
    INVERSION_NAME: (INVERSION_URL, 114382, "80d68dfab36b77824474dba9bba9eda972eaa39caecc073cbb30476dcf9cacbb"),
    "Cross_sections_Colorbar.zip": ("sciencebase-child-file", 2471945, "aa2bd459370de0b900eaecd2ef407370e166653bcaafdb0c9f07ea414995e75c"),
    "LandingPageMap.png": ("sciencebase-child-file", 9073663, "f7f8ad3ec4d95ab27810faea9c8f68ed66a7a41369009e5feadb3ea83713c876"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_atomic(url: str, target: Path, size: int, digest: str) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "GeoDeepBayes-WP8-Hualapai/2"})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as out:
            temporary = Path(out.name)
            with urllib.request.urlopen(request, timeout=120) as response:
                while block := response.read(1024 * 1024):
                    out.write(block)
        verify(temporary, size, digest)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify(path: Path, size: int, digest: str) -> None:
    if not path.is_file() or path.stat().st_size != size or sha256(path) != digest:
        raise RuntimeError(f"Hualapai provider anchor drift: {path.name}")


def build_manifest() -> dict[str, object]:
    child = json.loads((DATA / "sciencebase-item.json").read_text())
    parent = json.loads((DATA / "sciencebase-parent.json").read_text())
    if child.get("id") != CHILD_ID or child.get("parentId") != PARENT_ID or parent.get("id") != PARENT_ID:
        raise RuntimeError("ScienceBase parent/child relationship drift")
    provider_rows = child.get("files", [])
    provider_files = {row["name"]: row for row in provider_rows}
    if len(provider_rows) != 7 or len(provider_files) != 7:
        raise RuntimeError("ScienceBase provider inventory drift")
    members = []
    for name, (source, size, digest) in ANCHORS.items():
        path = DATA / name
        verify(path, size, digest)
        if name not in {"sciencebase-item.json", "sciencebase-parent.json"}:
            record = provider_files.get(name)
            if not record or record.get("size") != size or (
                source != "sciencebase-child-file" and record.get("downloadUri") != source
            ):
                raise RuntimeError(f"ScienceBase child file drift: {name}")
            source = record["downloadUri"]
        if name == INVERSION_NAME and source != INVERSION_URL:
            raise RuntimeError("ScienceBase inversion file URL drift")
        members.append({
            "path": name,
            "resource_kind": (
                "metadata_snapshot" if name in {"sciencebase-item.json", "sciencebase-parent.json"}
                else "provider_file"
            ),
            "source_url": source,
            "bytes": size,
            "sha256": digest,
        })
    return {
        "schema_version": "wp8-usgs-hualapai-csamt-permanent-training-manifest-v2",
        "scope": "permanently-training-only",
        "doi": "10.5066/P90KAJM4",
        "sciencebase_parent_id": PARENT_ID,
        "sciencebase_child_id": CHILD_ID,
        "license": "CC0-1.0",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "provider_member_count": 7,
        "metadata_snapshot_count": 2,
        "total_resource_count": 9,
        "members": members,
    }


def write_immutable(path: Path, value: dict[str, object]) -> None:
    body = (json.dumps(value, indent=2) + "\n").encode()
    if path.exists() and path.read_bytes() != body:
        raise RuntimeError("immutable Hualapai manifest drift")
    if not path.exists():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
                temporary = Path(out.name)
                out.write(body)
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    # Existing anchored files are verified, never overwritten. Missing members are
    # fetched atomically; child file URLs come only from the anchored child record.
    for name in ("sciencebase-item.json", "sciencebase-parent.json"):
        source, size, digest = ANCHORS[name]
        path = DATA / name
        if not path.exists():
            fetch_atomic(source, path, size, digest)
        verify(path, size, digest)
    child = json.loads((DATA / "sciencebase-item.json").read_text())
    provider_files = {row["name"]: row for row in child.get("files", [])}
    for name, (source, size, digest) in ANCHORS.items():
        if name not in {"sciencebase-item.json", "sciencebase-parent.json"}:
            record = provider_files.get(name)
            if not record or record.get("size") != size or (
                source != "sciencebase-child-file" and record.get("downloadUri") != source
            ):
                raise RuntimeError(f"ScienceBase child file drift: {name}")
            source = record["downloadUri"]
        path = DATA / name
        if not path.exists():
            fetch_atomic(source, path, size, digest)
        verify(path, size, digest)
    manifest = build_manifest()
    write_immutable(DATA / "raw-manifest.json", manifest)
    print(json.dumps({"members": len(manifest["members"]), "scope": manifest["scope"]}))


if __name__ == "__main__":
    main()
