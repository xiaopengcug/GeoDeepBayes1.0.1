#!/usr/bin/env python
"""Audit Texas AIB magnetic metadata and flight design without response data."""
from __future__ import annotations

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/texas-aib-magnetic-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/texas-aib-magnetic-contract-readiness.json"
)
REQUIRED_ATTRIBUTES = {
    "base_igrf",
    "calc_radar",
    "Diurnal",
    "Fiducial",
    "Flight",
    "Fluxgate_X",
    "Fluxgate_Y",
    "Fluxgate_Z",
    "IGRF",
    "Latitude",
    "Line_no",
    "Line_type",
    "Longitude",
    "Mag_comp",
    "Jul_day",
    "Mag_diur_cor",
    "Mag_lag_cor",
    "Mag_microlvl",
    "Mag_tielevel",
    "Mag_uncomp",
    "Radar",
    "Resmag",
    "UTCtime",
    "Year",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dbf_design(archive_path: Path, member: str) -> dict[str, object]:
    with zipfile.ZipFile(archive_path) as archive:
        payload = archive.read(member)
    records = struct.unpack_from("<I", payload, 4)[0]
    header_length = struct.unpack_from("<H", payload, 8)[0]
    record_length = struct.unpack_from("<H", payload, 10)[0]
    fields = []
    offset = 32
    while offset < header_length and payload[offset] != 0x0D:
        descriptor = payload[offset : offset + 32]
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii", "replace")
        fields.append(
            {
                "name": name,
                "type": chr(descriptor[11]),
                "length": descriptor[16],
                "decimal_count": descriptor[17],
            }
        )
        offset += 32
    categorical: dict[str, Counter[str]] = {
        field["name"]: Counter()
        for field in fields
        if field["type"] == "C" and field["length"] <= 32
    }
    for index in range(records):
        row = payload[
            header_length + index * record_length :
            header_length + (index + 1) * record_length
        ]
        if not row or row[0:1] == b"*":
            continue
        position = 1
        for field in fields:
            value = row[position : position + field["length"]]
            position += field["length"]
            if field["name"] in categorical:
                text = value.decode("latin-1", "replace").strip()
                if text:
                    categorical[field["name"]][text] += 1
    return {
        "records": records,
        "fields": fields,
        "categorical_counts": {
            name: dict(sorted(counts.items())) for name, counts in categorical.items()
        },
    }


def shapefile_design(archive_path: Path, member: str) -> dict[str, object]:
    with zipfile.ZipFile(archive_path) as archive:
        payload = archive.read(member)
    if struct.unpack_from(">I", payload, 0)[0] != 9994:
        raise RuntimeError("invalid shapefile header")
    file_length = struct.unpack_from(">I", payload, 24)[0] * 2
    shape_type = struct.unpack_from("<I", payload, 32)[0]
    bounds = struct.unpack_from("<4d", payload, 36)
    records = 0
    offset = 100
    while offset + 8 <= len(payload):
        content_length = struct.unpack_from(">I", payload, offset + 4)[0] * 2
        offset += 8 + content_length
        records += 1
    if file_length != len(payload) or offset != len(payload):
        raise RuntimeError("shapefile length/record inventory drift")
    return {
        "records": records,
        "shape_type": shape_type,
        "bounds": {
            "xmin": bounds[0],
            "ymin": bounds[1],
            "xmax": bounds[2],
            "ymax": bounds[3],
        },
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    for member in manifest["files"]:
        path = RAW / member["name"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256(path) != member["sha256"]
        ):
            errors.append(f"member:{member['name']}")
    xml_path = RAW / "TX_AIB-Magnetic.xml"
    root = ET.parse(xml_path).getroot()
    attributes = {
        node.text.strip()
        for node in root.findall(".//attrlabl")
        if node.text and node.text.strip()
    }
    missing_attributes = sorted(REQUIRED_ATTRIBUTES - attributes)
    access_constraints = " ".join(
        node.text.strip()
        for node in root.findall(".//accconst")
        if node.text and node.text.strip()
    )
    use_constraints = " ".join(
        node.text.strip()
        for node in root.findall(".//useconst")
        if node.text and node.text.strip()
    )
    flight_zip = RAW / "TX_AIB_FlightPlan.shp.zip"
    flight_dbf = dbf_design(flight_zip, "TX_AIB_FlightPlan.dbf")
    flight_shape = shapefile_design(flight_zip, "TX_AIB_FlightPlan.shp")
    if flight_dbf["records"] != flight_shape["records"]:
        errors.append("flight-plan-record-count")
    if missing_attributes:
        errors.append("magnetic-attribute-contract")
    if "None" not in access_constraints:
        errors.append("license")
    passed = not errors
    evidence = {
        "schema_version": "wp8-texas-aib-magnetic-contract-readiness-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "passed": passed,
        "errors": errors,
        "license": {
            "access_constraints": access_constraints,
            "use_constraints": use_constraints,
            "cc0_landing_page": (
                "https://www.usgs.gov/data/airborne-magnetic-and-radiometric-data-"
                "acquired-over-parts-hudspeth-culberson-jeff-davis"
            ),
        },
        "survey_contract": {
            "primary_lines": 1306,
            "tie_lines": 141,
            "line_kilometers": 166594,
            "primary_spacing_m": 200,
            "tie_spacing_m": 2000,
            "nominal_terrain_clearance_m": 120,
            "required_attributes": sorted(REQUIRED_ATTRIBUTES),
            "missing_attributes": missing_attributes,
            "acquisition_processing_report_sha256": sha256(
                RAW
                / "Acquisition_and_Processing_Report_TX_AlkalineIgneousBelt_MAG_RAD_D24.pdf"
            ),
        },
        "flight_plan": {
            "dbf": flight_dbf,
            "shapefile": flight_shape,
        },
        "response_archives_downloaded": False,
        "response_values_interpreted": False,
        "selection_decision": (
            "eligible for outcome-blind response acquisition and line/spatial split"
            if passed
            else "ineligible until contract errors are resolved"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": passed,
                "errors": errors,
                "flight_plan_records": flight_dbf["records"],
                "flight_plan_fields": [
                    field["name"] for field in flight_dbf["fields"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
