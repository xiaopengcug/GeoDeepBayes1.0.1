#!/usr/bin/env python
"""Freeze Zenodo metadata and a response-blind DC streamer role design."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/po-river-dc-streamer-v1"
RAW_METADATA = DATA / "zenodo-record-18183049.json"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "po-river-dc-streamer-design-v1.json"
)
URL = "https://zenodo.org/api/records/18183049"
SALT = "GeoDeepBayes-WP8-PoRiver-DC-v1"
STATIONS = 518
MEASUREMENTS_PER_STATION = 318
MACROBLOCK_STATIONS = 8


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def role(block: int) -> str:
    # 20/10/10/60 train/buffer/calibration/test, frozen before payload access.
    bucket = int(
        hashlib.sha256(f"{SALT}|{block}".encode()).hexdigest()[:12], 16
    ) % 10
    if bucket < 2:
        return "train"
    if bucket == 2:
        return "buffer"
    if bucket == 3:
        return "calibration"
    return "test"


def main() -> None:
    request = urllib.request.Request(
        URL, headers={"User-Agent": "GeoDeepBayes-WP8 PoRiver-DC/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    record = json.loads(raw)
    DATA.mkdir(parents=True, exist_ok=True)
    RAW_METADATA.write_bytes(raw)
    archive = next(
        file
        for file in record["files"]
        if file["key"] == "Electrical_Tomography_Data.7z"
    )
    blocks = []
    station_roles = {}
    for station in range(1, STATIONS + 1):
        block = (station - 1) // MACROBLOCK_STATIONS
        station_roles[str(station)] = role(block)
    for block in range((STATIONS + MACROBLOCK_STATIONS - 1) // MACROBLOCK_STATIONS):
        start = block * MACROBLOCK_STATIONS + 1
        stop = min(STATIONS, start + MACROBLOCK_STATIONS - 1)
        blocks.append(
            {
                "macroblock": block,
                "first_station": start,
                "last_station": stop,
                "role": role(block),
            }
        )
    counts = {
        role_name: sum(value == role_name for value in station_roles.values())
        for role_name in ("train", "buffer", "calibration", "test")
    }
    output = {
        "schema_version": "wp8-po-river-dc-streamer-design-v1",
        "source": "Zenodo record 18183049",
        "doi": "10.5281/zenodo.18183049",
        "zenodo_metadata_sha256": sha(raw),
        "access_right": record["metadata"]["access_right"],
        "license": record["metadata"]["license"]["id"],
        "declared_station_count": STATIONS,
        "declared_measurements_per_station": MEASUREMENTS_PER_STATION,
        "declared_observation_count": STATIONS * MEASUREMENTS_PER_STATION,
        "declared_station_step_m": 8,
        "declared_geometry": "13 electrodes; ABMN; EPSG:32632 positions",
        "declared_uncertainty": (
            "per-observation resistivity standard deviation in percent; "
            "3 stacks, increased to 6 when standard deviation exceeds 2%"
        ),
        "archive": {
            "key": archive["key"],
            "size": archive["size"],
            "checksum": archive["checksum"],
            "download_url": archive["links"]["self"],
        },
        "selection_frozen_before_response_access": True,
        "role_rule": (
            "SHA256(salt|8-station macroblock) modulo 10: "
            "20% train, 10% buffer, 10% calibration, 60% test"
        ),
        "salt_sha256": sha(SALT.encode()),
        "macroblock_station_count": MACROBLOCK_STATIONS,
        "macroblocks": blocks,
        "station_roles": station_roles,
        "partition_counts": counts,
        "design_test_cluster_upper_bound": counts["test"],
        "required_test_clusters": 223,
        "design_power_gate_possible": counts["test"] >= 223,
        "response_archive_downloaded": False,
        "response_values_interpreted": 0,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "partition_counts": counts,
                "design_test_cluster_upper_bound": counts["test"],
                "design_power_gate_possible": output[
                    "design_power_gate_possible"
                ],
                "metadata_sha256": output["zenodo_metadata_sha256"],
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
