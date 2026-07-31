#!/usr/bin/env python
"""Freeze all uncontaminated GA ground-gravity NetCDF payloads without reading arrays."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
CATALOGUE = DATA / "geophysical-datasets-gravity-point.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/ga-national-ground-gravity-design.json"
POOL = DATA / "pool"
OUT = DATA / "pool-manifest.json"
WORKERS = 6
ATTEMPTS = 6


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def download(record: dict) -> dict:
    survey_id = record["survey_id"]
    path = POOL / f"{survey_id}.nc"
    if not path.exists() or path.stat().st_size == 0:
        temporary = path.with_suffix(".nc.part")
        last_error = None
        for attempt in range(ATTEMPTS):
            try:
                request = urllib.request.Request(
                    record["file_download"],
                    headers={"User-Agent": "GeoDeepBayes-WP8 geometry-only audit"},
                )
                with urllib.request.urlopen(request, timeout=240) as response:
                    temporary.write_bytes(response.read())
                temporary.replace(path)
                break
            except Exception as error:
                last_error = error
                if attempt + 1 < ATTEMPTS:
                    time.sleep(2**attempt)
        else:
            raise RuntimeError(
                f"failed after {ATTEMPTS} attempts: {survey_id}"
            ) from last_error
    return {
        "survey_id": survey_id,
        "dataset_no": record["dataset_no"],
        "role": record["role"],
        "path": path.relative_to(DATA).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
        "source_url": record["file_download"],
    }


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    if len(catalogue["features"]) != 1634:
        raise RuntimeError("GA national ground-gravity catalogue drift")
    POOL.mkdir(parents=True, exist_ok=True)
    members = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(download, record) for record in design["records"]]
        for index, future in enumerate(as_completed(futures), 1):
            members.append(future.result())
            if index % 100 == 0:
                print(f"frozen {index}/{len(futures)}")
    members.sort(key=lambda value: value["survey_id"])
    result = {
        "schema_version": "wp8-ga-national-ground-gravity-pool-v1",
        "design_sha256": digest(DESIGN),
        "formal_excluded_surveys": design["formal_excluded_surveys"],
        "member_count": len(members),
        "total_bytes": sum(member["bytes"] for member in members),
        "members": members,
        "netcdf_array_values_interpreted_during_acquisition": 0,
        "response_values_interpreted_during_acquisition": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "members": len(members),
            "total_mib": round(result["total_bytes"] / 1024**2, 2),
        }
    )


if __name__ == "__main__":
    main()
