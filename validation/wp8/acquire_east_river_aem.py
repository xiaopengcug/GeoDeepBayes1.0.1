#!/usr/bin/env python
"""Acquire the USGS East River processed AEM candidate without interpreting responses."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/east-river-aem-v1"
ITEM_ID = "5f51c7b782ce4c3d1239a796"
API = f"https://www.sciencebase.gov/catalog/item/{ITEM_ID}?format=json"
RAW_ITEM_ID = "5f51c7a882ce4c3d1239a794"
RAW_API = f"https://www.sciencebase.gov/catalog/item/{RAW_ITEM_ID}?format=json"
USER_AGENT = "GeoDeepBayes-WP8-feasibility/1.0 (public scientific data audit)"
KEEP = {
    "EastRiver2017_AEMGateTime.csv",
    "EastRiver2017_ProcessedAEMData_100series.csv",
    "EastRiver2017_ProcessedAEMData_200series.csv",
    "EastRiver2017_ProcessedAEMData_300series.csv",
    "EastRiver2017_ProcessedAEMData_400series.csv",
    "EastRiver2017_AEMProcessedData.xml",
    "EastRiver2017_DataDictionary_ProcessedAEMData.csv",
}
RAW_KEEP = {
    "EastRiver2017_Geotech_DataReport.pdf",
    "EastRiver2017_AEMMagRawData.xml",
    "EastRiver2017_DataDictionary_EM_Mag.csv",
}


def request(url: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as response:
        body = response.read()
        headers = {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower() in {"content-length", "content-type", "etag", "last-modified"}
        }
    return body, headers


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    metadata_records = []
    files = {}
    for item_id, api, keep in (
        (ITEM_ID, API, KEEP),
        (RAW_ITEM_ID, RAW_API, RAW_KEEP),
    ):
        metadata_body, metadata_headers = request(api)
        metadata = json.loads(metadata_body)
        selected = {
            entry["name"]: {**entry, "sciencebase_item_id": item_id}
            for entry in metadata["files"]
            if entry["name"] in keep
        }
        if set(selected) != keep:
            raise RuntimeError(
                f"ScienceBase item membership drift: {item_id}: {sorted(set(keep) - set(selected))}"
            )
        files.update(selected)
        metadata_records.append(
            {
                "sciencebase_item_id": item_id,
                "sciencebase_api": api,
                "metadata_sha256": hashlib.sha256(metadata_body).hexdigest(),
                "http_metadata": metadata_headers,
            }
        )
    members = []
    for name in sorted(files):
        entry = files[name]
        path = RAW / name
        retrieved = None
        http_metadata: dict[str, str] = {"resume": "local-existing-file"}
        if not path.is_file():
            body, http_metadata = request(entry["downloadUri"])
            path.write_bytes(body)
            retrieved = datetime.now(timezone.utc).isoformat()
        if path.stat().st_size != int(entry["size"]):
            raise RuntimeError(f"size mismatch: {name}")
        os.chmod(path, stat.S_IREAD)
        members.append(
            {
                "name": name,
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": digest(path),
                "download_uri": entry["downloadUri"],
                "sciencebase_item_id": entry["sciencebase_item_id"],
                "retrieved_at_utc": retrieved,
                "http_metadata": http_metadata,
                "observation_response_interpreted": False,
            }
        )
        print(f"downloaded/verified {name}", flush=True)
    manifest = {
        "schema_version": "wp8-east-river-aem-raw-manifest-v1",
        "candidate_status": "acquired_not_selected",
        "doi": "10.5066/P949ZCZ8",
        "sciencebase_items": metadata_records,
        "license": "CC0 1.0 / U.S. public domain",
        "member_count": len(members),
        "total_bytes": sum(member["bytes"] for member in members),
        "observation_response_interpreted": False,
        "members": members,
    }
    temporary = RAW / "raw-manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(RAW / "raw-manifest.json")
    print(json.dumps({"members": len(members), "bytes": manifest["total_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
