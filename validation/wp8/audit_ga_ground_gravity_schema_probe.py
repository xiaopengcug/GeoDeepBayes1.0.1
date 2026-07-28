#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["netCDF4==1.7.2"]
# ///
"""Audit only GA NetCDF variable declarations; never read array values."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1"
RAW = DATA / "P199964-point-gravity.nc"
MANIFEST = DATA / "schema-probe-manifest.json"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/ga-ground-gravity-schema-probe.json"
REQUIRED = {
    "latitude",
    "longitude",
    "grav",
    "bouguer",
    "gravacc",
    "gndelev",
    "gndelevacc",
    "tc",
    "tcerr",
    "reliab_index",
}


def sha(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha(RAW) != manifest["sha256"]:
        raise RuntimeError("GA gravity schema probe raw drift")
    with Dataset(RAW, "r") as dataset:
        declared = {}
        for name, variable in dataset.variables.items():
            declared[name] = {
                "dtype": str(variable.dtype),
                "dimensions": list(variable.dimensions),
                "long_name": (
                    str(variable.getncattr("long_name"))
                    if "long_name" in variable.ncattrs()
                    else None
                ),
                "units": (
                    str(variable.getncattr("units"))
                    if "units" in variable.ncattrs()
                    else None
                ),
                "fill_value_declared": "_FillValue" in variable.ncattrs(),
            }
        point_count = len(dataset.dimensions["point"])
    result = {
        "schema_version": "wp8-ga-ground-gravity-schema-probe-v1",
        "raw_sha256": sha(RAW),
        "survey_id": "P199964",
        "point_count": point_count,
        "required_variables": sorted(REQUIRED),
        "required_variables_present": REQUIRED.issubset(declared),
        "declared_variables": declared,
        "array_values_read": 0,
        "response_array_values_read": 0,
        "pre_design_response_metadata_exposure": {
            "detected": True,
            "scope": "P199964 only",
            "kind": (
                "NetCDF actual_range attributes for grav, freeair, bouguer and "
                "terrain correction were displayed during the first manual header probe."
            ),
            "remediation": (
                "P199964 is wholly excluded from the subsequently frozen formal design."
            ),
        },
        "contract_potential": {
            "complete_bouguer_reconstructable": True,
            "per_observation_error_inputs_declared": True,
            "reason": (
                "The unified schema declares Bouguer anomaly, terrain correction, "
                "gravity accuracy, ground-elevation accuracy and terrain-correction "
                "error as point-dimension variables. Coverage/value validity across "
                "the remaining formal pool is not yet established."
            ),
        },
        "formal_confirmatory_contribution": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "points": point_count,
            "required_variables_present": result["required_variables_present"],
            "excluded_survey": "P199964",
        }
    )


if __name__ == "__main__":
    main()
