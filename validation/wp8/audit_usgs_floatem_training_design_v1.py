#!/usr/bin/env python
"""Freeze a training-only TEM range/power design and a sealed FloaTEM split."""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation" / "wp8" / "data"
EVIDENCE = ROOT / "validation" / "wp8" / "evidence" / "feasibility-v1"
OUTPUT = EVIDENCE / "usgs-floatem-training-design-power-v1.json"

LAND = DATA / "usgs-tallahatchie-ttem" / "MS-tTEM.zip"
MS_RIVER = DATA / "usgs-tallahatchie-floatem-sealed" / "MS-FloaTEM.zip"
RAINBOW = DATA / "usgs-rainbow-tem-sealed" / "CT-FloaTEM.zip"
BARRYVILLE = DATA / "usgs-barryville-tem-sealed" / "NY-FloaTEM.zip"
JAMESTOWN = DATA / "usgs-jamestown-tem-sealed" / "Jamestown_AVG.xyz"
SEALED = DATA / "usgs-lower-delaware-floatem-sealed" / "FloaTEM.zip"

RANGE_M = 325.0
TARGET_IMPROVEMENT = 0.10
ALPHA_ONE_SIDED = 0.05
TARGET_POWER = 0.80
LOCAL_NEIGHBOURS = 200
SALT = "wp8-tem-lower-delaware-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normal_crps(value: float, mean: float, sigma: float) -> float:
    sigma = max(float(sigma), 1e-6)
    z_score = (value - mean) / sigma
    return float(
        sigma
        * (
            z_score * (2 * norm.cdf(z_score) - 1)
            + 2 * norm.pdf(z_score)
            - 1 / math.sqrt(math.pi)
        )
    )


def greedy_indices(coordinates: np.ndarray, range_m: float) -> list[int]:
    chosen: list[int] = []
    range_squared = range_m**2
    order = np.lexsort((coordinates[:, 1], coordinates[:, 0]))
    for index in order:
        point = coordinates[index]
        if all(
            float(np.sum((point - coordinates[other]) ** 2)) > range_squared
            for other in chosen
        ):
            chosen.append(int(index))
    return chosen


def read_rhoa_csv(
    archive: Path, member: str
) -> tuple[np.ndarray, int]:
    grouped: dict[tuple[float, float], list[float]] = defaultdict(list)
    rows = 0
    with zipfile.ZipFile(archive) as container, container.open(member) as raw:
        stream = io.TextIOWrapper(raw, encoding="utf-8-sig")
        header = None
        for line in stream:
            if "TIMESTAMP" in line and "UTMX" in line and "RHOA_" in line:
                header = line.lstrip("/").strip().split(",")
                break
        if header is None:
            raise RuntimeError(f"RHOA header missing: {member}")
        x_index = header.index("UTMX")
        y_index = header.index("UTMY")
        response_indices = [
            index
            for index, name in enumerate(header)
            if name.startswith("RHOA_Ch")
            and not name.startswith("RHOA_STD")
        ]
        for line in stream:
            fields = line.strip().split(",")
            if len(fields) <= max(response_indices):
                continue
            try:
                coordinate = (
                    float(fields[x_index]),
                    float(fields[y_index]),
                )
                values = np.asarray(
                    [float(fields[index]) for index in response_indices]
                )
            except ValueError:
                continue
            valid = values[(values > 0) & np.isfinite(values)]
            if len(valid):
                grouped[coordinate].append(
                    float(np.median(np.log(valid)))
                )
                rows += 1
    array = np.asarray(
        [
            (x, y, float(np.mean(values)))
            for (x, y), values in grouped.items()
        ]
    )
    return array, rows


