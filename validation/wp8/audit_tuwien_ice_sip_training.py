#!/usr/bin/env python
"""Audit the TU Wien laboratory SIP imaging dataset as a solver reference."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/tuwien-ice-sip-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/tuwien-ice-sip-training-diagnostics.json"


def parse_ohm(text: str) -> tuple[np.ndarray, np.ndarray]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    electrode_count = int(lines[0])
    electrodes = np.array(
        [[float(value) for value in line.split()] for line in lines[2 : 2 + electrode_count]]
    )
    offset = 2 + electrode_count
    quadrupole_count = int(lines[offset])
    quadrupoles = np.array(
        [
            [float(value) for value in line.split()]
            for line in lines[offset + 2 : offset + 2 + quadrupole_count]
        ]
    )
    return electrodes, quadrupoles


def main() -> None:
    manifest = json.loads((DATA / "raw-manifest.json").read_text(encoding="utf-8"))
    archive = DATA / "03_imaging.zip"
    profiles = []
    electrode_reference = quadrupole_reference = None
    with zipfile.ZipFile(archive) as package:
        names = sorted(name for name in package.namelist() if name.endswith(".ohm"))
        for name in names:
            electrodes, quadrupoles = parse_ohm(package.read(name).decode("utf-8"))
            if electrode_reference is None:
                electrode_reference = electrodes
                quadrupole_reference = quadrupoles[:, :4]
            if not np.array_equal(electrodes, electrode_reference):
                raise RuntimeError("TU Wien SIP electrode geometry drift")
            if not np.array_equal(quadrupoles[:, :4], quadrupole_reference):
                raise RuntimeError("TU Wien SIP ABMN inventory drift")
            profiles.append(
                {
                    "path": name,
                    "frequency_hz": int(Path(name).stem.split("_")[-1]) / 1000,
                    "quadrupoles": len(quadrupoles),
                    "finite_responses": int(np.isfinite(quadrupoles[:, 4:]).sum()),
                }
            )
    evidence = {
        "schema_version": "wp8-tuwien-ice-sip-training-diagnostics-v1",
        "doi": manifest["doi"],
        "license": manifest["license"],
        "selection_role": "laboratory_solver_reference_only",
        "partition": "training-only",
        "sample_count": 1,
        "electrode_count": int(len(electrode_reference)),
        "electrode_dimensions": 3,
        "quadrupoles_per_frequency": int(len(quadrupole_reference)),
        "frequency_count": len(profiles),
        "frequency_range_hz": [
            min(item["frequency_hz"] for item in profiles),
            max(item["frequency_hz"] for item in profiles),
        ],
        "complex_observation_count": sum(item["quadrupoles"] for item in profiles),
        "response_fields": ["impedance_magnitude_ohm", "phase_mrad_negative_sign_convention"],
        "mesh_present": True,
        "geometry_constant_across_frequencies": True,
        "abmn_constant_across_frequencies": True,
        "explicit_uncertainty": False,
        "field_profile_link": False,
        "formal_cluster_contribution": 0,
        "decision": "parser_geometry_and_solver_convention_reference_only",
        "profiles": profiles,
        "buffer_values_read": 0,
        "calibration_values_read": 0,
        "test_values_read": 0,
        "test_unseal_count": 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "electrodes": evidence["electrode_count"],
                "quadrupoles": evidence["quadrupoles_per_frequency"],
                "frequencies": evidence["frequency_count"],
                "complex_observations": evidence["complex_observation_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
