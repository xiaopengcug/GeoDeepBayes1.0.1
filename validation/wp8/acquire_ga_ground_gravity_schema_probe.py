#!/usr/bin/env python
"""Freeze one high-reliability GA NetCDF for schema-only contract probing."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
URL = (
    "https://thredds.nci.org.au/thredds/fileServer/iv65/"
    "Geoscience_Australia_Geophysics_Reference_Data_Collection/"
    "ground_gravity/WA/point/P199964/P199964-point-gravity.nc"
)


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> None:
    path = DATA / "P199964-point-gravity.nc"
    request = urllib.request.Request(
        URL, headers={"User-Agent": "GeoDeepBayes-WP8 schema-only audit"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        path.write_bytes(response.read())
    manifest = {
        "schema_version": "wp8-ga-ground-gravity-schema-probe-raw-v1",
        "survey_id": "P199964",
        "survey_name": "Hamersley Iron Detailed Data",
        "catalogue_gravity_reliability": 6,
        "declared_station_count": 77202,
        "license": "CC BY 4.0 State of Western Australia",
        "source_url": URL,
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "response_values_interpreted_during_acquisition": 0,
    }
    (DATA / "schema-probe-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print({"bytes": manifest["bytes"], "sha256": manifest["sha256"]})


if __name__ == "__main__":
    main()
