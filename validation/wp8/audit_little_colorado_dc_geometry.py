#!/usr/bin/env python
"""Outcome-blind dimensionality audit for Little Colorado River ERT geometry."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = (
    ROOT
    / "_bmad-output/planning-artifacts/research/open-data/dc_ip"
    / "USGS_LittleColoradoRiver_ERT_2019"
)
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/little-colorado-dc-geometry.json"
ARCHIVES = ("MB2.5.zip", "MB2.5B.zip", "MB4.zip", "MB4B.zip")


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    profiles = {}
    for name in ARCHIVES:
        path = RAW / name
        with zipfile.ZipFile(path) as archive:
            member = next(member for member in archive.namelist() if member.endswith(".csv"))
            rows = [
                row
                for row in csv.DictReader(
                    io.StringIO(archive.read(member).decode("utf-8-sig"))
                )
                if row.get("Easting")
                and row.get("Northing")
                and row.get("Altitude (ft)")
            ]
        xy = np.asarray(
            [[float(row["Easting"]), float(row["Northing"])] for row in rows]
        )
        elevation = np.asarray([float(row["Altitude (ft)"]) * 0.3048 for row in rows])
        center = np.mean(xy, axis=0)
        _, _, vectors = np.linalg.svd(xy - center, full_matrices=False)
        along = (xy - center) @ vectors[0]
        cross = (xy - center) @ vectors[1]
        order = np.argsort(along)
        spacing = np.sqrt(np.sum(np.diff(xy[order], axis=0) ** 2, axis=1))
        median_spacing = float(np.median(spacing))
        maximum_crossline = float(np.max(np.abs(cross)))
        two_d_eligible = maximum_crossline <= 1.5 * median_spacing
        profiles[path.stem] = {
            "archive_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "archive_bytes": path.stat().st_size,
            "archive_sha256": sha(path),
            "gps_member": member,
            "electrodes": len(rows),
            "profile_length_m": float(np.ptp(along)),
            "median_electrode_spacing_m": median_spacing,
            "crossline_rms_m": float(np.sqrt(np.mean(cross**2))),
            "crossline_maximum_m": maximum_crossline,
            "crossline_maximum_spacing_ratio": maximum_crossline / median_spacing,
            "elevation_relief_m": float(np.ptp(elevation)),
            "two_d_eligibility_rule": (
                "maximum PCA crossline deviation <=1.5 median electrode spacings"
            ),
            "two_d_eligible": two_d_eligible,
        }
    requires_3d = [
        name for name, evidence in profiles.items() if not evidence["two_d_eligible"]
    ]
    result = {
        "schema_version": "wp8-little-colorado-dc-geometry-v1",
        "doi": "10.5066/P9TNW6SD",
        "parsed_fields": [
            "line name",
            "station number",
            "easting",
            "northing",
            "altitude",
        ],
        "resistance_or_apparent_resistivity_values_parsed": False,
        "profiles": profiles,
        "profiles_requiring_3d": requires_3d,
        "dimensionality": {
            "selected": "3-D",
            "passed": bool(requires_3d),
            "reason": (
                "the formal method path must cover every selected profile; MB4 has "
                "crossline curvature far beyond electrode spacing, so the available "
                "3-D nodal finite-volume DC path is mandatory"
            ),
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                name: {
                    "spacing_m": round(value["median_electrode_spacing_m"], 2),
                    "crossline_max_m": round(value["crossline_maximum_m"], 2),
                    "two_d": value["two_d_eligible"],
                }
                for name, value in profiles.items()
            }
            | {"selected": result["dimensionality"]["selected"]}
        )
    )


if __name__ == "__main__":
    main()
