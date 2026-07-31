"""Freeze a response-blind spatial design for the NTGS Pine Creek TDIP data."""

from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation" / "wp8" / "data" / "ntgs-pine-creek-source-zips"
EVIDENCE = (
    ROOT
    / "validation"
    / "wp8"
    / "evidence"
    / "feasibility-v1"
    / "ntgs-pine-creek-tdip-coordinate-design-v1.json"
)
TRAINING_ARCHIVE = DATA / "CR2011-0200_Geophysics.zip"
SEALED_ARCHIVE = DATA / "CR2016-0418_Geophysics.zip"
SALT = "wp8-ntgs-pine-creek-tdip-coordinate-design-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def training_centres_and_chargeability() -> np.ndarray:
    values: dict[tuple[float, float], list[float]] = defaultdict(list)
    excluded_suffixes = re.compile(r"_(25m|50m|edit)\.gdd$", re.IGNORECASE)
    with zipfile.ZipFile(TRAINING_ARCHIVE) as archive:
        for info in archive.infolist():
            if not info.filename.lower().endswith(".gdd"):
                continue
            if excluded_suffixes.search(info.filename):
                continue
            text = archive.read(info).decode("latin1", "replace")
            for line in text.splitlines():
                if not re.match(r"^\s*\d+\s+\d{2}/\d{2}/\d{4}", line):
                    continue
                fields = line.split()
                # GDD schema: LineRx, Rx1, Rx2 and M are columns 5, 10, 11, 20.
                x = float(fields[5])
                y = (float(fields[10]) + float(fields[11])) / 2.0
                chargeability = float(fields[20])
                values[(x, y)].append(chargeability)
    return np.asarray(
        [(x, y, float(np.mean(samples))) for (x, y), samples in values.items()],
        dtype=float,
    )


def correlation_bins(points: np.ndarray) -> list[dict[str, float | int]]:
    response = points[:, 2] - float(np.mean(points[:, 2]))
    variance = float(np.mean(response * response))
    bins: list[dict[str, float | int]] = []
    for lower in range(0, 1000, 50):
        products: list[float] = []
        for left in range(len(points)):
            for right in range(left + 1, len(points)):
                distance = float(
                    np.linalg.norm(points[left, :2] - points[right, :2])
                )
                if lower < distance <= lower + 50:
                    products.append(
                        float(response[left] * response[right] / variance)
                    )
        if len(products) >= 10:
            bins.append(
                {
                    "lower_m": lower,
                    "upper_m": lower + 50,
                    "pair_count": len(products),
                    "correlation": float(np.mean(products)),
                }
            )
    return bins


def frozen_training_range(bins: list[dict[str, float | int]]) -> tuple[int, int]:
    for index in range(len(bins) - 4):
        run = bins[index : index + 5]
        consecutive = all(
            int(right["lower_m"]) == int(left["upper_m"])
            for left, right in zip(run, run[1:])
        )
        if consecutive and all(abs(float(item["correlation"])) < 0.1 for item in run):
            stable_upper = int(run[0]["upper_m"])
            return stable_upper, int(math.ceil(stable_upper * 1.25 / 50.0) * 50)
    raise RuntimeError("no stable five-bin training-only correlation run")


def sealed_receiver_centres() -> tuple[set[tuple[float, float]], int, list[str]]:
    """Read only the first eight geometry columns; never parse response columns."""
    centres: set[tuple[float, float]] = set()
    row_count = 0
    members: list[str] = []
    with zipfile.ZipFile(SEALED_ARCHIVE) as archive:
        for info in archive.infolist():
            lowered = info.filename.lower()
            if not (lowered.endswith(".dat") and "/data/" in lowered):
                continue
            members.append(info.filename)
            geometry_header: list[str] | None = None
            text = archive.read(info).decode("latin1", "replace")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("C1X") or stripped.startswith("C1Y"):
                    geometry_header = stripped.split()[:8]
                    continue
                if geometry_header is None:
                    continue
                if not re.match(r"^[+-]?(?:\d|\.\d)", stripped):
                    continue
                fields = stripped.split()
                try:
                    geometry_values = [float(value) for value in fields[:8]]
                except ValueError:
                    continue
                geometry = dict(zip(geometry_header, geometry_values))
                required = {"P1X", "P2X", "P1Y", "P2Y"}
                if not required.issubset(geometry):
                    continue
                centres.add(
                    (
                        round((geometry["P1X"] + geometry["P2X"]) / 2.0, 3),
                        round((geometry["P1Y"] + geometry["P2Y"]) / 2.0, 3),
                    )
                )
                row_count += 1
    return centres, row_count, sorted(members)


