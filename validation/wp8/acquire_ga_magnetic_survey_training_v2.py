#!/usr/bin/env python
"""Freeze only the 77 training-role GA magnetic surveys from v2."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/geoscience-australia-magnetic-survey-design-v2.json"
DATA = ROOT / "validation/wp8/data/geoscience-australia-magnetic-survey-training-v2"
POOL = DATA / "pool"
OUT = DATA / "raw-manifest.json"
WORKERS = 12
ATTEMPTS = 6


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def download(record: dict) -> dict:
    path = POOL / f"{record['dataset_no']}.nc"
    if not path.exists() or path.stat().st_size == 0:
        temporary = path.with_suffix(".nc.part")
        error = None
        for attempt in range(ATTEMPTS):
            try:
                request = urllib.request.Request(
                    record["file_download"],
                    headers={
                        "User-Agent": "GeoDeepBayes-WP8 GA magnetic v2 training freeze"
                    },
                )
                with urllib.request.urlopen(request, timeout=600) as response, temporary.open(
                    "wb"
                ) as output:
                    for block in iter(
                        lambda: response.read(8 * 1024 * 1024), b""
                    ):
                        output.write(block)
                temporary.replace(path)
                break
            except Exception as caught:
                error = caught
                if attempt + 1 < ATTEMPTS:
                    time.sleep(2**attempt)
        else:
            raise RuntimeError(
                f"failed after {ATTEMPTS} attempts: {record['dataset_no']}"
            ) from error
    return {
        "dataset_no": record["dataset_no"],
        "survey_id": record["survey_id"],
        "survey_name": record["survey_name"],
        "state": record["state"],
        "survey_start_date": record["survey_start_date"],
        "flight_height_agl_m": record["flight_height_agl_m"],
        "line_spacing_min_m": record["line_spacing_min_m"],
        "line_spacing_max_m": record["line_spacing_max_m"],
        "line_azimuth_deg": record["line_azimuth_deg"],
        "license": record["license"],
        "path": path.relative_to(DATA).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "provider_url": record["file_download"],
    }


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    records = [record for record in design["records"] if record["role"] == "train"]
    if len(records) != 77 or design["response_values_interpreted"] != 0:
        raise RuntimeError("GA magnetic v2 training design drift")
    POOL.mkdir(parents=True, exist_ok=True)
    members = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(download, record) for record in records]
        for index, future in enumerate(as_completed(futures), 1):
            member = future.result()
            members.append(member)
            print(
                json.dumps(
                    {
                        "frozen": index,
                        "total": len(records),
                        "dataset_no": member["dataset_no"],
                        "mib": round(member["bytes"] / 1024**2, 2),
                    }
                ),
                flush=True,
            )
    members.sort(key=lambda item: item["dataset_no"])
    result = {
        "schema_version": "wp8-ga-magnetic-survey-training-freeze-v2",
        "design_sha256": sha(DESIGN),
        "role": "train",
        "member_count": len(members),
        "total_bytes": sum(member["bytes"] for member in members),
        "members": members,
        "acquisition_interpreted_response_values": 0,
        "buffer_files_downloaded": 0,
        "calibration_files_downloaded": 0,
        "test_files_downloaded": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "members": len(members),
            "total_gib": round(result["total_bytes"] / 1024**3, 3),
        }
    )


if __name__ == "__main__":
    main()