def read_jamestown() -> tuple[np.ndarray, int]:
    grouped: dict[tuple[float, float], list[float]] = defaultdict(list)
    rows = 0
    with JAMESTOWN.open(encoding="utf-8-sig") as stream:
        header = None
        for line in stream:
            if (
                "TIMESTAMP" in line
                and "LONGITUDE_X" in line
                and "RHOA_" in line
            ):
                header = line.lstrip("/").strip().split()
                break
        if header is None:
            raise RuntimeError("Jamestown RHOA header missing")
        x_index = header.index("LONGITUDE_X")
        y_index = header.index("LATITUDE_Y")
        response_indices = [
            index
            for index, name in enumerate(header)
            if name.startswith("RHOA_Ch")
            and not name.startswith("RHOA_STD")
        ]
        for line in stream:
            if line.startswith("/"):
                continue
            fields = line.split()
            if len(fields) <= max(response_indices):
                continue
            try:
                coordinate = (
                    float(fields[x_index]),
                    float(fields[y_index]),
                )
                values = np.asarray(
                    [float(fields[index]) for index in response_indices]
                )
            except ValueError:
                continue
            valid = values[(values > 0) & np.isfinite(values)]
            if len(valid):
                grouped[coordinate].append(
                    float(np.median(np.log(valid)))
                )
                rows += 1
    latitude = float(np.mean([item[1] for item in grouped]))
    array = np.asarray(
        [
            (
                longitude
                * 111_320
                * math.cos(math.radians(latitude)),
                point_latitude * 110_540,
                float(np.mean(values)),
            )
            for (longitude, point_latitude), values in grouped.items()
        ]
    )
    return array, rows


def land_training_range() -> dict:
    training, _ = read_rhoa_csv(
        LAND, "20180327_ShellmoundMS_tTEM_ALL_LINES_AVERAGE.csv"
    )
    coordinates = training[:, :2]
    response = training[:, 2]
    normalized = (coordinates - coordinates.mean(axis=0)) / coordinates.std(
        axis=0
    )
    matrix = np.column_stack([np.ones(len(coordinates)), normalized])
    residual = response - matrix @ np.linalg.lstsq(
        matrix, response, rcond=None
    )[0]
    variance = float(np.var(residual))
    upper_i, upper_j = np.triu_indices(len(coordinates), 1)
    distances = np.linalg.norm(
        coordinates[upper_i] - coordinates[upper_j], axis=1
    )
    products = residual[upper_i] * residual[upper_j] / variance
    bins = []
    for lower in range(0, 321, 10):
        selected = (distances >= lower) & (distances < lower + 10)
        if np.any(selected):
            bins.append(
                {
                    "lower_m": lower,
                    "upper_m": lower + 10,
                    "pair_count": int(np.sum(selected)),
                    "correlation": float(np.mean(products[selected])),
                }
            )
    stable = None
    for start in range(len(bins) - 4):
        run = bins[start : start + 5]
        if all(abs(item["correlation"]) < 0.1 for item in run):
            stable = run
            break
    if stable is None or stable[-1]["upper_m"] != 260:
        raise RuntimeError("training-only TEM stable range drift")
    return {
        "summary_response": "median log positive apparent resistivity across available gates, averaged at coordinate",
        "detrending": "first-order planar trend",
        "lag_bin_width_m": 10,
        "independence_rule": "first five consecutive lag bins with absolute residual correlation below 0.1",
        "stable_run": stable,
        "stable_upper_edge_m": 260,
        "safety_factor": 1.25,
        "frozen_range_m": RANGE_M,
        "training_positions": len(training),
    }


