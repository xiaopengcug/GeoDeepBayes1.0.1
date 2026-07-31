#!/usr/bin/env python
"""Freeze the response-blind Geoscience Australia national AEM catalogue."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-aem-catalog-v1"
BASE = "https://services.ga.gov.au/gis/geophysical-surveys/ows"
TYPE_NAME = "gadds:geophysical_datasets_aem"
EXPECTED_FEATURES = 72


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(params: dict[str, str]) -> bytes:
    url = BASE + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 response-blind AEM freeze"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    capabilities = fetch(
        {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"}
    )
    schema = fetch(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "DescribeFeatureType",
            "typeNames": TYPE_NAME,
        }
    )
    catalogue = fetch(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": TYPE_NAME,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": "10000",
        }
    )
    parsed = json.loads(catalogue)
    features = parsed.get("features", [])
    if (
        parsed.get("numberMatched") != EXPECTED_FEATURES
        or len(features) != EXPECTED_FEATURES
    ):
        raise RuntimeError("Geoscience Australia AEM catalogue count drift")
    paths = {
        "wfs-capabilities.xml": capabilities,
        "aem-schema.xsd": schema,
        "aem-catalog.geojson": catalogue,
    }
    members = []
    for name, content in paths.items():
        path = DATA / name
        path.write_bytes(content)
        members.append(
            {"path": name, "bytes": path.stat().st_size, "sha256": digest(path)}
        )
    manifest = {
        "schema_version": "wp8-geoscience-australia-aem-catalog-freeze-v1",
        "official_wfs": BASE,
        "type_name": TYPE_NAME,
        "feature_count": EXPECTED_FEATURES,
        "service_access_constraints": (
            "Creative Commons Attribution 4.0 International Licence"
        ),
        "catalogue_is_design_metadata_only": True,
        "aem_response_values_interpreted": 0,
        "members": members,
    }
    manifest_path = DATA / "raw-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in [*[DATA / name for name in paths], manifest_path]:
        os.chmod(path, 0o444)
    print(
        json.dumps(
            {
                "features": len(features),
                "catalogue_bytes": len(catalogue),
                "status": "frozen",
            }
        )
    )


if __name__ == "__main__":
    main()
