#!/usr/bin/env python
"""Freeze a response-blind spatial split from western Arkansas geometry columns."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/western-arkansas-magnetic-v1"
CSV = DATA / "AR21F1047_USGS_AR-WestCentral_MagneticLineData.csv"
MANIFEST = DATA / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/western-arkansas-magnetic-design-split.json"
CELL_M = 2000.0
MACROBLOCK_M = 20000.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def macroblock(x: float, y: float) -> str:
    return f"{int(x // MACROBLOCK_M)}:{int(y // MACROBLOCK_M)}"


def partition(block: str) -> str:
    bucket = int(
        hashlib.sha256(f"wp8-western-arkansas-mag-v1|{block}".encode()).hexdigest()[:8],
        16,
    ) % 100
    if bucket < 45:
        return "train"
    if bucket < 60:
        return "buffer"
    if bucket < 75:
        return "calibration"
    return "test"


def main() -> None:
    required = {
        "line",
        "flt",
        "date",
        "x",
        "y",
        "z",
        "Radar_final",
        "DTM_final",
        "mfluxX",
        "mfluxY",
        "mfluxZ",
        "IGRF",
        "magres",
    }
    cells: dict[str, dict] = {}
    line_cells: dict[str, set[str]] = defaultdict(set)
    rows = 0
    with CSV.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        indices = {name: header.index(name) for name in required}
        # Magnetic response columns are asserted present but never converted,
        # aggregated, displayed, or written by this split program.
        geometry_names = ("line", "flt", "date", "x", "y", "z", "Radar_final", "DTM_final")
        for row in reader:
            x = float(row[indices["x"]])
            y = float(row[indices["y"]])
            line = row[indices["line"]]
            cell = f"{int(x // CELL_M)}:{int(y // CELL_M)}"
            block = macroblock(x, y)
            record = cells.setdefault(
                cell,
                {
                    "cell": cell,
                    "macroblock": block,
                    "partition": partition(block),
                    "rows": 0,
                    "lines": set(),
                    "flights": set(),
                    "dates": set(),
                    "min_x": x,
                    "max_x": x,
                    "min_y": y,
                    "max_y": y,
                    "min_gps_z": float(row[indices["z"]]),
                    "max_gps_z": float(row[indices["z"]]),
                    "min_radar_m": float(row[indices["Radar_final"]]),
                    "max_radar_m": float(row[indices["Radar_final"]]),
                    "min_dtm_m": float(row[indices["DTM_final"]]),
                    "max_dtm_m": float(row[indices["DTM_final"]]),
                },
            )
            record["rows"] += 1
            record["lines"].add(line)
            record["flights"].add(row[indices["flt"]])
            record["dates"].add(row[indices["date"]])
            record["min_x"] = min(record["min_x"], x)
            record["max_x"] = max(record["max_x"], x)
            record["min_y"] = min(record["min_y"], y)
            record["max_y"] = max(record["max_y"], y)
            for field, column in (
                ("gps_z", "z"),
                ("radar_m", "Radar_final"),
                ("dtm_m", "DTM_final"),
            ):
                value = float(row[indices[column]])
                record[f"min_{field}"] = min(record[f"min_{field}"], value)
                record[f"max_{field}"] = max(record[f"max_{field}"], value)
            line_cells[line].add(cell)
            rows += 1
    serial = []
    for record in cells.values():
        for key in ("lines", "flights", "dates"):
            record[key] = sorted(record[key])
        serial.append(record)
    serial.sort(key=lambda value: value["cell"])
    counts = {
        role: sum(record["partition"] == role for record in serial)
        for role in ("train", "buffer", "calibration", "test")
    }
    payload = {
        "schema_version": "wp8-western-arkansas-magnetic-design-split-v1",
        "raw_manifest_sha256": sha(MANIFEST),
        "csv_path": str(CSV.relative_to(ROOT)).replace("\\", "/"),
        "csv_sha256": sha(CSV),
        "selection_inputs": geometry_names,
        "magnetic_response_values_interpreted": 0,
        "rows": rows,
        "unique_lines": len(line_cells),
        "spatial_cell_m": CELL_M,
        "partition_macroblock_m": MACROBLOCK_M,
        "partition_cell_counts": counts,
        "cells": serial,
        "line_cell_counts": {
            line: len(values) for line, values in sorted(line_cells.items())
        },
        "warning": (
            "2-km cells are design units only; training-only residual correlation "
            "must merge cells and expand buffers before formal eligibility"
        ),
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": rows,
                "lines": len(line_cells),
                "cells": len(serial),
                "partitions": counts,
            }
        )
    )


if __name__ == "__main__":
    main()
