#!/usr/bin/env python
"""Freeze an outcome-blind USGS ScienceBase airborne-magnetic catalogue."""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/wp8/data/usgs-sciencebase-magnetic-catalogue-v1"
RAW = OUT / "raw-items"
SEARCH_QUERY = "airborne magnetic survey"
SEARCH_MAX = 100
WORKERS = 12
ATTEMPTS = 5
USER_AGENT = "GeoDeepBayes-WP8 public-magnetic-catalogue/1.0"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def get_json(url: str) -> tuple[bytes, dict]:
    error: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
            return raw, json.loads(raw)
        except Exception as caught:
            error = caught
            if attempt + 1 < ATTEMPTS:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed after {ATTEMPTS} attempts: {url}") from error


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def magnetic_title(title: str) -> bool:
    lowered = title.lower()
    return (
        ("airborne magnetic" in lowered or "aeromagnetic" in lowered)
        and not (
            "radiometric flight line data" in lowered
            and "magnetic" not in lowered.replace("radiometric", "")
        )
    )


def line_file(file: dict) -> bool:
    text = " ".join(
        normalize_text(file.get(key))
        for key in ("name", "title", "contentType")
    ).lower()
    data_suffix = bool(
        re.search(r"\.(csv|xyz|txt|dat|nc)(\.zip|\.gz)?(?:\s|$)", text)
    )
    magnetic = any(
        token in text
        for token in ("mag", "magnetic", "aeromag", "flight", "line", "xyz")
    )
    excluded = any(
        token in text
        for token in (
            "radiometric",
            "spectrum",
            "spectra",
            "ternary",
            "geotiff",
            ".tif",
            "grid",
        )
    )
    return data_suffix and magnetic and not excluded


def bounding_boxes(item: dict) -> list[dict]:
    boxes = []
    for facet in item.get("facets") or []:
        box = facet.get("boundingBox")
        if not isinstance(box, dict):
            continue
        keys = ("minX", "minY", "maxX", "maxY")
        if all(isinstance(box.get(key), (int, float)) for key in keys):
            normalized = {key: float(box[key]) for key in keys}
            if normalized not in boxes:
                boxes.append(normalized)
    return boxes


def rights_evidence(item: dict) -> list[str]:
    values = []
    for key in ("rights", "citation", "summary", "body"):
        text = normalize_text(item.get(key))
        lowered = text.lower()
        if any(
            token in lowered
            for token in (
                "public domain",
                "cc0",
                "creative commons",
                "license",
                "rights",
            )
        ):
            values.append(text[:2000])
    for link in item.get("webLinks") or []:
        text = " ".join(
            normalize_text(link.get(key))
            for key in ("title", "type", "uri")
        )
        if any(token in text.lower() for token in ("license", "rights", "doi")):
            values.append(text[:2000])
    return values


def compact(item: dict) -> dict:
    files = item.get("files") or []
    candidates = []
    for file in files:
        if line_file(file):
            candidates.append(
                {
                    key: file.get(key)
                    for key in (
                        "name",
                        "title",
                        "contentType",
                        "size",
                        "dateUploaded",
                        "downloadUri",
                        "url",
                        "checksum",
                    )
                }
            )
    contacts = [
        {
            key: contact.get(key)
            for key in ("name", "organization", "type", "contactType")
        }
        for contact in item.get("contacts") or []
    ]
    return {
        "sciencebase_id": item["id"],
        "parent_id": item.get("parentId"),
        "title": item.get("title"),
        "citation": item.get("citation"),
        "purpose": item.get("purpose"),
        "dates": item.get("dates") or [],
        "contacts": contacts,
        "tags": item.get("tags") or [],
        "bounding_boxes": bounding_boxes(item),
        "candidate_line_files": candidates,
        "rights_evidence": rights_evidence(item),
        "item_url": f"https://www.sciencebase.gov/catalog/item/{item['id']}",
        "metadata_only_eligible": bool(
            magnetic_title(item.get("title") or "")
            and candidates
            and bounding_boxes(item)
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    pages = []
    offset = 0
    total = None
    item_stubs: dict[str, dict] = {}
    while total is None or offset < total:
        query = urllib.parse.urlencode(
            {
                "format": "json",
                "max": SEARCH_MAX,
                "offset": offset,
                "q": SEARCH_QUERY,
            }
        )
        url = f"https://www.sciencebase.gov/catalog/items?{query}"
        raw, page = get_json(url)
        page_path = OUT / f"search-offset-{offset}.json"
        page_path.write_bytes(raw)
        pages.append(
            {
                "offset": offset,
                "url": url,
                "path": page_path.relative_to(OUT).as_posix(),
                "sha256": sha256_bytes(raw),
                "returned": len(page.get("items") or []),
            }
        )
        total = int(page["total"])
        for item in page.get("items") or []:
            item_stubs[item["id"]] = item
        offset += SEARCH_MAX

    def acquire(item_id: str) -> tuple[str, bytes, dict]:
        url = (
            f"https://www.sciencebase.gov/catalog/item/{item_id}?format=json"
        )
        raw, item = get_json(url)
        return item_id, raw, item

    records = []
    raw_manifest = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(acquire, item_id): item_id
            for item_id in sorted(item_stubs)
        }
        for index, future in enumerate(as_completed(futures), 1):
            item_id, raw, item = future.result()
            path = RAW / f"{item_id}.json"
            path.write_bytes(raw)
            raw_manifest.append(
                {
                    "sciencebase_id": item_id,
                    "path": path.relative_to(OUT).as_posix(),
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                }
            )
            records.append(compact(item))
            print(
                json.dumps(
                    {
                        "frozen": index,
                        "total": len(item_stubs),
                        "sciencebase_id": item_id,
                    }
                ),
                flush=True,
            )

    records.sort(key=lambda record: record["sciencebase_id"])
    raw_manifest.sort(key=lambda record: record["sciencebase_id"])
    result = {
        "schema_version": "wp8-usgs-sciencebase-magnetic-catalogue-v1",
        "source_authority": "U.S. Geological Survey ScienceBase",
        "search_query": SEARCH_QUERY,
        "search_total_declared": total,
        "search_pages": pages,
        "raw_item_count": len(raw_manifest),
        "raw_items": raw_manifest,
        "records": records,
        "metadata_only_eligible_count": sum(
            record["metadata_only_eligible"] for record in records
        ),
        "magnetic_response_values_interpreted": 0,
        "candidate_files_downloaded": 0,
        "test_unseal_count": 0,
    }
    payload = (json.dumps(result, indent=2) + "\n").encode()
    (OUT / "catalogue.json").write_bytes(payload)
    print(
        json.dumps(
            {
                "declared": total,
                "frozen": len(raw_manifest),
                "metadata_only_eligible": result[
                    "metadata_only_eligible_count"
                ],
                "catalogue_sha256": sha256_bytes(payload),
            }
        )
    )


if __name__ == "__main__":
    main()
