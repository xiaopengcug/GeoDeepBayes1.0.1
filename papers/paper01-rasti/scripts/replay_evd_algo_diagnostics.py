#!/usr/bin/env python3
"""REV-R1-4/C-001：只读重放 EVD-ALGO-002 的四项稿件诊断值。"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from geodeepbayes.diagnostics import (
    bulk_ess,
    monte_carlo_standard_error,
    rank_normalized_split_rhat,
    tail_ess,
)


def sha256(path: Path) -> str:
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".py", ".md", ".txt", ".yml", ".yaml"}:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-label", required=True)
    args = parser.parse_args()

    source = args.source_root.resolve()
    raw_path = source / "raw-chains.npz"
    metrics_path = source / "metrics.json"
    config_path = args.config.resolve()
    before = {path.name: sha256(path) for path in (raw_path, metrics_path)}

    with np.load(raw_path, allow_pickle=False) as payload:
        draws = payload["draws"]
    rhat = np.asarray(rank_normalized_split_rhat(draws))
    bulk = np.asarray(bulk_ess(draws))
    tail = np.asarray(tail_ess(draws))
    mcse = np.asarray(monte_carlo_standard_error(draws))
    sd = draws.reshape(-1, draws.shape[-1]).std(axis=0, ddof=1)
    replayed = {
        "max_rhat": float(np.max(rhat)),
        "min_bulk_ess": float(np.min(bulk)),
        "min_tail_ess": float(np.min(tail)),
        "max_relative_mcse": float(np.max(mcse / np.maximum(sd, 1e-12))),
    }
    if not all(np.isfinite(value) for value in replayed.values()):
        raise RuntimeError("EVD-ALGO-002 重放产生非有限诊断")

    recorded_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    recorded = {name: recorded_metrics[name] for name in replayed}
    config = json.loads(config_path.read_text(encoding="utf-8"))
    thresholds = config["thresholds"]
    pass_checks = {
        "rhat": replayed["max_rhat"] <= thresholds["max_rhat"],
        "bulk_ess": replayed["min_bulk_ess"] >= thresholds["min_bulk_ess"],
        "tail_ess": replayed["min_tail_ess"] >= thresholds["min_tail_ess"],
        "relative_mcse": (
            replayed["max_relative_mcse"] <= thresholds["max_relative_mcse"]
        ),
    }
    manuscript_values = {
        "max_rhat_ceiling_5dp": np.ceil(replayed["max_rhat"] * 100000) / 100000,
        "min_bulk_ess_floor_integer": int(np.floor(replayed["min_bulk_ess"])),
        "min_tail_ess_floor_integer": int(np.floor(replayed["min_tail_ess"])),
        "max_relative_mcse_ceiling_4dp": (
            np.ceil(replayed["max_relative_mcse"] * 10000) / 10000
        ),
    }
    expected_manuscript_values = {
        "max_rhat_ceiling_5dp": 1.00374,
        "min_bulk_ess_floor_integer": 2496,
        "min_tail_ess_floor_integer": 1963,
        "max_relative_mcse_ceiling_4dp": 0.0202,
    }

    code_root = args.code_root.resolve()
    code_files = {
        "rhat.py": code_root / "src/geodeepbayes/diagnostics/rhat.py",
        "ess.py": code_root / "src/geodeepbayes/diagnostics/ess.py",
        "mcse.py": code_root / "src/geodeepbayes/diagnostics/mcse.py",
    }
    after = {path.name: sha256(path) for path in (raw_path, metrics_path)}
    result = {
        "schema_version": "ars-stage4-rev-r1-4-algo-diagnostic-replay-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "operation": "read-only historical replay; predecessor files preserved",
        "source_label": args.source_label,
        "source_sha256_before": before,
        "source_sha256_after": after,
        "source_integrity_preserved": before == after,
        "config_sha256": sha256(config_path),
        "code_sha256": {name: sha256(path) for name, path in code_files.items()},
        "recorded_diagnostics": recorded,
        "replayed_diagnostics": replayed,
        "delta_replayed_minus_recorded": {
            name: replayed[name] - recorded[name] for name in replayed
        },
        "threshold_checks": pass_checks,
        "all_four_thresholds_pass": all(pass_checks.values()),
        "manuscript_conservative_values": manuscript_values,
        "expected_manuscript_conservative_values": expected_manuscript_values,
        "manuscript_values_preserved": (
            manuscript_values == expected_manuscript_values
        ),
        "scope_boundary": (
            "generic non-geophysical algorithm-correctness asset only; "
            "no joint, field, scaling or production inference"
        ),
    }
    if not (
        result["source_integrity_preserved"]
        and result["all_four_thresholds_pass"]
        and result["manuscript_values_preserved"]
    ):
        raise RuntimeError("EVD-ALGO-002 重放未保持稿件诊断合同")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "source_integrity_preserved": result["source_integrity_preserved"],
                "all_four_thresholds_pass": result["all_four_thresholds_pass"],
                "manuscript_values_preserved": result["manuscript_values_preserved"],
                "replayed_diagnostics": replayed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
