#!/usr/bin/env python
# /// script
# dependencies = ["netCDF4==1.7.2", "numpy==2.4.1"]
# ///
"""Training-only diagnostics for the frozen USGS TEMPEST 2022 NetCDF."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-aem-training-expansion-design-v1.json"
)
DATA = ROOT / "validation/wp8/data/usgs-aem-training-expansion-v1/files"
OUT = (
    ROOT
    / "validation/wp8/evidence/feasibility-v1"
    / "usgs-tempest-2022-training-diagnostics-v1.json"
)
SCIENCEBASE_ID = "62ffc245d34e37cba73e1fa0"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def values(variable) -> np.ndarray:
    return np.asarray(np.ma.filled(variable[:], np.nan), dtype=np.float64)


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if (
        design["calibration_responses_interpreted"] != 0
        or design["test_responses_interpreted"] != 0
        or design["test_unseal_count"] != 0
    ):
        raise RuntimeError("USGS AEM training design is not sealed")
    survey = next(
        row for row in design["training_surveys"]
        if row["sciencebase_id"] == SCIENCEBASE_ID
    )
    payload = survey["payload"]
    path = DATA / f"{SCIENCEBASE_ID}__{payload['name']}"
    if not path.is_file() or path.stat().st_size != payload["size"]:
        raise RuntimeError("TEMPEST 2022 training payload incomplete")

    records = []
    total_pairs = 0
    total_rows = 0
    all_lines = set()
    with Dataset(path) as dataset:
        tabular = dataset.groups["survey"].groups["tabular"]
        for group_name in ("6", "7", "8"):
            group = tabular.groups[group_name]
            line = values(group.variables["line"])
            easting = values(group.variables["easting"])
            northing = values(group.variables["northing"])
            gate_times = values(group.variables["gate_times"])
            xs = values(group.variables["observed_EMSystem_1_XS"])
            zs = values(group.variables["observed_EMSystem_1_ZS"])
            xs_noise = values(group.variables["noise_EMSystem_1_XS"])
            zs_noise = values(group.variables["noise_EMSystem_1_ZS"])
            valid_xs = np.isfinite(xs) & np.isfinite(xs_noise) & (xs_noise > 0)
            valid_zs = np.isfinite(zs) & np.isfinite(zs_noise) & (zs_noise > 0)
            standardized_zs = np.where(valid_zs, zs / zs_noise, np.nan)
            scalar = np.nanmedian(
                np.sign(standardized_zs) * np.log1p(np.abs(standardized_zs)),
                axis=1,
            )
            correlations = []
            for lag in (1, 2, 4, 8, 16, 32, 64, 128, 256):
                selected = (
                    np.isfinite(scalar[:-lag])
                    & np.isfinite(scalar[lag:])
                    & np.isfinite(easting[:-lag])
                    & np.isfinite(easting[lag:])
                    & np.isfinite(northing[:-lag])
                    & np.isfinite(northing[lag:])
                    & (line[:-lag] == line[lag:])
                )
                if int(selected.sum()) < 100:
                    continue
                distance = (
                    np.sqrt(
                        (easting[:-lag][selected] - easting[lag:][selected]) ** 2
                        + (
                            northing[:-lag][selected]
                            - northing[lag:][selected]
                        )
                        ** 2
                    )
                    / 1000.0
                )
                correlations.append(
                    {
                        "index_lag": lag,
                        "pair_count": int(selected.sum()),
                        "median_distance_km": float(np.median(distance)),
                        "correlation": float(
                            np.corrcoef(
                                scalar[:-lag][selected],
                                scalar[lag:][selected],
                            )[0, 1]
                        ),
                    }
                )
            candidates = [
                row["median_distance_km"]
                for row in correlations
                if np.isfinite(row["correlation"])
                and np.isfinite(row["median_distance_km"])
                and abs(row["correlation"]) <= 0.05
            ]
            unique_lines = {
                int(value) for value in line[np.isfinite(line)].tolist()
            }
            pairs = int(valid_xs.sum() + valid_zs.sum())
            total_pairs += pairs
            total_rows += len(line)
            all_lines.update(unique_lines)
            records.append(
                {
                    "group": f"/survey/tabular/{group_name}",
                    "rows": int(len(line)),
                    "unique_lines": len(unique_lines),
                    "gate_count": int(len(gate_times)),
                    "gate_range_seconds": [
                        float(np.min(gate_times)),
                        float(np.max(gate_times)),
                    ],
                    "components": ["XS", "ZS"],
                    "valid_response_noise_pairs": pairs,
                    "zs_standardized_absolute_p95": float(
                        np.nanquantile(np.abs(standardized_zs), 0.95)
                    ),
                    "along_line_correlations": correlations,
                    "training_correlation_range_km": (
                        candidates[0] if candidates else None
                    ),
                }
            )
    result = {
        "schema_version": "wp8-usgs-tempest-2022-training-diagnostics-v1",
        "design_sha256": sha(DESIGN),
        "sciencebase_id": SCIENCEBASE_ID,
        "path": path.relative_to(ROOT).as_posix(),
        "payload_sha256": sha(path),
        "system": "TEMPEST",
        "processed_group_count": 3,
        "processed_rows": total_rows,
        "unique_lines": len(all_lines),
        "components": ["XS", "ZS"],
        "gate_count": 15,
        "valid_response_noise_pairs": total_pairs,
        "records": records,
        "formal_response_uncertainty_contract_ready": True,
        "paired_crps_effect_size_available": False,
        "power_gate_passed": False,
        "calibration_responses_interpreted": 0,
        "test_responses_interpreted": 0,
        "test_unseal_count": 0,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "processed_rows": total_rows,
                "unique_lines": len(all_lines),
                "valid_response_noise_pairs": total_pairs,
                "formal_contract_ready": True,
                "power_gate_passed": False,
                "test_unseal_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
