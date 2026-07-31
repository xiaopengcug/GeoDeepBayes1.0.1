#!/usr/bin/env python
"""Freeze the H+ Guidel 2025 raw square-wave SIP release response-blind."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/guidel-sip-2025-v1"
PAGE_URL = (
    "https://hplus.ore.fr/a-spectral-induced-polarization-instrument-using-square-wave-"
    "current-injection-to-track-critical-zone-processes-application-to-long-term-"
    "monitoring-of-a-wetland-guidel-france/"
)
ARCHIVE_URL = (
    "https://wp1-edu.sedoo.fr/wp-content-omp/uploads/sites/49/2026/02/"
    "Guidel_SIP_DOI_2026.zip"
)
DATA_DOI = "10.26169/hplus.guidel_spectral_induced_polarization"
DATACITE_URL = f"https://api.datacite.org/dois/{DATA_DOI}"
MONITORING_URL = (
    "https://hplus.ore.fr/documents/requests/guidel/"
    "guidel_sip_monitoring_data.csv.tgz"
)
ARTICLE_URL = "https://oup.silverchair-cdn.com/article-minimal/8472866"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 Guidel SIP freeze"}
    )
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as out:
        while block := response.read(1024 * 1024):
            out.write(block)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    page = DATA / "hplus-dataset-page.html"
    archive = DATA / "Guidel_SIP_DOI_2026.zip"
    datacite = DATA / "datacite-record.json"
    monitoring = DATA / "guidel_sip_monitoring_data.csv.tgz"
    article = DATA / "gji-ggag060-article.html"
    if not page.exists():
        fetch(PAGE_URL, page)
    if not datacite.exists():
        fetch(DATACITE_URL, datacite)
    if not archive.exists():
        fetch(ARCHIVE_URL, archive)
    if not monitoring.exists():
        fetch(MONITORING_URL, monitoring)
    if not article.exists():
        fetch(ARTICLE_URL, article)
    article_text = article.read_text(encoding="utf-8").replace("\N{NO-BREAK SPACE}", " ")
    for required in (
        "50 cm apart",
        "depths ranging from 23 to 93 cm",
        "stainless steel rings every 5 cm",
    ):
        if required not in article_text:
            raise RuntimeError(f"Guidel article geometry drift: {required}")
    record = json.loads(datacite.read_text(encoding="utf-8"))
    rights = record["data"]["attributes"]["rightsList"]
    if not any(
        item.get("rightsIdentifier", "").lower() == "cc-by-nc-sa-4.0"
        for item in rights
    ):
        raise RuntimeError("Guidel DataCite license drift")
    target = DATA / "raw-manifest.json"
    if target.exists():
        os.chmod(target, 0o644)
    manifest = {
        "schema_version": "wp8-guidel-sip-2025-raw-v1",
        "doi": DATA_DOI,
        "publisher": "SNO H+ / Geosciences Rennes",
        "site": "Guidel wetland, France",
        "license": "CC BY-NC-SA 4.0",
        "license_uri": "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode",
        "partition_assignment": "training-only",
        "partition_assignment_precedes_response_read": True,
        "selection_is_response_blind": True,
        "members": [
            {"path": page.name, "bytes": page.stat().st_size, "sha256": sha256(page), "source_url": PAGE_URL},
            {"path": datacite.name, "bytes": datacite.stat().st_size, "sha256": sha256(datacite), "source_url": DATACITE_URL},
            {"path": archive.name, "bytes": archive.stat().st_size, "sha256": sha256(archive), "source_url": ARCHIVE_URL},
            {"path": monitoring.name, "bytes": monitoring.stat().st_size, "sha256": sha256(monitoring), "source_url": MONITORING_URL},
            {"path": article.name, "bytes": article.stat().st_size, "sha256": sha256(article), "source_url": ARTICLE_URL},
        ],
        "response_values_interpreted_during_acquisition": 0,
        "test_unseal_count": 0,
    }
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in (page, datacite, archive, monitoring, article, target):
        os.chmod(path, 0o444)
    print(
        json.dumps(
            {
                "members": 5,
                "archive_bytes": archive.stat().st_size,
                "monitoring_bytes": monitoring.stat().st_size,
            }
        )
    )


if __name__ == "__main__":
    main()
