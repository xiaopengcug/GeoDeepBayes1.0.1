#!/usr/bin/env python
"""Outcome-blind structural audit of the preregistered WP8 field packages.

This program deliberately reads filenames, text headers, EDI section labels,
and XLSX string headers only.  It never parses an observation-value row.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from geodeepbayes.validation.feasibility import required_coverage_clusters

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "_bmad-output/planning-artifacts/research/open-data"
OUT = Path(__file__).resolve().parent / "evidence/feasibility-v1/field-contract-audit.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        return next(csv.reader(stream))


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return [item.filename for item in archive.infolist() if not item.is_dir()]


def first_csv_header_in_zip(path: Path) -> tuple[str, list[str]]:
    with zipfile.ZipFile(path) as archive:
        member = next(item for item in archive.infolist() if item.filename.lower().endswith(".csv"))
        first_line = archive.open(member).readline().decode("utf-8-sig", errors="replace")
    return member.filename, next(csv.reader([first_line]))


def xlsx_structure(path: Path) -> dict[str, object]:
    """Return sheet names and first-row string cells without numeric cell values."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = [node.attrib["name"] for node in workbook.findall(".//m:sheet", ns)]
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in strings.findall("m:si", ns)]
        headers: dict[str, list[str]] = {}
        for name in sorted(n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
            sheet = ET.fromstring(archive.read(name))
            row = sheet.find(".//m:sheetData/m:row[@r='1']", ns)
            values: list[str] = []
            if row is not None:
                for cell in row.findall("m:c", ns):
                    # Only shared or inline strings are admissible header evidence.
                    if cell.attrib.get("t") == "s":
                        node = cell.find("m:v", ns)
                        if node is not None and int(node.text or "-1") < len(shared):
                            values.append(shared[int(node.text or "0")])
                    elif cell.attrib.get("t") == "inlineStr":
                        node = cell.find("m:is", ns)
                        if node is not None:
                            values.append("".join(node.itertext()))
            headers[name] = values
    return {"sheets": sheets, "first_row_string_cells": headers}


def edi_sections(path: Path) -> dict[str, object]:
    sections: set[str] = set()
    members = zip_names(path)
    with zipfile.ZipFile(path) as archive:
        for member in members:
            with archive.open(member) as stream:
                for raw in stream:
                    line = raw.decode("ascii", errors="ignore").strip()
                    if line.startswith(">"):
                        token = re.split(r"[\s=]", line[1:].strip(), maxsplit=1)[0].upper()
                        if token:
                            sections.add(token)
    return {"member_count": len(members), "sections": sorted(sections)}


def validate_input_budget(input_paths: list[Path], maximum_input_bytes: int) -> int:
    """Two-phase raw then expanded ZIP budget validation without content reads."""
    consumed = sum(path.stat().st_size for path in input_paths)
    if consumed > maximum_input_bytes:
        raise ValueError("field-contract raw input byte budget exceeded")
    for path in input_paths:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for item in archive.infolist():
                    consumed += item.file_size
                    if consumed > maximum_input_bytes:
                        raise ValueError(
                            "field-contract expanded input byte budget exceeded"
                        )
    return consumed


def build_field_contract_audit(
    *, maximum_input_bytes: int = 512 * 1024 * 1024
) -> dict[str, object]:
    """Recompute outcome-blind contract evidence directly from original members."""
    magnetic = DATA / "magnetic/USGS_MountainPass_airborne_magnetic_2020/Magnetic_Data.csv"
    tdip = DATA / "dc_ip/Zenodo_Reykjanes_ERT_IP_monitoring_2025/ERT_IP_Reykjanes.zip"
    sip_dir = DATA / "dc_ip/Zenodo_Serpentinite_IP_Revil_2024"
    mt_dir = DATA / "mt/USGS_SanAndreas_Parkfield_MT_EDI_1990"
    csamt_dir = DATA / "csamt/USGS_Hualapai_CSAMT_GrandCanyonWest_PlainTankFlat_2019"
    wfem_dir = DATA / "wfem/Zenodo_BaotuSpring_WFEM_2025"

    csamt_raw = csamt_dir / "Raw-GrandCanyonWest_PlainTankFlat.zip"
    csamt_station = csamt_dir / "Station-GrandCanyonWest_PlainTankFlat.zip"
    wfem_files = sorted(wfem_dir.glob("*.dat"))
    input_paths = [
        magnetic, tdip, sip_dir / "Data 1.zip",
        *sorted(sip_dir.glob("*.xlsx")),
        mt_dir / "Magnetotelluric_Cross-Power_EDI.zip",
        mt_dir / "Magnetotelluric_Time-Series_EDI.zip",
        csamt_raw, csamt_station, *wfem_files,
    ]
    # Phase 1 is metadata-only: reject raw bytes before opening or probing ZIPs.
    validate_input_budget(input_paths, maximum_input_bytes)
    tdip_members = zip_names(tdip)
    tdip_header_member, tdip_header = first_csv_header_in_zip(tdip)
    coverage_required = {
        str(level): required_coverage_clusters(nominal=level)
        for level in (0.9, 0.95)
    }
    methods = {
        "gravity": {
            "contract_status": "blocked",
            "cluster_basis": "one regional grid package",
            "available_clusters": 1,
            "missing": ["independent spatial clusters and outcome-blind correlation length"],
        },
        "magnetic": {
            "contract_status": "candidate",
            "source_sha256": digest(magnetic),
            "header": csv_header(magnetic),
            "direction_boundary": {
                "FX_FY_FZ": "measured vector components; not accepted as remanence direction",
                "Bearing": "aircraft heading; not accepted as magnetization direction",
                "status": "explicitly bounded",
            },
            "cluster_basis": "flight-line identifiers exist; values not read by this audit",
            "available_clusters": None,
            "missing": ["outcome-blind line count/correlation length", "remanence prior provenance"],
        },
        "dc": {
            "contract_status": "blocked",
            "cluster_basis": "four named survey archives",
            "available_clusters": 4,
            "missing": ["validated per-observation error and sufficient independent clusters"],
        },
        "tdip": {
            "contract_status": "blocked",
            "source_sha256": digest(tdip),
            "member_count": len(tdip_members),
            "header_member": tdip_header_member,
            "header": tdip_header,
            "cluster_basis": "one CSV acquisition/date member per cluster candidate",
            "available_clusters": len(tdip_members),
            "missing": ["no explicit error/standard-deviation column"],
        },
        "sip_fdip": {
            "contract_status": "blocked",
            "archive_members": zip_names(sip_dir / "Data 1.zip"),
            "workbooks": {
                p.name: xlsx_structure(p)
                for p in sorted(sip_dir.glob("*.xlsx"))
            },
            "cluster_basis": "P1/P2 profile naming",
            "available_clusters": 2,
            "missing": ["unambiguous frequency-to-profile/station key", "sufficient independent clusters"],
        },
        "tem": {
            "contract_status": "blocked",
            "cluster_basis": "site list exists but site rows were not read",
            "available_clusters": None,
            "missing": ["outcome-blind site count/split", "field dimensionality diagnostic"],
        },
        "mt_amt": {
            "contract_status": "blocked",
            "cross_power": edi_sections(mt_dir / "Magnetotelluric_Cross-Power_EDI.zip"),
            "time_series": edi_sections(mt_dir / "Magnetotelluric_Time-Series_EDI.zip"),
            "cluster_basis": "EDI member/site",
            "available_clusters": len(zip_names(mt_dir / "Magnetotelluric_Cross-Power_EDI.zip")),
            "missing": ["processed impedance tensor sections", "impedance variance/error sections"],
        },
        "csamt": {
            "contract_status": "blocked",
            "raw_members": zip_names(csamt_raw),
            "station_members": zip_names(csamt_station),
            "cluster_basis": "named survey line",
            "available_clusters": len(zip_names(csamt_raw)),
            "missing": ["transmitter endpoint coordinates", "source-receiver distance", "near-field classification"],
        },
        "wfem": {
            "contract_status": "blocked",
            "file_count": len(wfem_files),
            "headers": sorted({tuple(csv_header(path)) for path in wfem_files}),
            "cluster_basis": "one named line file",
            "available_clusters": len(wfem_files),
            "missing": ["receiver coordinates", "source geometry", "phase", "field component", "geometric factor definition"],
        },
    }
    for item in methods.values():
        count = item["available_clusters"]
        item["coverage_power"] = {
            "required_clusters": coverage_required,
            "sufficient": bool(count is not None and count >= max(coverage_required.values())),
        }
    result = {
        "schema_version": "wp8-outcome-blind-field-contract-audit-v1",
        "audit_policy": "filenames, headers, EDI section labels, and XLSX string headers only",
        "observation_values_read_by_this_program": False,
        "formal_test_eligibility": "blocked until an outcome-blind split excludes contaminated members",
        "endpoint_exposure_incident": {
            "detected": True,
            "members_to_exclude_from_formal_test": [
                "tdip: first inspected CSV member (recorded above)",
                "csamt: Raw archive A1.raw",
                "csamt-backup-doi-10.5281/zenodo.5533467: K1-K9 AVG",
                "magnetic-backup-doi-10.5066/P91O2Y8W: Northwest Arkansas CSV",
                "wfem: 1 WFEM apparent resistivity of L1.dat",
            ],
            "scope": (
                "interactive inspections displayed observation rows before formal "
                "splits were frozen; ScienceBase also ignored an HTTP Range request "
                "and returned Northwest Arkansas magnetic CSV rows"
            ),
            "remediation": "retain only as training candidates or exclude whole named members before any formal test unseal",
        },
        "coverage_equivalence": {
            "margin": 0.05,
            "alpha_two_sided": 0.05,
            "power": 0.8,
            "required_clusters": coverage_required,
        },
        "methods": methods,
    }
    return result


def main() -> None:
    result = build_field_contract_audit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "methods": len(result["methods"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