def training_power() -> dict:
    sources = [
        (
            "tallahatchie_river",
            *read_rhoa_csv(
                MS_RIVER,
                "20181017_ShellmoundMS_FloaTEM_ALL_LINES_AVERAGED.csv",
            ),
        ),
        (
            "rainbow_reservoir",
            *read_rhoa_csv(
                RAINBOW,
                "20181115_RainbowReservoirCT_FloaTEM_ALL_LINES_AVERAGE.csv",
            ),
        ),
        (
            "barryville",
            *read_rhoa_csv(
                BARRYVILLE,
                "20181206_DelawareRiverNY_FloaTEM_ALL_LINES_AVERAGE.csv",
            ),
        ),
        ("jamestown", *read_jamestown()),
    ]
    scores = []
    inventories = []
    for label, training, row_count in sources:
        coordinates = training[:, :2]
        response = training[:, 2]
        held_indices = greedy_indices(coordinates, RANGE_M)
        inventories.append(
            {
                "site": label,
                "response_rows_interpreted": row_count,
                "unique_response_positions": len(training),
                "correlation_separated_positions": len(held_indices),
            }
        )
        for held_index in held_indices:
            distances = np.linalg.norm(
                coordinates - coordinates[held_index], axis=1
            )
            retained = distances > RANGE_M
            retained_response = response[retained]
            retained_distances = distances[retained]
            if len(retained_response) <= LOCAL_NEIGHBOURS:
                raise RuntimeError(f"insufficient buffered training: {label}")
            baseline_crps = normal_crps(
                response[held_index],
                float(np.mean(retained_response)),
                float(np.std(retained_response, ddof=1)),
            )
            nearest = np.argsort(retained_distances)[:LOCAL_NEIGHBOURS]
            local = retained_response[nearest]
            candidate_crps = normal_crps(
                response[held_index],
                float(np.mean(local)),
                float(np.std(local, ddof=1)),
            )
            scores.append(
                {
                    "site": label,
                    "baseline_crps": baseline_crps,
                    "candidate_crps": candidate_crps,
                }
            )
    site_baseline_means = {
        label: float(
            np.mean(
                [
                    item["baseline_crps"]
                    for item in scores
                    if item["site"] == label
                ]
            )
        )
        for label, *_ in sources
    }
    for item in scores:
        item["site_mean_baseline_crps"] = site_baseline_means[item["site"]]
        item["normalized_paired_crps_improvement"] = (
            item["baseline_crps"] - item["candidate_crps"]
        ) / item["site_mean_baseline_crps"]
    improvements = np.asarray(
        [item["normalized_paired_crps_improvement"] for item in scores]
    )
    observed_sd = float(np.std(improvements, ddof=1))
    sigma_upper = observed_sd * math.sqrt(
        (len(improvements) - 1)
        / chi2.ppf(0.05, len(improvements) - 1)
    )
    z_sum = norm.ppf(1 - ALPHA_ONE_SIDED) + norm.ppf(TARGET_POWER)
    required_crps = math.ceil(
        (z_sum * sigma_upper / TARGET_IMPROVEMENT) ** 2
    )
    return {
        "training_only": True,
        "source_inventory": inventories,
        "comparison": {
            "information_parity": "Both predictive distributions use only the same site-specific training apparent-resistivity summaries and coordinates.",
            "baseline": "site-global Gaussian predictive distribution",
            "candidate": "Gaussian predictive distribution from the nearest 200 retained training positions",
            "validation": "leave-one-325-m-separated-position-out after removing every training position within 325 m",
            "candidate_neighbour_count": LOCAL_NEIGHBOURS,
            "paired_estimand": "(baseline CRPS - candidate CRPS) divided by the training-only site mean baseline CRPS; this preserves a 10% site-relative target without unstable division by near-zero individual scores",
        },
        "paired_training_clusters": len(scores),
        "paired_cluster_scores": scores,
        "exploratory_mean_relative_improvement": float(
            np.mean(improvements)
        ),
        "paired_relative_improvement_sd": observed_sd,
        "paired_relative_improvement_sd_upper_95": sigma_upper,
        "power_target_relative_improvement": TARGET_IMPROVEMENT,
        "required_paired_crps_clusters_conservative": required_crps,
        "required_coverage_clusters": {"0.90": 223, "0.95": 118},
        "required_clusters_all_metrics": max(required_crps, 223),
        "alpha_one_sided": ALPHA_ONE_SIDED,
        "target_power": TARGET_POWER,
    }


