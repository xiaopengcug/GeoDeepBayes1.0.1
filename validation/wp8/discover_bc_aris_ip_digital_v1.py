"""Discover public BC ARIS IP reports with digital ground-geophysics archives.

This catalogue-only pass deliberately does not open ZIP members or PDF response
tables.  It is safe to use before a training/test split is frozen.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import http.cookiejar
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "https://apps.nrs.gov.bc.ca/pub/aris"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent
    / "evidence"
    / "feasibility-v1"
    / "bc-aris-ip-digital-catalogue-v1.json"
)
TOKEN_RE = re.compile(
    r'name="__RequestVerificationToken"[^>]+value="([^"]+)"'
)
ROW_RE = re.compile(
    r"<tr>\s*<td[^>]*>\s*<a[^>]+/Detail/(\d+)[^>]*>.*?</tr>",
    re.IGNORECASE | re.DOTALL,
)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(fragment: str) -> str:
    text = TAG_RE.sub(" ", fragment)
    return " ".join(html.unescape(text).split())


def absolute_url(path: str) -> str:
    return urllib.parse.urljoin(BASE_URL + "/", html.unescape(path))


def parse_page(page: str) -> list[dict]:
    records: list[dict] = []
    for match in ROW_RE.finditer(page):
        report_number = match.group(1)
        row = match.group(0)
        cells = CELL_RE.findall(row)
        hrefs = [absolute_url(value) for value in HREF_RE.findall(row)]
        archive_urls = sorted(
            {value for value in hrefs if re.search(r"[A-Z]?\.zip/?$", value, re.I)}
        )
        pdf_urls = sorted(
            {value for value in hrefs if re.search(r"\.pdf/?$", value, re.I)}
        )
        records.append(
            {
                "report_number": report_number,
                "property_name": clean_text(cells[2]) if len(cells) > 2 else "",
                "mining_division": clean_text(cells[3]) if len(cells) > 3 else "",
                "catalogue_location_dms": (
                    clean_text(cells[8]) if len(cells) > 8 else ""
                ),
                "general_work": clean_text(cells[9]) if len(cells) > 9 else "",
                "off_confidential": clean_text(cells[10]) if len(cells) > 10 else "",
                "detail_url": f"{BASE_URL}/Detail/{report_number}",
                "archive_urls": archive_urls,
                "pdf_urls": pdf_urls,
            }
        )
    return records


def head_metadata(url: str) -> dict:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            length = response.headers.get("Content-Length")
            return {
                "url": url,
                "http_status": response.status,
                "content_length": int(length) if length else None,
                "content_type": response.headers.get("Content-Type"),
                "content_disposition": response.headers.get(
                    "Content-Disposition"
                ),
            }
    except Exception as exc:  # fail visibly in evidence instead of dropping a record
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def discover() -> dict:
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    with opener.open(BASE_URL, timeout=60) as response:
        landing = response.read().decode("utf-8")
    token_match = TOKEN_RE.search(landing)
    if not token_match:
        raise RuntimeError("ARIS anti-forgery token was not found")

    form = [
        ("__RequestVerificationToken", token_match.group(1)),
        ("Params.MaxRecordsToReturnText", "All"),
        ("Params.SelectedGeneralWorkTypes", "GEOP"),
        ("Params.SelectedSpecificWorkTypes", "IPOL"),
        ("Params.SelectedKeywords[0]", "Digital data ground geophysics"),
        ("Params.AllKeywords", "True"),
        ("Params.AllCommodities", "False"),
        ("Params.LatitudeFrom", "0"),
        ("Params.LatitudeTo", "0"),
        ("Params.LongitudeFrom", "0"),
        ("Params.LongitudeTo", "0"),
        ("Params.MiningCampCd", "0"),
    ]
    request = urllib.request.Request(
        BASE_URL,
        data=urllib.parse.urlencode(form).encode("ascii"),
        method="POST",
    )
    with opener.open(request, timeout=60) as response:
        first_page = response.read().decode("utf-8")

    count_match = re.search(r"(\d+)\s+records found", first_page)
    if not count_match:
        raise RuntimeError("ARIS result count was not found")
    reported_count = int(count_match.group(1))
    page_count_match = re.search(r"Page 1\s+of\s+(\d+)", first_page)
    page_count = int(page_count_match.group(1)) if page_count_match else 1

    records = parse_page(first_page)
    for page_number in range(2, page_count + 1):
        with opener.open(
            f"{BASE_URL}/GridNav?page={page_number}", timeout=60
        ) as response:
            records.extend(parse_page(response.read().decode("utf-8")))

    by_number = {row["report_number"]: row for row in records}
    records = [by_number[key] for key in sorted(by_number, key=int, reverse=True)]
    if len(records) != reported_count:
        raise RuntimeError(
            f"ARIS returned {reported_count} records but parsed {len(records)}"
        )

    archive_urls = [
        url for record in records for url in record.get("archive_urls", [])
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        archive_metadata = list(executor.map(head_metadata, archive_urls))
    metadata_by_url = {row["url"]: row for row in archive_metadata}
    for record in records:
        record["archives"] = [
            metadata_by_url[url] for url in record.pop("archive_urls")
        ]

    valid_archives = [
        archive
        for record in records
        for archive in record["archives"]
        if archive.get("http_status") == 200
        and archive.get("content_length") is not None
    ]
    return {
        "schema_version": "wp8-bc-aris-ip-digital-catalogue-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "British Columbia Geological Survey",
            "catalogue": BASE_URL,
            "digital_data_policy": (
                "https://www2.gov.bc.ca/gov/content/industry/"
                "mineral-exploration-mining/british-columbia-geological-survey/"
                "assessmentreports/downloaddigitaldata"
            ),
            "terms": "https://www2.gov.bc.ca/gov/content/home/disclaimer",
        },
        "query": {
            "general_work": "GEOP (Geophysical)",
            "specific_work": "IPOL (Induced Polarization)",
            "all_keywords": ["Digital data ground geophysics"],
            "response_payloads_opened": False,
            "archive_members_listed": False,
            "pdf_response_tables_opened": False,
        },
        "catalogue_counts": {
            "reported_records": reported_count,
            "parsed_unique_records": len(records),
            "records_with_archive_endpoint": sum(
                bool(row["archives"]) for row in records
            ),
            "head_verified_archive_endpoints": len(valid_archives),
            "head_verified_total_bytes": sum(
                row["content_length"] for row in valid_archives
            ),
        },
        "gate_assessment": {
            "classification_complete": False,
            "reason": (
                "ARIS work-type metadata does not distinguish TDIP from "
                "frequency-domain or spectral IP; archive contracts and survey "
                "line separation must be audited after freezing a training/test "
                "discovery design."
            ),
            "formal_clusters_added": 0,
            "formal_gate_changed": False,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = discover()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["catalogue_counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
