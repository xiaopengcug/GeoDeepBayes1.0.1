#!/usr/bin/env python
"""Build a provenance-backed remanence prior from training rock samples only."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-rock-properties-v1/rock_property_data.csv"
DICTIONARY = ROOT / "validation/wp8/data/usgs-rock-properties-v1/data_dictionary.csv"
SPLIT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-rock-properties-design-split.json"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-rock-properties-remanence-prior.json"
)
CELL_KM = 100.0
REFERENCE_LATITUDE_DEG = 45.0


def role(longitude: float) -> str:
    x_km = longitude * 111.32 * math.cos(math.radians(REFERENCE_LATITUDE_DEG))
    stripe = math.floor(x_km / CELL_KM) % 12
    if stripe in {1, 2, 3, 4, 5}:
        return "train"
    if stripe in {7, 8}:
        return "calibration"
    if stripe in {10, 11}:
        return "test"
    return "buffer"


def number(text: str | None) -> float | None:
    try:
        value = float(text) if text not in (None, "") else None
    except ValueError:
        return None
    return value if value is not None and math.isfinite(value) else None


def robust_log_summary(values: list[float]) -> dict[str, float | int]:
    logged = np.log(np.asarray(values))
    median = float(np.median(logged))
    mad = float(np.median(np.abs(logged - median)))
    return {
        "n": len(values),
        "log_median": median,
        "log_mad": mad,
        "log_scale_1p4826_mad": 1.4826 * mad,
        "physical_median": float(math.exp(median)),
    }


def main() -> None:
    frozen = json.loads(SPLIT.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    intensity: list[float] = []
    q_values: list[float] = []
    vectors: list[list[float]] = []
    by_rock: dict[str, list[float]] = defaultdict(list)
    training_rows = 0
    ignored = 0
    with RAW.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            longitude = number(row["LONG_nad27"])
            if longitude is None or role(longitude) != "train":
                ignored += 1
                continue
            training_rows += 1
            rm = number(row["RM_a_m"])
            q = number(row["Q"])
            dec = number(row["DEC_deg"])
            inc = number(row["INC_deg"])
            if rm is not None and rm > 0:
                intensity.append(rm)
                by_rock[row["ROCK_TYPE"]].append(rm)
                counts["positive_remanence_intensity"] += 1
            if q is not None and q > 0:
                q_values.append(q)
                counts["positive_koenigsberger_ratio"] += 1
            if dec is not None and inc is not None and 0 <= dec <= 360 and -90 <= inc <= 90:
                dec_rad = math.radians(dec)
                inc_rad = math.radians(inc)
                vectors.append(
                    [
                        math.cos(inc_rad) * math.cos(dec_rad),
                        math.cos(inc_rad) * math.sin(dec_rad),
                        math.sin(inc_rad),
                    ]
                )
                counts["complete_direction"] += 1
            if rm is not None and rm > 0 and dec is not None and inc is not None:
                counts["complete_vector_magnetization"] += 1

    vector_array = np.asarray(vectors)
    mean_vector = vector_array.mean(axis=0) if len(vector_array) else np.zeros(3)
    resultant = float(np.linalg.norm(mean_vector))
    mean_unit = mean_vector / resultant if resultant else mean_vector
    result = {
        "schema_version": "wp8-usgs-rock-properties-remanence-prior-v1",
        "provenance": {
            "publisher": "U.S. Geological Survey",
            "doi": "10.5066/P9FONTGS",
            "data_dictionary_path": str(DICTIONARY.relative_to(ROOT)).replace("\\", "/"),
            "spatial_split_design_sha256": frozen["design_sha256"],
        },
        "response_policy": {
            "training_rows_interpreted": training_rows,
            "heldout_rows_skipped_before_property_conversion": ignored,
            "buffer_rows_interpreted": 0,
            "calibration_rows_interpreted": 0,
            "test_rows_interpreted": 0,
        },
        "measurement_contract": {
            "remanent_intensity": {"field": "RM_a_m", "unit": "A/m"},
            "koenigsberger_ratio": {"field": "Q", "accuracy": 0.01},
            "direction": {
                "fields": ["DEC_deg", "INC_deg"],
                "unit": "degrees",
                "accuracy_degrees": 0.5,
            },
            "susceptibility": {"field": "SUSC_10-3_si", "unit": "1e-3 SI"},
        },
        "availability_counts": dict(counts),
        "empirical_prior": {
            "remanence_intensity_a_m": robust_log_summary(intensity),
            "koenigsberger_ratio": robust_log_summary(q_values),
            "direction": {
                "n": len(vectors),
                "mean_unit_vector_north_east_down": mean_unit.tolist(),
                "mean_resultant_length": resultant,
                "recommended_family": "empirical or multimodal spherical prior; do not collapse to a single direction",
            },
            "rock_type_log_intensity_summaries": {
                rock: robust_log_summary(values)
                for rock, values in sorted(by_rock.items())
                if len(values) >= 10
            },
        },
        "prior_gate_passed": len(intensity) >= 100 and len(vectors) >= 100,
        "scope_limit": (
            "Western U.S. and Alaska samples are provenance for a broad remanence prior, "
            "not site-specific ground truth for any airborne survey."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_rows": training_rows,
                "remanence_intensity": len(intensity),
                "complete_direction": len(vectors),
                "prior_gate_passed": result["prior_gate_passed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
