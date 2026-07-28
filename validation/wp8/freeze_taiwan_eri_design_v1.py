"""Freeze a response-blind Taiwan ERI split with exactly 223 test components."""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "validation/wp8/data/taiwan-eri-metadata-v2"
INVENTORY = ROOT / "validation/wp8/data/taiwan-eri-mendeley-file-inventory-v2.json"
AUDIT = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-metadata-audit-v1.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/taiwan-eri-design-v1.json"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RANGE_M = 64.0
TRAIN_COUNT = 23
SALT = "wp8-taiwan-eri-response-blind-split-v1"


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


def number(value: object) -> float | None:
    try:
        return float(str(value).replace("°", "").strip())
    except ValueError:
        return None


def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat_l, lon_l = left
    lat_r, lon_r = right
    dy = (lat_l - lat_r) * 111_320
    dx = (lon_l - lon_r) * 111_320 * math.cos(
        math.radians((lat_l + lat_r) / 2)
    )
    return math.hypot(dx, dy)


def canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    folder_names = {folder["folder_id"]: folder["folder_name"] for folder in inventory}
    stg_files = [
        item["filename"]
        for folder in inventory
        for item in folder["files"]
        if item["filename"].lower().endswith(".stg")
    ]
    records: dict[tuple[float, float], dict[str, object]] = {}
    for path in sorted(META.glob("*.xlsx")):
        folder_id = path.name[:36]
        for row in workbook_rows(path):
            if len(row) < 6 or not row[0]:
                continue
            latitude, longitude = number(row[4]), number(row[5])
            if not (
                latitude is not None
                and longitude is not None
                and 20 < latitude < 27
                and 118 < longitude < 123
            ):
                continue
            key = (round(latitude, 7), round(longitude, 7))
            record = records.setdefault(
                key,
                {
                    "latitude": key[0],
                    "longitude": key[1],
                    "profiles": set(),
                    "workbooks": set(),
                    "metadata_folders": set(),
                    "stg_declared": False,
                },
            )
            record["profiles"].add(str(row[0]).strip())
            record["workbooks"].add(path.name)
            record["metadata_folders"].add(
                f"{folder_id}:{folder_names.get(folder_id, '')}"
            )
            text = "|".join(str(value) for value in row).lower()
            if "stg" in text or "supersting" in text:
                record["stg_declared"] = True

    points = sorted(records)
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

    for i, point in enumerate(points):
        for j in range(i):
            if distance(point, points[j]) <= RANGE_M:
                union(i, j)
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for index, point in enumerate(points):
        grouped[find(index)].append(point)

    components = []
    for members in grouped.values():
        member_records = [records[member] for member in sorted(members)]
        identity = ";".join(f"{lat:.7f},{lon:.7f}" for lat, lon in sorted(members))
        profile_keys = {
            canonical(profile)
            for item in member_records
            for profile in item["profiles"]
        }
        stg_matches = sorted(
            filename
            for filename in stg_files
            if any(
                canonical(Path(filename).stem).startswith(key)
                and (
                    len(canonical(Path(filename).stem)) == len(key)
                    or not canonical(Path(filename).stem)[len(key)].isdigit()
                )
                for key in profile_keys
            )
        )
        components.append(
            {
                "component_id": hashlib.sha256(identity.encode()).hexdigest()[:16],
                "centres": [
                    {
                        "latitude": item["latitude"],
                        "longitude": item["longitude"],
                        "profiles": sorted(item["profiles"]),
                        "workbooks": sorted(item["workbooks"]),
                        "metadata_folders": sorted(item["metadata_folders"]),
                    }
                    for item in member_records
                ],
                "stg_declared": any(item["stg_declared"] for item in member_records),
                "stg_file_name_matches": stg_matches,
            }
        )
    components.sort(key=lambda item: item["component_id"])
    eligible = [
        item
        for item in components
        if item["stg_declared"] and item["stg_file_name_matches"]
    ]
    if len(components) != 246 or len(eligible) < TRAIN_COUNT:
        raise RuntimeError("Taiwan ERI component population drift")
    eligible.sort(
        key=lambda item: hashlib.sha256(
            f"{SALT}|{item['component_id']}".encode()
        ).hexdigest()
    )
    training_ids = {item["component_id"] for item in eligible[:TRAIN_COUNT]}
    for component in components:
        component["role"] = (
            "training" if component["component_id"] in training_ids else "test"
        )
    counts = {
        "training": sum(item["role"] == "training" for item in components),
        "test": sum(item["role"] == "test" for item in components),
    }
    output = {
        "schema_version": "wp8-taiwan-eri-design-v1",
        "metadata_audit_sha256": sha256(AUDIT),
        "inventory_sha256": sha256(INVENTORY),
        "selection_frozen_before_response_payload_access": True,
        "selection_basis": "coordinates, profile labels, file-format declarations, and salted hashes only",
        "salt_sha256": hashlib.sha256(SALT.encode()).hexdigest(),
        "correlation_range_m": RANGE_M,
        "exact_unique_profile_centres": len(points),
        "component_count": len(components),
        "stg_eligible_component_count": len(eligible),
        "role_counts": counts,
        "required_test_clusters": 223,
        "design_cluster_gate_passes": counts == {"training": 23, "test": 223},
        "components": components,
        "response_payloads_downloaded": 0,
        "response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "component_count": len(components),
                "stg_eligible": len(eligible),
                "role_counts": counts,
                "design_cluster_gate_passes": output["design_cluster_gate_passes"],
            }
        )
    )


if __name__ == "__main__":
    main()
