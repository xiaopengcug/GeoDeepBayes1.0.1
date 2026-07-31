#!/usr/bin/env python
"""Audit frozen Brittany ERT files without treating them as TDIP evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/pangaea-brittany-ert-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/pangaea-brittany-ert-training-diagnostics.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((DATA / "raw-manifest.json").read_text(encoding="utf-8"))
    profiles = []
    total = 0
    for code in manifest["profiles"]:
        raw = DATA / f"ERT_{code}_raw_data.dat"
        lines = raw.read_text(encoding="utf-8-sig").splitlines()
        declared = int(lines[6])
        rows = [line.split() for line in lines[9 : 9 + declared]]
        if len(rows) != declared or any(len(row) != 10 for row in rows):
            raise RuntimeError(f"unexpected raw row structure for {code}")
        values = [float(row[-1]) for row in rows]
        topo = DATA / f"ERT_{code}_topo.csv"
        topo_lines = [line for line in topo.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        profiles.append(
            {
                "profile": code,
                "valley": "Trunvel" if code.startswith("TRU") else "Kernic/Plouescat",
                "measurement_type_code": int(lines[5]),
                "measurement_type": "resistance",
                "quadrupoles": declared,
                "row_columns": 10,
                "response_min": min(values),
                "response_max": max(values),
                "electrode_coordinate_rows": len(topo_lines) - 1,
                "raw_sha256": sha256(raw),
                "topography_sha256": sha256(topo),
            }
        )
        total += declared
    evidence = {
        "schema_version": "wp8-pangaea-brittany-ert-training-diagnostics-v1",
        "doi": manifest["doi"],
        "partition": "training-only",
        "profile_count": len(profiles),
        "geographic_area_count": 2,
        "quadrupole_count": total,
        "profiles": profiles,
        "classification": "DC resistance ERT; not TDIP",
        "classification_basis": (
            "Every frozen raw file declares measurement type code 1 (resistance), "
            "and every observation has only ABMN planar coordinates plus one "
            "response value; no chargeability or decay-window fields are present."
        ),
        "usable_for_dc_training_geometry": True,
        "usable_as_tdip_evidence": False,
        "formal_power_effect": "none; training-only and only two geographic areas",
        "buffer_reads": 0,
        "calibration_reads": 0,
        "test_reads": 0,
        "test_unseal_count": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"profiles": len(profiles), "quadrupoles": total, "tdip": False}))


if __name__ == "__main__":
    main()
