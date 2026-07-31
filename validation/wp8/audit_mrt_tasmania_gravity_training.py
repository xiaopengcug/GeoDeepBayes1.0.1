#!/usr/bin/env python
"""Training-only MRT Tasmania gravity correlation and contract audit."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/mrt-tasmania-gravity-v1"
RAW = DATA / "Gravity_Data_Geopackage.gpkg"
MANIFEST = DATA / "raw-manifest.json"
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/mrt-tasmania-gravity-design.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/mrt-tasmania-gravity-training.json"
LAG_KM = 2.5
MAX_LAG_KM = 100.0


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if design["raw_manifest_sha256"] != sha(MANIFEST):
        raise RuntimeError("MRT Tasmania design drift")
    assignments = {
        int(record["reading_id"]): record
        for record in design["records"]
        if record["role"] == "train"
    }
    connection = sqlite3.connect(f"file:{RAW}?mode=ro", uri=True)
    connection.execute("CREATE TEMP TABLE selected_train (reading_id INTEGER PRIMARY KEY)")
    connection.executemany(
        "INSERT INTO selected_train VALUES (?)", ((value,) for value in assignments)
    )
    # The join makes the response read policy explicit: no non-training row is selected.
    rows = connection.execute(
        """
        SELECT p.READING_ID, p.BOUGUER_ANOMALY
        FROM GRAVITY_POINTS AS p
        INNER JOIN selected_train AS s ON s.reading_id = p.READING_ID
        WHERE p.BOUGUER_ANOMALY IS NOT NULL
        """
    )
    training = []
    for reading_id, value in rows:
        assigned = assignments[int(reading_id)]
        training.append(
            (
                assigned["block"],
                float(assigned["easting"]),
                float(assigned["northing"]),
                assigned["source"] or "",
                float(value),
            )
        )
    connection.close()
    block_values = defaultdict(list)
    block_geometry = {}
    block_sources = defaultdict(lambda: defaultdict(int))
    for block, easting, northing, source, value in training:
        block_values[block].append(value)
        block_geometry[block] = (easting, northing)
        block_sources[block][source] += 1
    blocks = sorted(block_values)
    x = np.asarray([block_geometry[block][0] / 1000.0 for block in blocks])
    y = np.asarray([block_geometry[block][1] / 1000.0 for block in blocks])
    response = np.asarray([np.median(block_values[block]) for block in blocks])
    x = x - np.mean(x)
    y = y - np.mean(y)
    dominant = [max(block_sources[block], key=block_sources[block].get) for block in blocks]
    sources = sorted(set(dominant))
    columns = [np.ones(len(blocks)), x, y, x * x, x * y, y * y]
    # Include only source effects observed as the dominant source of a block.
    columns.extend(
        np.asarray([value == source for value in dominant], dtype=float)
        for source in sources[1:]
    )
    matrix = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(matrix, response, rcond=None)
    residual = response - matrix @ coefficients
    sill = float(np.var(residual, ddof=1))
    distance = np.sqrt((x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2)
    semivariance = 0.5 * (residual[:, None] - residual[None, :]) ** 2
    upper = np.triu(np.ones(distance.shape, dtype=bool), 1)
    distance, semivariance = distance[upper], semivariance[upper]
    variogram, reached = [], []
    edges = np.arange(0.0, MAX_LAG_KM + LAG_KM, LAG_KM)
    for start, end in zip(edges[:-1], edges[1:]):
        mask = (distance >= start) & (distance < end)
        pairs = int(np.count_nonzero(mask))
        value = float(np.mean(semivariance[mask])) if pairs else None
        variogram.append(
            {
                "lag_center_km": float((start + end) / 2),
                "pairs": pairs,
                "semivariance_mgal2": value,
            }
        )
        reached.append(pairs >= 20 and value is not None and value >= 0.95 * sill)
    correlation_range = MAX_LAG_KM
    censored = True
    for index in range(len(reached) - 1):
        if reached[index] and reached[index + 1]:
            correlation_range = max(LAG_KM, variogram[index]["lag_center_km"])
            censored = False
            break
    test_cells = {
        (
            math.floor(float(record["easting"]) / 1000.0 / correlation_range),
            math.floor(float(record["northing"]) / 1000.0 / correlation_range),
        )
        for record in design["records"]
        if record["role"] == "test"
    }
    adjusted = len(test_cells) if not censored else 0
    result = {
        "schema_version": "wp8-mrt-tasmania-gravity-training-v1",
        "design_sha256": sha(DESIGN),
        "training_response_rows_interpreted": len(training),
        "response_rows_interpreted": {
            "train": len(training),
            "buffer": 0,
            "calibration": 0,
            "test": 0,
        },
        "training_blocks": len(blocks),
        "dominant_source_count": len(sources),
        "residual_sill_mgal2": sill,
        "correlation_range_km": correlation_range,
        "range_censored_at_100km": censored,
        "variogram": variogram,
        "design_test_cluster_upper_bound": design["design_test_cluster_upper_bound"],
        "correlation_adjusted_test_cluster_upper_bound": adjusted,
        "cluster_power_gate_passes": (
            not censored and correlation_range < 5.0 and adjusted >= 223
        ),
        "complete_bouguer_contract": True,
        "per_observation_uncertainty_contract": False,
        "uncertainty_reason": (
            "GeoPackage has no uncertainty column. Official metadata says attribute "
            "accuracy is generally 0.1 mGal or better, but does not publish a "
            "station-specific propagated complete-Bouguer uncertainty."
        ),
        "formal_confirmatory_contribution": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "training_rows": len(training),
            "training_blocks": len(blocks),
            "range_km": correlation_range,
            "adjusted_test_upper_bound": adjusted,
            "passes": result["cluster_power_gate_passes"],
        }
    )


if __name__ == "__main__":
    main()
