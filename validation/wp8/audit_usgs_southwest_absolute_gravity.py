#!/usr/bin/env python
"""Audit suitability of the USGS Southwest absolute-gravity observations."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/usgs-southwest-absolute-gravity-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-southwest-absolute-gravity.json"


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def finite(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def main() -> None:
    stations = rows("sgp_agdb_stations_2025-12-19.csv")
    measurements = rows("sgp_agdb_measurements_2025-12-19.csv")
    station_counts = Counter(row["Station"] for row in measurements)
    uncertainty = "Uncertainty (microGal)"
    coordinates = ("Latitude (NAD83)", "Longitude (NAD83)", "Elevation (m NAVD88)")
    dates = [date.fromisoformat(row["Date"]) for row in measurements]
    gravity_fields = sorted(
        {
            key
            for row in measurements
            for key in row
            if any(term in key.lower() for term in ("gravity", "bouguer", "terrain", "anomaly"))
        }
    )
    result = {
        "dataset": "USGS Southwest Gravity Program Absolute-Gravity Database",
        "license": "CC0-1.0",
        "station_rows": len(stations),
        "measurement_rows": len(measurements),
        "unique_measured_stations": len(station_counts),
        "stations_with_repeated_measurements": sum(v > 1 for v in station_counts.values()),
        "maximum_measurements_at_one_station": max(station_counts.values()),
        "date_range": [min(dates).isoformat(), max(dates).isoformat()],
        "measurement_coordinate_rows_complete": sum(
            all(finite(row[field]) for field in coordinates) for row in measurements
        ),
        "uncertainty_rows_finite_positive": sum(
            finite(row[uncertainty]) and float(row[uncertainty]) > 0 for row in measurements
        ),
        "measurement_gravity_related_fields": gravity_fields,
        "has_complete_bouguer_anomaly": any(
            "bouguer" in field.lower() for field in gravity_fields
        ),
        "has_terrain_correction": any("terrain" in field.lower() for field in gravity_fields),
        "contract_assessment": {
            "absolute_gravity": "pass",
            "per_measurement_uncertainty": "pass",
            "complete_bouguer_anomaly": "fail",
            "terrain_correction": "fail",
            "formal_wp8_gravity_contribution": 0,
            "reason": (
                "The release is a reusable absolute-gravity reference network with "
                "per-measurement uncertainty, but it does not publish complete Bouguer "
                "anomaly or terrain-correction fields required by the registered contract."
            ),
        },
        "independence_note": (
            "Repeated dates at the same station are temporally correlated and are not "
            "counted as independent spatial clusters."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
