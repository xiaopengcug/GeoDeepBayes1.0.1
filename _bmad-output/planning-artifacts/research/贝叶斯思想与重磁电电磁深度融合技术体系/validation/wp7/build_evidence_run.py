from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import platform
from pathlib import Path
import sys


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def artifact(path: Path, base: Path) -> dict:
    return {
        "path": path.resolve().relative_to(base.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
        "locator": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--code", type=Path, action="append", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--outcome", choices=("succeeded", "failed", "blocked"), required=True)
    parser.add_argument("--seed", type=int, action="append", default=[])
    args = parser.parse_args()
    project = Path(__file__).resolve()
    while project.parent != project and not (project / "pyproject.toml").exists():
        project = project.parent
    run = args.run.resolve()
    output_files = sorted(
        path for path in run.iterdir()
        if path.is_file() and path.name != "evidence-run-v2.json"
    )
    code_manifest = [artifact(path.resolve(), project) for path in args.code]
    canonical = json.dumps(
        code_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    now = datetime.now(timezone.utc).isoformat()
    producer_manifest_path = run / "run-manifest.json"
    producer_manifest = (
        json.loads(producer_manifest_path.read_text(encoding="utf-8"))
        if producer_manifest_path.is_file() else None
    )
    if producer_manifest is not None:
        started_at = producer_manifest["started_at"]
        ended_at = producer_manifest["completed_at"]
        producer_outcome = (
            "succeeded" if producer_manifest["status"] != "Failed" else "failed"
        )
        if producer_outcome != args.outcome:
            raise RuntimeError("requested outcome contradicts producer manifest")
    else:
        started_at = ended_at = now
    manifest = {
        "schema_version": "2.0.0",
        "run_id": args.run_id,
        "evidence_id": args.evidence_id,
        "execution": {
            "started_at": started_at, "ended_at": ended_at, "outcome": args.outcome,
            "exit_code": 0 if args.outcome == "succeeded" else 2,
            "failure_reason": None if args.outcome == "succeeded" else "预注册数值门未全部通过",
        },
        "code": {
            "algorithm": "sha256-canonical-manifest-v1",
            "manifest": code_manifest,
            "sha256": sha256(canonical).hexdigest(),
        },
        "inputs": [artifact(args.input.resolve(), project)],
        "configs": [artifact(args.config.resolve(), project)],
        "outputs": [artifact(path, project) for path in output_files],
        "environment": {
            "os": platform.platform(), "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "python_sha256": digest(Path(sys.executable)),
            "uv_lock_sha256": digest(project / "uv.lock"),
        },
        "randomness": {"stochastic": bool(args.seed), "seeds": sorted(set(args.seed))},
        "approval": {
            "identity": "WP7独立复核待执行", "identity_type": "ai",
            "decided_at": now, "decision": "pending",
        },
        "claims": [] if args.outcome != "succeeded" else [{
            "claim_id": args.evidence_id, "scope": "synthetic",
            "max_maturity": "Synthetic-verified",
        }],
        "attestation": {
            "required": False, "subject_digest": None, "workflow": None,
            "commit_sha": None, "verified": False,
        },
    }
    (run / "evidence-run-v2.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