def greedy_pack(
    points: set[tuple[float, float]], separation_m: int
) -> list[tuple[float, float]]:
    selected: list[tuple[float, float]] = []
    squared = separation_m * separation_m
    for point in sorted(points):
        if all(
            (point[0] - other[0]) ** 2 + (point[1] - other[1]) ** 2 > squared
            for other in selected
        ):
            selected.append(point)
    return selected


def role_key(point: tuple[float, float]) -> str:
    payload = f"{SALT}|{point[0]:.3f}|{point[1]:.3f}".encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    training = training_centres_and_chargeability()
    bins = correlation_bins(training)
    stable_upper, range_m = frozen_training_range(bins)
    sealed, sealed_rows, sealed_members = sealed_receiver_centres()
    packed = greedy_pack(sealed, range_m)
    if len(packed) != 247:
        raise RuntimeError(f"expected 247 packed centres, found {len(packed)}")
    ordered = sorted(packed, key=role_key)
    calibration = ordered[:24]
    test = ordered[24:]
    if len(test) != 223:
        raise RuntimeError("sealed test must contain exactly 223 centres")
    payload = {
        "schema_version": "wp8-ntgs-pine-creek-tdip-coordinate-design-v1",
        "selection_frozen_before_sealed_response_interpretation": True,
        "training_archive": TRAINING_ARCHIVE.name,
        "training_archive_sha256": sha256(TRAINING_ARCHIVE),
        "sealed_archive": SEALED_ARCHIVE.name,
        "sealed_archive_sha256": sha256(SEALED_ARCHIVE),
        "contamination_ledger": {
            "training_report": "CR2011-0200",
            "sealed_report": "CR2016-0418",
            "sealed_response_values_interpreted": 0,
            "test_unseal_count": 0,
        },
        "training_only_correlation": {
            "unique_receiver_centres": int(len(training)),
            "bin_width_m": 50,
            "criterion": "first five consecutive bins with abs(correlation) < 0.1",
            "stable_run_first_bin_upper_m": stable_upper,
            "safety_factor": 1.25,
            "frozen_range_m": range_m,
            "bins": bins,
        },
        "sealed_coordinate_audit": {
            "members": sealed_members,
            "geometry_columns_parsed_only": [
                "C1X",
                "C2X",
                "P1X",
                "P2X",
                "C1Y",
                "C2Y",
                "P1Y",
                "P2Y",
            ],
            "response_columns_parsed": [],
            "raw_rows_with_geometry": sealed_rows,
            "unique_receiver_centres": len(sealed),
            "strictly_separated_packed_centres": len(packed),
            "minimum_separation_rule": f"strictly greater than {range_m} m",
        },
        "role_assignment": {
            "algorithm": "SHA256 salted ordering of the 247 packed coordinates",
            "salt": SALT,
            "calibration_count": len(calibration),
            "test_count": len(test),
            "calibration": [
                {"easting_m": x, "northing_m": y, "key": role_key((x, y))}
                for x, y in calibration
            ],
            "test": [
                {"easting_m": x, "northing_m": y, "key": role_key((x, y))}
                for x, y in test
            ],
        },
        "cluster_count_gate_possible": True,
        "paired_crps_effect_size_available": False,
        "power_gate_passes": False,
        "sealed_response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    EVIDENCE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k != "role_assignment"}, indent=2))


if __name__ == "__main__":
    main()
