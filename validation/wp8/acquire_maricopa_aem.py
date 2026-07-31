#!/usr/bin/env python
"""Acquire the public Maricopa 2018 AEM candidate without interpreting responses."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/maricopa-aem-v1"
OUTPUT = RAW / "raw-manifest.json"
ITEM_ID = "6197f026d34eb622f692eed1"
DOI = "10.5066/P9R1XBPG"
API_URL = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
USER_AGENT = "GeoDeepBayes-WP8-feasibility/1.0 (public scientific data audit)"
MEMBERS = {
    "MaricopaCA2018_SkyTEMApS_DataReport.pdf",
    "MaricopaCA2018.nc",
    "MaricopaCA2018.xml",
}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def download(url: str, path: Path) -> str:
    temporary = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    mode = "ab" if temporary.is_file() else "wb"
    offset = temporary.stat().st_size if temporary.is_file() else 0
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    with urllib.request.urlopen(request, timeout=300) as response:
        if offset and response.status != 206:
            mode = "wb"
        with temporary.open(mode) as target:
            for chunk in iter(lambda: response.read(4 * 1024 * 1024), b""):
                target.write(chunk)
    temporary.replace(path)
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        api_body = response.read()
    metadata = json.loads(api_body)
    files = {entry["name"]: entry for entry in metadata["files"]}
    if not MEMBERS <= files.keys():
        raise RuntimeError("Maricopa ScienceBase membership drift")
    members = []
    for name in sorted(MEMBERS):
        entry = files[name]
        path = RAW / name
        retrieved_at = None
        if not path.is_file():
            retrieved_at = download(entry["downloadUri"], path)
        if path.stat().st_size != int(entry["size"]):
            raise RuntimeError(f"Maricopa size mismatch: {name}")
        os.chmod(path, stat.S_IREAD)
        members.append(
            {
                "name": name,
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "download_uri": entry["downloadUri"],
                "retrieved_at_utc": retrieved_at,
                "observation_response_interpreted": False,
            }
        )
        print(f"downloaded/verified {name}", flush=True)
    result = {
        "schema_version": "wp8-maricopa-aem-raw-manifest-v1",
        "candidate_status": "acquired_not_selected",
        "doi": DOI,
        "sciencebase_item_id": ITEM_ID,
        "license": "USGS CC0/public domain",
        "api_sha256": hashlib.sha256(api_body).hexdigest(),
        "member_count": len(members),
        "total_bytes": sum(member["bytes"] for member in members),
        "members": members,
        "observation_response_interpreted": False,
    }
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(json.dumps({"members": len(members), "bytes": result["total_bytes"]}))


if __name__ == "__main__":
    main()
