#!/usr/bin/env python
"""Outcome-blind CSAMT dimensionality audit from official station coordinates."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPLIT = ROOT / "validation/wp8/evidence/feasibility-v1/csamt-candidate-split.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/csamt-geometry.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def axial_difference(left: float, right: float) -> float:
    return abs((left - right + 90.0) % 180.0 - 90.0)


def main() -> None:
    source = json.loads(SPLIT.read_text(encoding="utf-8"))
    if source.get("observation_values_read") is not False:
        raise RuntimeError("CSAMT geometry input is not outcome-blind")
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for site in source["sites"]:
        grouped[(site["release"], site["line"])].append(site)

    lines = {}
    azimuths = []
    for (release, line), sites in sorted(grouped.items()):
        xy = np.asarray([[row["easting_m"], row["northing_m"]] for row in sites])
        elevation = np.asarray(
            [row["elevation_m"] for row in sites if row["elevation_m"] is not None]
        )
        center = xy.mean(axis=0)
        _, _, vectors = np.linalg.svd(xy - center, full_matrices=False)
        along = (xy - center) @ vectors[0]
        cross = (xy - center) @ vectors[1]
        order = np.argsort(along)
        spacing = np.linalg.norm(np.diff(xy[order], axis=0), axis=1)
        median_spacing = float(np.median(spacing)) if len(spacing) else 0.0
        azimuth = float(
            np.degrees(np.arctan2(vectors[0, 0], vectors[0, 1])) % 180.0
        )
        azimuths.append(azimuth)
        lines[f"{release}|{line}"] = {
            "release": release,
            "line": line,
            "stations": len(sites),
            "azimuth_degrees_axial": azimuth,
            "profile_length_m": float(np.ptp(along)),
            "median_station_spacing_m": median_spacing,
            "crossline_rms_m": float(np.sqrt(np.mean(cross**2))),
            "crossline_maximum_m": float(np.max(np.abs(cross))),
            "elevation_relief_m": float(np.ptp(elevation)) if len(elevation) else None,
            "individual_line_2d_eligible": bool(
                median_spacing > 0
                and np.max(np.abs(cross)) <= 5.0 * median_spacing
            ),
        }

    max_azimuth_difference = max(
        axial_difference(left, right)
        for index, left in enumerate(azimuths)
        for right in azimuths[index + 1 :]
    )
    releases = sorted({row["release"] for row in source["sites"]})
    selected = "3-D finite-source"
    result = {
        "schema_version": "wp8-csamt-geometry-v1",
        "input_path": str(SPLIT.relative_to(ROOT)).replace("\\", "/"),
        "input_sha256": sha(SPLIT),
        "observation_or_inversion_values_parsed": False,
        "coordinate_source": "official USGS station ZIP members only",
        "crs": source["crs"],
        "release_count": len(releases),
        "releases": releases,
        "line_count": len(lines),
        "lines": lines,
        "maximum_axial_line_azimuth_difference_degrees": max_azimuth_difference,
        "dimensionality_rule": (
            "select method-wide 3-D finite-source physics when official stations "
            "span multiple sites and line azimuth families differ by more than 20 degrees; "
            "a per-line 2-D interpretation is not promoted to a consortium-wide contract"
        ),
        "dimensionality": {
            "selected": selected,
            "passed": bool(
                len(releases) >= 2 and max_azimuth_difference > 20.0
            ),
            "reason": (
                "the official consortium spans multiple separated sites and strongly "
                "different receiver-line azimuths; the unknown transmitter endpoints "
                "also preclude proving a shared 2-D source/profile plane"
            ),
        },
        "available_solver_compatible": True,
        "available_solver": "geodeepbayes.forward.controlled_source.CSAMTOperator",
        "solver_dimension": "3-D finite-line Maxwell",
        "contract_boundary": (
            "dimension selection does not repair the missing transmitter endpoint, "
            "source-distance, or near/transition/far observation metadata"
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "lines": len(lines),
                "releases": len(releases),
                "max_azimuth_difference": round(max_azimuth_difference, 3),
                "selected": selected,
            }
        )
    )


if __name__ == "__main__":
    main()
