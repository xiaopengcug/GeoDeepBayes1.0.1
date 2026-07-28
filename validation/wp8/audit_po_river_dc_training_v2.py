#!/usr/bin/env python
# /// script
# dependencies = ["numpy==2.4.1", "scipy==1.16.3"]
# ///
"""Parse only Po River DC training responses; keep remaining test rows sealed."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "po-river-dc-streamer-design-v2.json"
DATA = (
    ROOT
    / "validation/wp8/data/po-river-dc-streamer-v1/extracted"
    / "Electrical_Tomography_Data"
)
RESPONSES = DATA / "Resistivity_data.csv"
POSITIONS = DATA / "Electrodes_Positions.csv"
OUT = EVIDENCE / "po-river-dc-streamer-training-audit-v2.json"
ROWS_PER_STATION = 318
POSITIONS_PER_STATION = 13


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    roles = {int(key): value for key, value in design["station_roles"].items()}
    training = {station for station, role in roles.items() if role == "train"}
    if (
        not design["remaining_test_population_sealed"]
        or design["design_test_cluster_upper_bound"] < 223
    ):
        raise RuntimeError("Po River DC v2 design is not usable")

    response_by_station: dict[int, list[float]] = defaultdict(list)
    uncertainty_by_station: dict[int, list[float]] = defaultdict(list)
    type_counts: dict[str, int] = defaultdict(int)
    parsed_rows = 0
    skipped_response_rows = 0
    with RESPONSES.open("rb") as stream:
        header = stream.readline().decode("utf-8-sig").strip()
        for row_index, raw in enumerate(stream, 1):
            station = (row_index - 1) // ROWS_PER_STATION + 1
            if roles[station] != "train":
                skipped_response_rows += 1
                continue
            row = next(csv.reader([raw.decode("utf-8")]))
            if len(row) != 11 or int(row[0]) != row_index:
                raise RuntimeError(f"response row drift at {row_index}")
            rho = float(row[5])
            standard_deviation_percent = float(row[6])
            if not (
                math.isfinite(rho)
                and math.isfinite(standard_deviation_percent)
                and standard_deviation_percent >= 0
            ):
                raise RuntimeError(f"invalid training response at {row_index}")
            response_by_station[station].append(
                math.copysign(math.log1p(abs(rho)), rho)
            )
            uncertainty_by_station[station].append(
                standard_deviation_percent
            )
            type_counts[row[10].strip()] += 1
            parsed_rows += 1

    coordinates: dict[int, list[tuple[float, float]]] = defaultdict(list)
    with POSITIONS.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        position_header = next(reader)
        for row_index, row in enumerate(reader, 1):
            station = int(row[0])
            if station not in roles:
                raise RuntimeError(f"position station drift: {station}")
            coordinates[station].append((float(row[3]), float(row[4])))
    if any(len(value) != POSITIONS_PER_STATION for value in coordinates.values()):
        raise RuntimeError("electrode-position count drift")

    training_stations = sorted(training)
    station_response = np.asarray(
        [np.mean(response_by_station[station]) for station in training_stations]
    )
    station_xy = np.asarray(
        [
            np.mean(np.asarray(coordinates[station]), axis=0)
            for station in training_stations
        ]
    )
    # Remove the large-scale linear spatial trend before estimating local
    # dependence. This is training-only and fixed before any remaining test
    # response is interpreted.
    design_matrix = np.column_stack(
        [np.ones(len(station_xy)), station_xy[:, 0], station_xy[:, 1]]
    )
    residual = station_response - design_matrix @ np.linalg.lstsq(
        design_matrix, station_response, rcond=None
    )[0]
    pair_distance = []
    pair_product = []
    variance = float(np.var(residual))
    for left in range(len(training_stations)):
        for right in range(left + 1, len(training_stations)):
            distance = float(np.linalg.norm(station_xy[left] - station_xy[right]))
            pair_distance.append(distance)
            pair_product.append(float(residual[left] * residual[right] / variance))
    pair_distance_array = np.asarray(pair_distance)
    pair_product_array = np.asarray(pair_product)
    bins = []
    for lower in np.arange(0.0, 401.0, 16.0):
        upper = lower + 16.0
        selected = (pair_distance_array >= lower) & (
            pair_distance_array < upper
        )
        if int(selected.sum()) < 10:
            continue
        bins.append(
            {
                "lower_m": float(lower),
                "upper_m": float(upper),
                "pair_count": int(selected.sum()),
                "correlation": float(np.mean(pair_product_array[selected])),
            }
        )
    range_candidates = [
        item["upper_m"]
        for item in bins
        if item["correlation"] <= 0.05
    ]
    correlation_range_m = (
        float(range_candidates[0]) if range_candidates else 416.0
    )

    test_stations = [
        station for station, role in roles.items() if role == "test"
    ]
    test_xy = {
        station: np.mean(np.asarray(coordinates[station]), axis=0)
        for station in test_stations
    }
    accepted = []
    for station in sorted(test_stations):
        point = test_xy[station]
        if all(
            float(np.linalg.norm(point - test_xy[other]))
            >= correlation_range_m
            for other in accepted
        ):
            accepted.append(station)

    all_uncertainty = np.concatenate(
        [
            np.asarray(uncertainty_by_station[station])
            for station in training_stations
        ]
    )
    output = {
        "schema_version": "wp8-po-river-dc-streamer-training-audit-v2",
        "design_sha256": sha(DESIGN),
        "response_sha256": sha(RESPONSES),
        "positions_sha256": sha(POSITIONS),
        "response_header": header,
        "position_header": position_header,
        "training_station_count": len(training_stations),
        "training_response_rows_interpreted": parsed_rows,
        "nontraining_response_rows_byte_skipped": skipped_response_rows,
        "calibration_response_rows_interpreted": 0,
        "remaining_test_response_rows_interpreted": 0,
        "quarantined_response_rows_interpreted_during_audit": 0,
        "quadrupole_type_counts": dict(sorted(type_counts.items())),
        "per_observation_standard_deviation_present": True,
        "standard_deviation_percent": {
            "minimum": float(np.min(all_uncertainty)),
            "median": float(np.median(all_uncertainty)),
            "p95": float(np.quantile(all_uncertainty, 0.95)),
            "maximum": float(np.max(all_uncertainty)),
        },
        "training_station_log_resistivity_range": {
            "minimum": float(np.min(station_response)),
            "maximum": float(np.max(station_response)),
        },
        "training_detrended_correlation_bins": bins,
        "training_correlation_range_m": correlation_range_m,
        "remaining_test_station_count": len(test_stations),
        "correlation_separated_test_station_count": len(accepted),
        "correlation_separated_test_stations": accepted,
        "required_test_clusters": 223,
        "cluster_gate_passed": len(accepted) >= 223,
        "paired_crps_effect_size_available": False,
        "power_gate_passed": False,
        "remaining_test_population_sealed": True,
        "historical_exposure_incident_count": 1,
        "test_unseal_count_during_audit": 0,
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_stations": len(training_stations),
                "training_rows": parsed_rows,
                "correlation_range_m": correlation_range_m,
                "separated_test_stations": len(accepted),
                "cluster_gate_passed": output["cluster_gate_passed"],
                "remaining_test_rows_interpreted": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
