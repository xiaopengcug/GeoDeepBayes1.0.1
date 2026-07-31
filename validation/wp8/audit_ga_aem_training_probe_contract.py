#!/usr/bin/env python
"""Audit the frozen train-only GA TEMPEST package and training correlation."""
from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/geoscience-australia-aem-training-probe-v1"
ARCHIVE = DATA / "60847.zip"
MANIFEST = DATA / "raw-manifest.json"
INVENTORY = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/geoscience-australia-aem-training-probe-inventory.json"
)
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/geoscience-australia-aem-training-probe-contract.json"
)
DATA_MEMBERS = ("1RAWX", "1FINALX", "1RAWZ", "1FINALZ")
EXPECTED_COLUMNS = 42
RESPONSE_SLICE = slice(9, 24)
SAMPLE_SPACING_M = 12.0
EXACT_GATE_CENTERS_MS = [
    0.013,
    0.040,
    0.067,
    0.107,
    0.173,
    0.280,
    0.453,
    0.720,
    1.120,
    1.733,
    2.693,
    4.200,
    6.560,
    10.200,
    16.200,
]


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def printable_text(payload: bytes) -> str:
    return "\n".join(
        re.findall(r"[\x20-\x7e\r\n\t]{8,}", payload.decode("latin1", errors="ignore"))
    )


