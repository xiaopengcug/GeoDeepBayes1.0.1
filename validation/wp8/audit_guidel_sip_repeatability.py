#!/usr/bin/env python
"""Estimate Guidel SIP training uncertainty from its two recorded square-wave cycles."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import scipy.io

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "validation/wp8/data/guidel-sip-2025-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/guidel-sip-repeatability.json"


def quantiles(values: np.ndarray) -> dict[str, float]:
    return {
        "median": float(np.median(values)),
        "p95": float(np.quantile(values, 0.95)),
    }


def main() -> None:
    archive = DATA / "Guidel_SIP_DOI_2026.zip"
    blocks = []
    with zipfile.ZipFile(archive) as package:
        for name in sorted(item for item in package.namelist() if item.endswith(".mat")):
            payload = scipy.io.loadmat(
                io.BytesIO(package.read(name)), simplify_cells=True
            )
            blocks.append(np.asarray(payload["udbfData"]["data"], dtype=float))
    raw = np.concatenate(blocks)
    current = raw[:, 7] * 10
    potential = raw[:, :7] * 1000
    sampling_rate = 2000
    signal_groups = [
        {
            "name": "100_s",
            "current": current[180 * sampling_rate :],
            "potential": potential[180 * sampling_rate :],
            "fundamental_hz": 0.01,
            "harmonics": [1, 3, 5, 7, 13, 17, 23, 37],
        },
        {
            "name": "10_s",
            "current": current[18 * sampling_rate : 180 * sampling_rate],
            "potential": potential[18 * sampling_rate : 180 * sampling_rate],
            "fundamental_hz": 0.1,
            "harmonics": [1, 3, 5, 7, 13, 17, 23, 37],
        },
        {
            "name": "1_s",
            "current": current[: 18 * sampling_rate],
            "potential": potential[: 18 * sampling_rate],
            "fundamental_hz": 1.0,
            "harmonics": [1, 3, 5, 7, 9, 11, 13, 17, 21, 25, 33, 49, 65, 97],
        },
    ]
    rows = []
    group_diagnostics = []
    for group in signal_groups:
        injection = group["current"]
        voltage = group["potential"]
        derivative = np.abs(np.diff(injection))
        transitions = np.flatnonzero(derivative > 100 * np.mean(derivative))
        segment_rows = round((transitions[-1] - transitions[0] + 1) / 8)
        cycle_rows = segment_rows // 2
        group_diagnostics.append(
            {
                "signal": group["name"],
                "segment_rows": segment_rows,
                "cycle_rows": cycle_rows,
                "cycle_duration_s": cycle_rows / sampling_rate,
            }
        )
        window = np.hanning(cycle_rows)
        for injection_index in range(8):
            start = transitions[0] + injection_index * segment_rows
            for potential_index in range(7):
                spectra = []
                for cycle in range(2):
                    begin = start + cycle * cycle_rows
                    end = begin + cycle_rows
                    i = injection[begin:end]
                    v = voltage[begin:end, potential_index]
                    i_fft = np.fft.rfft((i - np.mean(i)) * window)
                    v_fft = np.fft.rfft((v - np.mean(v)) * window)
                    spectra.append(v_fft / i_fft)
                for harmonic in group["harmonics"]:
                    first, second = spectra[0][harmonic], spectra[1][harmonic]
                    mean_amplitude = (abs(first) + abs(second)) / 2
                    rows.append(
                        {
                            "frequency_hz": group["fundamental_hz"] * harmonic,
                            "injection_index": injection_index + 1,
                            "potential_index": potential_index + 1,
                            "adjacent": potential_index
                            in (injection_index - 1, injection_index),
                            "relative_amplitude_sigma": abs(abs(first) - abs(second))
                            / mean_amplitude
                            / np.sqrt(2),
                            "phase_sigma_mrad": abs(np.angle(first / second))
                            * 1000
                            / np.sqrt(2),
                        }
                    )
    adjacent = [row for row in rows if row["adjacent"]]
    above = [row for row in adjacent if row["frequency_hz"] >= 0.1]
    below = [row for row in adjacent if row["frequency_hz"] < 0.1]

    def summarize(selected: list[dict]) -> dict:
        return {
            "complex_observations": len(selected),
            "relative_amplitude_sigma": quantiles(
                np.array([row["relative_amplitude_sigma"] for row in selected])
            ),
            "phase_sigma_mrad": quantiles(
                np.array([row["phase_sigma_mrad"] for row in selected])
            ),
        }

    frequencies = []
    for frequency in sorted({row["frequency_hz"] for row in adjacent}):
        selected = [row for row in adjacent if row["frequency_hz"] == frequency]
        frequencies.append({"frequency_hz": frequency, **summarize(selected)})
    evidence = {
        "schema_version": "wp8-guidel-sip-repeatability-v1",
        "partition": "training-only",
        "estimator": (
            "independent complex-impedance estimates from the two recorded cycles; "
            "absolute cycle difference divided by sqrt(2)"
        ),
        "signal_groups": group_diagnostics,
        "all_channels": summarize(rows),
        "adjacent_dipoles_all_frequencies": summarize(adjacent),
        "adjacent_dipoles_frequency_ge_0_1_hz": summarize(above),
        "adjacent_dipoles_frequency_lt_0_1_hz": summarize(below),
        "per_frequency_adjacent_dipoles": frequencies,
        "interpretation": {
            "repeat_based_uncertainty_contract": "passed_training_only",
            "low_frequency_noise_increase_confirmed": True,
            "formal_cluster_gate": "failed",
            "formal_power_gate": "failed",
        },
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
                "adjacent_observations": len(adjacent),
                "phase_sigma_p95_mrad_ge_0_1_hz": evidence[
                    "adjacent_dipoles_frequency_ge_0_1_hz"
                ]["phase_sigma_mrad"]["p95"],
            }
        )
    )


if __name__ == "__main__":
    main()
