#!/usr/bin/env python
"""Freeze direct-parent metadata for the USGS magnetic ScienceBase catalogue."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE_DIR = (
    ROOT / "validation/wp8/data/usgs-sciencebase-magnetic-catalogue-v1"
)
CATALOGUE = CATALOGUE_DIR / "catalogue.json"
OUT = CATALOGUE_DIR / "raw-parents"
MANIFEST = CATALOGUE_DIR / "parent-manifest.json"
WORKERS = 12
ATTEMPTS = 5
USER_AGENT = "GeoDeepBayes-WP8 ScienceBase-parent-freeze/1.0"


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def acquire(item_id: str) -> tuple[str, bytes | None, int | None]:
    existing = OUT / f"{item_id}.json"
    if existing.exists() and existing.stat().st_size:
        raw = existing.read_bytes()
        item = json.loads(raw)
        if item.get("id") != item_id:
            raise RuntimeError(f"existing ScienceBase ID drift: {item_id}")
        return item_id, raw, None
    url = f"https://www.sciencebase.gov/catalog/item/{item_id}?format=json"
    error: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
            item = json.loads(raw)
            if item.get("id") != item_id:
                raise RuntimeError(f"ScienceBase ID drift: {item_id}")
            return item_id, raw, None
        except urllib.error.HTTPError as caught:
            if caught.code == 404:
                return item_id, None, 404
            error = caught
            if attempt + 1 < ATTEMPTS:
                time.sleep(2**attempt)
        except Exception as caught:
            error = caught
            if attempt + 1 < ATTEMPTS:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed after {ATTEMPTS} attempts: {item_id}") from error


def main() -> None:
    catalogue_raw = CATALOGUE.read_bytes()
    catalogue = json.loads(catalogue_raw)
    child_ids = {record["sciencebase_id"] for record in catalogue["records"]}
    parent_ids = sorted(
        {
            record["parent_id"]
            for record in catalogue["records"]
            if record.get("parent_id")
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(acquire, item_id): item_id for item_id in parent_ids
        }
        for index, future in enumerate(as_completed(futures), 1):
            item_id, raw, http_status = future.result()
            if raw is None:
                records.append(
                    {
                        "sciencebase_id": item_id,
                        "already_in_search_population": item_id in child_ids,
                        "available": False,
                        "http_status": http_status,
                        "path": None,
                        "bytes": 0,
                        "sha256": None,
                    }
                )
            else:
                path = OUT / f"{item_id}.json"
                path.write_bytes(raw)
                records.append(
                    {
                        "sciencebase_id": item_id,
                        "already_in_search_population": item_id in child_ids,
                        "available": True,
                        "http_status": 200,
                        "path": path.relative_to(CATALOGUE_DIR).as_posix(),
                        "bytes": len(raw),
                        "sha256": sha256(raw),
                    }
                )
            print(
                json.dumps(
                    {"frozen": index, "total": len(parent_ids), "id": item_id}
                ),
                flush=True,
            )
    records.sort(key=lambda record: record["sciencebase_id"])
    result = {
        "schema_version": "wp8-usgs-sciencebase-parent-metadata-v1",
        "catalogue_sha256": sha256(catalogue_raw),
        "direct_parent_count": len(parent_ids),
        "parents_already_in_search_population": sum(
            record["already_in_search_population"] for record in records
        ),
        "parents_outside_search_population": sum(
            not record["already_in_search_population"] for record in records
        ),
        "unavailable_parent_count": sum(
            not record["available"] for record in records
        ),
        "records": records,
        "magnetic_response_values_interpreted": 0,
        "candidate_files_downloaded": 0,
        "test_unseal_count": 0,
    }
    payload = (json.dumps(result, indent=2) + "\n").encode()
    MANIFEST.write_bytes(payload)
    print(
        json.dumps(
            {
                "parents": len(records),
                "outside_search": result["parents_outside_search_population"],
                "manifest_sha256": sha256(payload),
            }
        )
    )


if __name__ == "__main__":
    main()
