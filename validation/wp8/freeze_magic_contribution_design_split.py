#!/usr/bin/env python
"""Freeze a contribution-level MagIC split using location metadata only."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/magic-contributions-v1"
ARCHIVE = DATA / "magic-latest-100.zip"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/magic-contribution-design-split.json"
)


def bucket(contribution_id: int) -> str:
    value = int.from_bytes(
        hashlib.sha256(f"wp8-magic-v1:{contribution_id}".encode()).digest()[:8],
        "big",
    ) % 20
    if value < 12:
        return "train"
    if value < 15:
        return "buffer"
    if value < 18:
        return "calibration"
    return "test"


def location_metadata(archive: zipfile.ZipFile, member: str) -> dict[str, object]:
    locations = 0
    coordinate_rows = 0
    cells: set[str] = set()
    with archive.open(member) as raw:
        stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
        in_locations = False
        header: list[str] | None = None
        for line in stream:
            text = line.rstrip("\r\n")
            if text.startswith("tab delimited\t"):
                in_locations = text == "tab delimited\tlocations"
                header = None
                continue
            if text == ">>>>>>>>>>":
                in_locations = False
                header = None
                continue
            if not in_locations:
                continue
            if header is None:
                header = next(csv.reader([text], delimiter="\t"))
                continue
            values = next(csv.reader([text], delimiter="\t"))
            row = dict(zip(header, values))
            locations += 1
            try:
                lat = (float(row["lat_s"]) + float(row["lat_n"])) / 2
                lon = (float(row["lon_w"]) + float(row["lon_e"])) / 2
            except (KeyError, TypeError, ValueError):
                continue
            coordinate_rows += 1
            cells.add(f"{int((lat + 90) // 10):02d}:{int((lon + 180) // 10):02d}")
    return {
        "location_rows": locations,
        "coordinate_rows": coordinate_rows,
        "ten_degree_cells": sorted(cells),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    excluded = set(manifest["excluded_contribution_ids"])
    rows = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for member in archive.namelist():
            contribution_id = int(member.split("/", 1)[0])
            if contribution_id in excluded:
                continue
            metadata = location_metadata(archive, member)
            rows.append(
                {
                    "contribution_id": contribution_id,
                    "member": member,
                    "split": bucket(contribution_id),
                    **metadata,
                }
            )
    split_counts = Counter(row["split"] for row in rows)
    split_cells = {
        split: sorted(
            {
                cell
                for row in rows
                if row["split"] == split
                for cell in row["ten_degree_cells"]
            }
        )
        for split in ("train", "buffer", "calibration", "test")
    }
    evidence = {
        "schema_version": "wp8-magic-contribution-design-split-v1",
        "archive_sha256": manifest["archive"]["sha256"],
        "split_unit": "contribution_id",
        "split_rule": "sha256('wp8-magic-v1:' + contribution_id) modulo 20",
        "excluded_contribution_ids": sorted(excluded),
        "contributions": rows,
        "counts": dict(sorted(split_counts.items())),
        "location_rows": sum(row["location_rows"] for row in rows),
        "coordinate_rows": sum(row["coordinate_rows"] for row in rows),
        "ten_degree_cells_by_split": split_cells,
        "contribution_overlap": False,
        "location_cell_overlap_is_possible": True,
        "tables_read": ["locations"],
        "response_tables_read": [],
        "response_values_interpreted": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "counts": evidence["counts"],
                "location_rows": evidence["location_rows"],
                "coordinate_rows": evidence["coordinate_rows"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