def correlation_range_km(sequences: dict[int, list[float]]) -> dict:
    threshold = math.exp(-1.0)
    lags = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
    estimates = []
    for lag in lags:
        count = 0
        sum_x = 0.0
        sum_y = 0.0
        sum_xx = 0.0
        sum_yy = 0.0
        sum_xy = 0.0
        for values in sequences.values():
            if len(values) <= lag:
                continue
            for x, y in zip(values[:-lag], values[lag:]):
                if not (math.isfinite(x) and math.isfinite(y)):
                    continue
                count += 1
                sum_x += x
                sum_y += y
                sum_xx += x * x
                sum_yy += y * y
                sum_xy += x * y
        numerator = count * sum_xy - sum_x * sum_y
        denominator = math.sqrt(
            max(0.0, count * sum_xx - sum_x * sum_x)
            * max(0.0, count * sum_yy - sum_y * sum_y)
        )
        if count < 100 or denominator == 0:
            continue
        correlation = numerator / denominator
        estimates.append(
            {
                "lag_samples": lag,
                "lag_km": lag * SAMPLE_SPACING_M / 1000.0,
                "correlation": correlation,
                "pairs": count,
            }
        )
    crossing = next(
        (item for item in estimates if item["correlation"] <= threshold), None
    )
    return {
        "definition": "first sampled raw-minus-final residual lag with Pearson correlation <= exp(-1)",
        "sample_spacing_m": SAMPLE_SPACING_M,
        "threshold": threshold,
        "estimates": estimates,
        "range_km": crossing["lag_km"] if crossing else None,
        "right_censored": crossing is None,
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    if (
        manifest["covered_design_roles"] != ["train"]
        or manifest["test_unseal_count"] != 0
        or inventory["member_payloads_read"] != 0
        or inventory["archive_sha256"] != sha256(ARCHIVE)
    ):
        raise RuntimeError("GA AEM training evidence drift")
    stats = {}
    residuals: dict[str, dict[int, list[float]]] = {
        "x_window_15": defaultdict(list),
        "z_window_15": defaultdict(list),
    }
    with zipfile.ZipFile(ARCHIVE) as archive:
        report_text = printable_text(archive.read("Gilmore_report.doc"))
        contract_tokens = {
            "base_frequency_25_hz": "Base frequency" in report_text
            and "25Hz" in report_text,
            "square_waveform": "Waveform" in report_text
            and "Square" in report_text,
            "transmitter_area_186_m2": "Transmitter area" in report_text
            and "186m2" in report_text,
            "peak_current_300_a": "Peak current" in report_text
            and "300 A" in report_text,
            "fifteen_windows": "Number of output windows" in report_text
            and "15" in report_text,
            "window_extent_13_us_to_16_2_ms": "Window centre times" in report_text
            and "16.2 ms" in report_text,
            "receiver_dbdt_three_components": (
                "3 component dB/dt coils" in report_text
            ),
            "nominal_tx_rx_horizontal_100_m": (
                "Tx-Rx horizontal separation" in report_text
                and "100m" in report_text
            ),
            "nominal_tx_rx_vertical_55_m": (
                "Tx-Rx vertical separation" in report_text
                and "55m" in report_text
            ),
            "located_data_geometry_columns": all(
                token in report_text
                for token in (
                    "Tx loop altitude",
                    "Tx loop terrain clearance",
                    "Tx loop pitch",
                    "Tx loop roll",
                )
            ),
            "raw_modelling_transform_documented": (
                "System Specifications for Modelling TEMPEST Data" in report_text
                and "B-field sensor" in report_text
                and "100 % duty cycle square waveform" in report_text
            ),
            "repeat_line_documented": "Repeat survey Line (C18001)" in report_text,
        }
        exact_gate_table_tokens = [
            f"{value:.3f}" for value in EXACT_GATE_CENTERS_MS
        ]
        exact_gate_table_present = all(
            token in report_text for token in exact_gate_table_tokens
        )
        opened = {name: archive.open(name) for name in DATA_MEMBERS}
        try:
            row_count = 0
            line_ids = set()
            flights = set()
            bounds = [math.inf, math.inf, -math.inf, -math.inf]
            malformed = 0
            missing_response_rows = 0
            while True:
                rows = [opened[name].readline() for name in DATA_MEMBERS]
                if not any(rows):
                    break
                if not all(rows):
                    raise RuntimeError("GA AEM component files have unequal row counts")
                parsed = [row.split() for row in rows]
                if any(len(row) != EXPECTED_COLUMNS for row in parsed):
                    malformed += 1
                    continue
                keys = [tuple(row[:9]) + (row[41],) for row in parsed]
                if len(set(keys)) != 1:
                    raise RuntimeError("GA AEM raw/final component geometry is misaligned")
                values = [[float(value) for value in row] for row in parsed]
                line_id = int(values[0][0])
                line_ids.add(line_id)
                flights.add(int(values[0][41]))
                easting, northing = values[0][2:4]
                bounds[0] = min(bounds[0], easting)
                bounds[1] = min(bounds[1], northing)
                bounds[2] = max(bounds[2], easting)
                bounds[3] = max(bounds[3], northing)
                if any(
                    value <= -99999
                    for row in values
                    for value in row[RESPONSE_SLICE]
                ):
                    missing_response_rows += 1
                residuals["x_window_15"][line_id].append(
                    values[0][23] - values[1][23]
                )
                residuals["z_window_15"][line_id].append(
                    values[2][23] - values[3][23]
                )
                row_count += 1
        finally:
            for stream in opened.values():
                stream.close()
    for component, sequences in residuals.items():
        stats[component] = correlation_range_km(sequences)
    maximum_range = max(
        item["range_km"]
        for item in stats.values()
        if item["range_km"] is not None
    )
    result = {
        "schema_version": "wp8-geoscience-australia-aem-training-probe-contract-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "inventory_sha256": sha256(INVENTORY),
        "archive_sha256": sha256(ARCHIVE),
        "training_only": True,
        "report_contract_tokens": contract_tokens,
        "report_contract_token_gate_passed": all(contract_tokens.values()),
        "located_data": {
            "members": list(DATA_MEMBERS),
            "columns_per_row": EXPECTED_COLUMNS,
            "response_window_columns": list(range(10, 25)),
            "row_count": row_count,
            "unique_line_count": len(line_ids),
            "unique_flight_count": len(flights),
            "malformed_row_count": malformed,
            "missing_response_row_count": missing_response_rows,
            "agd84_zone_55_bounds_m": {
                "min_easting": bounds[0],
                "min_northing": bounds[1],
                "max_easting": bounds[2],
                "max_northing": bounds[3],
            },
            "raw_final_geometry_alignment_passed": True,
        },
        "training_residual_correlation": stats,
        "maximum_training_range_km": maximum_range,
        "national_55_km_centers_exceed_probe_range": maximum_range < 55.0,
        "uncertainty_contract": {
            "sferics_and_noise_diagnostics_present": True,
            "repeat_line_documented": True,
            "per_observation_standard_deviation_present": False,
            "training_only_uncertainty_model_ready": False,
        },
        "exact_gate_center_times_ms": EXACT_GATE_CENTERS_MS,
        "exact_gate_center_times_present": exact_gate_table_present,
        "national_heterogeneity_qualified": False,
        "formal_contract_ready": False,
        "formal_blockers": [
            "no per-observation EM standard deviation is delivered",
            "one 1999 TEMPEST training survey cannot qualify national multi-system correlation or uncertainty",
        ],
        "aem_response_values_interpreted": row_count * 4 * 15,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": row_count,
                "lines": len(line_ids),
                "flights": len(flights),
                "maximum_training_range_km": maximum_range,
                "formal_contract_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
