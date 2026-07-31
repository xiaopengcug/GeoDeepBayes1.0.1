#!/usr/bin/env python
"""Audit NTGS Kroda and Arunta TDIP payload contracts without treating lines as clusters."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/ntgs-tdip-training-candidates-v1"
MANIFEST = RAW / "raw-manifest.json"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/ntgs-tdip-training-candidates.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def header_fields(text: str) -> list[str]:
    lines = text.splitlines()
    return re.split(r"\s+", lines[2].strip()) if len(lines) >= 3 else []


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for member in manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            raise RuntimeError(f"NTGS TDIP frozen member drift: {member['path']}")

    kroda_path = RAW / "kroda-cr2018-0418-geophysics.zip"
    with zipfile.ZipFile(kroda_path) as archive:
        kroda_dat = [name for name in archive.namelist() if name.lower().endswith(".dat")]
        kroda_rows = 0
        kroda_dates = set()
        kroda_headers = []
        for name in kroda_dat:
            text = archive.read(name).decode("utf-8", errors="replace")
            lines = text.splitlines()
            kroda_rows += max(0, len(lines) - 3)
            match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", lines[0])
            if match:
                kroda_dates.add(match.group(1))
            kroda_headers.append(header_fields(text))

    arunta_path = RAW / "arunta-cr2024-0690-geophysics.zip"
    with zipfile.ZipFile(arunta_path) as archive:
        names = archive.namelist()
        arunta_raw = [name for name in names if "/Raw/" in name and name.endswith(".gdd")]
        arunta_esf = [name for name in names if "/ESF/" in name and name.endswith(".dat")]
        raw_dates = Counter()
        raw_contracts = []
        for name in arunta_raw:
            text = archive.read(name).decode("latin1", errors="replace")
            lines = text.splitlines()
            match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
            if match:
                raw_dates[match.group(1)] += 1
            raw_contracts.append(
                {
                    "windows_20": "Windows: 20" in lines[1],
                    "delay_ms_40": "Delay (ms): 40" in lines[1],
                    "timing_present": "Timing (ms):" in lines[1],
                    "vp_error_present": "ErrVp" in lines[3],
                    "chargeability_error_present": "ErrM" in lines[3],
                    "stack_count_present": "Stack" in lines[3],
                    "window_columns_20": all(f"M{i:02d}" in lines[3] for i in range(1, 21)),
                }
            )
        esf_headers = [
            header_fields(archive.read(name).decode("latin1", errors="replace"))
            for name in arunta_esf
        ]

    required_kroda = {
        "C1X", "C1Y", "C2X", "C2Y", "P1X", "P1Y", "P2X", "P2Y",
        "I", "Vp", "SD", "Nstack", *(f"IP{i}" for i in range(1, 21)),
    }
    required_arunta_esf = {
        "C1X", "C1Y", "C2X", "C2Y", "P1X", "P1Y", "P2X", "P2Y",
        "I", "Vp", "SD", "Nstack", *(f"IP{i}" for i in range(1, 21)),
    }
    result = {
        "schema_version": "wp8-ntgs-tdip-training-candidates-audit-v1",
        "raw_manifest_sha256": sha256(MANIFEST),
        "repository_access": {
            "publicly_downloadable": True,
            "statutory_open_file_reports": True,
            "explicit_reuse_license_on_item_pages": False,
            "formal_license_gate_passes": False,
        },
        "kroda_2018": {
            "report_id": "CR2018-0418",
            "survey_count": 1,
            "line_file_count": len(kroda_dat),
            "observation_row_count": kroda_rows,
            "acquisition_date_count": len(kroda_dates),
            "all_files_have_contract_fields": all(
                required_kroda.issubset(set(fields)) for fields in kroda_headers
            ),
            "window_count": 20,
            "window_widths_ms_present": True,
            "integral_range_ms": [590, 1540],
        },
        "arunta_2024": {
            "report_id": "CR2024-0690",
            "survey_count": 1,
            "raw_gdd_file_count": len(arunta_raw),
            "processed_esf_line_count": len(arunta_esf),
            "raw_acquisition_date_count": len(raw_dates),
            "all_raw_files_have_contract_fields": all(
                all(contract.values()) for contract in raw_contracts
            ),
            "all_esf_files_have_geometry_windows_and_sd": all(
                required_arunta_esf.issubset(set(fields)) for fields in esf_headers
            ),
            "window_count": 20,
            "delay_ms": 40,
        },
        "independent_survey_upper_bound": 2,
        "minimum_required_independent_clusters": 223,
        "formal_observation_contract_ready": False,
        "formal_cluster_power_gate_passes": False,
        "selection_role": "training_candidates_only",
        "formal_test_endpoints_inspected": False,
        "test_unseal_count": 0,
        "conclusion": (
            "Both payloads expose unusually complete TDIP geometry, 20-window decay, "
            "current, primary-voltage, stacking and error/repeatability fields. They "
            "are only two campaigns, and GEMIS item pages do not declare a reusable "
            "license for these company-submitted statutory reports. They therefore "
            "remain training candidates and contribute no formal clusters."
        ),
    }
    if (
        result["kroda_2018"]["line_file_count"] != 4
        or result["kroda_2018"]["all_files_have_contract_fields"] is not True
        or result["arunta_2024"]["raw_gdd_file_count"] != 15
        or result["arunta_2024"]["processed_esf_line_count"] != 14
        or result["arunta_2024"]["raw_acquisition_date_count"] != 15
        or result["arunta_2024"]["all_raw_files_have_contract_fields"] is not True
        or result["arunta_2024"]["all_esf_files_have_geometry_windows_and_sd"] is not True
    ):
        raise RuntimeError("NTGS TDIP candidate structure drift")
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "kroda_rows": kroda_rows,
                "arunta_raw_dates": len(raw_dates),
                "formal_clusters": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
