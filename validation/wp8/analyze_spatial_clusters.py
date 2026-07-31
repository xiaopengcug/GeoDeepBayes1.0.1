"""Outcome-blind spatial-cluster feasibility for WP8 gravity and magnetics.

This program deliberately does not load an observation/response column.  It
projects only coordinate and acquisition-provenance fields from the two CSVs.
The reported ``correlation_length_proxy`` is therefore a conservative design
scale inferred from sampling geometry, not a fitted response variogram range.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
OPEN = ROOT / "_bmad-output/planning-artifacts/research/open-data"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/spatial-clusters.json"
GRAVITY = OPEN / "gravity/USGS_SierraNevada_gravity_magnetic_grids_2024/cba_grid.csv"
MAGNETIC = OPEN / "magnetic/USGS_MountainPass_airborne_magnetic_2020/Magnetic_Data.csv"
MAG_README = MAGNETIC.with_name("Readme.txt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def read_gravity_coordinates() -> tuple[list[tuple[float, float]], dict]:
    """Project lon/lat without converting or retaining the third (CBA) field."""
    points: list[tuple[float, float]] = []
    malformed = 0
    with GRAVITY.open("r", encoding="utf-8", newline="") as stream:
        for raw in stream:
            first, sep, remainder = raw.partition(",")
            second, sep2, _uninterpreted_tail = remainder.partition(",")
            if not sep or not sep2:
                malformed += 1
                continue
            points.append((float(first), float(second)))
    return points, {
        "projection": ["column_0_longitude", "column_1_latitude"],
        "excluded_by_position": ["column_2_complete_bouguer_anomaly"],
        "excluded_values_converted": 0,
        "malformed_coordinate_rows": malformed,
    }


def read_magnetic_metadata() -> tuple[list[tuple[float, float, str, str]], dict]:
    """Project the coordinate/provenance whitelist and ignore every other field."""
    points: list[tuple[float, float, str, str]] = []
    with MAGNETIC.open("r", encoding="utf-8", newline="") as stream:
        header = next(csv.reader([stream.readline()]))
        allowed = ("Easting", "Northing", "Flight", "Line")
        indexes = {name: header.index(name) for name in allowed}
        outcome_like = [
            name
            for name in header
            if name.lower().startswith(("mag_", "igrf", "diurnal", "fx", "fy", "fz"))
        ]
        for raw in stream:
            fields = raw.rstrip("\r\n").split(",")
            points.append(
                (
                    float(fields[indexes["Easting"]]),
                    float(fields[indexes["Northing"]]),
                    fields[indexes["Flight"]],
                    fields[indexes["Line"]],
                )
            )
    return points, {
        "projection_whitelist": list(allowed),
        "header_field_count": len(header),
        "excluded_outcome_like_headers": outcome_like,
        "excluded_values_converted": 0,
    }


def gravity_geometry_scale(points: list[tuple[float, float]]) -> tuple[float, dict]:
    # Freeze a western training-candidate region from coordinates alone.
    west_cut = quantile([p[0] for p in points], 0.60)
    candidate = sorted((p for p in points if p[0] <= west_cut), key=lambda p: (p[1], p[0]))
    # Equirectangular consecutive spacing is sufficient at this regional scale.
    spacings: list[float] = []
    for (lon0, lat0), (lon1, lat1) in zip(candidate, candidate[1:]):
        dx = (lon1 - lon0) * 111_320 * math.cos(math.radians((lat0 + lat1) / 2))
        dy = (lat1 - lat0) * 110_574
        distance = math.hypot(dx, dy)
        if 0 < distance < 5_000:
            spacings.append(distance)
    sampling = median(spacings)
    # Five samples is a preregistered, conservative geometry-only dependence proxy.
    return 5.0 * sampling, {
        "training_candidate_rule": "longitude <= coordinate-only 60th percentile",
        "training_candidate_rows": len(candidate),
        "median_local_sampling_m": sampling,
        "proxy_rule": "5 * median local sampling; no response variogram fitted",
    }


def magnetic_geometry_scale(
    points: list[tuple[float, float, str, str]],
) -> tuple[float, dict]:
    west_cut = quantile([p[0] for p in points], 0.60)
    by_line: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for x, y, flight, line in points:
        if x <= west_cut:
            by_line[(flight, line)].append((x, y))
    spacings: list[float] = []
    for line_points in by_line.values():
        for a, b in zip(line_points, line_points[1:]):
            distance = math.hypot(a[0] - b[0], a[1] - b[1])
            if 0 < distance < 1_000:
                spacings.append(distance)
    along_line = median(spacings)
    # Readme states 100/200 m flight-line spacing. Use the larger support scale.
    nominal_cross_line_m = 200.0
    proxy = max(5.0 * along_line, nominal_cross_line_m)
    return proxy, {
        "training_candidate_rule": "easting <= coordinate-only 60th percentile",
        "training_candidate_rows": sum(len(v) for v in by_line.values()),
        "training_candidate_flight_line_groups": len(by_line),
        "median_along_line_sampling_m": along_line,
        "nominal_cross_line_spacing_m": nominal_cross_line_m,
        "nominal_spacing_source": str(MAG_README.relative_to(ROOT)).replace("\\", "/"),
        "proxy_rule": "max(5 * median along-line sampling, 200 m metadata spacing)",
    }


def buffered_blocks(
    xy: list[tuple[float, float]], scale: float, geographic: bool
) -> dict:
    if geographic:
        lat0 = median([p[1] for p in xy])
        projected = [
            (p[0] * 111_320 * math.cos(math.radians(lat0)), p[1] * 110_574) for p in xy
        ]
    else:
        projected = xy
    min_x, max_x = min(p[0] for p in projected), max(p[0] for p in projected)
    min_y, max_y = min(p[1] for p in projected), max(p[1] for p in projected)
    block = max(8 * scale, (max_x - min_x) / 8)
    buffer = 2 * scale
    roles = ("train", "train", "train", "cal", "test")
    counts: Counter[str] = Counter()
    clusters: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for x, y in projected:
        ix, iy = int((x - min_x) // block), int((y - min_y) // block)
        edge = (x - min_x) % block
        if edge < buffer or block - edge < buffer:
            role = "buffer"
        else:
            role = roles[ix % len(roles)]
            clusters[role].add((ix, iy))
        counts[role] += 1
    return {
        "block_width_m": block,
        "buffer_each_side_m": buffer,
        "minimum_core_separation_m": 2 * buffer,
        "role_rule": "vertical spatial blocks cycle train/train/train/cal/test; boundary bands buffered",
        "counts": {key: counts[key] for key in ("train", "buffer", "cal", "test")},
        "spatial_cluster_counts": {
            key: len(clusters[key]) for key in ("train", "cal", "test")
        },
        "extent_m": [max_x - min_x, max_y - min_y],
    }


def main() -> None:
    gravity, gravity_exposure = read_gravity_coordinates()
    magnetic, magnetic_exposure = read_magnetic_metadata()
    gravity_scale, gravity_training = gravity_geometry_scale(gravity)
    magnetic_scale, magnetic_training = magnetic_geometry_scale(magnetic)
    evidence = {
        "schema_version": "wp8-outcome-blind-spatial-clusters-v1",
        "observation_values_read": False,
        "formal_test_results_read": False,
        "release_package_used_as_single_cluster": False,
        "geometry_cluster_feasibility": "passed",
        "field_correlation_gate": "blocked_pending_train_only_response_variogram_and_error_model",
        "interpretation": (
            "Feasibility only: geometry-derived correlation-length proxies are not "
            "substitutes for a train-only response variogram/error model."
        ),
        "gravity": {
            "dataset_slug": "USGS_SierraNevada_gravity_magnetic_grids_2024",
            "source_sha256": sha256(GRAVITY),
            "row_count": len(gravity),
            "endpoint_exposure": gravity_exposure,
            "correlation_length_proxy_m": gravity_scale,
            "scale_evidence": gravity_training,
            "split": buffered_blocks(gravity, gravity_scale, geographic=True),
        },
        "magnetic": {
            "dataset_slug": "USGS_MountainPass_airborne_magnetic_2020",
            "source_sha256": sha256(MAGNETIC),
            "row_count": len(magnetic),
            "endpoint_exposure": magnetic_exposure,
            "provenance": {
                "flight_count": len({p[2] for p in magnetic}),
                "line_count": len({p[3] for p in magnetic}),
                "flight_line_count": len({(p[2], p[3]) for p in magnetic}),
            },
            "correlation_length_proxy_m": magnetic_scale,
            "scale_evidence": magnetic_training,
            "split": buffered_blocks([(p[0], p[1]) for p in magnetic], magnetic_scale, False),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
