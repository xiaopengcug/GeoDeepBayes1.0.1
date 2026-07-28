#!/usr/bin/env python
"""Audit Cymric field tables without promoting FDEM to WFEM."""
from __future__ import annotations

import json
import math
from pathlib import Path

from acquire_oedi_cymric_wfem_mapping import ANCHORS, DATA, DOI, LICENSE, SOURCES, sha256

OUTPUT = DATA / "contract-audit.json"
FIELD_FILES = {
    "cymric_field_data1_5hz.txt": {"part": 1, "frequency_hz": 5.0, "orientation_deg": 0},
    "cymric2_field_data_1Hz.txt": {"part": 2, "frequency_hz": 1.0, "orientation_deg": 75},
    "cymric2_field_data_5Hz.txt": {"part": 2, "frequency_hz": 5.0, "orientation_deg": 75},
}


def parse_field_table(text: str, expected_shape: tuple[int, int]) -> dict[str, object]:
    rows = [
        line.replace(",", " ").split()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("%")
    ]
    widths = sorted({len(row) for row in rows})
    numeric_ok = True
    for row in rows:
        try:
            numeric_ok = numeric_ok and all(math.isfinite(float(value)) for value in row)
        except ValueError:
            numeric_ok = False
    actual_width = widths[0] if len(widths) == 1 else -1
    if (len(rows), actual_width) != expected_shape or not numeric_ok:
        raise ValueError("field table shape or finite numeric contract failed")
    return {
        "row_count": len(rows),
        "column_counts": widths,
        "phase_degrees_present": "phase (degrees)" in text.lower(),
    }


def build_audit(data: Path = DATA, *, require_real_contract: bool = True) -> dict[str, object]:
    manifest = json.loads((data / "raw-manifest.json").read_text())
    errors: list[str] = []
    if require_real_contract and data.resolve() != DATA.resolve():
        errors.append("real_data_path")
    if (
        manifest.get("schema_version")
        != "wp8-oedi-cymric-fdem-permanent-training-manifest-v1"
        or manifest.get("mapping_role") != "FDEM-to-WFEM-contract-candidate-only"
        or
        manifest.get("scope") != "permanently-training-only"
        or manifest.get("field_validation_eligible") is not False
        or manifest.get("sealed_test_accessed") is not False
        or manifest.get("fdem_is_wfem") is not False
        or manifest.get("doi") != DOI
        or manifest.get("license", {}).get("spdx") != LICENSE
    ):
        errors.append("boundary_or_source")
    rows = manifest.get("members", [])
    frozen = {row.get("path"): row for row in rows}
    if len(rows) != 6 or len(frozen) != 6 or set(frozen) != set(ANCHORS):
        errors.append("member_inventory")
    for name, (url, size, digest) in ANCHORS.items():
        path = data / name
        row = frozen.get(name, {})
        if (
            not path.is_file()
            or path.stat().st_size != size
            or sha256(path) != digest
            or row.get("source_url") != url
            or row.get("bytes") != size
            or row.get("sha256") != digest
        ):
            errors.append(f"provider_member:{name}")
    tables = []
    for name, design in FIELD_FILES.items():
        path = data / name
        expected = frozen.get(name, {})
        if (
            not path.is_file()
            or path.stat().st_size != expected.get("bytes")
            or sha256(path) != expected.get("sha256")
            or expected.get("source_url") != SOURCES[name]
        ):
            errors.append(f"member:{name}")
            continue
        text = path.read_text(errors="replace")
        expected_shape = (16, 2) if name == "cymric_field_data1_5hz.txt" else (63, 3)
        try:
            parsed = parse_field_table(text, expected_shape)
        except ValueError:
            errors.append(f"table_shape_or_numeric:{name}")
            parsed = {"row_count": 0, "column_counts": [], "phase_degrees_present": False}
        phase_present = parsed["phase_degrees_present"]
        if phase_present != (expected_shape[1] == 3):
            errors.append(f"phase_header:{name}")
        tables.append({
            **design, "path": name, **parsed,
            "distance_unit": "m", "response_unit": "V/m",
        })
    contract = {
        "source_current": False,
        "phase_or_complex_response_complete": False,
        "absolute_receiver_geometry": False,
        "absolute_source_geometry": False,
        "geometric_factor": False,
        "distance_from_wellhead": True,
        "ex_amplitude_v_per_m": True,
        "frequency": True,
        "relative_orientation": True,
    }
    return {
        "schema_version": "wp8-oedi-cymric-fdem-wfem-mapping-audit-v1",
        "audit_mode": "real-provider-contract" if require_real_contract else "test-structure-only",
        "scope": "permanently-training-only",
        "doi": DOI,
        "license": LICENSE,
        "method_identity": {"observed": "FDEM", "mapped_to_wfem": False},
        "field_tables": tables,
        "configuration_figures": 2,
        "contract_fields": contract,
        "missing_required_wfem_fields": [
            key for key in (
                "source_current", "phase_or_complex_response_complete", "absolute_receiver_geometry",
                "absolute_source_geometry", "geometric_factor"
            ) if not contract[key]
        ],
        "independent_site_cluster_upper_bound": 1 if require_real_contract else "not_assessed",
        "formal_status": "blocked",
        "field_validation_eligible": False,
        "sealed_test_accessed": False if require_real_contract else "not_assessed",
        "errors": errors,
        "structure_audit_passed": not errors,
    }


def write_immutable_contract(path: Path, value: dict[str, object]) -> None:
    if value.get("audit_mode") != "real-provider-contract":
        raise RuntimeError("test structure audit cannot be written as formal evidence")
    body = (json.dumps(value, indent=2) + "\n").encode()
    if path.exists() and path.read_bytes() != body:
        raise RuntimeError("immutable OEDI Cymric contract audit drift")
    if not path.exists():
        path.write_bytes(body)


def main() -> None:
    value = build_audit()
    if not value["structure_audit_passed"]:
        raise SystemExit(json.dumps(value))
    write_immutable_contract(OUTPUT, value)
    print(json.dumps({"tables": len(value["field_tables"]), "formal_status": value["formal_status"]}))


if __name__ == "__main__":
    main()
