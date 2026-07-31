#!/usr/bin/env python
"""Freeze GA's anonymous national catalogue of ground-gravity point datasets."""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
WFS = "https://services.ga.gov.au/gis/geophysical-surveys/wfs"
FILTER = "MEASURE_SUB_TYPE='gravity point data' AND DATASET_TYPE='point'"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "GeoDeepBayes-WP8 public-data audit"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    query = urllib.parse.urlencode(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "gadds:geophysical_datasets_gravity",
            "outputFormat": "application/json",
            "count": 3000,
            "cql_filter": FILTER,
        }
    )
    url = f"{WFS}?{query}"
    raw = DATA / "geophysical-datasets-gravity-point.json"
    raw.write_bytes(fetch(url))
    catalogue = json.loads(raw.read_text(encoding="utf-8"))
    features = catalogue["features"]
    declared = [
        feature["properties"].get("GRAVITY_STATIONS") for feature in features
    ]
    manifest = {
        "schema_version": "wp8-ga-national-ground-gravity-catalogue-v1",
        "dataset": "Geoscience Australia ground-gravity point dataset catalogue",
        "source_url": url,
        "catalogue": {
            "path": raw.name,
            "bytes": raw.stat().st_size,
            "sha256": sha(raw),
            "number_matched": catalogue["numberMatched"],
            "number_returned": catalogue["numberReturned"],
        },
        "dataset_count": len(features),
        "datasets_with_declared_station_count": sum(
            isinstance(value, (int, float)) for value in declared
        ),
        "declared_station_total": int(
            sum(value for value in declared if isinstance(value, (int, float)))
        ),
        "licenses": sorted(
            {
                feature["properties"].get("LICENCE")
                for feature in features
                if feature["properties"].get("LICENCE")
            }
        ),
        "anonymous_file_download_urls": sum(
            bool(feature["properties"].get("FILE_DOWNLOAD")) for feature in features
        ),
        "response_values_interpreted_during_acquisition": 0,
    }
    (DATA / "raw-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        {
            "datasets": manifest["dataset_count"],
            "declared_stations": manifest["declared_station_total"],
            "download_urls": manifest["anonymous_file_download_urls"],
        }
    )


if __name__ == "__main__":
    main()
