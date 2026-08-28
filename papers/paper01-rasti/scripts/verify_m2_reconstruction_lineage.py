#!/usr/bin/env python
"""REV-R1-5：验证 M2 事后 gate ledger 的逐字段来源，不覆盖历史工件。"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_ledger_row(metrics: dict) -> dict:
    diagnostic = metrics["diagnostics"]
    map_result = metrics["map"]
    adapt_log = metrics.get("adapt_log_chain0", [])
    return {
        "adapt_segments_a_rw_zero": sum(
            item["accept_a_rw"] == 0.0 for item in adapt_log),
        "adapt_segments_total": len(adapt_log),
        "arm": metrics["arm"],
        "b_rw_accept_last_segment": (
            adapt_log[-1]["accept_b_rw"] if adapt_log else None),
        "bulk_ess": diagnostic["bulk_ess"],
        "checks": diagnostic["checks"],
        "f3_fallback_rate": diagnostic["f3_fallback_rate"],
        "folded_split_rhat": diagnostic["folded_split_rhat"],
        "map_converged": map_result["converged"],
        "map_log_density": map_result["log_density"],
        "map_n_outer": map_result["n_outer"],
        "mode_visits_per_chain": diagnostic["mode_visits_per_chain"],
        "rank_normalized_split_rhat": diagnostic[
            "rank_normalized_split_rhat"],
        "relative_mcse": diagnostic["relative_mcse"],
        "run_id": metrics["run_id"],
        "scales_final": metrics.get("scales_final"),
        "scenario_id": metrics["scenario_id"],
        "seed": metrics["config"]["seed"],
        "stage1_accept_rate": metrics.get("stage1_accept_rate"),
        "stage2_accept_rate_overall": metrics[
            "stage2_accept_rate_overall"] if "stage2_accept_rate_overall" in metrics else None,
        "status": diagnostic["status"],
        "tail_ess": diagnostic["tail_ess"],
        "timing_seconds": metrics["timing_seconds"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot-label", required=True)
    args = parser.parse_args()

    pilot = args.pilot_root.resolve()
    evaluation = pilot / "evaluation"
    ledger_path = evaluation / "m2-gate-ledger.json"
    aggregation_path = evaluation / "m2-posthoc-aggregation.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    recorded = {row["run_id"]: row for row in ledger["runs"]}

    records = []
    for run_dir in sorted((pilot / "runs").iterdir()):
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "metrics.json"
        manifest_path = run_dir / "run-manifest.json"
        raw_path = run_dir / "raw-chains.npz"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        expected = expected_ledger_row(metrics)
        actual = recorded.get(metrics["run_id"])
        records.append({
            "run_id": metrics["run_id"],
            "metrics_path": metrics_path.relative_to(pilot).as_posix(),
            "metrics_sha256": sha256(metrics_path),
            "run_manifest_path": manifest_path.relative_to(pilot).as_posix(),
            "run_manifest_sha256": sha256(manifest_path),
            "raw_chains_path": raw_path.relative_to(pilot).as_posix(),
            "raw_chains_sha256": sha256(raw_path),
            "ledger_row_exact_match": actual == expected,
            "field_lineage": {
                "arm_and_run_identity": "metrics.json: arm, run_id, scenario_id, config.seed",
                "diagnostics": "metrics.json: diagnostics.*",
                "map": "metrics.json: map.{converged,log_density,n_outer}",
                "adaptation": "metrics.json: adapt_log_chain0 and scales_final",
                "timing": "metrics.json: timing_seconds",
            },
        })

    unbound = sorted(set(recorded) - {record["run_id"] for record in records})
    result = {
        "schema_version": "ars-stage4-rev-r1-5-lineage-audit-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "nature": "post-hoc additive audit; no historical artifact modified",
        "pilot_label": args.pilot_label,
        "historical_evaluation": {
            "gate_ledger_path": ledger_path.relative_to(pilot).as_posix(),
            "gate_ledger_sha256": sha256(ledger_path),
            "aggregation_path": aggregation_path.relative_to(pilot).as_posix(),
            "aggregation_sha256": sha256(aggregation_path),
            "runtime_generated": False,
        },
        "summary": {
            "run_count": len(records),
            "exact_match_count": sum(
                record["ledger_row_exact_match"] for record in records),
            "unbound_ledger_run_ids": unbound,
            "all_rows_exact": (
                all(record["ledger_row_exact_match"] for record in records)
                and not unbound
            ),
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["all_rows_exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
