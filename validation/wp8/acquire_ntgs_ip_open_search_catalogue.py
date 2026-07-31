#!/usr/bin/env python
"""Freeze the GEMIS OpenSearch IP catalogue and item pages, without data payloads."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ntgs-ip-open-search-catalogue-v1"
BASE = "https://geoscience.nt.gov.au/gemis/ntgsjspui"
QUERIES = (
    '"induced polarisation"',
    '"induced polarization"',
    '"IP survey"',
    "DCIP",
    "PDIP",
    "GAIP",
)
ATOM = {"a": "http://www.w3.org/2005/Atom"}
OPEN = {"o": "http://a9.com/-/spec/opensearch/1.1/"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 NTGS IP catalogue audit"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    feeds = []
    handles: dict[str, str] = {}
    for query_index, query in enumerate(QUERIES):
        start = 1
        while True:
            url = (
                f"{BASE}/open-search/?"
                + urllib.parse.urlencode(
                    {"query": query, "rpp": 100, "start": start}
                )
            )
            payload = fetch(url)
            name = f"feed-q{query_index:02d}-start{start:04d}.xml"
            path = DATA / name
            if path.exists():
                os.chmod(path, 0o644)
            path.write_bytes(payload)
            root = ET.fromstring(payload)
            entries = root.findall("a:entry", ATOM)
            for entry in entries:
                title = entry.findtext("a:title", default="", namespaces=ATOM)
                link = next(
                    (
                        item.attrib["href"]
                        for item in entry.findall("a:link", ATOM)
                        if item.attrib.get("rel") == "alternate"
                    ),
                    None,
                )
                if link:
                    handles[link] = title
            feeds.append(
                {
                    "path": name,
                    "bytes": len(payload),
                    "sha256": sha256(path),
                    "source_url": url,
                    "entry_count": len(entries),
                }
            )
            total = int(root.findtext("o:totalResults", default="0", namespaces=OPEN))
            if start + len(entries) > total or not entries:
                break
            start += len(entries)

    def freeze_page(item: tuple[str, str]) -> dict[str, object]:
        url, title = item
        handle = re.search(r"/handle/1/(\d+)$", url)
        if not handle:
            raise RuntimeError(f"unexpected GEMIS handle: {url}")
        payload = fetch(url)
        name = f"item-{handle.group(1)}.html"
        path = DATA / name
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(payload)
        return {
            "path": name,
            "bytes": len(payload),
            "sha256": sha256(path),
            "source_url": url,
            "title": title,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        pages = list(executor.map(freeze_page, sorted(handles.items())))
    manifest = {
        "schema_version": "wp8-ntgs-ip-open-search-catalogue-v1",
        "queries": list(QUERIES),
        "feeds": feeds,
        "pages": pages,
        "unique_item_count": len(pages),
        "data_payloads_downloaded": 0,
        "response_values_interpreted": 0,
        "formal_test_endpoints_inspected": False,
        "test_unseal_count": 0,
    }
    manifest_path = DATA / "raw-manifest.json"
    if manifest_path.exists():
        os.chmod(manifest_path, 0o644)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in [
        manifest_path,
        *(DATA / member["path"] for member in feeds),
        *(DATA / member["path"] for member in pages),
    ]:
        os.chmod(path, 0o444)
    print(json.dumps({"feeds": len(feeds), "items": len(pages)}))


if __name__ == "__main__":
    main()
