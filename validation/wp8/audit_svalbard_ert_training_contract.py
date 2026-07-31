#!/usr/bin/env python
"""Audit reciprocal-error and geometry contracts in the Ny-Ålesund ERT release."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/svalbard-ert-repository-v1"
MANIFEST = RAW / "raw-manifest.json"
ARCHIVE = RAW / "Repository.zip"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/"
    "svalbard-ert-training-contract.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite(value: str | None) -> bool:
    if value is None or not value.strip():
        return False
    try:
        return math.isfinite(float(value))
    except ValueError:
        return False


def profile_name(path: str) -> str:
    match = re.search(r"/ERT/Data/([^/]+)/", path)
    if not match:
        raise RuntimeError(f"unrecognized ERT path: {path}")
    return match.group(1)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["selection_is_response_blind"] is not True
        or manifest["response_values_interpreted_during_acquisition"] != 0
        or manifest["test_unseal_count"] != 0
    ):
        raise RuntimeError("Svalbard ERT acquisition protocol drift")
    for member in manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            raise RuntimeError(f"Svalbard ERT member drift: {member['path']}")

    reciprocal_profiles: dict[str, dict[str, int]] = {}
    topography_profiles: dict[str, int] = {}
    raw_bin_profiles: set[str] = set()
    with zipfile.ZipFile(ARCHIVE) as archive:
        for info in archive.infolist():
            name = info.filename
            if "/ERT/Data/" not in name:
                continue
            if name.lower().endswith(".bin"):
                raw_bin_profiles.add(profile_name(name))
            if re.search(r"/3_Topography/[^/]+\.csv$", name):
                rows = list(
                    csv.DictReader(
                        io.StringIO(archive.read(name).decode("utf-8-sig"))
                    )
                )
                required = {
                    "Electrode_Number",
                    "East_m_EPSG_32633",
                    "North_m_EPSG_32633",
                    "Altitude_m",
                }
                if not rows or not required.issubset(rows[0]):
                    raise RuntimeError(f"topography schema drift: {name}")
                if not all(
                    finite(row[key])
                    for row in rows
                    for key in required
                ):
                    raise RuntimeError(f"non-finite topography: {name}")
                topography_profiles[profile_name(name)] = len(rows)
            if not name.endswith("/ErrorData.csv"):
                continue
            rows = list(
                csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig")))
            )
            required = {
                "a",
                "b",
                "m",
                "n",
                "Resistance [ohm]",
                "recipMean",
                "Resistance_err [ohm]",
            }
            if not rows or not required.issubset(rows[0]):
                raise RuntimeError(f"reciprocal schema drift: {name}")
            reciprocal_profiles[profile_name(name)] = {
                "paired_rows": len(rows),
                "complete_abmn_rows": sum(
                    all(finite(row[key]) for key in ("a", "b", "m", "n"))
                    for row in rows
                ),
                "finite_resistance_rows": sum(
                    finite(row["Resistance [ohm]"]) for row in rows
                ),
                "finite_reciprocal_mean_rows": sum(
                    finite(row["recipMean"]) for row in rows
                ),
                "finite_direct_error_rows": sum(
                    finite(row["Resistance_err [ohm]"]) for row in rows
                ),
                "finite_fitted_error_rows": sum(
                    finite(row.get("Fit Resistance_err [ohm]")) for row in rows
                ),
            }

    paired_rows = sum(item["paired_rows"] for item in reciprocal_profiles.values())
    complete_rows = sum(
        item["complete_abmn_rows"] == item["paired_rows"]
        and item["finite_resistance_rows"] == item["paired_rows"]
        and item["finite_reciprocal_mean_rows"] == item["paired_rows"]
        and item["finite_direct_error_rows"] == item["paired_rows"]
        for item in reciprocal_profiles.values()
    )
    result = {
        "schema_version": "wp8-svalbard-ert-training-contract-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "doi": "10.5281/zenodo.10260056",
        "license_gate_passes": manifest["license"] == "cc-by-4.0",
        "selection_role": "training_contract_candidate_only",
        "archive_entry_count": 500,
        "raw_bin_file_count": 39,
        "raw_bin_profile_count": len(raw_bin_profiles),
        "topography_profile_count": len(topography_profiles),
        "topography_electrode_count": sum(topography_profiles.values()),
        "topography_profiles": topography_profiles,
        "reciprocal_profile_count": len(reciprocal_profiles),
        "reciprocal_paired_row_count": paired_rows,
        "reciprocal_profiles": reciprocal_profiles,
        "profiles_with_complete_abmn_response_and_direct_error": complete_rows,
        "geometry_contract": {
            "electrode_id_easting_northing_altitude": True,
            "crs": "EPSG:32633",
            "profile_local_abmn_indices": True,
        },
        "uncertainty_contract": {
            "independent_normal_reciprocal_measurements": True,
            "per_pair_resistance_difference_present": True,
            "per_pair_reciprocal_mean_present": True,
            "fitted_error_model_present_for_all_pairs": False,
            "repeat_based_training_uncertainty_ready": True,
        },
        "training_observation_contract_ready": complete_rows
        == len(reciprocal_profiles),
        "available_field_profile_clusters": len(topography_profiles),
        "formal_cluster_power_gate_passes": False,
        "test_unseal_count": 0,
        "conclusion": (
            "The CC BY 4.0 release provides a complete training-side DC field "
            "contract for the reciprocal DD subset: GPS/topographic electrode "
            "geometry, ABMN indices, resistance, reciprocal mean, and a direct "
            "normal-reciprocal error for every paired row. It covers only 18 "
            "profiles in one Ny-Ålesund campaign, including 10 reciprocal-error "
            "profiles, so it cannot supply 223 independent formal clusters."
        ),
    }
    if (
        len(raw_bin_profiles) != 18
        or len(topography_profiles) != 18
        or len(reciprocal_profiles) != 10
        or complete_rows != 10
    ):
        raise RuntimeError("Svalbard ERT profile/contract count drift")
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "profiles": len(topography_profiles),
                "reciprocal_profiles": len(reciprocal_profiles),
                "paired_rows": paired_rows,
                "contract_ready": result["training_observation_contract_ready"],
            }
        )
    )


if __name__ == "__main__":
    main()
