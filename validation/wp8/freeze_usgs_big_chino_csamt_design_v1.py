from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/wp8/data/usgs-big-chino-stations.zip"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-big-chino-csamt-design-v1.json"
SALT = "usgs-big-chino-csamt-v1"
MIN_DISTANCE_M = 200.0


def digest(value: str) -> str:
    return hashlib.sha256(f"{SALT}|{value}".encode()).hexdigest()


def distance(a: dict, b: dict) -> float:
    return math.hypot(a["easting_m"] - b["easting_m"], a["northing_m"] - b["northing_m"])


def main() -> None:
    stations = []
    with ZipFile(SOURCE) as archive:
        lines = sorted(archive.namelist())
        ranked_lines = sorted(lines, key=digest)
        training_lines = set(ranked_lines[:6])
        for name in lines:
            text = archive.read(name).decode("utf-8-sig")
            for row in csv.DictReader(io.StringIO(text)):
                stations.append(
                    {
                        "line": Path(name).stem,
                        "station": row["Station"],
                        "easting_m": float(row["Easting"]),
                        "northing_m": float(row["Northing"]),
                    }
                )

    training = [p for p in stations if f"{p['line']}.stn" in training_lines]
    candidates = [p for p in stations if f"{p['line']}.stn" not in training_lines]
    eligible = [p for p in candidates if all(distance(p, q) >= MIN_DISTANCE_M for q in training)]
    selected = []
    for point in sorted(eligible, key=lambda p: digest(f"{p['line']}|{p['station']}")):
        if all(distance(point, prior) >= MIN_DISTANCE_M for prior in selected):
            selected.append(point)

    result = {
        "design_version": "usgs-big-chino-csamt-design-v1",
        "status": "frozen_before_response_archive_download_or_inspection",
        "source": {
            "doi": "10.5066/P9KGKWNL",
            "license": "US Government public domain",
            "station_archive_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "outcome_blinding": {
            "read": ["line name", "station", "easting", "northing", "elevation"],
            "not_downloaded_or_read": ["raw CSAMT response archive", "inversion response archive"],
        },
        "split": {
            "training_lines": sorted(Path(x).stem for x in training_lines),
            "sealed_test_lines": sorted(
                Path(x).stem for x in set(lines).difference(training_lines)
            ),
            "minimum_training_test_distance_m": MIN_DISTANCE_M,
            "minimum_test_test_distance_m": MIN_DISTANCE_M,
            "salt": SALT,
        },
        "counts": {
            "lines": len(lines),
            "stations": len(stations),
            "training_stations": len(training),
            "candidate_test_stations": len(candidates),
            "eligible_after_training_distance": len(eligible),
            "sealed_independent_test_clusters": len(selected),
        },
        "sealed_test_cluster_geometry": selected,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["split"], ensure_ascii=False))
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
