#!/usr/bin/env python
"""Freeze and audit the restored USGS Sevier/Red Knoll CSAMT raw package.

The provider's version-2 parent ZIP was previously unavailable.  This audit
opens the restored responses, so the release is permanently training-only and
cannot be used as a response-blind formal-test population.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-sevier-fault-csamt-v2"
ARCHIVE = DATA / "Sevier_Fault_CSAMT_all_data_files.zip"
EVIDENCE = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "usgs-sevier-fault-csamt-raw-audit-v2.json"
)
ITEM = "5f31f31682cee144fb2ead0c"
FILENAME = "Sevier_Fault_CSAMT_all_data_files.zip"
EXPECTED_BYTES = 328_632
EXPECTED_MD5 = "d77f1080c4051c8f330424e00a38159d"
EXPECTED_SHA256 = "59e087bb2f8d5f6ab43e40642a9860561dd2a4e4665f9e85b2f84a9493dbcabd"

FREQUENCY_RE = re.compile(
    r"^\s*(?P<frequency>[0-9.]+)\s+Hz\s+\d+\s+Cyc\s+Tx Curr\s+"
    r"(?P<current>[0-9.]+)\s*$"
)
COMPONENT_RE = re.compile(r"^\s*\d+\s+(?P<component>Ex|Ey|Hx|Hy)\s+")
RX_RE = re.compile(r"^Tx\s+\d+\s+Rx\s+(?P<rx>\d+)\s+")


def digest(value: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, value).hexdigest()


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "GeoDeepBayes-WP8/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "GeoDeepBayes-WP8/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def audit_raw(text: str) -> dict:
    frequencies: set[float] = set()
    currents: set[float] = set()
    receivers: set[int] = set()
    components: dict[str, int] = {}
    frequency_blocks = 0
    component_rows = 0
    for line in text.splitlines():
        match = FREQUENCY_RE.match(line)
        if match:
            frequency_blocks += 1
            frequencies.add(float(match.group("frequency")))
            currents.add(float(match.group("current")))
            continue
        match = RX_RE.match(line)
        if match:
            receivers.add(int(match.group("rx")))
            continue
        match = COMPONENT_RE.match(line)
        if match:
            component = match.group("component")
            components[component] = components.get(component, 0) + 1
            component_rows += 1
    return {
        "frequency_block_count": frequency_blocks,
        "unique_frequencies_hz": sorted(frequencies),
        "unique_frequency_count": len(frequencies),
        "transmitter_currents_a": sorted(currents),
        "receiver_ids": sorted(receivers),
        "receiver_id_count": len(receivers),
        "component_row_count": component_rows,
        "component_rows": dict(sorted(components.items())),
    }


def audit_stations(text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text)))
    normalized = [
        {
            key.strip().lower(): value.strip()
            for key, value in row.items()
            if key is not None and value is not None
        }
        for row in rows
    ]
    eastings = [float(row["easting"]) for row in normalized]
    northings = [float(row["northing"]) for row in normalized]
    elevations = [float(row["elevation"]) for row in normalized]
    stations = [float(row["station"]) for row in normalized]
    return {
        "station_count": len(rows),
        "station_min_m": min(stations),
        "station_max_m": max(stations),
        "easting_min_m": min(eastings),
        "easting_max_m": max(eastings),
        "northing_min_m": min(northings),
        "northing_max_m": max(northings),
        "elevation_min_m": min(elevations),
        "elevation_max_m": max(elevations),
    }


def main() -> None:
    metadata = fetch_json(
        f"https://www.sciencebase.gov/catalog/item/{ITEM}?format=json"
    )
    matches = [
        row
        for row in metadata.get("files", [])
        if row.get("name") == FILENAME
    ]
    if len(matches) != 1:
        raise RuntimeError("restored parent ZIP was not uniquely resolved")
    source = matches[0]
    archive_bytes = fetch_bytes(source["downloadUri"])
    if len(archive_bytes) != EXPECTED_BYTES:
        raise RuntimeError("provider archive size drift")
    if digest(archive_bytes, "md5") != EXPECTED_MD5:
        raise RuntimeError("provider archive MD5 drift")
    if digest(archive_bytes, "sha256") != EXPECTED_SHA256:
        raise RuntimeError("provider archive SHA-256 drift")

    DATA.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists() and ARCHIVE.read_bytes() != archive_bytes:
        raise RuntimeError("local immutable archive differs from provider")
    if not ARCHIVE.exists():
        ARCHIVE.write_bytes(archive_bytes)

    lines: dict[str, dict] = {}
    members: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as package:
        for info in sorted(package.infolist(), key=lambda row: row.filename):
            if info.is_dir():
                continue
            payload = package.read(info)
            members.append(
                {
                    "path": info.filename,
                    "bytes": len(payload),
                    "sha256": digest(payload, "sha256"),
                }
            )
            lower = info.filename.lower()
            line = "Sv1" if "/sv1" in lower else "Sv2" if "/sv2" in lower else None
            if line is None:
                continue
            record = lines.setdefault(line, {})
            text = payload.decode("utf-8-sig", errors="replace")
            if lower.endswith(".raw"):
                record["raw"] = audit_raw(text)
            elif ".stn_" in lower:
                record["stations"] = audit_stations(text)
            elif ".mtm_" in lower:
                record["inversion_member_bytes"] = len(payload)

    evidence = {
        "schema_version": "wp8-usgs-sevier-fault-csamt-raw-audit-v2",
        "audit_date": "2026-07-25",
        "source": {
            "doi": "10.5066/P9QF9PFR",
            "sciencebase_item": ITEM,
            "license": "United States public domain",
            "archive_path": ARCHIVE.relative_to(ROOT).as_posix(),
            "archive_bytes": len(archive_bytes),
            "archive_md5": digest(archive_bytes, "md5"),
            "archive_sha256": digest(archive_bytes, "sha256"),
            "provider_parent_zip_restored": True,
        },
        "partition": "permanently-training-only",
        "formal_test_responses_opened": 0,
        "test_unseal_count": 0,
        "members": members,
        "lines": lines,
        "gate_assessment": {
            "observation_payload_present": True,
            "electric_and_magnetic_components_present": all(
                {"Ex", "Hy"} <= set(row["raw"]["component_rows"])
                for row in lines.values()
            ),
            "transmitter_current_present": True,
            "transmitter_endpoint_coordinates_present": False,
            "sampled_transmitter_waveform_present": False,
            "independent_profile_upper_bound": len(lines),
            "minimum_independent_test_clusters": 223,
            "observation_contract_passes": False,
            "cluster_gate_passes": False,
            "power_gate_passes": False,
            "reason": (
                "The restored official ZIP supplies genuine multicomponent raw "
                "responses, station coordinates and transmitter current, but only "
                "two survey lines. It does not publish transmitter endpoints or a "
                "sampled waveform and was opened as training-only."
            ),
        },
        "formal_test_result": None,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
