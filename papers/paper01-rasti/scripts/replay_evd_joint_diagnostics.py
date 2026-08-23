#!/usr/bin/env python
"""REV-R1-4：旁路回放 EVD-JOINT-001 历史链，不修改任何前件。"""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from geodeepbayes.benchmarks.joint_block import (
    compute_diagnostics,
    load_diagnostic_thresholds,
)


DIAGNOSTIC_FIELDS = (
    "rank_normalized_split_rhat",
    "folded_split_rhat",
    "bulk_ess",
    "tail_ess",
    "relative_mcse",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_baseline(metrics: dict | None) -> dict | None:
    if not metrics:
        return None
    diagnostic = metrics.get("diagnostics")
    if diagnostic is None:
        diagnostic = metrics.get("metrics", {}).get("diagnostics")
    return diagnostic


def replay_one(raw_path_text: str, source_root_text: str) -> dict:
    raw_path = Path(raw_path_text)
    source_root = Path(source_root_text)
    metrics_path = raw_path.with_name("metrics.json")
    raw_sha_before = sha256(raw_path)
    metrics_sha_before = sha256(metrics_path) if metrics_path.exists() else None

    with np.load(raw_path, allow_pickle=False) as payload:
        draws = payload["draws"]
        functional = payload["functional_chains"]
        log_density = payload["log_density"]
        channels = np.concatenate(
            [draws, functional, log_density[..., None]], axis=2)
        diagnostics = compute_diagnostics(
            channels, log_density, load_diagnostic_thresholds())

    baseline_metrics = None
    if metrics_path.exists():
        baseline_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    baseline = extract_baseline(baseline_metrics)
    deltas = {}
    for field in DIAGNOSTIC_FIELDS:
        old_value = baseline.get(field) if baseline else None
        new_value = diagnostics.get(field)
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            deltas[field] = new_value - old_value
        else:
            deltas[field] = None

    raw_sha_after = sha256(raw_path)
    metrics_sha_after = sha256(metrics_path) if metrics_path.exists() else None
    return {
        "source_relative_path": raw_path.relative_to(source_root).as_posix(),
        "source_raw_sha256": raw_sha_before,
        "source_metrics_relative_path": (
            metrics_path.relative_to(source_root).as_posix()
            if metrics_path.exists() else None
        ),
        "source_metrics_sha256": metrics_sha_before,
        "source_integrity_preserved": (
            raw_sha_before == raw_sha_after
            and metrics_sha_before == metrics_sha_after
        ),
        "shape": list(channels.shape),
        "baseline_diagnostics": baseline,
        "replayed_diagnostics": diagnostics,
        "status_transition": {
            "from": baseline.get("status") if baseline else None,
            "to": diagnostics["status"],
        },
        "metric_deltas_new_minus_old": deltas,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--code-root", type=Path, required=True)
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    raw_paths = sorted(source_root.rglob("raw-chains.npz"))
    if not raw_paths:
        raise RuntimeError(f"未找到历史链文件：{source_root}")

    records = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(replay_one, str(path), str(source_root)): path
            for path in raw_paths
        }
        total = len(futures)
        for completed, future in enumerate(as_completed(futures), 1):
            record = future.result()
            records.append(record)
            print(
                json.dumps(
                    {
                        "completed": completed,
                        "total": total,
                        "path": record["source_relative_path"],
                        "status": record["replayed_diagnostics"]["status"],
                        "stop_reason": record["replayed_diagnostics"].get(
                            "diagnostic_stop_reason"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    records.sort(key=lambda item: item["source_relative_path"])
    transition_counts: dict[str, int] = {}
    stop_reason_counts: dict[str, int] = {}
    for record in records:
        transition = record["status_transition"]
        key = f"{transition['from']}->{transition['to']}"
        transition_counts[key] = transition_counts.get(key, 0) + 1
        reason = record["replayed_diagnostics"].get("diagnostic_stop_reason")
        reason_key = str(reason)
        stop_reason_counts[reason_key] = stop_reason_counts.get(reason_key, 0) + 1

    code_root = args.code_root.resolve()
    code_files = {
        "rhat.py": code_root / "src/geodeepbayes/diagnostics/rhat.py",
        "ess.py": code_root / "src/geodeepbayes/diagnostics/ess.py",
        "mcse.py": code_root / "src/geodeepbayes/diagnostics/mcse.py",
        "joint_block.py": code_root / "src/geodeepbayes/benchmarks/joint_block.py",
        "diagnostic-contract.json": (
            code_root / "validation/wp2-toy/diagnostic-contract.json"
        ),
    }
    result = {
        "schema_version": "ars-stage4-rev-r1-4-diagnostic-replay-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "operation": "read-only historical replay; predecessors preserved",
        "source_root": source_root.as_posix(),
        "source_count": len(records),
        "workers": args.workers,
        "code_and_contract_sha256": {
            name: sha256(path) for name, path in code_files.items()
        },
        "summary": {
            "all_source_integrity_preserved": all(
                record["source_integrity_preserved"] for record in records),
            "status_transition_counts": transition_counts,
            "diagnostic_stop_reason_counts": stop_reason_counts,
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
