#!/usr/bin/env python
"""Freeze non-response contract documents for USGS time-domain AEM surveys."""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = (
    ROOT
    / "validation/wp8/data/usgs-sciencebase-aem-catalogue-v2/catalogue.json"
)
RAW_ITEMS = CATALOGUE.parent / "raw-items"
OUT = ROOT / "validation/wp8/data/usgs-sciencebase-aem-contract-docs-v1"
FILES = OUT / "files"
MANIFEST = OUT / "manifest.json"
QUARANTINE = OUT / "quarantine-response-package"
SYSTEMS = {
    "SkyTEM 304",
    "SkyTEM 304M",
    "SkyTEM 306HPM",
    "SkyTEM 312",
    "SkyTEM 312M",
    "VTEM",
    "TEMPEST",
}
DOC = re.compile(
    r"(dict|readme|report|metadata|revision|version|\.xml$|\.ncml$|\.pdf$|\.txt$)",
    re.I,
)
RESPONSE = re.compile(r"\.(nc|csv|xyz|dat)(\.zip|\.gz)?$", re.I)
ATTEMPTS = 5
WORKERS = 8
USER_AGENT = "GeoDeepBayes-WP8 AEM-contract-docs/1.0"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(
    urls: list[str], *, name: str, declared_size: int | None
) -> tuple[bytes, str]:
    error: Exception | None = None
    for url in urls:
        for attempt in range(ATTEMPTS):
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT}
                )
                with urllib.request.urlopen(request, timeout=180) as response:
                    data = response.read()
                if declared_size is not None and len(data) != int(declared_size):
                    raise RuntimeError(
                        f"length mismatch for {name}: "
                        f"{len(data)} != {declared_size}"
                    )
                if name.lower().endswith(".pdf") and not data.startswith(b"%PDF"):
                    raise RuntimeError(f"non-PDF payload for {name}")
                return data, url
            except Exception as caught:
                error = caught
                if isinstance(caught, HTTPError) and caught.code in {403, 404}:
                    break
                if attempt + 1 < ATTEMPTS:
                    time.sleep(2**attempt)
    raise RuntimeError(f"all document URLs failed: {urls}") from error


def safe_name(item_id: str, name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*#]+', "_", name).strip(" .")
    return f"{item_id}__{cleaned}"


def main() -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    selected = []
    surveys = []
    for record in catalogue["records"]:
        systems = sorted(set(record["systems"]) & SYSTEMS)
        if not record["metadata_only_candidate"] or not systems:
            continue
        item = json.loads(
            (RAW_ITEMS / f"{record['sciencebase_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        surveys.append(
            {
                "sciencebase_id": record["sciencebase_id"],
                "parent_id": record["parent_id"],
                "title": record["title"],
                "systems": systems,
                "bounding_boxes": record["bounding_boxes"],
            }
        )
        for file in item.get("files") or []:
            name = str(file.get("name") or "")
            title = str(file.get("title") or "")
            url = file.get("downloadUri")
            if not url or not DOC.search(f"{name} {title}"):
                continue
            # A named response table is never admitted merely because its title
            # also contains "metadata"; XML/NCML/PDF/TXT and explicit data
            # dictionaries are the only frozen contract evidence.
            is_dictionary = bool(re.search(r"dict", f"{name} {title}", re.I))
            extension = Path(name).suffix.lower()
            if extension not in {".xml", ".ncml", ".pdf", ".txt", ".csv"}:
                continue
            if RESPONSE.search(name) and not is_dictionary:
                continue
            selected.append(
                {
                    "sciencebase_id": record["sciencebase_id"],
                    "systems": systems,
                    "name": name,
                    "title": title or None,
                    "declared_size": file.get("size"),
                    "download_uri": url,
                    "local_name": safe_name(record["sciencebase_id"], name),
                    "document_role": (
                        "data_dictionary"
                        if is_dictionary
                        else "non_response_contract_document"
                    ),
                }
            )

    FILES.mkdir(parents=True, exist_ok=True)

    def acquire(record: dict) -> tuple[dict, bytes]:
        fallback = (
            "https://www.sciencebase.gov/catalog/file/get/"
            f"{record['sciencebase_id']}?"
            + urllib.parse.urlencode({"name": record["name"]})
        )
        data, resolved_url = get(
            [record["download_uri"], fallback],
            name=record["name"],
            declared_size=record["declared_size"],
        )
        return {**record, "resolved_download_uri": resolved_url}, data

    frozen = []
    unavailable = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(acquire, record): record for record in selected
        }
        for index, future in enumerate(as_completed(futures), 1):
            submitted = futures[future]
            try:
                record, data = future.result()
            except Exception as caught:
                unavailable.append(
                    {
                        **submitted,
                        "status": "unavailable_after_retries",
                        "error": repr(caught),
                    }
                )
                print(
                    json.dumps(
                        {
                            "unavailable": submitted["name"],
                            "error": repr(caught),
                        }
                    ),
                    flush=True,
                )
                continue
            path = FILES / record["local_name"]
            path.write_bytes(data)
            frozen.append(
                {
                    **record,
                    "path": path.relative_to(OUT).as_posix(),
                    "bytes": len(data),
                    "sha256": digest(data),
                }
            )
            print(
                json.dumps(
                    {
                        "frozen": index,
                        "total": len(selected),
                        "name": record["name"],
                    }
                ),
                flush=True,
            )
    frozen.sort(key=lambda value: (value["sciencebase_id"], value["name"]))
    unavailable.sort(
        key=lambda value: (value["sciencebase_id"], value["name"])
    )
    surveys.sort(key=lambda value: value["sciencebase_id"])
    result = {
        "schema_version": "wp8-usgs-sciencebase-aem-contract-docs-v1",
        "catalogue_sha256": digest(CATALOGUE.read_bytes()),
        "survey_count": len(surveys),
        "surveys": surveys,
        "document_count": len(frozen),
        "documents": frozen,
        "unavailable_document_count": len(unavailable),
        "unavailable_documents": unavailable,
        "excluded_response_package_download_incidents": [
            {
                "path": path.relative_to(OUT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path.read_bytes()),
                "response_values_interpreted": 0,
                "disposition": "quarantined_and_excluded",
            }
            for path in sorted(QUARANTINE.glob("*"))
            if path.is_file()
        ],
        "response_files_downloaded": sum(
            1 for path in QUARANTINE.glob("*") if path.is_file()
        ),
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    payload = (json.dumps(result, indent=2) + "\n").encode()
    MANIFEST.write_bytes(payload)
    print(
        json.dumps(
            {
                "surveys": len(surveys),
                "documents": len(frozen),
                "manifest_sha256": digest(payload),
                "response_values_interpreted": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
