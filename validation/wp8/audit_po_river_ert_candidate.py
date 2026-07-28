#!/usr/bin/env python
"""Outcome-blind contract and absolute cluster-bound audit for Po River ERT."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/po-river-ert-v1"
ARCHIVE = DATA / "Electrical_Tomography_Data.7z"
MANIFEST = DATA / "raw-manifest.json"
RECORD = DATA / "source-record.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/po-river-ert-candidate.json"
POSITIONS = "Electrical_Tomography_Data/Electrodes_Positions.csv"
RESPONSES = "Electrical_Tomography_Data/Resistivity_data.csv"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def member(name: str) -> bytes:
    result = subprocess.run(
        ["tar", "-xOf", str(ARCHIVE), name],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return result.stdout


def main() -> None:
    positions = list(
        csv.DictReader(io.StringIO(member(POSITIONS).decode("utf-8-sig")))
    )
    # Header only: no response row is opened or parsed in this audit.
    response_header = member(RESPONSES).splitlines()[0].decode("utf-8-sig")
    headers = next(csv.reader([response_header]))
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in positions:
        grouped[int(row["num_shot"])].append(
            (
                float(row["x(m)_EPSG32632"]),
                float(row["y(m)_EPSG32632"]),
            )
        )
    centers = {
        shot: np.mean(np.asarray(points), axis=0)
        for shot, points in sorted(grouped.items())
    }
    ordered = sorted(centers)
    step_lengths = np.asarray(
        [
            np.linalg.norm(centers[right] - centers[left])
            for left, right in zip(ordered[:-1], ordered[1:], strict=True)
        ]
    )
    footprint_m = 48.0
    selected = [ordered[0]]
    path_since_selected = 0.0
    for index, shot in enumerate(ordered[1:]):
        path_since_selected += step_lengths[index]
        if path_since_selected >= footprint_m:
            selected.append(shot)
            path_since_selected = 0.0

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    required = {
        "ABMN": all(name in headers for name in ("A", "B", "M", "N")),
        "apparent_resistivity": "Rho(Ohm*m)" in headers,
        "standard_deviation_percent": "St.Dev.(%)" in headers,
        "primary_voltage": "V_MN(mV) " in headers,
        "injected_current": "I_AB(mA)" in headers,
        "array_type": (
            "datatype(WennerShlumberger;DipoleDipole;Gapfiller)" in headers
        ),
        "electrode_xy": len(positions) == 518 * 13,
        "crs": any("EPSG32632" in name for name in positions[0]),
        "license": record["metadata"]["license"]["id"] == "cc-by-4.0",
    }
    result = {
        "schema_version": "wp8-po-river-ert-candidate-v1",
        "doi": record["metadata"]["doi"],
        "archive_path": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": sha(ARCHIVE),
        "raw_manifest_sha256": sha(MANIFEST),
        "source_record_sha256": sha(RECORD),
        "observation_values_parsed": False,
        "response_header": headers,
        "electrode_position_rows": len(positions),
        "station_count": len(grouped),
        "median_station_step_m": float(np.median(step_lengths)),
        "electric_streamer_footprint_m": footprint_m,
        "maximum_nonoverlapping_footprint_units": len(selected),
        "required_wp8_test_clusters": 223,
        "can_meet_cluster_gate_before_correlation_adjustment": len(selected) >= 223,
        "contract_fields": required,
        "contract_header_and_metadata_complete_except_topographic_elevation": (
            all(required.values())
        ),
        "missing": [
            "per-electrode elevation/topography is in the separate 1.36-GB QGIS archive",
            "correlation-adjusted independent clusters",
            "training-only paired-CRPS effect size",
        ],
        "rejection": (
            "518 stations are spaced about 8 m but each acquisition reuses a 48-m "
            "streamer footprint; the absolute non-overlap upper bound is below 223 "
            "before any response-correlation merging, so this release cannot close "
            "the preregistered DC cluster gate by itself"
        ),
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "stations": len(grouped),
                "median_step_m": round(float(np.median(step_lengths)), 3),
                "nonoverlap_upper_bound": len(selected),
                "header_contract": all(required.values()),
            }
        )
    )


if __name__ == "__main__":
    main()
