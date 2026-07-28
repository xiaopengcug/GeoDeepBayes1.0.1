"""Response-blind design audit of the CSAMT package in NTGS CR2013-0857."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = (
    ROOT
    / "validation/wp8/data/ntgs-cr2013-0857-csamt-v1/"
    "CR2013-0857_Geophysics.zip"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "ntgs-cr20130857-csamt-design-audit-v1.json"
)
REPORT_MEMBER = "Geophysics/CSAMT_Survey_Data/Logistics Report.pdf"
ARCHIVE_SHA256 = (
    "4a5217a3c03ecac251d8eab213bb0c8f129bc7108d239e1ee8e85e5adc2890ca"
)
LINE_ROLES = {
    "train": [
        "7411000N",
        "7411200N",
        "7411450N",
        "7411600N",
        "7411650N",
        "7411700N",
        "7411750N",
        "7411800N",
        "7412000N",
        "7412050N",
    ],
    "calibration": ["7412300N"],
    "test": ["7412500N", "7412900N"],
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def report_text(payload: bytes) -> str:
    return "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages
    )


def station_rows(payload: bytes) -> list[list[float]]:
    rows = []
    for line in payload.decode("latin1").splitlines():
        fields = line.split()
        if len(fields) >= 4:
            rows.append([float(value) for value in fields[:4]])
    return rows


def main() -> None:
    if sha256(ARCHIVE.read_bytes()) != ARCHIVE_SHA256:
        raise SystemExit("archive is not the frozen CR2013-0857 package")

    response_extensions = {".avg", ".raw", ".mtd", ".mtm", ".png"}
    with ZipFile(ARCHIVE) as archive:
        members = archive.namelist()
        report_payload = archive.read(REPORT_MEMBER)
        text = report_text(report_payload)
        stn_members = sorted(
            name for name in members if name.lower().endswith(".stn")
        )
        coordinate_lines = {}
        for name in stn_members:
            payload = archive.read(name)
            rows = station_rows(payload)
            coordinate_lines[Path(name).stem] = {
                "member": name,
                "bytes": len(payload),
                "sha256": sha256(payload),
                "coordinate_row_count": len(rows),
                "easting_range_m": [
                    min(row[1] for row in rows),
                    max(row[1] for row in rows),
                ],
                "northing_range_m": [
                    min(row[2] for row in rows),
                    max(row[2] for row in rows),
                ],
            }

        response_members = [
            name
            for name in members
            if Path(name).suffix.lower() in response_extensions
        ]
        field_sheet_members = [
            name for name in members if name.lower().endswith(".xls")
        ]

    required_phrases = {
        "published_soundings": "205 scalar (TM) CSAMT soundings",
        "line_count": "thirteen lines",
        "station_spacing": "25m station spacing",
        "frequency_range": "4 to 8192 Hertz",
        "receiver_components": "E-field (Ex) dipoles and one central H-field (Hy)",
        "transmitter_model": "Zonge GGT-30 geophysical transmitter",
        "transmitter_current": "approximately 12 Amps",
        "source_length": "1995",
    }
    normalized = re.sub(r"\s+", " ", text).replace("‐", "-")
    phrase_checks = {
        key: value.lower() in normalized.lower()
        for key, value in required_phrases.items()
    }
    if not all(phrase_checks.values()):
        raise SystemExit(f"logistics report contract drift: {phrase_checks}")

    coordinate_row_count = sum(
        line["coordinate_row_count"] for line in coordinate_lines.values()
    )
    evidence = {
        "schema_version": "wp8-ntgs-cr20130857-csamt-design-audit-v1",
        "audit_date": "2026-07-25",
        "source_landing_page": (
            "https://geoscience.nt.gov.au/gemis/ntgsjspui/handle/1/90282"
        ),
        "archive_download": (
            "https://geoscience.nt.gov.au/gemis/ntgsjspui/bitstream/"
            "1/90282/2/CR2013-0857_Geophysics.zip"
        ),
        "archive_path": ARCHIVE.relative_to(ROOT).as_posix(),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": ARCHIVE_SHA256,
        "report_member": REPORT_MEMBER,
        "report_bytes": len(report_payload),
        "report_sha256": sha256(report_payload),
        "archive_member_count": len(members),
        "response_member_count": len(response_members),
        "response_payload_members_opened": 0,
        "test_response_members_opened": 0,
        "geometry_members_opened": len(stn_members),
        "field_sheet_members_present": len(field_sheet_members),
        "field_sheet_members_opened_by_audit": 0,
        "survey_year": 2012,
        "survey_area": "Arltunga East and West",
        "published_line_count": 13,
        "published_sounding_count": 205,
        "published_line_km": 5.125,
        "receiver_spacing_m": 25,
        "frequency_range_hz": [4, 8192],
        "mode": "scalar TM",
        "receiver_contract": {
            "electric_component": "Ex",
            "electric_dipole_length_m": 25,
            "magnetic_component": "Hy",
            "receiver": "Zonge GDP-32ii",
            "magnetic_sensor": "EMI ANT-6",
        },
        "transmitter_contract": {
            "type": "grounded electric dipole",
            "model": "Zonge GGT-30 with ZMG-30 generator and XMT-32 controller",
            "center_gda94_zone_53": [478230, 7405490],
            "orientation_deg_true": 90,
            "length_m": 1995,
            "derived_endpoints_gda94_zone_53": [
                [477232.5, 7405490.0],
                [479227.5, 7405490.0],
            ],
            "maximum_current_a_approximate": 12,
            "frequency_dependent_current_not_in_report": True,
            "sampled_waveform_present": False,
        },
        "coordinate_file_count": len(stn_members),
        "coordinate_row_count": coordinate_row_count,
        "coordinate_count_differs_from_published_soundings": (
            coordinate_row_count != 205
        ),
        "coordinate_lines": coordinate_lines,
        "line_roles": LINE_ROLES,
        "role_assignment_basis": (
            "line identity and station coordinates only; the two spatially "
            "separate western-grid lines are sealed test lines"
        ),
        "role_assignment_frozen_before_response_access": True,
        "minimum_independent_test_clusters": 223,
        "absolute_sounding_upper_bound": 205,
        "line_level_cluster_upper_bound": 13,
        "observation_contract_ready": False,
        "cluster_gate_passes": False,
        "power_gate_passes": False,
        "rights_gate_ready": False,
        "reason": (
            "The anonymous NTGS package contains raw and averaged CSAMT data, "
            "13 coordinate-bearing lines, exact transmitter center/orientation/"
            "length, Ex/Hy receiver components, 4--8192 Hz acquisition and "
            "approximately 12 A maximum current. The logistics report does not "
            "publish sampled transmitter-waveform values, the item page does "
            "not state a reusable data licence, and even the unadjusted 205-"
            "sounding upper bound is below the frozen 223-cluster requirement. "
            "Response members remained unopened."
        ),
    }
    OUTPUT.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "published_soundings": evidence["published_sounding_count"],
                "coordinate_rows": coordinate_row_count,
                "response_members_opened": 0,
                "output": OUTPUT.relative_to(ROOT).as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
