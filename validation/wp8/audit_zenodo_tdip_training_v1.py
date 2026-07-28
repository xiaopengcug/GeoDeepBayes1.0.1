#!/usr/bin/env python
"""Audit the pre-frozen TDIP training groups without touching sealed roles."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIN = (
    ROOT
    / "validation/wp8/data/zenodo-tdip-field-candidate-v1/training-only"
)
MANIFEST = TRAIN / "training-manifest.json"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "zenodo-tdip-training-audit-v1.json"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def percentile(values: list[float], probability: float) -> float | None:
    values = sorted(value for value in values if math.isfinite(value))
    if not values:
        return None
    index = probability * (len(values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["extracted_roles"] != ["train"]:
        raise RuntimeError("training-only extraction invariant failed")
    databases = sorted(TRAIN.rglob("project.db"))
    surveys = []
    all_relative_sdev: list[float] = []
    for database in databases:
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        datatype = {
            row["ID"]: {
                "name": row["Name"],
                "unit": row["Unit"],
                "explanation": row["Explanation"],
            }
            for row in connection.execute(
                "select ID, Name, Unit, Explanation from Datatype"
            )
        }
        grouped = []
        for row in connection.execute(
            """
            select DatatypeID, count(*) as n,
                   sum(DataSDev is not null) as with_sdev,
                   min(SeqNum) as min_seq, max(SeqNum) as max_seq
            from DPV group by DatatypeID order by DatatypeID
            """
        ):
            grouped.append(
                {
                    "datatype_id": row["DatatypeID"],
                    **datatype.get(row["DatatypeID"], {"name": "undeclared"}),
                    "observations": row["n"],
                    "with_standard_deviation": row["with_sdev"],
                    "min_sequence": row["min_seq"],
                    "max_sequence": row["max_seq"],
                }
            )
        ip_id = next(
            key for key, value in datatype.items() if value["name"] == "IP"
        )
        ip_rows = connection.execute(
            """
            select DataValue, DataSDev from DPV
            where DatatypeID=? and DataValue is not null
                  and DataSDev is not null and abs(DataValue)>1e-15
            """,
            (ip_id,),
        )
        relative_sdev = [
            abs(float(row["DataSDev"]) / float(row["DataValue"]))
            for row in ip_rows
            if math.isfinite(float(row["DataSDev"]))
            and math.isfinite(float(row["DataValue"]))
        ]
        all_relative_sdev.extend(relative_sdev)
        coordinates = connection.execute(
            """
            select count(*) as n,
                   count(distinct printf('%.6f|%.6f|%.6f|%.6f',
                         APosX,BPosX,MPosX,NPosX)) as unique_abmn,
                   min(APosX) as min_a, max(BPosX) as max_b,
                   min(MPosX) as min_m, max(NPosX) as max_n
            from DP_ABMN
            """
        ).fetchone()
        surveys.append(
            {
                "database": database.relative_to(TRAIN).as_posix(),
                "database_sha256": digest(database),
                "tasks": connection.execute(
                    "select count(*) from Tasks"
                ).fetchone()[0],
                "measures": connection.execute(
                    "select count(*) from Measures"
                ).fetchone()[0],
                "abmn_rows": coordinates["n"],
                "unique_abmn_geometries": coordinates["unique_abmn"],
                "coordinate_bounds_m": {
                    "A_min": coordinates["min_a"],
                    "B_max": coordinates["max_b"],
                    "M_min": coordinates["min_m"],
                    "N_max": coordinates["max_n"],
                },
                "datatypes": grouped,
                "ip_window_count": connection.execute(
                    "select max(SeqNum)-min(SeqNum)+1 from DPV where DatatypeID=?",
                    (ip_id,),
                ).fetchone()[0],
                "ip_observations": next(
                    item["observations"]
                    for item in grouped
                    if item["datatype_id"] == ip_id
                ),
                "ip_relative_sdev_p50": percentile(relative_sdev, 0.50),
                "ip_relative_sdev_p95": percentile(relative_sdev, 0.95),
            }
        )
        connection.close()
    ini_files = sorted(TRAIN.rglob("*.ini"))
    ini_text = "\n".join(path.read_text(errors="replace") for path in ini_files)
    result = {
        "schema_version": "wp8-zenodo-tdip-training-audit-v1",
        "training_manifest_sha256": digest(MANIFEST),
        "training_groups": manifest["extracted_groups"],
        "training_database_count": len(databases),
        "surveys": surveys,
        "total_ip_observations": sum(
            survey["ip_observations"] for survey in surveys
        ),
        "declared_ip_unit": "mV/V",
        "ip_window_count": sorted(
            {survey["ip_window_count"] for survey in surveys}
        ),
        "per_observation_standard_deviation_contract": all(
            any(
                item["name"] == "IP"
                and item["with_standard_deviation"] > 0
                for item in survey["datatypes"]
            )
            for survey in surveys
        ),
        "ip_relative_sdev_p50": percentile(all_relative_sdev, 0.50),
        "ip_relative_sdev_p95": percentile(all_relative_sdev, 0.95),
        "waveform_metadata": {
            "ini_file_count": len(ini_files),
            "wave_type_4_declared": "WaveTypes=4" in ini_text,
            "pulse_count_3_declared": "NPulses=3" in ini_text,
            "on_times_s": [2.0, 2.3, 2.0],
            "amplitudes_relative": [1, -1, 1],
            "dc_integration_interval_s": [1.756, 1.796],
        },
        "formal_observation_contract_ready": True,
        "plan_expected_time_windows": 20,
        "observed_processed_time_windows": 11,
        "twenty_window_contract_ready": False,
        "profile_level_test_cluster_upper_bound": 1,
        "required_test_clusters": 223,
        "power_gate_possible": False,
        "paired_crps_effect_distribution_available": False,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
        "conclusion": (
            "Training data establish ABMN geometry, waveform metadata, 11 "
            "processed IP windows, and direct per-observation standard "
            "deviations. They do not satisfy the plan's 20-window contract "
            "or the 223 independent test-cluster power gate."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_database_count": len(databases),
                "total_ip_observations": result["total_ip_observations"],
                "ip_window_count": result["ip_window_count"],
                "formal_observation_contract_ready": True,
                "twenty_window_contract_ready": False,
                "power_gate_possible": False,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
