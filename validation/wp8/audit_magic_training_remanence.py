#!/usr/bin/env python
"""Audit untreated MagIC remanence using frozen training contributions only."""
from __future__ import annotations

import csv
import io
import json
import math
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/magic-contributions-v1"
ARCHIVE = DATA / "magic-latest-100.zip"
RAW_MANIFEST = DATA / "raw-manifest.json"
SPLIT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/magic-contribution-design-split.json"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/magic-training-remanence-prior.json"
)
MAGNITUDE_FIELDS = {
    "magn_volume": "A/m",
    "magn_mass": "A m^2/kg",
    "magn_moment": "A m^2",
}


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def summarize_positive(values: list[float], unit: str) -> dict[str, object]:
    logs = [math.log10(value) for value in values]
    return {
        "unit": unit,
        "count": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
        "log10_q05": quantile(logs, 0.05),
        "log10_q25": quantile(logs, 0.25),
        "log10_q50": quantile(logs, 0.50),
        "log10_q75": quantile(logs, 0.75),
        "log10_q95": quantile(logs, 0.95),
    }


def circular_summary(values: list[float]) -> dict[str, float | int]:
    radians = [math.radians(value) for value in values]
    mean_sin = statistics.fmean(math.sin(value) for value in radians)
    mean_cos = statistics.fmean(math.cos(value) for value in radians)
    resultant = math.hypot(mean_sin, mean_cos)
    return {
        "count": len(values),
        "circular_mean_degrees": math.degrees(math.atan2(mean_sin, mean_cos)) % 360,
        "mean_resultant_length": resultant,
    }


def parse_training_member(
    archive: zipfile.ZipFile,
    member: str,
    magnitudes: dict[str, list[float]],
    declinations: list[float],
    inclinations: list[float],
) -> dict[str, object]:
    contribution_id = int(member.split("/", 1)[0])
    counts = Counter()
    specimens: set[str] = set()
    methods = Counter()
    with archive.open(member) as raw:
        stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
        in_measurements = False
        header: list[str] | None = None
        for line in stream:
            text = line.rstrip("\r\n")
            if text.startswith("tab delimited\t"):
                in_measurements = text == "tab delimited\tmeasurements"
                header = None
                continue
            if text == ">>>>>>>>>>":
                in_measurements = False
                header = None
                continue
            if not in_measurements:
                continue
            if header is None:
                header = next(csv.reader([text], delimiter="\t"))
                continue
            values = next(csv.reader([text], delimiter="\t"))
            row = dict(zip(header, values))
            counts["measurement_rows"] += 1
            method_tokens = {
                token.strip()
                for token in row.get("method_codes", "").replace(":", " ").split()
                if token.strip()
            }
            methods.update(method_tokens)
            if "LT-NO" not in method_tokens:
                continue
            counts["untreated_rows"] += 1
            if row.get("specimen"):
                specimens.add(row["specimen"])
            row_has_magnitude = False
            for field in MAGNITUDE_FIELDS:
                try:
                    value = float(row.get(field, ""))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value) and value > 0:
                    magnitudes[field].append(value)
                    counts[f"positive_{field}"] += 1
                    row_has_magnitude = True
            try:
                dec = float(row.get("dir_dec", ""))
                inc = float(row.get("dir_inc", ""))
            except (TypeError, ValueError):
                continue
            if (
                row_has_magnitude
                and math.isfinite(dec)
                and math.isfinite(inc)
                and -90 <= inc <= 90
            ):
                declinations.append(dec % 360)
                inclinations.append(inc)
                counts["complete_vector_rows"] += 1
    return {
        "contribution_id": contribution_id,
        "measurement_rows": counts["measurement_rows"],
        "untreated_rows": counts["untreated_rows"],
        "untreated_unique_specimens": len(specimens),
        "complete_vector_rows": counts["complete_vector_rows"],
        "positive_magnitude_rows": {
            field: counts[f"positive_{field}"] for field in MAGNITUDE_FIELDS
        },
        "observed_method_codes": sorted(methods),
    }


def main() -> None:
    raw_manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    training = [
        row["member"] for row in split["contributions"] if row["split"] == "train"
    ]
    magnitudes: dict[str, list[float]] = defaultdict(list)
    declinations: list[float] = []
    inclinations: list[float] = []
    contributions = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for member in training:
            contributions.append(
                parse_training_member(
                    archive, member, magnitudes, declinations, inclinations
                )
            )
    complete_contributions = sum(
        row["complete_vector_rows"] > 0 for row in contributions
    )
    untreated_contributions = sum(row["untreated_rows"] > 0 for row in contributions)
    prior_gate = len(declinations) >= 100 and complete_contributions >= 10
    evidence = {
        "schema_version": "wp8-magic-training-remanence-prior-v1",
        "raw_archive_sha256": raw_manifest["archive"]["sha256"],
        "design_split_sha256": __import__("hashlib").sha256(
            SPLIT.read_bytes()
        ).hexdigest(),
        "training_contributions_interpreted": len(training),
        "buffer_contributions_interpreted": 0,
        "calibration_contributions_interpreted": 0,
        "test_contributions_interpreted": 0,
        "excluded_contribution_ids": split["excluded_contribution_ids"],
        "selection_rule": (
            "measurement method_codes contains exact token LT-NO; positive magnitude; "
            "finite direction where vector completeness is claimed"
        ),
        "magnitude_distributions": {
            field: summarize_positive(values, MAGNITUDE_FIELDS[field])
            for field, values in magnitudes.items()
            if values
        },
        "direction_distribution": {
            "declination": circular_summary(declinations) if declinations else None,
            "inclination": {
                "count": len(inclinations),
                "mean_degrees": statistics.fmean(inclinations),
                "median_degrees": statistics.median(inclinations),
                "q05_degrees": quantile(inclinations, 0.05),
                "q95_degrees": quantile(inclinations, 0.95),
            }
            if inclinations
            else None,
        },
        "untreated_contributions": untreated_contributions,
        "complete_vector_contributions": complete_contributions,
        "complete_vector_rows": len(declinations),
        "prior_gate_definition": (
            "at least 100 complete untreated vectors from at least 10 contributions"
        ),
        "prior_gate_passed": prior_gate,
        "contributions": contributions,
        "tables_read": ["measurements"],
        "held_out_response_values_read": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_contributions": len(training),
                "untreated_contributions": untreated_contributions,
                "complete_vector_contributions": complete_contributions,
                "complete_vector_rows": len(declinations),
                "magnitude_counts": {
                    field: len(values) for field, values in magnitudes.items()
                },
                "prior_gate_passed": prior_gate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
