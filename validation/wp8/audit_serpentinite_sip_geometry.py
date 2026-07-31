#!/usr/bin/env python
"""Outcome-blind dimensionality audit for the Serpentinite IP survey geometry."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = (
    ROOT
    / "_bmad-output/planning-artifacts/research/open-data/dc_ip"
    / "Zenodo_Serpentinite_IP_Revil_2024/Data 1.zip"
)
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/serpentinite-sip-geometry.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    profiles = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        members = sorted(name for name in archive.namelist() if name.lower().endswith(".csv"))
        for member in members:
            text = archive.read(member).decode("latin-1")
            rows = list(csv.reader(io.StringIO(text), delimiter=";"))
            data = [
                row
                for row in rows[1:]
                if len(row) >= 5 and row[0].strip() and row[1].strip() and row[4].strip()
            ]
            xy = np.asarray([[float(row[0]), float(row[1])] for row in data])
            elevation = np.asarray([float(row[4]) for row in data])
            center = np.mean(xy, axis=0)
            _, _, vectors = np.linalg.svd(xy - center, full_matrices=False)
            along = (xy - center) @ vectors[0]
            cross = (xy - center) @ vectors[1]
            order = np.argsort(along)
            spacing = np.sqrt(np.sum(np.diff(xy[order], axis=0) ** 2, axis=1))
            median_spacing = float(np.median(spacing))
            profiles[Path(member).stem] = {
                "member": member,
                "electrodes": len(data),
                "profile_length_m": float(np.ptp(along)),
                "median_electrode_spacing_m": median_spacing,
                "crossline_rms_m": float(np.sqrt(np.mean(cross**2))),
                "crossline_maximum_m": float(np.max(np.abs(cross))),
                "elevation_relief_m": float(np.ptp(elevation)),
                "two_d_eligibility_rule": (
                    "maximum PCA crossline deviation <=5 median electrode spacings"
                ),
                "two_d_eligible": bool(
                    np.max(np.abs(cross)) <= 5.0 * median_spacing
                ),
            }
    result = {
        "schema_version": "wp8-serpentinite-sip-geometry-v1",
        "archive_path": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": sha(ARCHIVE),
        "parsed_members": members,
        "apparent_resistivity_chargeability_or_spectral_values_parsed": False,
        "profiles": profiles,
        "dimensionality": {
            "selected": "2-D profile",
            "passed": all(profile["two_d_eligible"] for profile in profiles.values()),
            "reason": (
                "two spatially distinct electrode profiles are individually near-linear; "
                "their field ERT/IP observations require lateral profile structure and "
                "cannot be represented by a 1-D homogeneous halfspace"
            ),
        },
        "available_solver_compatible": True,
        "available_solver_limitation": (
            "ColeCole2DOperator matches profile dimensionality; its explicit "
            "finite-difference transpose remains WP8-0 research-scale"
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                name: {
                    "electrodes": value["electrodes"],
                    "crossline_max_m": round(value["crossline_maximum_m"], 3),
                    "relief_m": round(value["elevation_relief_m"], 3),
                }
                for name, value in profiles.items()
            }
            | {"selected": result["dimensionality"]["selected"]}
        )
    )


if __name__ == "__main__":
    main()
