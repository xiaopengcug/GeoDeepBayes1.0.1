#!/usr/bin/env python
"""Build a read-only Git/artifact persistence plan for the WP8/WP9 package.

This script deliberately does not stage, commit, push, open a PR, or contact a
remote.  It classifies the already-published WP9 manifest members and records
the remaining authorization and live-gate blockers.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.validate_repository_scope import (  # noqa: E402
    ABSOLUTE_PATH,
    FORBIDDEN_PARTS,
    MAX_BYTES,
    permitted_forbidden_path,
    SECRET_PATTERNS,
)


RESEARCH = (
    ROOT
    / "_bmad-output/planning-artifacts/research"
    / "贝叶斯思想与重磁电电磁深度融合技术体系"
)
WP9 = RESEARCH / "validation/wp9"
MANIFEST = WP9 / "manifest-v1.json"
FINAL_GATES = WP9 / "final-gates-v1.json"
OUTPUT = WP9 / "persistence-plan-v1.json"
SUPPLEMENT_MANIFEST = (
    ROOT / "validation/wp8/synthetic/supplements-v1/manifest.json"
)
SUPPLEMENT_GENERATOR = "validation/wp8/generate_synthetic_supplements.py"
FROZEN_BASELINE_COMMIT = "50e25166f8897f0fc6e82cbadbc3c4f0a98c14d5"
RESEARCH_RELATIVE = (
    "_bmad-output/planning-artifacts/research/"
    "贝叶斯思想与重磁电电磁深度融合技术体系"
)

# These are execution/control inputs beyond the evidence members already
# enumerated by manifest-v1.json.  They do not pretend to be a full remote
# release closure while the live WP5/WP7/WP8 gates remain blocked.
CONTROL_INPUTS = (
    ".github/workflows/ci.yml",
    ".gitignore",
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "tools/validate_repository_scope.py",
    "validation/wp8/generate_synthetic_supplements.py",
    "validation/wp8/validate_wp8.py",
    "validation/wp9/build_persistence_plan.py",
    "_bmad-output/implementation-artifacts/spec-persist-wp8-wp9-remote-attestation.md",
    "_bmad-output/implementation-artifacts/spec-rebuild-locked-reproducible-environment.md",
    "_bmad-output/implementation-artifacts/spec-verify-and-remediate-acceptance-review03.md",
    "_bmad-output/implementation-artifacts/spec-wp9-specialist-review-hardening.md",
    "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp9/manifest-v1.json",
    f"{RESEARCH_RELATIVE}/validate-governance.ps1",
    f"{RESEARCH_RELATIVE}/validate-wp5.ps1",
    f"{RESEARCH_RELATIVE}/validate-wp6.ps1",
    f"{RESEARCH_RELATIVE}/validate-wp7.ps1",
    f"{RESEARCH_RELATIVE}/ACTIVE_MANIFEST",
    f"{RESEARCH_RELATIVE}/manifest.yaml",
    f"{RESEARCH_RELATIVE}/WP5-consistency-input-root.sha256",
    f"{RESEARCH_RELATIVE}/WP5-upstream-allowlist.json",
    f"{RESEARCH_RELATIVE}/六角色独立再审-WP5.md",
    f"{RESEARCH_RELATIVE}/validation/wp5-consistency/active-output.json",
    f"{RESEARCH_RELATIVE}/validation/wp7/validate_wp7.py",
    f"{RESEARCH_RELATIVE}/validation/wp7/synthetic-v6-config.json",
    f"{RESEARCH_RELATIVE}/validation/wp7/signoff-v4.json",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/build_evidence_root.py",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/record_attestation.py",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/validate_wp6.py",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/test-worker-acl.ps1",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/test-worker-uid.sh",
    f"{RESEARCH_RELATIVE}/contracts/contract-registry.json",
    f"{RESEARCH_RELATIVE}/contracts/data-contract.schema.json",
    f"{RESEARCH_RELATIVE}/contracts/operator-capability.schema.json",
    f"{RESEARCH_RELATIVE}/contracts/evidence-run.schema.json",
    f"{RESEARCH_RELATIVE}/contracts/validate_contracts.py",
    f"{RESEARCH_RELATIVE}/contracts/wp6_governance.py",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/legacy-index.json",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/governance-snapshots.json",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/signoff.json",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/policy.json",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/protection-sources.json",
    f"{RESEARCH_RELATIVE}/validation/wp6-governance/gc_versions.py",
)
CONTROL_DIRECTORIES = (
    f"{RESEARCH_RELATIVE}/validation/wp7/versions/synthetic-block-v6-20260724",
    f"{RESEARCH_RELATIVE}/validation/wp7/versions/do27-v4-20260724",
    "src/geodeepbayes",
    "tests",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_git(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        input=input_bytes,
        capture_output=True,
        check=False,
    )


def _tracked_paths() -> set[str]:
    process = _run_git("ls-files", "-z")
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace"))
    return {
        item.decode("utf-8").replace("\\", "/")
        for item in process.stdout.split(b"\0")
        if item
    }


def _staged_paths() -> set[str]:
    process = _run_git("diff", "--cached", "--name-only", "-z")
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace"))
    return {
        item.decode("utf-8").replace("\\", "/")
        for item in process.stdout.split(b"\0")
        if item
    }


def _git_head() -> str:
    process = _run_git("rev-parse", "HEAD")
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace"))
    value = process.stdout.decode("ascii", errors="strict").strip()
    if len(value) != 40 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise RuntimeError("git rev-parse returned an invalid commit")
    return value


def _head_blob_sha256(relative: str) -> str | None:
    process = _run_git("show", f"HEAD:{relative}")
    if process.returncode:
        return None
    return hashlib.sha256(process.stdout).hexdigest()


def _ignore_rule(relative: str) -> str | None:
    quiet = _run_git("check-ignore", "-q", "--no-index", "--", relative)
    if quiet.returncode == 1:
        return None
    if quiet.returncode:
        raise RuntimeError(quiet.stderr.decode("utf-8", errors="replace"))
    verbose = _run_git("check-ignore", "-v", "--no-index", "--", relative)
    if verbose.returncode:
        raise RuntimeError(verbose.stderr.decode("utf-8", errors="replace"))
    rule_and_path = verbose.stdout.decode("utf-8", errors="replace").strip()
    rule_source = rule_and_path.split("\t", 1)[0]
    fields = rule_source.rsplit(":", 2)
    if len(fields) != 3 or not fields[2]:
        raise RuntimeError("git check-ignore returned an invalid verbose rule")
    return fields[2]


def _scan_text(path: Path) -> dict[str, Any]:
    normalized = "/" + path.relative_to(ROOT).as_posix()
    result: dict[str, Any] = {
        "secret_patterns": [],
        "absolute_path": False,
        "oversized": path.stat().st_size > MAX_BYTES,
        "forbidden_path": (
            any(part in normalized for part in FORBIDDEN_PARTS)
            and not permitted_forbidden_path(normalized)
        ),
    }
    if result["oversized"]:
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return result
    result["secret_patterns"] = sorted(
        name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)
    )
    result["absolute_path"] = bool(ABSOLUTE_PATH.search(text))
    return result


def _control_inputs() -> tuple[str, ...]:
    expanded = list(CONTROL_INPUTS)
    for relative in CONTROL_DIRECTORIES:
        directory = ROOT / relative
        if not directory.is_dir():
            raise FileNotFoundError(relative)
        expanded.extend(
            path.relative_to(ROOT).as_posix()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in {".pyc", ".pyo"}
        )
    if len(expanded) != len(set(expanded)):
        raise ValueError("duplicate explicit execution control path")
    return tuple(expanded)


def _expected_wp9_manifest_paths() -> set[str]:
    validator_path = ROOT / "validation/wp9/validate_wp9.py"
    spec = importlib.util.spec_from_file_location(
        "wp9_validator_for_persistence_plan", validator_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load WP9 validator")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    return {
        path.relative_to(ROOT).as_posix()
        for path in validator.expected_manifest_members()
    }


def _verify_deterministic_generation(
    supplement_manifest: dict[str, Any],
) -> dict[str, Any]:
    generator_path = ROOT / SUPPLEMENT_GENERATOR
    expected = {
        item["path"]: item["sha256"]
        for item in supplement_manifest.get("members", [])
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("sha256"), str)
    }
    runs: list[dict[str, str]] = []
    for run_index in range(2):
        spec = importlib.util.spec_from_file_location(
            f"wp8_supplement_generator_{run_index}", generator_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load WP8 supplement generator")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory(prefix="wp8-supplement-replay-") as temp:
            generator.ROOT = Path(temp)
            generator.OUTPUT = (
                generator.ROOT / "validation/wp8/synthetic/supplements-v1"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                if generator.main() != 0:
                    raise RuntimeError("WP8 supplement generator failed")
            run = {
                path.relative_to(generator.ROOT).as_posix(): sha256_file(path)
                for path in generator.OUTPUT.glob("*.npz")
            }
            runs.append(run)
    runs_equal = runs[0] == runs[1]
    matches_declared = runs[0] == expected
    return {
        "status": "passed" if runs_equal and matches_declared else "blocked",
        "generator": SUPPLEMENT_GENERATOR,
        "generator_sha256": sha256_file(generator_path),
        "replay_count": 2,
        "replays_equal": runs_equal,
        "matches_declared_hashes": matches_declared,
        "generated_hashes": runs[0],
    }


def _validate_supplement_manifest(
    supplement_manifest: dict[str, Any],
) -> set[str]:
    if supplement_manifest.get("schema_version") != "wp8-synthetic-supplements-v1":
        raise ValueError("unexpected WP8 supplement manifest schema")
    members = supplement_manifest.get("members")
    if not isinstance(members, list):
        raise ValueError("invalid WP8 supplement manifest members")
    expected = {
        "sip_fdip": "validation/wp8/synthetic/supplements-v1/sip_fdip.npz",
        "csamt": "validation/wp8/synthetic/supplements-v1/csamt.npz",
        "wfem": "validation/wp8/synthetic/supplements-v1/wfem.npz",
    }
    paths: list[str] = []
    methods: list[str] = []
    for member in members:
        if (
            not isinstance(member, dict)
            or not isinstance(member.get("method"), str)
            or not isinstance(member.get("path"), str)
            or not isinstance(member.get("sha256"), str)
        ):
            raise ValueError("invalid WP8 supplement manifest member")
        method = member["method"]
        relative = member["path"]
        if expected.get(method) != relative:
            raise ValueError("unexpected WP8 supplement method/path")
        path = (ROOT / relative).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            raise ValueError(f"unsafe or missing WP8 supplement: {relative}")
        if sha256_file(path) != member["sha256"]:
            raise ValueError(f"WP8 supplement hash drift: {relative}")
        if _ignore_rule(relative) is None:
            raise ValueError(f"WP8 generated supplement must remain ignored: {relative}")
        methods.append(method)
        paths.append(relative)
    if len(methods) != len(set(methods)) or set(methods) != set(expected):
        raise ValueError("duplicate or incomplete WP8 supplement methods")
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate WP8 supplement paths")
    return set(paths)


def _record(
    relative: str,
    tracked: set[str],
    staged: set[str],
    generated_paths: set[str],
    *,
    source: str,
) -> dict[str, Any]:
    normalized = Path(relative).as_posix()
    path = (ROOT / normalized).resolve()
    root = ROOT.resolve()
    if root not in path.parents:
        raise ValueError(f"path escapes repository root: {relative}")
    canonical = path.relative_to(root).as_posix()
    if normalized != canonical:
        raise ValueError(f"path is not canonical repo-root-relative: {relative}")
    if not path.is_file():
        raise FileNotFoundError(normalized)
    ignore_rule = _ignore_rule(normalized)
    if normalized in generated_paths:
        classification = "required-generated-artifact"
    elif ignore_rule:
        classification = "required-but-ignored-unresolved"
    else:
        classification = "required-git"
    worktree_sha256 = sha256_file(path)
    head_sha256 = _head_blob_sha256(normalized) if normalized in tracked else None
    record = {
        "path": normalized,
        "source": source,
        "classification": classification,
        "tracked": normalized in tracked,
        "tracked_in_head": head_sha256 is not None,
        "staged": normalized in staged,
        "head_sha256": head_sha256,
        "head_matches_worktree": (
            head_sha256 == worktree_sha256 if head_sha256 is not None else False
        ),
        "ignored": ignore_rule is not None,
        "ignore_rule": ignore_rule,
        "bytes": path.stat().st_size,
        "sha256": worktree_sha256,
        "scan": _scan_text(path),
    }
    if normalized in generated_paths:
        record["generator"] = SUPPLEMENT_GENERATOR
    return record


def build_plan() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != "wp9-final-manifest-v1"
        or manifest.get("path_basis") != "repo-root-relative"
    ):
        raise ValueError("unexpected WP9 manifest schema")
    manifest_members = manifest.get("members")
    if not isinstance(manifest_members, list) or not manifest_members:
        raise ValueError("WP9 manifest has no members")
    manifest_paths = [
        member.get("path") if isinstance(member, dict) else None
        for member in manifest_members
    ]
    if (
        any(not isinstance(path, str) for path in manifest_paths)
        or len(manifest_paths) != len(set(manifest_paths))
    ):
        raise ValueError("duplicate or invalid WP9 manifest path")
    if set(manifest_paths) != _expected_wp9_manifest_paths():
        raise ValueError("incomplete or unexpected WP9 manifest member set")

    supplement_manifest = json.loads(SUPPLEMENT_MANIFEST.read_text(encoding="utf-8"))
    generated_paths = _validate_supplement_manifest(supplement_manifest)
    tracked = _tracked_paths()
    staged = _staged_paths()
    observed_head = _git_head()

    manifest_records = []
    for member in manifest_members:
        if not isinstance(member, dict) or not isinstance(member.get("path"), str):
            raise ValueError("invalid WP9 manifest member")
        record = _record(
            member["path"],
            tracked,
            staged,
            generated_paths,
            source="wp9-manifest-v1",
        )
        if (
            member.get("sha256") != record["sha256"]
            or member.get("bytes") != record["bytes"]
        ):
            raise ValueError(f"WP9 manifest member drift: {member['path']}")
        manifest_records.append(record)
    by_path = {record["path"]: record for record in manifest_records}
    control_records = []
    for relative in _control_inputs():
        if relative in by_path:
            continue
        control_records.append(
            _record(
                relative,
                tracked,
                staged,
                generated_paths,
                source="explicit-execution-control",
            )
        )

    records = manifest_records + control_records
    plan_relative = OUTPUT.relative_to(ROOT).as_posix()
    plan_artifact = {
        "path": plan_relative,
        "classification": "local-and-ci-derived-report",
        "self_hash_omitted": True,
        "required_git": False,
        "reproducible_from_required_script_and_bound_inputs": True,
    }
    required_git = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-git"
    )
    required_generated = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-generated-artifact"
    )
    unresolved_ignored = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-but-ignored-unresolved"
    )
    untracked_required_git = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-git" and not record["tracked"]
    )
    tracked_modified_required_git = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-git"
        and record["tracked"]
        and not record["head_matches_worktree"]
    )
    unpersisted_required_git = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-git"
        and not record["head_matches_worktree"]
    )
    staged_required_git = sorted(
        record["path"]
        for record in records
        if record["classification"] == "required-git" and record["staged"]
    )
    scan_failures = sorted(
        record["path"]
        for record in records
        if record["scan"]["secret_patterns"]
        or record["scan"]["absolute_path"]
        or record["scan"]["oversized"]
        or record["scan"]["forbidden_path"]
    )
    generation_replay = _verify_deterministic_generation(supplement_manifest)

    final_gates = json.loads(FINAL_GATES.read_text(encoding="utf-8"))
    if final_gates.get("schema_version") != "wp9-final-gates-v1":
        raise ValueError("unexpected final-gates schema")
    gates = final_gates.get("gates")
    expected_gates = {
        "pytest",
        "governance",
        "wp5",
        "wp6_self_test",
        "wp7_self_test",
        "wp8_synthetic_completion",
        "wp9_acceptance",
    }
    if not isinstance(gates, dict) or set(gates) != expected_gates:
        raise ValueError("invalid final-gates gate set")
    derived_live_blockers = [
        name
        for name, gate in gates.items()
        if not isinstance(gate, dict) or gate.get("status") != "passed"
    ]
    release_acceptance = final_gates.get("release_acceptance", {})
    if not isinstance(release_acceptance, dict):
        raise ValueError("invalid final-gates release_acceptance")
    live_blockers = release_acceptance.get("blocking_gates", [])
    expected_status = "blocked" if derived_live_blockers else "passed"
    if (
        not isinstance(live_blockers, list)
        or live_blockers != derived_live_blockers
        or release_acceptance.get("status") != expected_status
        or final_gates.get("status") != expected_status
    ):
        raise ValueError("invalid final-gates blocking derivation")

    blockers = [
        "git/remote mutation is Ask First and has not been authorized",
        "no commit, push, PR, protected-branch CI, or remote attestation was performed",
    ]
    if unpersisted_required_git:
        blockers.append(
            f"{len(unpersisted_required_git)} required Git paths are not persisted "
            "with current content at the frozen baseline"
        )
    if required_generated:
        blockers.append(
            f"{len(required_generated)} ignored generated artifacts require deterministic "
            "regeneration and hash verification in the eventual remote workflow"
        )
    if unresolved_ignored:
        blockers.append(
            f"{len(unresolved_ignored)} required ignored paths have no approved distribution rule"
        )
    if live_blockers:
        blockers.append("live gates remain blocked: " + ", ".join(live_blockers))
    if scan_failures:
        blockers.append(f"{len(scan_failures)} required paths failed repository-scope scanning")
    if generation_replay["status"] != "passed":
        blockers.append("ignored generated artifacts failed deterministic replay")
    if observed_head != FROZEN_BASELINE_COMMIT:
        blockers.append("observed HEAD differs from the frozen specification baseline")
    if staged_required_git:
        blockers.append(
            f"{len(staged_required_git)} required Git paths already have staged changes"
        )

    return {
        "schema_version": "wp8-wp9-persistence-plan-v1",
        "generated_by": "validation/wp9/build_persistence_plan.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_baseline_commit": FROZEN_BASELINE_COMMIT,
        "observed_head": observed_head,
        "authorization": {
            "git_add_commit_push_pr": "not-authorized",
            "remote_configuration_or_publication": "not-authorized",
            "operations_performed_by_builder": [],
            "observed_head_matches_frozen_baseline": (
                observed_head == FROZEN_BASELINE_COMMIT
            ),
            "observed_staged_required_paths": staged_required_git,
        },
        "manifest_binding": {
            "path": MANIFEST.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(MANIFEST),
            "declared_members": len(manifest_records),
            "resolved_members": len(manifest_records),
            "closure": "passed",
        },
        "plan_artifact": plan_artifact,
        "classification_counts": {
            "manifest_members": len(manifest_records),
            "additional_control_inputs": len(control_records),
            "required_git": len(required_git),
            "required_generated_artifacts": len(required_generated),
            "required_but_ignored_unresolved": len(unresolved_ignored),
            "untracked_required_git": len(untracked_required_git),
            "tracked_modified_required_git": len(tracked_modified_required_git),
            "unpersisted_required_git": len(unpersisted_required_git),
            "staged_required_git": len(staged_required_git),
            "scan_failures": len(scan_failures),
        },
        "required_git": required_git,
        "required_generated_artifacts": required_generated,
        "required_but_ignored_unresolved": unresolved_ignored,
        "untracked_required_git": untracked_required_git,
        "tracked_modified_required_git": tracked_modified_required_git,
        "unpersisted_required_git": unpersisted_required_git,
        "records": records,
        "repository_scope_scan": {
            "status": "passed" if not scan_failures else "blocked",
            "failed_paths": scan_failures,
            "patterns_source": "tools/validate_repository_scope.py",
        },
        "deterministic_generation": generation_replay,
        "live_gate_snapshot": {
            "path": FINAL_GATES.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(FINAL_GATES),
            "status": final_gates.get("status"),
            "blocking_gates": live_blockers,
        },
        "local_preparation": (
            "passed"
            if not scan_failures
            and not unresolved_ignored
            and generation_replay["status"] == "passed"
            and observed_head == FROZEN_BASELINE_COMMIT
            and not staged_required_git
            else "blocked"
        ),
        "release_ready": False,
        "remote_attestation_verified": False,
        "blockers": blockers,
    }


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _resolve_output(path: Path) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    resolved = candidate.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise ValueError("output path must stay inside the repository")
    return resolved


def _plan_exit_code(plan: dict[str, Any]) -> int:
    return 0 if plan.get("local_preparation") == "passed" else 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = _resolve_output(args.output)
    plan = build_plan()
    _atomic_write(output, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "local_preparation": plan["local_preparation"],
                "release_ready": plan["release_ready"],
                "manifest_closure": plan["manifest_binding"]["closure"],
                "counts": plan["classification_counts"],
                "blockers": plan["blockers"],
                "output": output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
        )
    )
    return _plan_exit_code(plan)


if __name__ == "__main__":
    raise SystemExit(main())
