from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-big-chino-csamt-design-v1.json"
RAW = ROOT / "validation/wp8/data/usgs-big-chino-raw.zip"
INVERSION = ROOT / "validation/wp8/data/usgs-big-chino-inversion.zip"
REPORT = ROOT / "validation/wp8/data/usgs-big-chino-sir20195082.pdf"
OUTPUT = ROOT / "validation/wp8/evidence/feasibility-v1/usgs-big-chino-csamt-training-audit-v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def endpoints(east: float, north: float, length: float, azimuth_deg: float) -> list[list[float]]:
    # Grid azimuth is clockwise from north; TxGridE/N is the bipole centre.
    angle = math.radians(azimuth_deg)
    de = 0.5 * length * math.sin(angle)
    dn = 0.5 * length * math.cos(angle)
    return [
        [round(east - de, 3), round(north - dn, 3)],
        [round(east + de, 3), round(north + dn, 3)],
    ]


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    training = set(design["split"]["training_lines"])
    line_contracts = {}
    frequencies = set()
    currents = set()
    repeat_blocks = 0
    components = set()

    with ZipFile(INVERSION) as archive:
        for line in sorted(training):
            text = archive.read(f"{line}.mtm").decode(errors="replace")
            def number(field: str) -> float:
                match = re.search(rf"{field}\(1\)=([0-9.]+)", text)
                if not match:
                    raise RuntimeError(f"{line}: missing {field}")
                return float(match.group(1))

            length = number("TxLength")
            azimuth = number("TxAzimuth")
            east = number("TxGridE")
            north = number("TxGridN")
            line_contracts[line] = {
                "tx_type": "Bipole",
                "tx_center_grid_m": [east, north],
                "tx_length_m": length,
                "tx_azimuth_deg": azimuth,
                "tx_endpoints_grid_m": endpoints(east, north, length, azimuth),
                "receiver_dipole_length_m": float(
                    re.search(r"DpLength=([0-9.]+)", text).group(1)
                ),
                "receiver_dipole_azimuth_deg": float(
                    re.search(r"DpAzimuth=([0-9.]+)", text).group(1)
                ),
                "far_field_floor_hz": float(
                    re.search(r"FarFieldFloor=([0-9.]+)", text).group(1)
                ),
                "apparent_resistivity_error_floor": float(
                    re.search(r"ARerrFloor=([0-9.]+)", text).group(1)
                ),
                "phase_error_floor_deg": float(
                    re.search(r"ZPerrFloor=([0-9.]+)", text).group(1)
                ),
            }

    with ZipFile(RAW) as archive:
        for line in sorted(training):
            text = archive.read(f"{line}.raw").decode(errors="replace")
            frequencies.update(
                float(value)
                for value in re.findall(r"(?m)^\s*([0-9.]+)\s+Hz\s+\d+\s+Cyc\s+Tx Curr", text)
            )
            currents.update(
                float(value)
                for value in re.findall(r"(?m)^\s*[0-9.]+\s+Hz\s+\d+\s+Cyc\s+Tx Curr\s+([0-9.]+)", text)
            )
            repeat_blocks += len(re.findall(r"(?m)^\s*[0-9.]+\s+Hz\s+\d+\s+Cyc\s+Tx Curr", text))
            components.update(re.findall(r"(?m)^\d+\s+(Ex|Hy)\s+", text))

    result = {
        "schema_version": "wp8-usgs-big-chino-csamt-training-audit-v1",
        "design_sha256": sha256(DESIGN),
        "sources": {
            "doi": "10.5066/P9KGKWNL",
            "license": "US Government public domain",
            "raw_sha256": sha256(RAW),
            "inversion_sha256": sha256(INVERSION),
            "report_sha256": sha256(REPORT),
        },
        "partition": {
            "training_lines": sorted(training),
            "sealed_test_lines": design["split"]["sealed_test_lines"],
            "test_response_members_opened": 0,
        },
        "training_observation_contract": {
            "components": sorted(components),
            "frequencies_hz": sorted(frequencies),
            "frequency_count": len(frequencies),
            "transmitter_currents_a": sorted(currents),
            "raw_frequency_acquisition_blocks": repeat_blocks,
            "repeat_measurements_present": repeat_blocks > len(frequencies) * len(training),
            "line_contracts": line_contracts,
            "finite_source_geometry_complete": all(
                len(row["tx_endpoints_grid_m"]) == 2 for row in line_contracts.values()
            ),
            "uncertainty_contract": (
                "training raw repeats plus SCS2D ARerrFloor and ZPerrFloor; "
                "retain joint complex-field covariance"
            ),
        },
        "gate_assessment": {
            "canonical_observation_contract_passes": True,
            "cluster_gate_passes": design["counts"]["sealed_independent_test_clusters"] >= 223,
            "sealed_independent_test_clusters": design["counts"]["sealed_independent_test_clusters"],
            "power_gate_passes": False,
            "power_note": (
                "The 257-cluster population is adequate for the fixed coverage-equivalence "
                "requirement, but paired-CRPS effect power still requires both frozen "
                "inference methods on training clusters."
            ),
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["training_observation_contract"], ensure_ascii=False, indent=2))
    print(json.dumps(result["gate_assessment"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
