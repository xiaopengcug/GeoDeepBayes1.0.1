#!/usr/bin/env python
"""Fail-closed audit of the official Hualapai CSAMT training-only package."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-hualapai-csamt-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-hualapai-csamt-contract.json"
RAW_ZIP = RAW / "Raw-GrandCanyonWest_PlainTankFlat.zip"
STATION_ZIP = RAW / "Station-GrandCanyonWest_PlainTankFlat.zip"
INVERSION_ZIP = RAW / "Inversions-GrandCanyonWest_PlainTankFlat.zip"
CROSS_SECTION_ZIP = RAW / "Cross_sections_Colorbar.zip"
EXPECTED_LINES = {"A1", "A2", "PT1", "PT2", "PT3", "QB1", "QB2", "QB3", "WG"}
EXPECTED_MEMBER_ANCHORS = {
    "sciencebase-item.json": (22604, "28153604f1b45277c5e79276515ede7ca4230cf7bc50b27bc2bbc9427e580ab3"),
    "sciencebase-parent.json": (3115, "d691118c8fa188dcc2ba8c894417c6688dbda70d0d624c76febf21052df06346"),
    "Grand Canyon West and Plain Tank Flat CSAMT metadata.xml": (21060, "345e2d25817a36b525f8981526fd9be831bcc0cd0c563ce85cbce49722b32da9"),
    "KMZ files for Grand Canyon West and Plain Tank Flat CSAMT.kmz": (2489978, "0548e12b591fd90c79e2bf0bfc7c963c7e215824d30d759bc010b075384b3e74"),
    "Raw-GrandCanyonWest_PlainTankFlat.zip": (644983, "cc7fb61c96d18f6e255248810bb0884cdaad42550d5ea1214131bf59033ad0db"),
    "Station-GrandCanyonWest_PlainTankFlat.zip": (6499, "e22aaf87194ca2fd06e0bfc6c01ceadaefb75c169c350a313bb5cd010f5337ad"),
    "Inversions-GrandCanyonWest_PlainTankFlat.zip": (114382, "80d68dfab36b77824474dba9bba9eda972eaa39caecc073cbb30476dcf9cacbb"),
    "Cross_sections_Colorbar.zip": (2471945, "aa2bd459370de0b900eaecd2ef407370e166653bcaafdb0c9f07ea414995e75c"),
    "LandingPageMap.png": (9073663, "f7f8ad3ec4d95ab27810faea9c8f68ed66a7a41369009e5feadb3ea83713c876"),
}
FIELDS = (
    "TxLength", "TxAzimuth", "TxGridE", "TxGridN",
    "DpLength", "DpAzimuth", "ARerrFloor", "ZPerrFloor",
)
EXPECTED_MTM_VALUES = {
    "A1": (1000, 90, 241960, 3972019, 100, 90, 7.5, 4.5),
    "A2": (1000, 90, 241960, 3972019, 100, 90, 8.1, 10.6),
    "PT1": (1000, 37, 264773, 3948975, 100, 37, .6, 1.1),
    "PT2": (1000, 110, 267001, 3943284, 100, 110, 4.0, 2.3),
    "PT3": (1000, 37, 269051, 3944094, 100, 37, 2.3, 1.6),
    "QB1": (1000, 75, 243109, 3982818, 100, 75, 10.8, 3.8),
    "QB2": (1000, 75, 243109, 3982818, 100, 75, 10.9, 3.8),
    "QB3": (1000, 175, 247597, 3975580, 100, 175, 3.0, 1.0),
    "WG": (1000, 37, 262383, 3947140, 100, 37, 3.2, 2.6),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_lines(path: Path, suffix: str) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError(f"{path.name}: duplicate archive path")
        expected_root = {".raw": "Raw", ".stn": "Station", ".mtm": "Inversions"}[suffix]
        expected = {f"{expected_root}/"} | {
            f"{expected_root}/{line}{suffix}" for line in EXPECTED_LINES
        }
        if set(names) != expected or len(names) != len(expected):
            raise RuntimeError(f"{path.name}: unsafe or aliased archive path")
        return [Path(name).stem for name in names if name.endswith(suffix)]


def require_exact_archive_paths(path: Path, expected: set[str]) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    if len(names) != len(set(names)) or set(names) != expected:
        raise RuntimeError(f"{path.name}: unsafe, duplicate, aliased, or unexpected path")
    for name in names:
        parts = name.replace("\\", "/").split("/")
        if "\\" in name or name.startswith(("/", "\\")) or any(
            part in {"", ".", ".."} for part in parts
        ):
            raise RuntimeError(f"{path.name}: unsafe archive path")


def require_exact_lines(lines: list[str], label: str) -> None:
    if len(lines) != len(EXPECTED_LINES) or set(lines) != EXPECTED_LINES:
        raise RuntimeError(f"{label} line inventory drift")


def parse_mtm(text: str, line: str) -> dict[str, float]:
    values: dict[str, float] = {}
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?)"
    for field in FIELDS:
        indexed = r"\(1\)" if field.startswith("Tx") else ""
        matches = re.findall(
            rf"(?<![A-Za-z0-9_]){field}{indexed}\s*=\s*{number}(?![A-Za-z0-9_.])",
            text,
        )
        if len(matches) != 1:
            raise RuntimeError(f"{line}: missing or duplicate {field}")
        value = float(matches[0])
        if not math.isfinite(value):
            raise RuntimeError(f"{line}: non-finite {field}")
        values[field] = value
    for field in ("TxLength", "DpLength"):
        if values[field] <= 0:
            raise RuntimeError(f"{line}: non-positive {field}")
    if not 100000 <= values["TxGridE"] <= 900000 or not 0 < values["TxGridN"] <= 10000000:
        raise RuntimeError(f"{line}: Tx coordinates outside UTM zone 12N numeric bounds")
    for field in ("TxAzimuth", "DpAzimuth"):
        if not 0 <= values[field] < 360:
            raise RuntimeError(f"{line}: invalid {field}")
    for field in ("ARerrFloor", "ZPerrFloor"):
        if values[field] < 0:
            raise RuntimeError(f"{line}: negative {field}")
    return values


def write_immutable_atomic(path: Path, value: dict[str, object]) -> None:
    body = (json.dumps(value, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError("immutable Hualapai contract drift")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            out.write(body)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def audit() -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != "wp8-usgs-hualapai-csamt-permanent-training-manifest-v2"
        or manifest.get("scope") != "permanently-training-only"
        or manifest.get("field_validation_eligible") is not False
        or manifest.get("sealed_test_accessed") is not False
        or manifest.get("license") != "CC0-1.0"
        or manifest.get("sciencebase_parent_id") != "5474ec49e4b04d7459a7eab2"
        or manifest.get("sciencebase_child_id") != "5d1a9d8fe4b0941bde6029a9"
        or manifest.get("provider_member_count") != 7
        or manifest.get("metadata_snapshot_count") != 2
        or manifest.get("total_resource_count") != 9
    ):
        raise RuntimeError("Hualapai permanent-training manifest drift")
    members = manifest.get("members", [])
    if len(members) != 9 or len({row["path"] for row in members}) != 9:
        raise RuntimeError("Hualapai manifest inventory drift")
    for member in members:
        expected = EXPECTED_MEMBER_ANCHORS.get(member["path"])
        if expected != (member["bytes"], member["sha256"]):
            raise RuntimeError(f"Hualapai fixed provider anchor drift: {member['path']}")
        expected_kind = (
            "metadata_snapshot"
            if member["path"] in {"sciencebase-item.json", "sciencebase-parent.json"}
            else "provider_file"
        )
        if member.get("resource_kind") != expected_kind:
            raise RuntimeError(f"Hualapai resource kind drift: {member['path']}")
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            raise RuntimeError(f"Hualapai member drift: {member['path']}")
    child = json.loads((RAW / "sciencebase-item.json").read_text(encoding="utf-8"))
    parent = json.loads((RAW / "sciencebase-parent.json").read_text(encoding="utf-8"))
    if (
        child.get("id") != "5d1a9d8fe4b0941bde6029a9"
        or child.get("parentId") != "5474ec49e4b04d7459a7eab2"
        or parent.get("id") != "5474ec49e4b04d7459a7eab2"
        or len(child.get("files", [])) != 7
    ):
        raise RuntimeError("ScienceBase parent/child metadata snapshot drift")

    raw_lines = archive_lines(RAW_ZIP, ".raw")
    station_lines = archive_lines(STATION_ZIP, ".stn")
    inversion_lines = archive_lines(INVERSION_ZIP, ".mtm")
    require_exact_archive_paths(
        CROSS_SECTION_ZIP,
        {
            "AP1.gif", "AP2.gif", "Model_Resistivity_Colorbar.png",
            "PT1.gif", "PT2.gif", "PT3.gif", "QB1.gif", "QB2.gif",
            "QB3.gif", "WG.gif",
        },
    )
    for lines, label in ((raw_lines, "raw"), (station_lines, "station"), (inversion_lines, "inversion")):
        require_exact_lines(lines, label)
    if not (set(raw_lines) == set(station_lines) == set(inversion_lines)):
        raise RuntimeError("cross-archive line inventory drift")

    station_counts: dict[str, int] = {}
    with zipfile.ZipFile(STATION_ZIP) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".stn"):
                rows = list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"))))
                if not rows or not {"Station", "Easting", "Northing", "Elevation"}.issubset(rows[0]):
                    raise RuntimeError(f"station schema drift: {name}")
                station_counts[Path(name).stem] = len(rows)

    mtm: dict[str, dict[str, float]] = {}
    headers: dict[str, str] = {}
    with zipfile.ZipFile(INVERSION_ZIP) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".mtm"):
                line = Path(name).stem
                text = archive.read(name).decode("latin1")
                mtm[line] = parse_mtm(text, line)
                match = re.search(r"Header\(1\)\s*=\s*'([^']*)'", text)
                headers[line] = match.group(1).strip() if match else ""
    for line, expected in EXPECTED_MTM_VALUES.items():
        if tuple(mtm[line][field] for field in FIELDS) != expected:
            raise RuntimeError(f"{line}: MTM anchored value drift")

    # The anchored XML/KMZ and official MTM headers do not prove the requested
    # Quartermaster/Horse Flat and Plain Tank Flat line-to-site assignments.
    # AIRPORT labels for A1/A2 alone cannot establish a complete three-site map.
    expected_airport_headers = {"A1": "Line AIRPORT 1", "A2": "Line AIRPORT2 E"}
    airport_marker_verified = all(headers.get(line) == header for line, header in expected_airport_headers.items())
    site_mapping = {
        "status": "unsupported_by_anchored_official_evidence",
        "requested_three_site_mapping_accepted": False,
        "lines_are_sites": False,
        "supported_partial_marker": (
            {"A1": "AIRPORT", "A2": "AIRPORT2"} if airport_marker_verified else {}
        ),
        "partial_marker_verified_from_mtm_headers": airport_marker_verified,
        "unresolved_lines": sorted(EXPECTED_LINES - {"A1", "A2"}),
        "rule": "no site assignment from line prefix or geographic guess",
    }
    result: dict[str, object] = {
        "schema_version": "wp8-usgs-hualapai-csamt-contract-v2",
        "raw_manifest_sha256": sha256(MANIFEST),
        "doi": "10.5066/P90KAJM4",
        "scope": "permanently-training-only",
        "field_validation_eligible": False,
        "sealed_test_accessed": False,
        "license_gate_passes": True,
        "line_ids": sorted(EXPECTED_LINES),
        "raw_line_file_count": len(raw_lines),
        "station_line_file_count": len(station_lines),
        "inversion_line_file_count": len(inversion_lines),
        "receiver_station_count": sum(station_counts.values()),
        "station_counts_by_line": station_counts,
        "mtm_source_and_error_contract_by_line": mtm,
        "mtm_header_by_line": headers,
        "source_coordinates_imputed": False,
        "site_mapping": site_mapping,
        "available_provider_line_clusters": 9,
        "formal_cluster_power_gate_passes": False,
        "observation_contract_ready": False,
        "conclusion": (
            "The nine official MTM files provide finite, nonzero transmitter coordinates, "
            "source/dipole geometry, and error floors aligned exactly to raw and station lines. "
            "This entire package remains permanently training-only. Anchored evidence does not "
            "prove a complete three-site mapping; lines are not treated as independent sites, "
            "so field validation and formal cluster/power claims remain blocked."
        ),
    }
    if result["receiver_station_count"] != 543:
        raise RuntimeError("Hualapai station count drift")
    return result


def main() -> None:
    result = audit()
    write_immutable_atomic(OUTPUT, result)
    print(json.dumps({"lines": 9, "stations": 543, "site_mapping": result["site_mapping"]["status"]}))


if __name__ == "__main__":
    main()
