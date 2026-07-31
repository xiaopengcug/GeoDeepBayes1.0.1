#!/usr/bin/env python3
"""Freeze an outcome-blind Project Magnet high-altitude survey design.

This script reads only the public NCEI catalogue HTML.  It does not download
MAG88T observations and therefore cannot expose candidate-test responses.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from pathlib import Path


CATALOGUE_URL = "https://www.ncei.noaa.gov/products/airborne-magnetic-data"
TRAINING_SURVEY = "PM-HI-ALT-WORLD-C32-051"
SALT = "wp8-ncei-project-magnet-high-alt-v1-2026-07-25"
OUT = Path("validation/wp8/evidence/feasibility-v1/ncei-project-magnet-design-v1.json")


def clean(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?is)<[^>]+>", " ", cell))).strip()


def main() -> None:
    request = urllib.request.Request(CATALOGUE_URL, headers={"User-Agent": "WP8-public-data-audit/1.0"})
    source = urllib.request.urlopen(request, timeout=60).read()
    text = source.decode("utf-8", errors="replace")
    records = []
    for row in re.findall(r"(?is)<tr.*?</tr>", text):
        cells = re.findall(r"(?is)<td.*?</td>", row)
        if len(cells) < 8:
            continue
        values = [clean(cell) for cell in cells]
        project, survey_id, start_year, end_year, nominal_altitude = values[:5]
        if project != "Project Magnet High-Altitude World":
            continue
        zip_urls = re.findall(r'href="([^"]+\.zip)"', row, flags=re.I)
        if not zip_urls:
            continue
        # Restrict the sealed population to the homogeneous declared-altitude
        # series. The already inspected C32-051 survey is permanently training.
        eligible = "25,000 FT AG" in nominal_altitude
        role = "excluded_ineligible"
        if survey_id == TRAINING_SURVEY:
            role = "training_exposed"
            eligible = True
        elif eligible:
            role = "sealed_test_candidate"
        records.append(
            {
                "survey_id": survey_id,
                "project": project,
                "start_year": start_year,
                "end_year": end_year,
                "nominal_altitude": nominal_altitude,
                "survey_zip_url": zip_urls[-1],
                "role": role,
                "role_hash_sha256": hashlib.sha256(f"{SALT}|{survey_id}".encode()).hexdigest(),
            }
        )

    records.sort(key=lambda item: item["survey_id"])
    artifact = {
        "schema_version": "wp8-ncei-project-magnet-design-v1",
        "created_utc": "2026-07-25T00:00:00Z",
        "catalogue_url": CATALOGUE_URL,
        "catalogue_sha256": hashlib.sha256(source).hexdigest(),
        "licence_basis": {
            "catalogue_record": "https://catalog.data.gov/dataset/airborne-magnetic-trackline-database",
            "licence": "https://creativecommons.org/publicdomain/zero/1.0/",
            "description": "NOAA/NCEI Airborne Magnetic Trackline Database public-domain archive",
        },
        "split_salt": SALT,
        "selection_contract": {
            "project_exact": "Project Magnet High-Altitude World",
            "candidate_nominal_altitude_contains": "25,000 FT AG",
            "training_exception": TRAINING_SURVEY,
            "test_response_fields_must_not_be_displayed_or_summarized_during_geometry_audit": True,
            "spatial_cluster_minimum_separation_km": 120.0,
            "minimum_sealed_test_clusters": 223,
        },
        "counts": {
            "catalogue_project_surveys": len(records),
            "training_exposed_surveys": sum(r["role"] == "training_exposed" for r in records),
            "sealed_test_candidate_surveys": sum(r["role"] == "sealed_test_candidate" for r in records),
            "excluded_ineligible_surveys": sum(r["role"] == "excluded_ineligible" for r in records),
        },
        "records": records,
        "response_values_interpreted_during_selection": 0,
        "test_unseal_count": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact["counts"], indent=2))


if __name__ == "__main__":
    main()
