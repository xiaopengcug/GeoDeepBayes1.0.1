#!/usr/bin/env python
"""Parse only frozen GA AEM training responses after coordinate role assignment."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/geoscience-australia-aem-multisystem-v1"
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
MANIFEST = RAW / "raw-manifest.json"
SPLIT = EVIDENCE / "geoscience-australia-aem-multisystem-spatial-split.json"
CONTRACT = EVIDENCE / "geoscience-australia-aem-multisystem-contract.json"
OUTPUT = EVIDENCE / "geoscience-australia-aem-multisystem-train-diagnostics.json"
MAX_ASSIGNMENT_KM = 45.0
SAMPLE_EVERY_TRAIN_ROWS = 20


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2)
    dy = (lat1 - lat2) * 111.2
    dx = (lon1 - lon2) * 111.2 * math.cos(mean_lat)
    return math.hypot(dx, dy)


def parse_definitions(text: str) -> dict[str, dict]:
    fields: dict[str, dict] = {}
    offset = 0
    pattern = re.compile(
        r"(?:^|;)\s*([A-Za-z][A-Za-z0-9_]*)\s*:"
        r"\s*(?:(\d+))?([AF])(\d+)",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if "ST=RECD,RT=COMM" in line.upper():
            continue
        for match in pattern.finditer(line):
            label = match.group(1).strip()
            count = int(match.group(2) or 1)
            width = int(match.group(4))
            fields[label.lower()] = {
                "label": label,
                "offset": offset,
                "count": count,
                "width": width,
                "end": offset + count * width,
            }
            offset += count * width
    fields["_record"] = {"width": offset}
    return fields


def scalar(line: str, field: dict) -> str:
    return line[field["offset"] : field["offset"] + field["width"]].strip()


def vector(line: str, field: dict) -> list[float]:
    values = []
    for index in range(field["count"]):
        start = field["offset"] + index * field["width"]
        token = line[start : start + field["width"]].strip()
        if not token:
            continue
        try:
            value = float(token)
        except ValueError:
            continue
        if value <= -9_000_000 or math.isclose(value, -9.99999999):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def choose(fields: dict, *names: str) -> dict:
    for name in names:
        if name.lower() in fields:
            return fields[name.lower()]
    raise KeyError(names)


def representative(line: str, fields: dict, system: str) -> tuple[float | None, float | None, int]:
    if system == "VTEM":
        response = vector(line, choose(fields, "SFz"))
        uncertainty: list[float] = []
    else:
        response = vector(line, choose(fields, "HM_Z_"))
        uncertainty = vector(line, choose(fields, "RUNC_HM_Z_"))
    if not response:
        return None, None, 0
    late = response[max(0, len(response) * 2 // 3) :]
    nonzero = [abs(value) for value in late if value != 0]
    if not nonzero:
        return None, None, len(response) + len(uncertainty)
    response_summary = math.log10(statistics.median(nonzero))
    valid_uncertainty = [value for value in uncertainty if 0 <= value < 100]
    uncertainty_summary = (
        statistics.median(valid_uncertainty) if valid_uncertainty else None
    )
    return response_summary, uncertainty_summary, len(response) + len(uncertainty)


def correlation_diagnostic(samples: list[dict]) -> dict:
    by_line: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        by_line[sample["line"]].append(sample)
    pairs: dict[int, list[tuple[float, float]]] = defaultdict(list)
    residual_count = 0
    for line_samples in by_line.values():
        if len(line_samples) < 8:
            continue
        values = np.asarray([item["response"] for item in line_samples], dtype=float)
        x = np.arange(values.size, dtype=float)
        residual = values - np.polyval(np.polyfit(x, values, 1), x)
        residual_count += residual.size
        for index in range(len(line_samples)):
            for lag in range(1, min(26, len(line_samples) - index)):
                other = index + lag
                distance = distance_km(
                    line_samples[index]["latitude"],
                    line_samples[index]["longitude"],
                    line_samples[other]["latitude"],
                    line_samples[other]["longitude"],
                )
                if distance > 30:
                    break
                distance_bin = max(1, math.ceil(distance))
                pairs[distance_bin].append((residual[index], residual[other]))
    bins = []
    for distance_bin, values in sorted(pairs.items()):
        if len(values) < 30:
            continue
        left = np.asarray([pair[0] for pair in values])
        right = np.asarray([pair[1] for pair in values])
        if np.std(left) == 0 or np.std(right) == 0:
            correlation = 0.0
        else:
            correlation = float(np.corrcoef(left, right)[0, 1])
        bins.append(
            {
                "distance_bin_upper_km": distance_bin,
                "pair_count": len(values),
                "pearson_correlation": round(correlation, 6),
            }
        )
    correlation_range = None
    for index in range(len(bins) - 1):
        if (
            abs(bins[index]["pearson_correlation"]) <= 0.05
            and abs(bins[index + 1]["pearson_correlation"]) <= 0.05
        ):
            correlation_range = bins[index]["distance_bin_upper_km"]
            break
    if correlation_range is None and bins:
        correlation_range = bins[-1]["distance_bin_upper_km"]
    return {
        "sample_residual_count": residual_count,
        "distance_bins": bins,
        "descriptive_correlation_range_km": correlation_range,
        "range_rule": "first of two consecutive 1-km bins with |Pearson r| <= 0.05; otherwise maximum supported bin",
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        manifest["selection_was_response_blind"] is not True
        or split["split_is_response_blind"] is not True
        or contract["audit_is_response_blind"] is not True
        or split["test_unseal_count"] != 0
    ):
        raise RuntimeError("GA AEM training prerequisites drift")

    results = []
    sealed_response_rows = Counter({"buffer": 0, "calibration": 0, "test": 0})
    total_response_values = 0
    for member in manifest["members"]:
        dataset_number = member["dataset_number"]
        centers = [
            cell for cell in split["cells"]
            if dataset_number in cell["covering_dataset_numbers"]
        ]
        archive_path = RAW / member["path"]
        role_rows: Counter = Counter()
        samples: list[dict] = []
        train_rows = 0
        response_rows = 0
        uncertainty_rows = 0
        with zipfile.ZipFile(archive_path) as archive:
            dfn_name = next(
                name for name in archive.namelist() if name.lower().endswith(".dfn")
            )
            dat_name = next(
                name for name in archive.namelist() if name.lower().endswith(".dat")
            )
            fields = parse_definitions(
                archive.read(dfn_name).decode("latin1", errors="replace")
            )
            longitude_field = choose(fields, "Longitude", "LONGITUD")
            latitude_field = choose(fields, "Latitude")
            line_field = choose(fields, "Line", "FLTLINE")
            with archive.open(dat_name) as source:
                for raw_line in source:
                    line = raw_line.decode("ascii", errors="replace").rstrip("\r\n")
                    if len(line) != fields["_record"]["width"] or line.startswith("COMM"):
                        continue
                    try:
                        longitude = float(scalar(line, longitude_field))
                        latitude = float(scalar(line, latitude_field))
                    except ValueError:
                        role_rows["invalid_coordinate"] += 1
                        continue
                    nearest = min(
                        centers,
                        key=lambda cell: distance_km(
                            latitude, longitude, cell["latitude"], cell["longitude"]
                        ),
                    )
                    nearest_distance = distance_km(
                        latitude, longitude, nearest["latitude"], nearest["longitude"]
                    )
                    role = (
                        nearest["role"]
                        if nearest_distance <= MAX_ASSIGNMENT_KM
                        else "outside_design_support"
                    )
                    role_rows[role] += 1
                    if role != "train":
                        # No response or uncertainty slice is converted here.
                        continue
                    train_rows += 1
                    response, uncertainty, interpreted = representative(
                        line, fields, member["system"]
                    )
                    total_response_values += interpreted
                    if response is None:
                        continue
                    response_rows += 1
                    if uncertainty is not None:
                        uncertainty_rows += 1
                    if train_rows % SAMPLE_EVERY_TRAIN_ROWS == 0:
                        samples.append(
                            {
                                "line": scalar(line, line_field),
                                "latitude": latitude,
                                "longitude": longitude,
                                "response": response,
                                "relative_uncertainty": uncertainty,
                            }
                        )
        diagnostic = correlation_diagnostic(samples)
        uncertainty_values = [
            sample["relative_uncertainty"]
            for sample in samples
            if sample["relative_uncertainty"] is not None
        ]
        results.append(
            {
                "system": member["system"],
                "dataset_number": dataset_number,
                "record_id": member["record_id"],
                "archive_sha256": sha256(archive_path),
                "data_member": dat_name,
                "role_row_counts": dict(sorted(role_rows.items())),
                "training_response_rows_interpreted": response_rows,
                "training_uncertainty_rows_interpreted": uncertainty_rows,
                "diagnostic_sample_stride": SAMPLE_EVERY_TRAIN_ROWS,
                "diagnostic_sample_count": len(samples),
                "sample_median_relative_uncertainty": (
                    round(statistics.median(uncertainty_values), 8)
                    if uncertainty_values else None
                ),
                "correlation": diagnostic,
            }
        )

    result = {
        "schema_version": "wp8-geoscience-australia-aem-multisystem-train-diagnostics-v1",
        "manifest_sha256": sha256(MANIFEST),
        "split_sha256": sha256(SPLIT),
        "contract_sha256": sha256(CONTRACT),
        "coordinate_first_role_assignment": True,
        "maximum_assignment_distance_km": MAX_ASSIGNMENT_KM,
        "products": results,
        "training_response_values_interpreted": total_response_values,
        "sealed_response_rows_interpreted": dict(sealed_response_rows),
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "formal_national_correlation_gate_passes": False,
        "warning": (
            "These are product-level descriptive training diagnostics. They do "
            "not establish a national unsampled-survey tolerance bound or a "
            "paired-CRPS effect size."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "products": len(results),
        "role_rows": {
            str(item["dataset_number"]): item["role_row_counts"] for item in results
        },
        "training_response_values": total_response_values,
        "sealed_response_rows": result["sealed_response_rows_interpreted"],
    }))


if __name__ == "__main__":
    main()
