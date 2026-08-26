#!/usr/bin/env python3
"""生成可确定性重建的 joint diagnostics 健康输入正向对照。"""
from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np


SEED = 20260825
SHAPE = (4, 2000, 3)
OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "evidence" / "positive-control"
INPUT_PATH = OUTPUT_ROOT / "joint-diagnostics-input.npz"
EXPECTED_PATH = OUTPUT_ROOT / "joint-diagnostics-expected.json"


def _npy_bytes(value: np.ndarray) -> bytes:
    stream = BytesIO()
    np.lib.format.write_array(stream, value, allow_pickle=False)
    return stream.getvalue()


def _write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, _npy_bytes(arrays[name]))


def main() -> None:
    rng = np.random.default_rng(SEED)
    channels = rng.standard_normal(SHAPE)
    log_density = rng.standard_normal(SHAPE[:2])
    _write_deterministic_npz(
        INPUT_PATH,
        {"channels": channels, "log_density": log_density},
    )
    expected = {
        "schema_version": "paper01-joint-diagnostics-positive-control/1.0",
        "generator": {
            "seed": SEED,
            "channels_shape": list(SHAPE),
            "log_density_shape": list(SHAPE[:2]),
        },
        "input_sha256": hashlib.sha256(INPUT_PATH.read_bytes()).hexdigest(),
        "thresholds": {
            "rank_normalized_split_rhat_max": 1.1,
            "bulk_ess_min": 100.0,
            "tail_ess_min": 100.0,
            "relative_mcse_max": 0.2,
        },
        "expected": {
            "status": "Passed",
            "checks": {
                "rhat": True,
                "bulk_ess": True,
                "tail_ess": True,
                "relative_mcse": True,
                "mode_visits": True,
            },
            "n_channels": 3,
            "diagnostic_stop_reason": None,
        },
        "scope": (
            "instrument positive control only; not an experiment, independent "
            "reproduction, or geophysical validation"
        ),
    }
    EXPECTED_PATH.write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
