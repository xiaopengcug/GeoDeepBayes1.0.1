#!/usr/bin/env python
"""Audit public access paths for the sealed Texas AIB response archive."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/texas-aib-response-access.json"
)
CUID = "cmmfhsco500600vpdcjjd4tu8"
ITEM_ID = "69ab5a87b66b01cd2fd12813"
NAME = "TX_AIB_mag.csv.zip"
EXPECTED_BYTES = 4_236_679_294
MANAGER = f"https://sciencebase.usgs.gov/manager/download/{CUID}"
REQUEST_PAGE = (
    f"https://www.sciencebase.gov/catalog/item/requestDownload/{ITEM_ID}"
    "?filePath=__s3__"
)
UNSIGNED_S3 = (
    "https://prod-is-usgs-sb-prod-content.s3.amazonaws.com/"
    f"{ITEM_ID}/{NAME}"
)


def probe(url: str, method: str = "HEAD", limit: int = 8192) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "GeoDeepBayes-WP8 public-data feasibility audit"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(limit) if method == "GET" else b""
            return {
                "url": url,
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "body_prefix": body.decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as error:
        body = error.read(limit) if method == "GET" else b""
        return {
            "url": url,
            "status": error.code,
            "content_type": error.headers.get("Content-Type"),
            "content_length": error.headers.get("Content-Length"),
            "body_prefix": body.decode("utf-8", "replace"),
        }


def main() -> None:
    manager = probe(MANAGER)
    request_page = probe(REQUEST_PAGE, method="GET")
    unsigned = probe(UNSIGNED_S3)
    captcha_required = (
        request_page["status"] == 200
        and "Captcha check" in str(request_page["body_prefix"])
    )
    direct_archive_available = (
        manager["status"] == 200
        and manager["content_type"] == "application/zip"
        and int(manager["content_length"] or 0) == EXPECTED_BYTES
    )
    evidence = {
        "schema_version": "wp8-texas-aib-response-access-v1",
        "sciencebase_item_id": ITEM_ID,
        "file": NAME,
        "expected_bytes": EXPECTED_BYTES,
        "manager_probe": {key: value for key, value in manager.items() if key != "body_prefix"},
        "request_page_probe": {
            key: value for key, value in request_page.items() if key != "body_prefix"
        },
        "unsigned_s3_probe": {
            key: value for key, value in unsigned.items() if key != "body_prefix"
        },
        "captcha_required_for_presigned_url": captcha_required,
        "direct_archive_available_without_human_challenge": direct_archive_available,
        "response_bytes_read": 0,
        "status": (
            "direct_download_available"
            if direct_archive_available
            else "human_captcha_required_for_temporary_presigned_url"
            if captcha_required and unsigned["status"] == 403
            else "public_access_path_unresolved"
        ),
        "unblock_condition": (
            "complete the ScienceBase browser CAPTCHA and provide the resulting "
            "unexpired direct S3 URL; then run the resumable sealed acquisition"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "manager_status": manager["status"],
                "request_page_status": request_page["status"],
                "unsigned_s3_status": unsigned["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
