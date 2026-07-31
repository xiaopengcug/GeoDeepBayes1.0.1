from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import openpyxl


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/wp8/data/geodoi-wuxi-comprehensive-em-v1/InsituData.xlsx"
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/geodoi-wuxi-fdip-outcome-blind-design-v1.json"
)
OUTPUT = (
    ROOT / "validation/wp8/evidence/feasibility-v1/geodoi-wuxi-fdip-training-audit-v1.json"
)
TRAIN_LINES = {5000, 5200, 5400}
LAG_BINS_M = [(0, 25), (25, 50), (50, 75), (75, 100), (100, 150), (150, 250)]


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) < 8 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["Tab.4"]
    rows = []
    for row_number, row in enumerate(sheet.iter_rows(min_row=7, values_only=True), start=7):
        line, point, fs, rho, north, east = row[:6]
        if (
            line not in TRAIN_LINES
            or fs is None
            or rho is None
            or north is None
            or east is None
        ):
            continue
        rows.append(
            {
                "row": row_number,
                "line": int(line),
                "point": int(point),
                "fs_percent": float(fs),
                "rho_ohm_m": float(rho),
                "north_m": float(north),
                "east_m": float(east),
            }
        )

    pairs = []
    for index, a in enumerate(rows):
        for b in rows[index + 1 :]:
            distance = math.hypot(a["east_m"] - b["east_m"], a["north_m"] - b["north_m"])
            pairs.append((distance, a, b))

    diagnostics = []
    for low, high in LAG_BINS_M:
        selected = [(a, b) for distance, a, b in pairs if low <= distance < high]
        diagnostics.append(
            {
                "lag_m": [low, high],
                "pair_count": len(selected),
                "fs_pearson": pearson(
                    [a["fs_percent"] for a, _ in selected],
                    [b["fs_percent"] for _, b in selected],
                ),
                "log_rho_pearson": pearson(
                    [math.log(a["rho_ohm_m"]) for a, _ in selected],
                    [math.log(b["rho_ohm_m"]) for _, b in selected],
                ),
            }
        )

    result = {
        "audit_version": "geodoi-wuxi-fdip-training-audit-v1",
        "design_version": design["design_version"],
        "response_scope": "training lines only: 5000, 5200, 5400",
        "training_row_count": len(rows),
        "response_completeness": {
            "fs_percent_complete": len(rows),
            "rho_ohm_m_complete": len(rows),
        },
        "lagged_pair_correlations": diagnostics,
        "independence_decision_rule": (
            "The preregistered 50 m radius is unsupported if either absolute "
            "Pearson correlation in the 50-75 m bin exceeds 0.20."
        ),
        "independence_supported_at_50m": all(
            item[key] is not None and abs(item[key]) <= 0.20
            for item in diagnostics
            if item["lag_m"] == [50, 75]
            for key in ("fs_pearson", "log_rho_pearson")
        ),
        "limitations": [
            "The workbook provides no repeat-measurement uncertainty column.",
            "FS is a dual-frequency amplitude-percent response, not a full SIP spectrum.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
