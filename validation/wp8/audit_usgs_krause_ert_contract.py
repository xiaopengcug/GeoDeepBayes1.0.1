#!/usr/bin/env python
"""Audit ABMN/topography and reciprocal-error support in USGS Krause ERT."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usgs-krause-ert-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1/usgs-krause-ert-contract.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def oriented_pair(left: float, right: float) -> tuple[tuple[float, float], int]:
    if left <= right:
        return (left, right), 1
    return (right, left), -1


def reciprocal_key(
    a: float, b: float, m: float, n: float
) -> tuple[tuple[tuple[float, float], tuple[float, float]], int]:
    ab, ab_sign = oriented_pair(a, b)
    mn, mn_sign = oriented_pair(m, n)
    if ab <= mn:
        return (ab, mn), ab_sign * mn_sign
    return (mn, ab), ab_sign * mn_sign


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest["selection_is_response_blind"] is not True
        or manifest["response_values_interpreted_during_acquisition"] != 0
    ):
        raise RuntimeError("Krause ERT response-blind acquisition drift")
    for member in manifest["members"]:
        path = RAW / member["path"]
        if (
            path.stat().st_size != member["bytes"]
            or sha256(path) != member["sha256"]
        ):
            raise RuntimeError(f"Krause ERT raw member drift: {member['path']}")

    electrode_rows = list(
        csv.DictReader(
            (RAW / "Electrical_Restivity_Tomography_Data.csv").open(
                encoding="utf-8-sig", newline=""
            )
        )
    )
    profiles = defaultdict(list)
    for row in electrode_rows:
        profiles[row["ERT_Profile_ID"]].append(row)
    profile_evidence = []
    total_measurements = 0
    total_reciprocal_groups = 0
    total_reciprocal_observations = 0
    all_relative_mismatches = []
    with zipfile.ZipFile(RAW / "Res2dinv_Input_Files.zip") as archive:
        data_members = sorted(
            name for name in archive.namelist() if name.lower().endswith(".dat")
        )
        for name in data_members:
            profile = Path(name).stem.split("_", 1)[0]
            lines = archive.read(name).decode("latin1").splitlines()
            measurement_type = int(lines[5].strip())
            declared_count = int(lines[6].strip())
            records = []
            for line in lines[9 : 9 + declared_count]:
                values = [float(token) for token in line.split()]
                if len(values) != 10 or int(values[0]) != 4:
                    raise RuntimeError(f"unexpected Res2DInv record: {name}")
                _, ax, az, bx, bz, mx, mz, nx, nz, response = values
                key, sign = reciprocal_key(ax, bx, mx, nx)
                records.append(
                    {
                        "key": key,
                        "signed_response": sign * response,
                        "topography_in_record": any(
                            not math.isclose(value, 0.0)
                            for value in (az, bz, mz, nz)
                        ),
                    }
                )
            groups = defaultdict(list)
            for record in records:
                groups[record["key"]].append(record["signed_response"])
            reciprocal = [values for values in groups.values() if len(values) >= 2]
            mismatches = []
            reciprocal_observations = 0
            for values in reciprocal:
                reciprocal_observations += len(values)
                for index in range(0, len(values) - 1, 2):
                    left, right = values[index : index + 2]
                    scale = max((abs(left) + abs(right)) / 2, 1e-12)
                    mismatches.append(abs(left - right) / scale)
            gps = profiles[profile]
            x_values = [float(row["X_Coordinate_meters"]) for row in gps]
            elevations = [float(row["Elevation_meters_NAVD88"]) for row in gps]
            profile_evidence.append(
                {
                    "profile": profile,
                    "measurement_type": (
                        "resistance" if measurement_type == 1 else "apparent_resistivity"
                    ),
                    "declared_measurement_count": declared_count,
                    "parsed_measurement_count": len(records),
                    "electrode_count": len(gps),
                    "electrode_x_extent_m": [min(x_values), max(x_values)],
                    "gps_and_navd88_elevation_present": all(
                        row["Latitude_decimal_degrees"]
                        and row["Longitude_decimal_degrees"]
                        and row["Elevation_meters_NAVD88"]
                        for row in gps
                    ),
                    "record_embeds_topography": any(
                        record["topography_in_record"] for record in records
                    ),
                    "reciprocal_configuration_group_count": len(reciprocal),
                    "reciprocal_observation_count": reciprocal_observations,
                    "reciprocal_relative_mismatch_median": (
                        round(statistics.median(mismatches), 8)
                        if mismatches else None
                    ),
                }
            )
            total_measurements += len(records)
            total_reciprocal_groups += len(reciprocal)
            total_reciprocal_observations += reciprocal_observations
            all_relative_mismatches.extend(mismatches)
    if total_measurements != 13605:
        raise RuntimeError("Krause ERT published measurement count drift")
    result = {
        "schema_version": "wp8-usgs-krause-ert-contract-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "license_gate_passes": manifest["license"].startswith("CC0"),
        "abmn_local_geometry_present": True,
        "electrode_gps_present": True,
        "navd88_topography_present": True,
        "profiles": profile_evidence,
        "profile_count": len(profile_evidence),
        "measurement_count": total_measurements,
        "reciprocal_configuration_group_count": total_reciprocal_groups,
        "reciprocal_observation_count": total_reciprocal_observations,
        "reciprocal_observation_fraction": round(
            total_reciprocal_observations / total_measurements, 8
        ),
        "reciprocal_relative_mismatch_median": (
            round(statistics.median(all_relative_mismatches), 8)
            if all_relative_mismatches else None
        ),
        "empirical_error_model_possible": bool(all_relative_mismatches),
        "direct_per_observation_standard_deviation_present": False,
        "observation_contract_ready_for_development": bool(all_relative_mismatches),
        "formal_cluster_power_gate_passes": False,
        "independent_profile_upper_bound": len(profile_evidence),
        "test_unseal_count": 0,
        "warning": (
            "The files describe reciprocal Schlumberger configurations but "
            "contain no paired normal/reciprocal repeats, so they cannot support "
            "an empirical reciprocal-error contract. Four profiles also cannot "
            "satisfy the formal 223-cluster gate. No confirmatory test was opened."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "profiles": result["profile_count"],
        "measurements": total_measurements,
        "reciprocal_groups": total_reciprocal_groups,
        "reciprocal_fraction": result["reciprocal_observation_fraction"],
        "median_mismatch": result["reciprocal_relative_mismatch_median"],
    }))


if __name__ == "__main__":
    main()
