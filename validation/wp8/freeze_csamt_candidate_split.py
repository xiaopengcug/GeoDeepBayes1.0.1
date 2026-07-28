#!/usr/bin/env python
"""Freeze an outcome-blind CSAMT candidate split from official station tables.

Only station-coordinate ZIP members are opened. Raw response and inversion
archives are deliberately neither downloaded nor inspected.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/csamt-consortium-v1"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/csamt-candidate-split.json"

RELEASES = (
    {
        "id": "big-chino",
        "doi": "10.5066/P9KGKWNL",
        "station_url": (
            "https://www.sciencebase.gov/catalog/file/get/"
            "5bbc0d6ae4b0fc368ead0abe?"
            "f=__disk__f9%2F04%2F5b%2Ff9045bff9a9279011ab8bf462f69f18cc7875f1c"
        ),
        "raw_url": (
            "https://www.sciencebase.gov/catalog/file/get/"
            "5bbc0cc4e4b0fc368ead0ab7?"
            "f=__disk__9e%2Fa6%2F5c%2F9ea65c5503ed73267a64db2115e6b9bcf81d3105"
        ),
    },
    {
        "id": "hualapai",
        "doi": "10.5066/P90KAJM4",
        "sciencebase_item": "5d1a9d8fe4b0941bde6029a9",
        "station_filename": "Station-GrandCanyonWest_PlainTankFlat.zip",
        "raw_filename": "Raw-GrandCanyonWest_PlainTankFlat.zip",
    },
    {
        "id": "red-knoll",
        "doi": "10.5066/P9QF9PFR",
        "station_url": (
            "https://www.sciencebase.gov/catalog/file/get/"
            "5f32150782cee144fb2ead3b?"
            "f=__disk__03%2F61%2F3b%2F03613b3a5528cc42db2a15cf1b98c899930eabaf"
        ),
        "raw_url": (
            "https://www.sciencebase.gov/catalog/file/get/"
            "5f320e3582cee144fb2ead2e?"
            "f=__disk__3c%2Ff1%2Fa0%2F3cf1a0b5368168b070ec40f30bed148812e13cdb"
        ),
    },
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def station_url(release: dict) -> str:
    if "station_url" in release:
        return str(release["station_url"])
    metadata = get_json(
        f"https://www.sciencebase.gov/catalog/item/{release['sciencebase_item']}?format=json"
    )
    matches = [
        member["downloadUri"]
        for member in metadata["files"]
        if member["name"] == release["station_filename"]
    ]
    if len(matches) != 1:
        raise RuntimeError(f"station ZIP not uniquely resolved for {release['id']}")
    return matches[0]


def raw_url(release: dict) -> str:
    if "raw_url" in release:
        return str(release["raw_url"])
    metadata = get_json(
        f"https://www.sciencebase.gov/catalog/item/{release['sciencebase_item']}?format=json"
    )
    matches = [
        member["downloadUri"]
        for member in metadata["files"]
        if member["name"] == release["raw_filename"]
    ]
    if len(matches) != 1:
        raise RuntimeError(f"raw ZIP not uniquely resolved for {release['id']}")
    return matches[0]


def normalized_row(row: dict[str, str]) -> tuple[str, float, float, float | None]:
    fields = {key.strip().lower(): value.strip() for key, value in row.items() if key}
    station = fields["station"]
    easting = float(fields["easting"])
    northing = float(fields["northing"])
    elevation = float(fields["elevation"]) if fields.get("elevation") else None
    return station, easting, northing, elevation


def partition(cell_key: str) -> str:
    # Fixed proportions are candidate assignments only. Spatial correlation
    # components and buffers are expanded later using training responses.
    bucket = int(hashlib.sha256(f"wp8-csamt-v1|{cell_key}".encode()).hexdigest()[:8], 16) % 100
    if bucket < 25:
        return "train"
    if bucket < 35:
        return "buffer"
    if bucket < 50:
        return "calibration"
    return "test"


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    releases_out = []
    sites: list[dict[str, object]] = []
    exact_coordinates: set[tuple[float, float]] = set()
    duplicate_count = 0
    for release in RELEASES:
        url = station_url(release)
        with urllib.request.urlopen(url, timeout=120) as response:
            archive_bytes = response.read()
        archive_path = DATA / f"{release['id']}-station.zip"
        if archive_path.exists():
            if sha256_bytes(archive_path.read_bytes()) != sha256_bytes(archive_bytes):
                raise RuntimeError(f"provider station archive drift for {release['id']}")
        else:
            archive_path.write_bytes(archive_bytes)
        member_records = []
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            for info in sorted(archive.infolist(), key=lambda value: value.filename):
                if info.is_dir() or not (info.filename.lower().endswith((".stn", ".txt"))):
                    continue
                payload = archive.read(info)
                rows = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
                count = 0
                for row in rows:
                    station, easting, northing, elevation = normalized_row(row)
                    coordinate = (round(easting, 3), round(northing, 3))
                    if coordinate in exact_coordinates:
                        duplicate_count += 1
                    exact_coordinates.add(coordinate)
                    # The three official records specify NAD83 UTM zone 12N.
                    # A 250-m design cell is larger than two 100-m receiver
                    # dipoles while retaining enough candidate units for the
                    # preregistered test. It is not claimed to be a
                    # correlation-adjusted inference cluster.
                    cell_key = f"{int(easting // 250)}:{int(northing // 250)}"
                    site_key = sha256_bytes(
                        f"{release['id']}|{info.filename}|{station}|{easting:.3f}|{northing:.3f}".encode()
                    )
                    sites.append(
                        {
                            "site_key": site_key,
                            "release": release["id"],
                            "line": Path(info.filename).stem,
                            "provider_station": station,
                            "easting_m": easting,
                            "northing_m": northing,
                            "elevation_m": elevation,
                            "crs": "NAD83 / UTM zone 12N (EPSG:26912)",
                            "design_cell_250m": cell_key,
                            "candidate_partition": partition(cell_key),
                        }
                    )
                    count += 1
                member_records.append(
                    {
                        "path": info.filename,
                        "bytes": info.file_size,
                        "crc32": f"{info.CRC:08x}",
                        "station_rows": count,
                    }
                )
        os.chmod(archive_path, 0o444)
        response_url = raw_url(release)
        raw_archive_path = DATA / f"{release['id']}-raw-sealed.zip"
        raw_archive_error = None
        try:
            with urllib.request.urlopen(response_url, timeout=120) as response:
                raw_archive_bytes = response.read()
            if raw_archive_path.exists():
                if sha256_bytes(raw_archive_path.read_bytes()) != sha256_bytes(raw_archive_bytes):
                    raise RuntimeError(f"provider raw archive drift for {release['id']}")
            else:
                raw_archive_path.write_bytes(raw_archive_bytes)
            # infolist() reads the ZIP central directory only. No compressed
            # raw observation member is opened or decompressed here.
            with zipfile.ZipFile(io.BytesIO(raw_archive_bytes)) as raw_archive:
                raw_members = [
                    {
                        "path": info.filename,
                        "bytes": info.file_size,
                        "compressed_bytes": info.compress_size,
                        "crc32": f"{info.CRC:08x}",
                    }
                    for info in sorted(raw_archive.infolist(), key=lambda value: value.filename)
                    if not info.is_dir()
                ]
            os.chmod(raw_archive_path, 0o444)
            raw_archive_record = {
                "raw_archive_local": str(raw_archive_path.relative_to(ROOT)).replace("\\", "/"),
                "raw_archive_bytes": len(raw_archive_bytes),
                "raw_archive_sha256": sha256_bytes(raw_archive_bytes),
                "raw_archive_opened_members": 0,
                "raw_archive_members_from_central_directory": raw_members,
            }
        except urllib.error.HTTPError as error:
            raw_archive_error = f"HTTP {error.code}: {error.reason}"
            raw_archive_record = {
                "raw_archive_local": None,
                "raw_archive_bytes": None,
                "raw_archive_sha256": None,
                "raw_archive_opened_members": 0,
                "raw_archive_members_from_central_directory": [],
            }
        releases_out.append(
            {
                "id": release["id"],
                "doi": release["doi"],
                "station_url": url,
                "local_archive": str(archive_path.relative_to(ROOT)).replace("\\", "/"),
                "archive_bytes": len(archive_bytes),
                "archive_sha256": sha256_bytes(archive_bytes),
                "members": member_records,
                "raw_archive_url": response_url,
                "raw_archive_access_error": raw_archive_error,
                **raw_archive_record,
            }
        )

    sites.sort(key=lambda value: str(value["site_key"]))
    counts = {
        name: sum(site["candidate_partition"] == name for site in sites)
        for name in ("train", "buffer", "calibration", "test")
    }
    cells = {
        name: len(
            {
                str(site["design_cell_250m"])
                for site in sites
                if site["candidate_partition"] == name
            }
        )
        for name in counts
    }
    line_partitions: dict[str, set[str]] = {}
    for site in sites:
        key = f"{site['release']}|{site['line']}"
        line_partitions.setdefault(key, set()).add(str(site["candidate_partition"]))
    mixed_lines = {
        key: sorted(partitions)
        for key, partitions in sorted(line_partitions.items())
        if len(partitions) > 1
    }
    available_raw_line_members = sum(
        len(release["raw_archive_members_from_central_directory"])
        for release in releases_out
    )
    payload = {
        "schema_version": "wp8-csamt-candidate-split-v1",
        "status": "candidate_assignments_frozen_training_response_not_opened",
        "selection_inputs": "official station ZIP coordinates only; no raw response or inversion members",
        "raw_archive_access": (
            "raw ZIP containers downloaded, hashed and made read-only; central directories inspected; "
            "zero compressed observation members opened or decompressed"
        ),
        "observation_values_read": False,
        "crs": "NAD83 / UTM zone 12N (EPSG:26912)",
        "exact_coordinate_duplicates_across_full_consortium": duplicate_count,
        "unique_station_coordinates": len(exact_coordinates),
        "candidate_partition_counts": counts,
        "candidate_250m_cell_counts": cells,
        "provider_raw_granularity_audit": {
            "available_raw_line_members": available_raw_line_members,
            "provider_station_lines": len(line_partitions),
            "station_lines_mixing_candidate_partitions": len(mixed_lines),
            "mixed_line_partitions": mixed_lines,
            "safe_training_member_extraction_possible": False,
            "reason": (
                "provider raw members are whole-line files, while every inventoried station line "
                "contains more than one candidate partition; opening a raw line for training would "
                "also open calibration/test observations"
            ),
            "line_level_split_upper_bound": len(line_partitions),
            "line_level_split_meets_223_test_clusters": False,
        },
        "partition_warning": (
            "250-m cells are outcome-blind design units, not independent clusters; "
            "training-only response correlation length must merge cells and expand buffers "
            "before calibration/test membership can become formal"
        ),
        "releases": releases_out,
        "sites": sites,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "sites": len(sites),
                "unique_coordinates": len(exact_coordinates),
                "duplicates": duplicate_count,
                "partition_counts": counts,
                "cell_counts": cells,
            }
        )
    )


if __name__ == "__main__":
    main()
