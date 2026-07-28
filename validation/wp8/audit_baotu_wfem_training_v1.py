#!/usr/bin/env python
"""Audit only pre-frozen Baotu WFEM training line files."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = (
    ROOT
    / "_bmad-output/planning-artifacts/research/open-data/wfem"
    / "Zenodo_BaotuSpring_WFEM_2025"
)
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
DESIGN = EVIDENCE / "baotu-wfem-line-split-v1.json"
OUT = EVIDENCE / "baotu-wfem-training-audit-v1.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if not design["selection_frozen_before_response_interpretation"]:
        raise RuntimeError("Baotu WFEM design is not frozen")
    records = []
    all_frequencies = set()
    total_rows = 0
    for item in design["lines"]:
        if item["role"] != "train":
            continue
        path = DATA / item["name"]
        if sha(path) != item["sha256"]:
            raise RuntimeError(f"Baotu WFEM integrity drift: {path.name}")
        stations = set()
        frequencies = set()
        rho_min = math.inf
        rho_max = -math.inf
        rows = 0
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["Station", "Fre", "Rho_mn"]:
                raise RuntimeError(f"Baotu WFEM schema drift: {path.name}")
            for row in reader:
                station = row["Station"].strip()
                frequency = float(row["Fre"])
                rho = float(row["Rho_mn"])
                if not station or not math.isfinite(frequency) or not math.isfinite(rho):
                    raise RuntimeError(f"invalid Baotu training row: {path.name}")
                stations.add(station)
                frequencies.add(frequency)
                rho_min = min(rho_min, rho)
                rho_max = max(rho_max, rho)
                rows += 1
        total_rows += rows
        all_frequencies.update(frequencies)
        records.append(
            {
                "name": item["name"],
                "sha256": item["sha256"],
                "rows_interpreted": rows,
                "unique_station_labels": len(stations),
                "frequency_count": len(frequencies),
                "frequency_range_hz": [min(frequencies), max(frequencies)],
                "apparent_resistivity_range_ohm_m": [rho_min, rho_max],
            }
        )
    result = {
        "schema_version": "wp8-baotu-wfem-training-audit-v1",
        "design_sha256": sha(DESIGN),
        "training_line_count": len(records),
        "training_rows_interpreted": total_rows,
        "training_frequency_count": len(all_frequencies),
        "training_frequency_range_hz": [
            min(all_frequencies),
            max(all_frequencies),
        ],
        "records": records,
        "observed_columns": ["Station", "Fre", "Rho_mn"],
        "receiver_coordinates_present": False,
        "source_geometry_present": False,
        "source_current_present": False,
        "phase_present": False,
        "field_component_present": False,
        "geometric_factor_definition_present": False,
        "per_observation_error_present": False,
        "formal_observation_contract_ready": False,
        "line_level_test_cluster_upper_bound": design[
            "line_level_test_cluster_upper_bound"
        ],
        "required_test_clusters": 223,
        "cluster_gate_passed": False,
        "spatial_correlation_audit_possible": False,
        "dimensionality_gate_passed": False,
        "paired_crps_effect_size_available": False,
        "power_gate_passed": False,
        "buffer_response_values_interpreted": 0,
        "calibration_response_values_interpreted": 0,
        "test_response_values_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "training_lines": len(records),
                "training_rows": total_rows,
                "frequency_count": len(all_frequencies),
                "frequency_range_hz": result["training_frequency_range_hz"],
                "formal_contract_ready": False,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
