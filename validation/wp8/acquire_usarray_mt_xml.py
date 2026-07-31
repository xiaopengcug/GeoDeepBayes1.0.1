#!/usr/bin/env python
"""Acquire EMTF source XML without interpreting sealed partition payloads."""
from __future__ import annotations

import hashlib
import html
import http.client
import json
import os
import re
import stat
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usarray-ta-emtf-v1"
XML = RAW / "xml"
EDI_MANIFEST = RAW / "raw-manifest.json"
OUTPUT = RAW / "xml-raw-manifest.json"
PARTIAL_OUTPUT = RAW / "xml-raw-manifest.partial.json"
USER_AGENT = "GeoDeepBayes-WP8-feasibility/1.0 (public scientific data audit)"


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def request(url: str, attempts: int = 5) -> tuple[bytes, dict[str, str]]:
    error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as response:
                try:
                    body = response.read()
                except http.client.IncompleteRead as exc:
                    # SPUD occasionally omits the terminating HTTP chunk while
                    # delivering the complete small XML/HTML payload.
                    body = exc.partial
                    if not body:
                        raise
                headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower() in {"content-type", "content-length", "etag", "last-modified"}
                }
            return body, headers
        except Exception as exc:  # network retry boundary
            error = exc
            time.sleep(min(8, 2**attempt))
    raise RuntimeError(f"request failed after {attempts} attempts: {url}: {error}")


def source_xml_url(spud_id: str) -> tuple[str, str]:
    item_url = f"https://ds.iris.edu/spudservice/emtf/{spud_id}"
    body, _ = request(item_url)
    # Service wraps escaped XML in an HTML <pre>; this step reads only item
    # metadata needed to resolve SourceData, not transfer-function values.
    metadata = html.unescape(body.decode("utf-8", errors="strict"))
    match = re.search(
        r"<SourceData\s+id=\"(\d+)\">[\s\S]*?"
        r"<MimeType>application/xml</MimeType>[\s\S]*?"
        r"<DataLink>(?:<a[^>]*>)?https?://[^<]*/spudservice/data/(\d+)",
        metadata,
        re.IGNORECASE,
    )
    if not match or match.group(1) != match.group(2):
        raise RuntimeError(f"source XML link missing or inconsistent: {spud_id}")
    source_id = match.group(1)
    return f"https://ds.iris.edu/spudservice/data/{source_id}", source_id


def embedded_xml(spud_id: str) -> tuple[bytes, dict[str, str], str]:
    """Extract the official EMTF XML tab embedded in the public item page."""
    url = f"https://ds.iris.edu/spud/emtf/{spud_id}"
    page, headers = request(url)
    text = page.decode("utf-8", errors="strict")
    match = re.search(
        r"<pre><span[^>]*>\s*(&lt;EM_TF&gt;[\s\S]*?&lt;/EM_TF&gt;)\s*</span>\s*</pre>",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError(f"embedded EMTF XML missing: {spud_id}")
    body = html.unescape(match.group(1)).encode("utf-8")
    return body, headers, url


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    edi = json.loads(EDI_MANIFEST.read_text(encoding="utf-8"))
    XML.mkdir(parents=True, exist_ok=True)
    split = {str(member["spud_id"]): member["split"] for member in edi["members"]}

    def acquire(spud_id: str) -> dict[str, object]:
        path = XML / f"{spud_id}.xml"
        if path.is_file():
            body = path.read_bytes()
            headers = {"resume": "local-existing-file"}
            retrieved = None
            source_id = None
            source_url = f"https://ds.iris.edu/spudservice/emtf/{spud_id}#SourceData"
        else:
            try:
                body, headers, source_url = embedded_xml(spud_id)
                source_id = None
            except RuntimeError as embedded_error:
                if "embedded EMTF XML missing" not in str(embedded_error):
                    raise
                source_url, source_id = source_xml_url(spud_id)
                body, headers = request(source_url)
            if not body.lstrip().startswith((b"<?xml", b"<EM_T")):
                raise RuntimeError(f"non-XML source payload: {spud_id}")
            path.write_bytes(body)
            retrieved = datetime.now(timezone.utc).isoformat()
        os.chmod(path, stat.S_IREAD)
        return {
            "spud_id": spud_id,
            "split": split[spud_id],
            "source_data_id": source_id,
            "request_url": source_url,
            "retrieved_at_utc": retrieved,
            "http_metadata": headers,
            "bytes": len(body),
            "sha256": sha(body),
            "path": f"xml/{spud_id}.xml",
            "payload_interpreted": False,
        }

    ids = sorted(split, key=int)
    members = []
    # Six page requests are modest and avoid the service endpoint's stricter
    # chunked-response throttling.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(acquire, spud_id): spud_id for spud_id in ids}
        for index, future in enumerate(as_completed(futures), 1):
            members.append(future.result())
            if index % 25 == 0 or index == len(ids):
                print(f"downloaded/verified XML {index}/{len(ids)}", flush=True)
                atomic_json(
                    PARTIAL_OUTPUT,
                    {
                        "schema_version": "wp8-usarray-ta-xml-partial-manifest-v1",
                        "completed": index,
                        "target": len(ids),
                        "members": sorted(
                            members, key=lambda item: int(str(item["spud_id"]))
                        ),
                    },
                )
    members.sort(key=lambda item: int(str(item["spud_id"])))
    manifest = {
        "schema_version": "wp8-usarray-ta-xml-raw-manifest-v1",
        "survey_doi": "10.17611/DP/EMTF/USARRAY/TA",
        "split_frozen_before_requests": True,
        "member_count": len(members),
        "total_xml_bytes": sum(int(item["bytes"]) for item in members),
        "sealed_payloads_interpreted": False,
        "members": members,
    }
    atomic_json(OUTPUT, manifest)
    PARTIAL_OUTPUT.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "members": len(members),
                "bytes": manifest["total_xml_bytes"],
                "splits": {
                    role: sum(member["split"] == role for member in members)
                    for role in ("train", "buffer", "calibration", "test")
                },
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
