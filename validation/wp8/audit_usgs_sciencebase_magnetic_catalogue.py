#!/usr/bin/env python
"""Audit frozen USGS ScienceBase magnetic metadata without reading responses."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-sciencebase-magnetic-catalogue-v1"
CATALOGUE = DATA / "catalogue.json"
PARENTS = DATA / "parent-manifest.json"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-sciencebase-magnetic-catalogue-audit-v1.json"
)
RANGE_KM = 75.0
RIGHTS_POLICY = "https://www.usgs.gov/data-management/data-licensing"
PROCESSING_TERMS = (
    "processed",
    "diurnal",
    "igrf",
    "level",
    "residual magnetic",
    "total magnetic",
)
NON_OBSERVATION = re.compile(
    r"dictionary|channel.?name|datadxny|metadata|readme|radiometric|"
    r"spectr|ternary|grid|resistivity|model",
    re.I,
)
LINE_SUFFIX = re.compile(r"\.(csv|xyz|txt|dat|nc)(\.zip|\.gz)?$", re.I)


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_raw(folder: str, item_id: str) -> dict | None:
    path = DATA / folder / f"{item_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def boxes(item: dict | None) -> list[dict]:
    found = []
    for facet in (item or {}).get("facets") or []:
        box = facet.get("boundingBox")
        if not isinstance(box, dict):
            continue
        keys = ("minX", "minY", "maxX", "maxY")
        if not all(isinstance(box.get(key), (int, float)) for key in keys):
            continue
        normalized = {key: float(box[key]) for key in keys}
        if (
            -180 <= normalized["minX"] <= normalized["maxX"] <= 180
            and -90 <= normalized["minY"] <= normalized["maxY"] <= 90
            and normalized not in found
        ):
            found.append(normalized)
    return found


def text(item: dict | None) -> str:
    if not item:
        return ""
    values = [
        str(item.get(key) or "")
        for key in ("title", "summary", "body", "purpose", "citation")
    ]
    values.extend(str(tag) for tag in item.get("tags") or [])
    return " ".join(values).lower()


def observation_files(item: dict) -> list[dict]:
    result = []
    for file in item.get("files") or []:
        name = file.get("name") or ""
        if not LINE_SUFFIX.search(name) or NON_OBSERVATION.search(name):
            continue
        lowered = " ".join(
            str(file.get(key) or "") for key in ("name", "title", "contentType")
        ).lower()
        if not any(
            token in lowered
            for token in ("mag", "flight", "line", "xyz", "total.field")
        ):
            continue
        result.append(
            {
                key: file.get(key)
                for key in (
                    "name",
                    "title",
                    "contentType",
                    "size",
                    "dateUploaded",
                    "downloadUri",
                    "checksum",
                )
            }
        )
    return result


def bbox_distance_km(a: dict, b: dict) -> float:
    latitude_gap = max(
        0.0, a["minY"] - b["maxY"], b["minY"] - a["maxY"]
    )
    longitude_gap = max(
        0.0, a["minX"] - b["maxX"], b["minX"] - a["maxX"]
    )
    latitude = (
        a["minY"] + a["maxY"] + b["minY"] + b["maxY"]
    ) / 4.0
    return math.hypot(
        latitude_gap * 111.32,
        longitude_gap * 111.32 * math.cos(math.radians(latitude)),
    )


def maximum_independent(records: list[dict]) -> tuple[list[int], int, float]:
    edges = []
    for index in range(len(records)):
        for other in range(index):
            if (
                bbox_distance_km(
                    records[index]["bounding_box"],
                    records[other]["bounding_box"],
                )
                < RANGE_KM
            ):
                edges.append((index, other))
    if not edges:
        return list(range(len(records))), 0, 0.0
    rows = [row for row in range(len(edges)) for _ in (0, 1)]
    columns = [node for edge in edges for node in edge]
    matrix = coo_matrix(
        (np.ones(2 * len(edges)), (rows, columns)),
        shape=(len(edges), len(records)),
    ).tocsr()
    result = milp(
        c=-np.ones(len(records)),
        integrality=np.ones(len(records)),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(
            matrix, -np.inf, np.ones(len(edges))
        ),
        options={"mip_rel_gap": 0.0},
    )
    if result.status != 0 or result.x is None:
        raise RuntimeError(f"HiGHS independent-set failure: {result.message}")
    selected = [index for index, value in enumerate(result.x) if value > 0.5]
    return selected, len(edges), float(result.mip_gap)


def main() -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    parent_manifest = json.loads(PARENTS.read_text(encoding="utf-8"))
    records = []
    rejected = []
    for summary in catalogue["records"]:
        child = load_raw("raw-items", summary["sciencebase_id"])
        if child is None:
            raise RuntimeError(f"missing frozen child: {summary['sciencebase_id']}")
        parent_id = child.get("parentId")
        parent = load_raw("raw-parents", parent_id) if parent_id else None
        files = observation_files(child)
        own_boxes = boxes(child)
        parent_boxes = boxes(parent)
        source = "item" if own_boxes else "direct_parent" if parent_boxes else None
        selected_box = (own_boxes or parent_boxes or [None])[0]
        combined_text = text(child) + " " + text(parent)
        processing = [
            term for term in PROCESSING_TERMS if term in combined_text
        ]
        minimally_processed = "minimally processed" in combined_text
        raw_file = any(
            re.search(r"(^|[_-])raw(data)?([_.-]|$)", file["name"], re.I)
            for file in files
        )
        title = str(child.get("title") or "")
        magnetic_title = (
            "magnetic" in title.lower() or "aeromagnetic" in title.lower()
        )
        restrictive_notice = any(
            phrase in combined_text
            for phrase in (
                "all rights reserved",
                "permission required",
                "not for redistribution",
            )
        )
        reasons = []
        if not magnetic_title:
            reasons.append("title_not_magnetic")
        if not files:
            reasons.append("no_observational_line_file")
        if selected_box is None:
            reasons.append("no_item_or_direct_parent_bbox")
        if not processing:
            reasons.append("no_documented_processing_term")
        if minimally_processed:
            reasons.append("minimally_processed_not_corrected")
        if raw_file:
            reasons.append("raw_magnetic_file_not_corrected")
        if restrictive_notice:
            reasons.append("restrictive_rights_notice")
        record = {
            "sciencebase_id": child["id"],
            "provider_unit": parent_id or child["id"],
            "parent_id": parent_id,
            "title": title,
            "observational_line_files": files,
            "processing_evidence_terms": processing,
            "bounding_box_source": source,
            "bounding_box": selected_box,
            "rights_basis": RIGHTS_POLICY,
            "item_url": f"https://www.sciencebase.gov/catalog/item/{child['id']}",
        }
        if reasons:
            record["rejection_reasons"] = reasons
            rejected.append(record)
        else:
            records.append(record)

    by_provider: dict[str, list[dict]] = {}
    for record in records:
        by_provider.setdefault(record["provider_unit"], []).append(record)
    deduplicated = []
    duplicate_exclusions = []
    for provider, candidates in by_provider.items():
        ordered = sorted(
            candidates,
            key=lambda record: hashlib.sha256(
                (
                    "wp8-usgs-mag-product-v1|"
                    f"{provider}|{record['sciencebase_id']}"
                ).encode()
            ).hexdigest(),
        )
        deduplicated.append(ordered[0])
        duplicate_exclusions.extend(ordered[1:])
    deduplicated.sort(key=lambda record: record["sciencebase_id"])
    selected_indices, edge_count, mip_gap = maximum_independent(deduplicated)
    selected = [deduplicated[index] for index in selected_indices]

    result = {
        "schema_version": "wp8-usgs-sciencebase-magnetic-catalogue-audit-v1",
        "catalogue_sha256": sha(CATALOGUE),
        "parent_manifest_sha256": sha(PARENTS),
        "source_authority": "U.S. Geological Survey ScienceBase",
        "rights_policy": RIGHTS_POLICY,
        "raw_search_item_count": catalogue["raw_item_count"],
        "direct_parent_count": parent_manifest["direct_parent_count"],
        "unavailable_direct_parent_count": parent_manifest[
            "unavailable_parent_count"
        ],
        "pre_dedup_eligible_count": len(records),
        "unique_provider_unit_count": len(deduplicated),
        "duplicate_product_exclusion_count": len(duplicate_exclusions),
        "rejected_count": len(rejected),
        "range_km": RANGE_KM,
        "bbox_conflict_edge_count": edge_count,
        "maximum_independent_set_count": len(selected),
        "maximum_independent_set_mip_gap": mip_gap,
        "eligible_records": deduplicated,
        "maximum_independent_set_sciencebase_ids": [
            record["sciencebase_id"] for record in selected
        ],
        "duplicate_product_exclusions": duplicate_exclusions,
        "rejected_records": rejected,
        "selection_interpreted_response_values": 0,
        "candidate_files_downloaded": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "eligible": len(deduplicated),
            "bbox_independent": len(selected),
            "conflict_edges": edge_count,
            "mip_gap": mip_gap,
            "unavailable_parents": result["unavailable_direct_parent_count"],
        }
    )


if __name__ == "__main__":
    main()
