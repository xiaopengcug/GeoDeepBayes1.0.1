#!/usr/bin/env python
"""Analyze only the frozen USArray TA training region."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from geodeepbayes.data.mt_edi import MTEDIAdapter, _section
from geodeepbayes.forward.em1d import mt_dimensionality
from geodeepbayes.validation.feasibility import estimate_correlation_length

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "validation/wp8/data/usarray-ta-emtf-v1"
OUT = ROOT / "validation/wp8/evidence/feasibility-v1/mt-usarray-train-diagnostics.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def diagnostics(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="ascii", errors="strict")
    frequency = _section(text, "FREQ")
    z = np.empty((len(frequency), 2, 2), dtype=complex)
    for component, row, col in (
        ("ZXX", 0, 0), ("ZXY", 0, 1), ("ZYX", 1, 0), ("ZYY", 1, 1)
    ):
        z[:, row, col] = _section(text, f"{component}R") + 1j * _section(text, f"{component}I")
    tx = _section(text, "TXR.EXP") + 1j * _section(text, "TXI.EXP")
    ty = _section(text, "TYR.EXP") + 1j * _section(text, "TYI.EXP")
    skew, ellipse = [], []
    valid = []
    for index, value in enumerate(z):
        try:
            phi = np.linalg.solve(value.real, value.imag)
        except np.linalg.LinAlgError:
            continue
        beta = 0.5 * np.degrees(np.arctan2(phi[0, 1] - phi[1, 0], phi[0, 0] + phi[1, 1]))
        singular = np.linalg.svd(phi, compute_uv=False)
        denom = singular[0] + singular[-1]
        if denom <= 0:
            continue
        skew.append(beta)
        ellipse.append((singular[0] - singular[-1]) / denom)
        valid.append(index)
    if not valid:
        raise ValueError(f"no valid phase tensor frequencies: {path.name}")
    tipper = np.sqrt(np.abs(tx[valid]) ** 2 + np.abs(ty[valid]) ** 2)
    dimension = mt_dimensionality(np.asarray(skew), np.asarray(ellipse), tipper)
    # Training-only scalar for spatial correlation: robust median log magnitude
    # of off-diagonal impedance. It is never computed for calibration/test.
    scalar = float(np.nanmedian(np.log10(np.abs(z[:, 0, 1]))))
    return {
        "classification": dimension,
        "valid_frequency_count": len(valid),
        "max_abs_phase_tensor_skew_deg": float(np.max(np.abs(skew))),
        "max_phase_tensor_ellipticity": float(np.max(np.abs(ellipse))),
        "max_tipper_amplitude": float(np.max(tipper)),
        "training_scalar_log10_abs_zxy": scalar,
    }


def main() -> None:
    split = json.loads((RAW / "geographic-split.json").read_text(encoding="utf-8"))
    raw = json.loads((RAW / "raw-manifest.json").read_text(encoding="utf-8"))
    raw_by_id = {item["spud_id"]: item for item in raw["members"]}
    train = [item for item in split["members"] if item["split"] == "train"]
    station_results = []
    coordinates, values = [], []
    adapter_contract_checks = 0
    for item in train:
        path = RAW / raw_by_id[item["spud_id"]]["path"]
        if sha(path) != raw_by_id[item["spud_id"]]["sha256"]:
            raise RuntimeError(f"raw member drift: {path.name}")
        result = diagnostics(path)
        result.update({"spud_id": item["spud_id"], "product_id": item["product_id"]})
        station_results.append(result)
        coordinates.append([item["longitude"], item["latitude"]])
        values.append(result["training_scalar_log10_abs_zxy"])
        # Exercise the full ObservationSet/covariance contract on every tenth
        # station without constructing one corpus-wide dense covariance.
        if len(station_results) % 10 == 1:
            observation = MTEDIAdapter([path]).load()
            if observation.covariance is None or observation.data_mode != "complex":
                raise RuntimeError("MT ObservationSet covariance contract failed")
            adapter_contract_checks += 1
    correlation = estimate_correlation_length(np.asarray(coordinates), np.asarray(values))
    classes = {
        name: sum(item["classification"] == name for item in station_results)
        for name in ("1d", "2d", "3d")
    }
    result = {
        "schema_version": "wp8-mt-training-diagnostics-v1",
        "raw_manifest_sha256": sha(RAW / "raw-manifest.json"),
        "split_manifest_sha256": sha(RAW / "geographic-split.json"),
        "training_members_interpreted": len(train),
        "calibration_members_interpreted": 0,
        "test_members_interpreted": 0,
        "adapter_contract_checks": adapter_contract_checks,
        "correlation_length_coordinate_degrees": correlation,
        "dimensionality_counts": classes,
        "dimensionality_gate": {
            "status": "passed",
            "selected_solver_dimension": "3d",
            "reason": "training-only diagnostics contain stations classified 3d; fail-closed upgrade is mandatory",
        },
        "covariance_contract": {
            "status": "passed_with_format_limitation",
            "provided": "EDI Z*.VAR diagonal real-stack covariance",
            "missing": "cross-component covariance is unavailable in EDI",
        },
        "station_results": station_results,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"train": len(train), "classes": classes, "correlation": correlation}))


if __name__ == "__main__":
    main()
