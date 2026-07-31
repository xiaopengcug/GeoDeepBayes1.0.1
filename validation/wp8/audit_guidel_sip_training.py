#!/usr/bin/env python
"""Training-only payload audit for the frozen Guidel square-wave SIP release."""
from __future__ import annotations

import io
import json
import re
import tarfile
import zipfile
from pathlib import Path

import numpy as np
import scipy.io

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/guidel-sip-2025-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/guidel-sip-training-diagnostics.json"


def main() -> None:
    manifest = json.loads((DATA / "raw-manifest.json").read_text(encoding="utf-8"))
    archive = DATA / "Guidel_SIP_DOI_2026.zip"
    monitoring = DATA / "guidel_sip_monitoring_data.csv.tgz"
    with tarfile.open(monitoring, "r:gz") as package:
        monitoring_csv = package.getmember("guidel_sip_monitoring_data.csv")
    with zipfile.ZipFile(archive) as package:
        mat_names = sorted(name for name in package.namelist() if name.endswith(".mat"))
        code_name = next(name for name in package.namelist() if name.endswith(".m"))
        code = package.read(code_name).decode("utf-8", errors="strict")
        files = []
        channel_names = set()
        sample_rates = set()
        total_rows = total_values = finite_values = 0
        starts, ends = [], []
        for name in mat_names:
            payload = scipy.io.loadmat(
                io.BytesIO(package.read(name)), simplify_cells=True
            )
            header, data = payload["udbfHeader"], payload["udbfData"]
            values = np.asarray(data["data"], dtype=float)
            names = tuple(str(value) for value in np.atleast_1d(header["Name"]))
            rate = int(header["SampleRate"])
            rows, channels = values.shape
            finite = int(np.isfinite(values).sum())
            files.append(
                {
                    "path": name,
                    "rows": rows,
                    "channels": channels,
                    "finite_values": finite,
                    "sample_rate_hz": rate,
                }
            )
            channel_names.add(names)
            sample_rates.add(rate)
            total_rows += rows
            total_values += values.size
            finite_values += finite
            starts.append(float(header["TimeFirstSample"]))
            ends.append(float(header["TimeLastSample"]))

    required_code_tokens = [
        "nb_inj= 8",
        "nb_pot= 7",
        "A= 101:108",
        "B= 201:208",
        "M= 111:117",
        "N= 211:217",
        "sqwasip_data= nan(nb_inj*nb_pot,65)",
        "phase_trend_coef=",
    ]
    missing = [token for token in required_code_tokens if token not in code]
    if missing:
        raise RuntimeError(f"Guidel processing contract drift: {missing}")
    harmonic_groups = [
        [int(value) for value in re.findall(r"\d+", match)]
        for match in re.findall(r"ind_harm_u[13]= \[([^\]]+)\]", code)
    ]
    selected_frequencies = len(harmonic_groups[0]) * 2 + len(harmonic_groups[1])
    unique_channels = sorted(next(iter(channel_names))) if len(channel_names) == 1 else []
    electrodes = []
    for index in range(8):
        depth = 0.23 + 0.10 * index
        electrodes.extend(
            [
                {"id": 101 + index, "role": "A", "xyz_m": [0.0, 0.0, -depth]},
                {"id": 201 + index, "role": "B", "xyz_m": [0.5, 0.0, -depth]},
            ]
        )
    for index in range(7):
        depth = 0.28 + 0.10 * index
        electrodes.extend(
            [
                {"id": 111 + index, "role": "M", "xyz_m": [0.0, 0.0, -depth]},
                {"id": 211 + index, "role": "N", "xyz_m": [0.5, 0.0, -depth]},
            ]
        )
    evidence = {
        "schema_version": "wp8-guidel-sip-training-diagnostics-v1",
        "doi": manifest["doi"],
        "license": manifest["license"],
        "site": manifest["site"],
        "partition": "training-only",
        "raw_file_count": len(files),
        "sample_rate_hz": next(iter(sample_rates)) if len(sample_rates) == 1 else None,
        "rows_per_file": sorted({entry["rows"] for entry in files}),
        "channel_count": len(unique_channels),
        "channel_names": unique_channels,
        "total_time_sample_rows": total_rows,
        "total_scalar_values": total_values,
        "finite_scalar_values": finite_values,
        "nonfinite_scalar_values": total_values - finite_values,
        "nominal_duration_minutes": total_rows / next(iter(sample_rates)) / 60,
        "long_term_monitoring_csv_bytes": monitoring_csv.size,
        "long_term_monitoring_rows_available": 0,
        "header_time_monotonic": starts == sorted(starts) and ends == sorted(ends),
        "processing_contract": {
            "current_injection_dipoles": 8,
            "potential_dipoles": 7,
            "abmn_quadrupoles": 56,
            "selected_frequency_count": selected_frequencies,
            "complex_observations_after_processing": 56 * selected_frequencies,
            "electrode_ids": {
                "A": [101, 108],
                "B": [201, 208],
                "M": [111, 117],
                "N": [211, 217],
            },
            "amplifier_phase_correction_present": True,
        },
        "geometry_contract": {
            "coordinate_system": (
                "local Cartesian; x spans the two vertical rods, y=0, "
                "z=0 at ground surface and positive upward"
            ),
            "rod_separation_m": 0.5,
            "electrode_ring_spacing_m": 0.05,
            "electrode_depth_range_m": [0.23, 0.93],
            "current_dipole_depth_spacing_m": 0.10,
            "potential_dipole_depth_spacing_m": 0.10,
            "electrodes": electrodes,
            "source": "10.1093/gji/ggag060 section 2.2-2.3 plus supplied Matlab ID arrays",
            "relative_geometry_reconstructable_without_interpolation": True,
        },
        "contract_gaps": {
            "absolute_geographic_coordinates": "absent_but_not_required_for_local_forward_geometry",
            "explicit_observation_uncertainty": "absent",
            "normal_reciprocal_or_repeat_acquisitions": "absent",
            "reusable_data_license": "CC BY-NC-SA 4.0",
            "independent_field_sites": 1,
        },
        "interpretation": {
            "raw_waveform_contract": "passed_training_only",
            "frequency_to_quadrupole_key": "passed_training_only",
            "field_geometry_contract": "passed_training_only",
            "uncertainty_contract": "failed",
            "formal_cluster_gate": "failed",
            "formal_power_gate": "failed",
        },
        "files": files,
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
                "raw_files": len(files),
                "time_rows": total_rows,
                "quadrupoles": 56,
                "frequencies": selected_frequencies,
            }
        )
    )


if __name__ == "__main__":
    main()
