#!/usr/bin/env python
"""Run the locked local gate suite and publish auditable gate logs."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = (
    ROOT / "_bmad-output/planning-artifacts/research"
    / "贝叶斯思想与重磁电电磁深度融合技术体系"
)
WP9 = RESEARCH / "validation/wp9"
LOG_DIR = WP9 / "gate-logs-v1"
OUTPUT = WP9 / "final-gates-v1.json"
SCRIPT = Path(__file__).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def portable_text(value: str) -> str:
    normalized = value.replace(str(ROOT), ".")
    normalized = normalized.replace(str(ROOT).replace("\\", "/"), ".")
    user_home = str(Path.home())
    normalized = normalized.replace(user_home, "<user-home>")
    normalized = normalized.replace(user_home.replace("\\", "/"), "<user-home>")
    return normalized


def portable_argv(argv: list[str]) -> list[str]:
    return [portable_text(value) for value in argv]


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def command_log(
    name: str,
    argv: list[str],
    *,
    storage_dir: Path,
    timeout: int = 1800,
) -> dict[str, Any]:
    started = utc_now()
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    ended = utc_now()
    portable_stdout = portable_text(completed.stdout)
    portable_stderr = portable_text(completed.stderr)
    payload = {
        "schema_version": "wp9-gate-log-v1",
        "gate": name,
        "argv": portable_argv(argv),
        "cwd": ".",
        "started_at_utc": started,
        "ended_at_utc": ended,
        "exit_code": completed.returncode,
        "stdout": portable_stdout,
        "stderr": portable_stderr,
        "output_normalization": "repository-root-to-dot; user-home-redacted",
        "stdout_sha256": sha256_bytes(portable_stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(portable_stderr.encode("utf-8")),
    }
    path = storage_dir / f"{name}.json"
    atomic_json(path, payload)
    final_path = LOG_DIR / f"{name}.json"
    return {
        "path": final_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "temporary_path": str(path),
        "exit_code": completed.returncode,
        "stdout": portable_stdout,
        "stderr": portable_stderr,
        "argv": portable_argv(argv),
    }


def git_snapshot() -> dict[str, Any]:
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    ).stdout
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    ).stdout
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {
        "baseline_commit": head,
        "worktree_dirty": bool(status),
        "tracked_diff_sha256": sha256_bytes(diff),
        "status_paths_sha256": sha256_bytes(status),
    }


def log_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {"path": record["path"], "sha256": record["sha256"]}


def parse_count(pattern: str, text: str) -> int:
    matches = re.findall(pattern, text)
    return int(matches[-1]) if matches else 0


def inside_run() -> int:
    storage_dir = Path(os.environ["GDB_GATE_LOG_STAGING"]).resolve()
    python = str(Path(sys.executable).resolve())
    pwsh = "pwsh"
    versions = RESEARCH / "validation/wp7/versions"
    wp7_signoff = RESEARCH / "validation/wp7/signoff-v4.json"
    commands = {
        "pytest": [python, "-m", "pytest", "-q"],
        "governance": [
            pwsh, "-NoProfile", "-File", str(RESEARCH / "validate-governance.ps1"),
        ],
        "wp5": [
            pwsh, "-NoProfile", "-File", str(RESEARCH / "validate-wp5.ps1"),
        ],
        "wp6_self_test": [
            pwsh, "-NoProfile", "-File", str(RESEARCH / "validate-wp6.ps1"),
            "-SelfTest", "-SkipTests",
        ],
        "wp7_self_test": [
            pwsh, "-NoProfile", "-File", str(RESEARCH / "validate-wp7.ps1"),
            "-SyntheticRun", str(versions / "synthetic-block-v6-20260724"),
            "-Do27Run", str(versions / "do27-v4-20260724"),
            "-Signoff", str(wp7_signoff), "-SelfTest",
        ],
        "wp8_synthetic_completion": [
            python, "validation/wp8/validate_wp8.py", "--phase", "synthetic",
        ],
        "wp9_acceptance": [python, "validation/wp9/validate_wp9.py"],
    }
    logs = {
        name: command_log(name, argv, storage_dir=storage_dir)
        for name, argv in commands.items()
    }
    pytest_output = logs["pytest"]["stdout"] + logs["pytest"]["stderr"]
    governance_output = (
        logs["governance"]["stdout"] + logs["governance"]["stderr"]
    )
    gate_status = {
        name: "passed" if record["exit_code"] == 0 else "blocked"
        for name, record in logs.items()
    }
    gates: dict[str, Any] = {
        "pytest": {
            "status": gate_status["pytest"],
            "passed": parse_count(r"(\d+) passed", pytest_output),
            "skipped": parse_count(r"(\d+) skipped", pytest_output),
            "warnings": parse_count(r"(\d+) warnings", pytest_output),
            "exit_code": logs["pytest"]["exit_code"],
            "argv": logs["pytest"]["argv"],
            "log": log_ref(logs["pytest"]),
        },
        "governance": {
            "status": gate_status["governance"],
            "entries": parse_count(r"entries=(\d+)", governance_output),
            "release_paths": parse_count(r"release_paths=(\d+)", governance_output),
            "evidence_ids": parse_count(r"evidence_ids=(\d+)", governance_output),
            "cited_refs": parse_count(r"cited_refs=(\d+)", governance_output),
            "exit_code": logs["governance"]["exit_code"],
            "argv": logs["governance"]["argv"],
            "log": log_ref(logs["governance"]),
        },
    }
    for name in (
        "wp5", "wp6_self_test", "wp7_self_test",
        "wp8_synthetic_completion", "wp9_acceptance",
    ):
        output = logs[name]["stdout"] + logs[name]["stderr"]
        gates[name] = {
            "status": gate_status[name],
            "exit_code": logs[name]["exit_code"],
            "argv": logs[name]["argv"],
            "log": log_ref(logs[name]),
        }
        if name == "wp6_self_test":
            gates[name]["release"] = False
        if name == "wp8_synthetic_completion":
            gates[name]["field_validated"] = False
            match = re.search(r'"reason_code":\s*"([^"]+)"', output)
            gates[name]["reason_code"] = match.group(1) if match else None
        if name == "wp9_acceptance":
            gates[name]["scope"] = "saved local evidence package only"
        if gate_status[name] == "blocked":
            known = {
                "wp5": ["root drift ACTIVE_MANIFEST"],
                "wp7_self_test": [
                    "synthetic signoff root mismatch",
                    "do27 signoff root mismatch",
                ],
                "wp8_synthetic_completion": [
                    "method-validation:semantic-replay-mismatch"
                ],
            }
            gates[name]["errors"] = [
                item for item in known.get(name, []) if item in output
            ]
    required = list(gates)
    blocking = [name for name in required if gates[name]["status"] != "passed"]
    environment = {
        "status": "passed",
        "uv": "0.11.29",
        "uv_on_path": bool(os.environ.get("PATH")) and bool(
            subprocess.run(
                ["where.exe", "uv"],
                capture_output=True,
                check=False,
            ).returncode == 0
        ),
        "local_invocation_fallback": "python -m uv",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "powershell": subprocess.run(
            ["pwsh", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "python_version_file_sha256": sha256_file(ROOT / ".python-version"),
        "pyproject_sha256": sha256_file(ROOT / "pyproject.toml"),
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        **git_snapshot(),
        "runner_sha256": sha256_file(SCRIPT),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("matplotlib", "simpeg", "discretize", "numpy", "scipy")
        },
        "bootstrap_log": {
            "path": (
                LOG_DIR / "environment-bootstrap.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256_file(storage_dir / "environment-bootstrap.json"),
        },
    }
    payload = {
        "schema_version": "wp9-final-gates-v1",
        "evidence_kind": "current-local-rerun",
        "generated_by": SCRIPT.relative_to(ROOT).as_posix(),
        "generated_at_utc": utc_now(),
        "status": "passed" if not blocking else "blocked",
        "environment": environment,
        "gates": gates,
        "release_acceptance": {
            "status": "passed" if not blocking else "blocked",
            "blocking_gates": blocking,
            "additional_external_requirements": [
                "Git persistence of the required evidence closure",
                "remote required-gates run",
                "remote attestation",
                "authorized WP5 re-sign and any required human review",
            ],
        },
    }
    for staged in sorted(storage_dir.glob("*.json")):
        atomic_json(
            LOG_DIR / staged.name,
            json.loads(staged.read_text(encoding="utf-8")),
        )
    atomic_json(OUTPUT, payload)
    print(
        json.dumps(
            {"output": str(OUTPUT), "status": payload["status"], "blocking": blocking},
            ensure_ascii=False,
        )
    )
    return 0 if not blocking else 4


def bootstrap() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="geodeepbayes-final-gates-") as temporary:
        storage_dir = Path(temporary)
        lock = command_log(
            "bootstrap-lock",
            [sys.executable, "-m", "uv", "lock", "--check"],
            storage_dir=storage_dir,
            timeout=300,
        )
        sync = command_log(
            "bootstrap-sync",
            [sys.executable, "-m", "uv", "sync", "--frozen", "--extra", "dev"],
            storage_dir=storage_dir,
            timeout=1800,
        )
        bootstrap_path = storage_dir / "environment-bootstrap.json"
        atomic_json(
            bootstrap_path,
            {
                "schema_version": "wp9-environment-bootstrap-v1",
                "uv_version": subprocess.run(
                    [sys.executable, "-m", "uv", "--version"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                "lock": log_ref(lock),
                "sync": log_ref(sync),
                "status": (
                    "passed"
                    if lock["exit_code"] == 0 and sync["exit_code"] == 0
                    else "blocked"
                ),
            },
        )
        if lock["exit_code"] != 0 or sync["exit_code"] != 0:
            return 4
        locked_python = ROOT / ".venv/Scripts/python.exe"
        environment = dict(os.environ)
        environment["GDB_GATE_LOG_STAGING"] = str(storage_dir)
        completed = subprocess.run(
            [str(locked_python), str(SCRIPT), "--inside"],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    return inside_run() if args.inside else bootstrap()


if __name__ == "__main__":
    raise SystemExit(main())