def sealed_coordinates() -> tuple[np.ndarray, dict]:
    coordinates = []
    members = []
    with zipfile.ZipFile(SEALED) as container:
        for member in sorted(container.namelist()):
            if not member.endswith("_dat.xyz"):
                continue
            count = 0
            with container.open(member) as raw:
                stream = io.TextIOWrapper(raw, encoding="utf-8-sig")
                header_seen = False
                for line in stream:
                    if line.startswith("/"):
                        if (
                            "LINE_NO" in line
                            and "UTMX" in line
                            and "UTMY" in line
                        ):
                            header_seen = True
                        continue
                    if not header_seen:
                        continue
                    # Deliberately parse only LINE_NO, UTMX and UTMY. The
                    # remainder is never tokenized or converted.
                    prefix = line.split(None, 3)[:3]
                    if len(prefix) < 3:
                        continue
                    try:
                        point = (float(prefix[1]), float(prefix[2]))
                    except ValueError:
                        continue
                    coordinates.append(point)
                    count += 1
            members.append({"member": member, "coordinate_rows": count})
    unique = np.asarray(sorted(set(coordinates)))
    return unique, {
        "members": members,
        "coordinate_rows": len(coordinates),
        "unique_positions": len(unique),
        "coordinate_fields_read": ["LINE_NO", "UTMX", "UTMY"],
        "response_columns_interpreted": 0,
        "test_unseal_count": 0,
    }


def main() -> None:
    for path in (
        LAND,
        MS_RIVER,
        RAINBOW,
        BARRYVILLE,
        JAMESTOWN,
        SEALED,
    ):
        if not path.is_file():
            raise RuntimeError(f"missing source: {path}")
    correlation = land_training_range()
    power = training_power()
    sealed, sealed_inventory = sealed_coordinates()
    packed_indices = greedy_indices(sealed, RANGE_M)
    packed = sealed[packed_indices]
    ordered = sorted(
        packed.tolist(),
        key=lambda point: hashlib.sha256(
            f"{SALT}|{point[0]:.3f}|{point[1]:.3f}".encode()
        ).hexdigest(),
    )
    if len(ordered) != 465:
        raise RuntimeError(f"sealed packing drift: {len(ordered)}")
    required = power["required_clusters_all_metrics"]
    calibration = ordered[:24]
    test = ordered[24 : 24 + required]
    buffer = ordered[24 + required :]
    available_test = len(test)
    payload = {
        "schema_version": "wp8-usgs-floatem-training-design-power-v1",
        "audit_mode": "training_only_power_and_response_blind_sealed_design",
        "license": "US-public-domain",
        "training_source_sha256": {
            path.name + ":" + path.parent.name: sha256(path)
            for path in (LAND, MS_RIVER, RAINBOW, BARRYVILLE, JAMESTOWN)
        },
        "sealed_archive": str(SEALED.relative_to(ROOT)).replace("\\", "/"),
        "sealed_archive_sha256": sha256(SEALED),
        "training_only_correlation": correlation,
        "training_only_power": power,
        "sealed_coordinate_inventory": sealed_inventory,
        "sealed_packing": {
            "algorithm": "lexicographic greedy packing with Euclidean distance strictly greater than frozen range",
            "frozen_range_m": RANGE_M,
            "packed_position_count": len(ordered),
        },
        "role_assignment": {
            "salt_sha256": hashlib.sha256(SALT.encode()).hexdigest(),
            "calibration_count": len(calibration),
            "test_count": len(test),
            "buffer_count": len(buffer),
            "test_coordinate_sha256": hashlib.sha256(
                json.dumps(test, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "available_correlation_adjusted_test_clusters": available_test,
        "required_clusters_all_metrics": required,
        "selection_frozen_before_sealed_response_interpretation": True,
        "wp8_0_cluster_gate_passes": available_test >= 223,
        "wp8_0_power_gate_passes": available_test >= required,
        "sealed_response_values_interpreted": 0,
        "test_unseal_count": 0,
        "formal_test_result": None,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_clusters": power["paired_training_clusters"],
                "sd_upper_95": power[
                    "paired_relative_improvement_sd_upper_95"
                ],
                "required_crps": power[
                    "required_paired_crps_clusters_conservative"
                ],
                "required_all": required,
                "sealed_packed": len(ordered),
                "test": available_test,
                "cluster_gate": payload["wp8_0_cluster_gate_passes"],
                "power_gate": payload["wp8_0_power_gate_passes"],
            }
        )
    )


if __name__ == "__main__":
    main()
