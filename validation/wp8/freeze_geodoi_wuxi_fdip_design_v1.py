from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/wp8/data/geodoi-wuxi-comprehensive-em-v1/InsituData.xlsx"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/geodoi-wuxi-fdip-outcome-blind-design-v1.json"
)
TRAIN_LINES = {5000, 5200, 5400}
MIN_DISTANCE_M = 50.0
SALT = "geodoi-wuxi-fdip-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distance(a: dict, b: dict) -> float:
    return math.hypot(a["east_m"] - b["east_m"], a["north_m"] - b["north_m"])


def rank(point: dict) -> str:
    key = (
        f"{SALT}|{point['line']}|{point['point']}|"
        f"{point['east_m']:.3f}|{point['north_m']:.3f}"
    )
    return hashlib.sha256(key.encode()).hexdigest()


def main() -> None:
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["Tab.4"]
    points = []
    for row_number, row in enumerate(sheet.iter_rows(min_row=7, values_only=True), start=7):
        line, point = row[0], row[1]
        north, east = row[4], row[5]
        if line is None or point is None or north is None or east is None:
            continue
        points.append(
            {
                "row": row_number,
                "line": int(line),
                "point": int(point),
                "north_m": float(north),
                "east_m": float(east),
            }
        )

    train = [p for p in points if p["line"] in TRAIN_LINES]
    candidates = [p for p in points if p["line"] > max(TRAIN_LINES)]

    eligible = [
        p
        for p in candidates
        if all(distance(p, q) >= MIN_DISTANCE_M for q in train)
    ]
    selected = []
    for point in sorted(eligible, key=rank):
        if all(distance(point, prior) >= MIN_DISTANCE_M for prior in selected):
            selected.append(point)

    result = {
        "design_version": "geodoi-wuxi-fdip-outcome-blind-design-v1",
        "status": "frozen_before_additional_response_inspection",
        "source": {
            "path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(SOURCE),
            "doi": "10.3974/geodb.2018.03.08.V1",
            "sheet": "Tab.4",
        },
        "outcome_blinding": {
            "geometry_columns_read": ["Line", "Point", "North", "East"],
            "response_columns_not_read_by_this_script": [
                "FS (%)",
                "Apparent resistivity",
            ],
        },
        "split": {
            "training_lines": sorted(TRAIN_LINES),
            "buffer_lines_excluded": [],
            "sealed_test_line_rule": "line > 5400",
            "minimum_training_test_distance_m": MIN_DISTANCE_M,
            "minimum_test_test_distance_m": MIN_DISTANCE_M,
            "deterministic_order_salt": SALT,
        },
        "counts": {
            "all_valid_geometry_rows": len(points),
            "training_rows": len(train),
            "buffer_rows": 0,
            "candidate_test_rows": len(candidates),
            "eligible_after_training_distance": len(eligible),
            "sealed_independent_test_clusters": len(selected),
        },
        "sealed_test_cluster_geometry": selected,
        "gate_note": (
            "The 50 m spacing is a preregistered candidate independence radius. "
            "It must be rejected or enlarged if training-only spatial diagnostics "
            "show material dependence beyond 50 m."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
