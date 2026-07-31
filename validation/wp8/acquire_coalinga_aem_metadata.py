#!/usr/bin/env python
"""Freeze response-blind public metadata for the Coalinga 2022 AEM candidate."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/coalinga-aem-v1"
OUTPUT = RAW / "metadata-manifest.json"
ITEM_ID = "69717efcd4be023817e33b98"
DOI = "10.5066/P14TP9LW"
API_URL = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
USER_AGENT = "GeoDeepBayes-WP8-feasibility/1.0 (public scientific data audit)"
ALLOWED = {
    "CoalingaCA2022_SkyTEMApS_DataReport.pdf",
    "CoalingaCA2022.xml",
}
CATALOG_ONLY_MEMBERS = {
    "CoalingaCA2022.ncml",
    "CoalingaCA2022.nc",
    "CoalingaCA2022_ContractorsDataPackage.zip",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def retrieve(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    api_body = retrieve(API_URL)
    metadata = json.loads(api_body)
    files = {entry["name"]: entry for entry in metadata["files"]}
    if not ALLOWED <= files.keys() or not CATALOG_ONLY_MEMBERS <= files.keys():
        raise RuntimeError("Coalinga ScienceBase membership drift")

    members = []
    for name in sorted(ALLOWED):
        entry = files[name]
        path = RAW / name
        retrieved_at = None
        if not path.is_file():
            body = retrieve(entry["downloadUri"])
            temporary = path.with_suffix(path.suffix + ".part")
            temporary.write_bytes(body)
            temporary.replace(path)
            retrieved_at = datetime.now(timezone.utc).isoformat()
        if path.stat().st_size != int(entry["size"]):
            raise RuntimeError(f"Coalinga size mismatch: {name}")
        os.chmod(path, stat.S_IREAD)
        members.append(
            {
                "name": name,
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": file_digest(path),
                "download_uri": entry["downloadUri"],
                "retrieved_at_utc": retrieved_at,
                "observation_response_interpreted": False,
            }
        )

    catalog_only = [
        {
            "name": name,
            "bytes": int(files[name]["size"]),
            "download_uri": files[name]["downloadUri"],
            "downloaded": False,
            "observation_response_interpreted": False,
        }
        for name in sorted(CATALOG_ONLY_MEMBERS)
    ]
    result = {
        "schema_version": "wp8-coalinga-aem-metadata-manifest-v1",
        "candidate_status": "acquired_metadata_not_selected",
        "doi": DOI,
        "sciencebase_item_id": ITEM_ID,
        "license": "USGS CC0/public domain",
        "api_url": API_URL,
        "api_sha256": digest(api_body),
        "member_count": len(members),
        "members": members,
        "catalog_only_members": catalog_only,
        "observation_response_interpreted": False,
    }
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(
        json.dumps(
            {
                "members": len(members),
                "bytes": sum(member["bytes"] for member in members),
                "response_bytes_read": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
