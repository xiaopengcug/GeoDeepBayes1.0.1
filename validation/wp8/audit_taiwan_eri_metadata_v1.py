"""Response-blind metadata audit for the Taiwan ERI Mendeley dataset."""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data"
META = DATA / "taiwan-eri-metadata-v2"
INVENTORY = DATA / "taiwan-eri-mendeley-file-inventory-v2.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-unexposed-candidate-design-v1.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-metadata-audit-v1.json"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workbook_rows(path: Path):
    with ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
                for item in root
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in relationships}
        for sheet in workbook.find(f"{{{MAIN_NS}}}sheets"):
            target = targets[sheet.attrib[f"{{{REL_NS}}}id"]].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            root = ET.fromstring(archive.read(target))
            for row in root.findall(f".//{{{MAIN_NS}}}row"):
                cells: dict[int, str] = {}
                for cell in row.findall(f"{{{MAIN_NS}}}c"):
                    letters = re.match(r"[A-Z]+", cell.attrib["r"]).group()
                    column = 0
                    for letter in letters:
                        column = column * 26 + ord(letter) - 64
                    value_node = cell.find(f"{{{MAIN_NS}}}v")
                    value = "" if value_node is None else value_node.text
                    if cell.attrib.get("t") == "s" and value:
                        value = shared[int(value)]
                    cells[column - 1] = value
                yield [cells.get(i, "") for i in range(max(cells, default=-1) + 1)]


def coordinate(value: object) -> float | None:
    try:
        return float(str(value).replace("°", "").strip())
    except ValueError:
        return None


def cluster_count(points: list[tuple[float, float]], threshold_m: float) -> int:
    parent = list(range(len(points)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for i, (lat_i, lon_i) in enumerate(points):
        for j in range(i):
            lat_j, lon_j = points[j]
            dy = (lat_i - lat_j) * 111_320
            dx = (lon_i - lon_j) * 111_320 * math.cos(
                math.radians((lat_i + lat_j) / 2)
            )
            if dx * dx + dy * dy <= threshold_m * threshold_m:
                union(i, j)
    return len({find(index) for index in range(len(points))})


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    files = [item for folder in inventory for item in folder["files"]]
    extension_counts: dict[str, int] = {}
    for item in files:
        suffix = Path(item["filename"]).suffix.lower()
        extension_counts[suffix] = extension_counts.get(suffix, 0) + 1

    rows = []
    for path in sorted(META.glob("*.xlsx")):
        for row in workbook_rows(path):
            if len(row) < 6 or not row[0]:
                continue
            latitude, longitude = coordinate(row[4]), coordinate(row[5])
            if (
                latitude is not None
                and longitude is not None
                and 20 < latitude < 27
                and 118 < longitude < 123
            ):
                rows.append((latitude, longitude))
    points = sorted({(round(lat, 7), round(lon, 7)) for lat, lon in rows})
    sensitivity = {
        str(distance): cluster_count(points, distance)
        for distance in (1, 10, 32, 64, 100, 250, 500, 1000)
    }

    evidence = {
        "schema_version": "wp8-taiwan-eri-metadata-audit-v1",
        "design_sha256": sha256(DESIGN),
        "selection_frozen_before_response_payload_access": design[
            "selection_frozen_before_response_payload_access"
        ],
        "doi": design["candidate"]["doi"],
        "license": design["license"],
        "declared_profile_count": design["candidate"]["declared_profile_count"],
        "public_folder_count": len(inventory),
        "public_file_count": len(files),
        "file_extension_counts": dict(sorted(extension_counts.items())),
        "coordinate_workbook_count": len(list(META.glob("*.xlsx"))),
        "coordinate_rows_parsed": len(rows),
        "exact_unique_profile_centres": len(points),
        "training_correlation_range_m": 64,
        "effective_spatial_clusters_at_training_range": sensitivity["64"],
        "required_test_clusters": 223,
        "cluster_count_gate_possible": sensitivity["64"] >= 223,
        "cluster_sensitivity": sensitivity,
        "observation_contract_metadata": {
            "stg_files": extension_counts.get(".stg", 0),
            "urf_files": extension_counts.get(".urf", 0),
            "stg_official_fields": [
                "V/I",
                "repeat error percent",
                "output current",
                "apparent resistivity",
                "A/B/M/N xyz coordinates",
            ],
            "contract_status": "possible_pending_frozen_training_only_header_audit",
        },
        "paired_crps_effect_size_available": False,
        "power_gate_passed": False,
        "response_payloads_downloaded": 0,
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
        "notes": [
            "The 251 exact centres are obtained from public coordinate workbooks only; "
            "the repository declares 265 profiles.",
            "At 64 m, 246 response-blind spatial components exceed the 223 cluster "
            "count requirement, but paired-CRPS effect size remains unavailable.",
        ],
    }
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
