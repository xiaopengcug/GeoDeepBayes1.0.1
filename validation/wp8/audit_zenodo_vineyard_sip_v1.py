"""Fail-closed audit of the public Zenodo vineyard field-SIP release."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/zenodo-vineyard-sip-15731729"
ARCHIVE = DATA / "SIP_Field_data.complete.7z"
EXTRACTED = DATA / "extracted/SIP_Field_data"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/zenodo-vineyard-field-sip-audit-v1.json"
EXPECTED_SIZE = 326_775_934
EXPECTED_MD5 = "ef21c75b57afd66727291d12adf0c7f3"


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def audit_das1(path: Path) -> dict:
    lines = path.read_text(encoding="latin-1").splitlines()
    start = lines.index("#data_start")
    frequency_line = next(line for line in lines[start:] if "Frequency =" in line)
    frequencies = [float(value) for value in re.findall(r"Frequency =\s*([+.0-9]+)", frequency_line)]
    rows = [line for line in lines[start + 1 :] if re.match(r"^\d{6}\s", line)]
    header = "\n".join(lines[start : start + 5])
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "measurement_rows": len(rows),
        "frequencies_hz": frequencies,
        "has_abmn_geometry": all(token in header for token in (" A ", " B ", " M ", " N ")),
        "has_complex_response": "Amplitude" in header and "Phase" in header,
        "has_repeat_uncertainty": "Amp Std." in header and "Phase Std" in header,
    }


def audit_psip(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("X_Value,"))
    rows = list(csv.DictReader(lines[header_index:]))
    frequencies = sorted(
        {float(row["Frequency[Hz]"]) for row in rows if row.get("Frequency[Hz]", "").strip()}
    )
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "spectral_rows": len(rows),
        "frequencies_hz": frequencies,
        "has_magnitude": "Magnitude[ratio]" in rows[0],
        "has_phase": "Phase_Shift[rad]" in rows[0],
        "has_repeat_loop": "Loop" in rows[0],
    }


def main() -> None:
    archive = {
        "path": ARCHIVE.relative_to(ROOT).as_posix(),
        "bytes": ARCHIVE.stat().st_size,
        "md5": digest(ARCHIVE, "md5"),
        "sha256": digest(ARCHIVE, "sha256"),
    }
    assert archive["bytes"] == EXPECTED_SIZE
    assert archive["md5"] == EXPECTED_MD5

    das1 = [audit_das1(path) for path in sorted(EXTRACTED.rglob("*.Data"))]
    psip_path = next(EXTRACTED.rglob("Raw_SIP_FieldData*CoaxialCableSetup.csv"))
    psip = audit_psip(psip_path)
    assert len(das1) == 6
    assert all(item["measurement_rows"] > 0 for item in das1)
    assert all(item["has_abmn_geometry"] and item["has_complex_response"] for item in das1)
    assert all(item["has_repeat_uncertainty"] for item in das1)
    assert psip["spectral_rows"] > 0 and psip["has_magnitude"] and psip["has_phase"]

    result = {
        "schema_version": "wp8-zenodo-vineyard-field-sip-audit-v1",
        "source": {
            "record": "https://zenodo.org/records/15731729",
            "doi": "10.5281/zenodo.15731729",
            "license": "CC-BY-4.0",
        },
        "archive": archive,
        "raw_data": {
            "das1_files": das1,
            "psip": psip,
            "campaign_dates": ["2023-03-16", "2023-03-17", "2023-06-22", "2023-07-13", "2023-08-30"],
            "published_profiles": ["AA'", "BB'"],
            "independent_spatial_cluster_upper_bound": 2,
        },
        "gate_assessment": {
            "observation_pass": True,
            "clusters_pass": False,
            "power_pass": False,
            "reason": (
                "The release provides raw field complex SIP responses, ABMN geometry, and repeat "
                "uncertainty fields, but only two independent spatial profiles. Campaigns, "
                "frequencies, quadrupoles, and duplicate cable setups are repeated observations, "
                "not ten independent spatial clusters; no qualifying prospective power evidence "
                "is included."
            ),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["gate_assessment"], ensure_ascii=False))


if __name__ == "__main__":
    main()
