#!/usr/bin/env python
"""Freeze an outcome-blind USGS ScienceBase airborne-EM metadata catalogue."""
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
OUT = ROOT / "validation/wp8/data/usgs-sciencebase-aem-catalogue-v2"
RAW = OUT / "raw-items"
QUERIES = (
    "airborne electromagnetic survey",
    "SkyTEM",
    "VTEM",
    "TEMPEST airborne",
)
PAGE_SIZE = 100
WORKERS = 12
ATTEMPTS = 5
USER_AGENT = "GeoDeepBayes-WP8 public-AEM-catalogue/1.0"
SYSTEM_PATTERNS = {
    "SkyTEM 304M": r"skytem\s*304m",
    "SkyTEM 304": r"skytem\s*304(?!m)",
    "SkyTEM 306HPM": r"skytem\s*306hpm",
    "SkyTEM 312M": r"skytem\s*312m",
    "SkyTEM 312": r"skytem\s*312(?!m)",
    "SkyTEM 508": r"skytem\s*508",
    "VTEM": r"\bvtem\b",
    "TEMPEST": r"\btempest\b",
    "Resolve": r"\bresolve\b",
    "DIGHEM": r"\bdighem\b",
}
DATA_FILE = re.compile(r"\.(nc|csv|xyz|dat)(\.zip|\.gz)?$", re.I)


def sha256(value: bytes) -> str:
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


def item_text(item: dict) -> str:
    values = [
        str(item.get(key) or "")
        for key in ("title", "summary", "body", "purpose", "citation")
    ]
    values.extend(json.dumps(tag, sort_keys=True) for tag in item.get("tags") or [])
    return " ".join(values)


def bounding_boxes(item: dict) -> list[dict]:
    result = []
    for facet in item.get("facets") or []:
        box = facet.get("boundingBox")
        if not isinstance(box, dict):
            continue
        keys = ("minX", "minY", "maxX", "maxY")
        if all(isinstance(box.get(key), (int, float)) for key in keys):
            normalized = {key: float(box[key]) for key in keys}
            if normalized not in result:
                result.append(normalized)
    return result


def compact(item: dict) -> dict:
    text = item_text(item)
    lowered = text.lower()
    systems = [
        name
        for name, pattern in SYSTEM_PATTERNS.items()
        if re.search(pattern, text, re.I)
    ]
    files = []
    for file in item.get("files") or []:
        name = file.get("name") or ""
        description = " ".join(
            str(file.get(key) or "")
            for key in ("name", "title", "contentType")
        )
        if DATA_FILE.search(name) and any(
            term in description.lower()
            for term in (
                "aem",
                "electromagnetic",
                "em_",
                "em-",
                "skytem",
                "vtem",
                "tempest",
                "resolve",
            )
        ):
            files.append(
                {
                    key: file.get(key)
                    for key in (
                        "name",
                        "title",
                        "contentType",
                        "size",
                        "dateUploaded",
                        "downloadUri",
                        "checksum",
                    )
                }
            )
    processing = {
        "mentions_processed": "processed" in lowered,
        "mentions_fully_processed": "fully processed" in lowered,
        "mentions_minimally_processed": "minimally processed" in lowered,
        "mentions_raw": bool(re.search(r"\braw\b", lowered)),
        "mentions_uncertainty_or_error": any(
            term in lowered
            for term in (
                "uncertainty",
                "standard deviation",
                "error estimate",
                "relative error",
                "noise",
            )
        ),
        "mentions_time_channels": any(
            term in lowered
            for term in ("time channel", "time gate", "gate time", "time-domain")
        ),
        "mentions_flight_height": any(
            term in lowered
            for term in ("flight height", "terrain clearance", "height above")
        ),
    }
    return {
        "sciencebase_id": item["id"],
        "parent_id": item.get("parentId"),
        "title": item.get("title"),
        "citation": item.get("citation"),
        "dates": item.get("dates") or [],
        "systems": systems,
        "processing_flags": processing,
        "bounding_boxes": bounding_boxes(item),
        "candidate_data_files": files,
        "item_url": f"https://www.sciencebase.gov/catalog/item/{item['id']}",
        "metadata_only_candidate": bool(
            ("airborne electromagnetic" in lowered or "aem" in lowered)
            and systems
            and files
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    pages = []
    stubs: dict[str, dict] = {}
    declared_totals = {}
    for query_text in QUERIES:
        total = None
        offset = 0
        while total is None or offset < total:
            query = urllib.parse.urlencode(
                {
                    "format": "json",
                    "max": PAGE_SIZE,
                    "offset": offset,
                    "q": query_text,
                }
            )
            url = f"https://www.sciencebase.gov/catalog/items?{query}"
            raw, page = get_json(url)
            slug = re.sub(r"[^a-z0-9]+", "-", query_text.lower()).strip("-")
            path = OUT / f"search-{slug}-offset-{offset}.json"
            path.write_bytes(raw)
            pages.append(
                {
                    "query": query_text,
                    "offset": offset,
                    "url": url,
                    "path": path.relative_to(OUT).as_posix(),
                    "bytes": len(raw),
                    "sha256": sha256(raw),
                    "returned": len(page.get("items") or []),
                }
            )
            total = int(page["total"])
            declared_totals[query_text] = total
            for item in page.get("items") or []:
                stubs[item["id"]] = item
            offset += PAGE_SIZE

    def acquire(item_id: str) -> tuple[str, bytes, dict]:
        url = f"https://www.sciencebase.gov/catalog/item/{item_id}?format=json"
        raw, item = get_json(url)
        return item_id, raw, item

    records = []
    raw_manifest = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(acquire, item_id): item_id
            for item_id in sorted(stubs)
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
                    "sha256": sha256(raw),
                }
            )
            records.append(compact(item))
            print(
                json.dumps(
                    {"frozen": index, "total": len(stubs), "id": item_id}
                ),
                flush=True,
            )
    records.sort(key=lambda record: record["sciencebase_id"])
    raw_manifest.sort(key=lambda record: record["sciencebase_id"])
    result = {
        "schema_version": "wp8-usgs-sciencebase-aem-catalogue-v2",
        "source_authority": "U.S. Geological Survey ScienceBase",
        "search_queries": list(QUERIES),
        "search_totals_declared": declared_totals,
        "search_pages": pages,
        "raw_item_count": len(raw_manifest),
        "raw_items": raw_manifest,
        "records": records,
        "metadata_only_candidate_count": sum(
            record["metadata_only_candidate"] for record in records
        ),
        "systems_declared": sorted(
            {
                system
                for record in records
                if record["metadata_only_candidate"]
                for system in record["systems"]
            }
        ),
        "aem_response_values_interpreted": 0,
        "candidate_files_downloaded": 0,
        "test_unseal_count": 0,
    }
    payload = (json.dumps(result, indent=2) + "\n").encode()
    (OUT / "catalogue.json").write_bytes(payload)
    print(
        json.dumps(
            {
                "declared_by_query": declared_totals,
                "frozen": len(raw_manifest),
                "candidates": result["metadata_only_candidate_count"],
                "systems": result["systems_declared"],
                "catalogue_sha256": sha256(payload),
            }
        )
    )


if __name__ == "__main__":
    main()
