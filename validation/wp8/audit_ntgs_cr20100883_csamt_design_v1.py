"""Geometry-only audit of the CSAMT portion of NTGS CR2010-0883."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "validation/wp8/data/ntgs-cr2010-0883-v1/CR20100883AC.zip"
INVENTORY = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "ntgs-cr20100883-response-blind-inventory-v1.json"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "ntgs-cr20100883-csamt-design-audit-v1.json"
)

LINES = {
    "Hermitage-1000": {
        "mde": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Hermitage-RisingStar/CSAMT/1000/L1000-cs.mde"
        ),
        "stn": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Hermitage-RisingStar/CSAMT/1000/L1000.utm.stn"
        ),
        "published_soundings": 20,
    },
    "Rising-Star-2000": {
        "mde": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Hermitage-RisingStar/CSAMT/2000/L2000-cs.mde"
        ),
        "stn": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Hermitage-RisingStar/CSAMT/2000/L2000.utm.stn"
        ),
        "published_soundings": 21,
    },
    "Rising-Star-3000": {
        "mde": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Hermitage-RisingStar/CSAMT/3000/L3000-cs.mde"
        ),
        "stn": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Hermitage-RisingStar/CSAMT/3000/L3000.utm.stn"
        ),
        "published_soundings": 20,
    },
    "Trinity-L34": {
        "mde": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Trinity/CSAMT/L34/L34.mde"
        ),
        "stn": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Trinity/CSAMT/L34/L34.utm.stn"
        ),
        "published_soundings": 25,
    },
    "Trinity-L35": {
        "mde": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Trinity/CSAMT/L35/L35.mde"
        ),
        "stn": (
            "geophysics/Geophysics/Original/Electrical_Geophysics/2009/"
            "Processed_Data/Trinity/CSAMT/L35/L35.utm.stn"
        ),
        "published_soundings": 25,
    },
}


def member_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def values(text: str, key: str) -> list[str]:
    pattern = re.compile(
        rf"^\s*\$\s*{re.escape(key)}\s*=\s*(.*?)\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return [match.group(1).strip().strip('"') for match in pattern.finditer(text)]


def number(value: str) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
    if not match:
        raise ValueError(value)
    return float(match.group())


def endpoints(center_x: float, center_y: float, azimuth: float, length: float):
    radians = math.radians(azimuth)
    dx = 0.5 * length * math.sin(radians)
    dy = 0.5 * length * math.cos(radians)
    return [
        [round(center_x - dx, 3), round(center_y - dy, 3)],
        [round(center_x + dx, 3), round(center_y + dy, 3)],
    ]


def main() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    if inventory["archive_sha256"] != (
        "8667d4b7c95eafe82d560c729641d29de0e45ca76500905a3e7284cd36a4b03d"
    ):
        raise SystemExit("inventory archive hash is not the frozen CR2010-0883 hash")

    audited = {}
    with ZipFile(ARCHIVE) as archive:
        for name, contract in LINES.items():
            mde_payload = archive.read(contract["mde"])
            stn_payload = archive.read(contract["stn"])
            mde = mde_payload.decode("latin1")
            stn_rows = [
                row.split()
                for row in stn_payload.decode("latin1").splitlines()
                if row.strip()
            ]
            center_x_values = values(mde, "Tx.CenterX")
            center_y_values = values(mde, "Tx.CenterY")
            center_values = values(mde, "Tx.Center")
            azimuth_values = [number(item) for item in values(mde, "Tx.Azimuth")]
            if not azimuth_values:
                azimuth_values = [
                    number(item.split(",")[0]) for item in values(mde, "Tx.HPR")
                ]
            length_values = [number(item) for item in values(mde, "Tx.Length")]
            if center_values:
                xy = [number(item) for item in center_values[0].split(",")[:2]]
            else:
                xy = [number(center_x_values[0]), number(center_y_values[0])]
            unique_azimuths = sorted(set(azimuth_values))
            unique_lengths = sorted(set(length_values))
            unambiguous = len(unique_azimuths) == 1 and len(unique_lengths) == 1
            audited[name] = {
                "mde_member": contract["mde"],
                "mde_bytes": len(mde_payload),
                "mde_sha256": member_sha256(mde_payload),
                "stn_member": contract["stn"],
                "stn_bytes": len(stn_payload),
                "stn_sha256": member_sha256(stn_payload),
                "station_coordinate_row_count": len(stn_rows),
                "published_sounding_count": contract["published_soundings"],
                "transmitter_center_mga_zone_53": xy,
                "transmitter_azimuth_values_deg": unique_azimuths,
                "transmitter_length_values_m": unique_lengths,
                "transmitter_geometry_unambiguous": unambiguous,
                "derived_transmitter_endpoints_mga_zone_53": (
                    endpoints(xy[0], xy[1], unique_azimuths[0], unique_lengths[0])
                    if unambiguous
                    else None
                ),
            }

    sounding_count = sum(
        row["published_sounding_count"] for row in audited.values()
    )
    evidence = {
        "schema_version": "wp8-ntgs-cr20100883-csamt-design-audit-v1",
        "audit_date": "2026-07-25",
        "source_landing_page": (
            "https://geoscience.nt.gov.au/gemis/ntgsjspui/handle/1/90121"
        ),
        "archive_path": ARCHIVE.relative_to(ROOT).as_posix(),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": inventory["archive_sha256"],
        "inventory_path": INVENTORY.relative_to(ROOT).as_posix(),
        "inventory_sha256": member_sha256(INVENTORY.read_bytes()),
        "response_payload_members_opened": 0,
        "test_response_members_opened": 0,
        "geometry_members_opened": 10,
        "survey_year": 2009,
        "survey_line_count": len(audited),
        "published_sounding_count": sounding_count,
        "published_line_km": 11.1,
        "frequency_range_hz": [4, 8192],
        "receiver_spacing_m": 100,
        "transmitter_type": "grounded bipole",
        "transmitter_geometry_unambiguous_line_count": sum(
            row["transmitter_geometry_unambiguous"] for row in audited.values()
        ),
        "sampled_transmitter_waveform_present": False,
        "lines": audited,
        "independent_cluster_upper_bound": sounding_count,
        "minimum_independent_test_clusters": 223,
        "observation_contract_ready": False,
        "cluster_gate_passes": False,
        "power_gate_passes": False,
        "reason": (
            "Geometry-only MDE/STN parsing establishes five coordinate-bearing "
            "CSAMT lines and 111 published soundings. Four lines have a unique "
            "source center, azimuth and length from which endpoints are "
            "derivable; Trinity L35 contains conflicting azimuths and a 945 m "
            "length inconsistent with the 1500 m logistics-report description. "
            "No sampled transmitter waveform is published, and the absolute "
            "sounding upper bound remains below 223."
        ),
    }
    OUTPUT.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "published_sounding_count": sounding_count,
        "unambiguous_transmitter_lines": (
            evidence["transmitter_geometry_unambiguous_line_count"]
        ),
        "output": OUTPUT.relative_to(ROOT).as_posix(),
    }, indent=2))


if __name__ == "__main__":
    main()
