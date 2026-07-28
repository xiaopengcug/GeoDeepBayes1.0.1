#!/usr/bin/env python
"""Freeze the anonymous MRT Tasmania gravity GeoPackage archive."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/mrt-tasmania-gravity-v1"
ARCHIVE_URL = (
    "https://www.mrt.tas.gov.au/mrtdoc/public_files/"
    "Gravity_Data_Geopackage.zip"
)
LANDING_URL = (
    "https://www.mrt.tas.gov.au/products/digital_data/"
    "data_downloads/geophysics_data"
)
METADATA_URL = (
    "https://www.thelist.tas.gov.au/app/content/data/geo-meta-data-record"
    "?detailRecordUID=eff3fe13-7531-409f-ad1d-4e9ff6e071ea"
)
LICENSE_URL = "https://www.mrt.tas.gov.au/products/database_searches"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 public-data audit"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / "Gravity_Data_Geopackage.zip"
    archive.write_bytes(fetch(ARCHIVE_URL))
    manifest = {
        "schema_version": "wp8-mrt-tasmania-gravity-raw-v1",
        "dataset": "Gravity Measurements Data (Mineral Resources Tasmania)",
        "landing_url": LANDING_URL,
        "metadata_url": METADATA_URL,
        "source_url": ARCHIVE_URL,
        "license": "Creative Commons Attribution 3.0 Australia",
        "license_evidence_url": LICENSE_URL,
        "archive": {
            "path": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
        },
        "response_values_interpreted_during_acquisition": 0,
        "anonymous_download": True,
    }
    (DATA / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(manifest["archive"])


if __name__ == "__main__":
    main()
