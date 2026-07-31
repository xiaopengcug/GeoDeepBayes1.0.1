#!/usr/bin/env python
"""Audit, explicitly publish, and verify the local WP9 acceptance package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = (
    ROOT / "_bmad-output/planning-artifacts/research"
    / "贝叶斯思想与重磁电电磁深度融合技术体系"
)
WP9 = RESEARCH / "validation/wp9"
REGISTRY = WP9 / "finding-registry-v1.json"
REVIEWS = WP9 / "reviews-v1"
LEDGER = RESEARCH / "整改台账03.md"
REPORT = RESEARCH / "整改落实报告03.md"
STATUS = RESEARCH / "evidence-status-03.md"
CLAIM_MAP = RESEARCH / "主张-证据映射03.md"
ACCEPTANCE_REVIEW = RESEARCH / "验收审查意见03.md"
MANIFEST = WP9 / "manifest-v1.json"
FINAL_GATES = WP9 / "final-gates-v1.json"
WP8_ROOT = ROOT / "validation/wp8"
WP8_COMPLETION = WP8_ROOT / "evidence/feasibility-v1/wp8-synthetic-completion-v1.json"
WP8_BINDINGS = {
    "authorization": WP8_ROOT / "evidence/wp8-1-start.json",
    "method_validation": (
        WP8_ROOT / "evidence/feasibility-v1/wp8-1-method-synthetic-validation-v1.json"
    ),
    "supplement_manifest": WP8_ROOT / "synthetic/supplements-v1/manifest.json",
    "method_policy": WP8_ROOT / "synthetic/method-validation-policy-v1.json",
    "synthetic_readiness": WP8_ROOT / "synthetic/readiness.json",
}
WP8_METHOD_VALIDATION = WP8_BINDINGS["method_validation"]
WP8_SUPPLEMENT_MANIFEST = WP8_BINDINGS["supplement_manifest"]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
EXPECTED_METHODS = {
    "gravity", "magnetic", "dc", "tdip", "sip_fdip",
    "tem", "mt_amt", "csamt", "wfem",
}
PRIMARY_WP = {
    1: 5, 2: 4, 3: 5, 4: 5, 5: 5,
    6: 1, 7: 1, 8: 1, 9: 1, 10: 1,
    11: 3, 12: 3, 13: 3, 14: 3,
    15: 2, 16: 2, 17: 2, 18: 2,
    19: 1, 20: 1, 21: 4, 22: 4, 23: 1, 24: 2, 25: 7,
    26: 4, 27: 3, 28: 4,
    29: 6, 30: 6, 31: 6, 32: 6, 33: 2, 34: 2, 35: 6,
    36: 8, 37: 8, 38: 8, 39: 8, 40: 8, 41: 8,
    42: 5, 43: 5, 44: 3, 45: 3, 46: 5, 47: 7, 48: 8,
    49: 3, 50: 4, 51: 1, 52: 5, 53: 3, 54: 3, 55: 8,
    56: 3, 57: 3, 58: 3, 59: 3, 60: 1,
}

BUILD_REGISTRY = ROOT / "validation/wp9/build_finding_registry.py"
RUN_REVIEWS = ROOT / "validation/wp9/run_specialist_reviews.py"
VALIDATOR = ROOT / "validation/wp9/validate_wp9.py"
BUILD_WP8_COMPLETION = ROOT / "validation/wp8/build_synthetic_completion.py"
RUN_FINAL_GATES = ROOT / "validation/wp9/run_final_gates.py"

IDENTITY_TYPE = "automated-ai-specialist-evidence-review"
SCOPE_LIMIT = (
    "AI evidence review only; not a human signature, field validation, "
    "resource certification, regulatory approval, or production certification."
)
COMMON_CHECKS = {
    "evidence_exists",
    "evidence_hashes_match",
    "work_packages_done",
    "synthetic_not_field_claim",
}
SPECIALISTS = {
    "geophysics-forward-physics": {
        "name": "地球物理与正演物理",
        "wps": {"WP3", "WP8"},
        "key": "forward_unit_consistent",
    },
    "bayesian-uq-statistics": {
        "name": "贝叶斯/UQ与统计设计",
        "wps": {"WP1", "WP4", "WP8"},
        "key": "sbc_coverage_recorded",
    },
    "numerical-discretization": {
        "name": "算法数值与离散化",
        "wps": {"WP2", "WP7", "WP8"},
        "key": "discretization_converged",
    },
    "engineering-governance-reproducibility": {
        "name": "工程架构、数据治理与可复现性",
        "wps": {"WP5", "WP6", "WP7", "WP8"},
        "key": "gates_blocked_on_fail",
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def safe_repo_file(relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    candidate = (ROOT / relative).resolve()
    if ROOT.resolve() not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def parse_ledger_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in LEDGER.read_text(encoding="utf-8-sig").splitlines():
        if not re.match(r"^\| R03-\d{4} \| R03-F-[0-9a-f]+ \|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 12:
            continue
        rows.append(
            {
                "id": cells[0],
                "source_finding_id": cells[1],
                "severity": cells[3],
                "section": cells[4],
                "summary": cells[7],
                "status": cells[9],
                "evidence_path": cells[10],
                "verification_role": cells[11],
            }
        )
    return rows


def validate_registry(registry: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    if set(registry) != {
        "schema_version", "status", "ledger_sha256", "counts", "findings"
    }:
        errors.append("registry:fields")
    if registry.get("schema_version") != "wp9-finding-registry-v1":
        errors.append("registry:schema")
    if registry.get("status") != "passed":
        errors.append("registry:status")
    findings = registry.get("findings")
    if not isinstance(findings, list):
        errors.append("registry:findings")
        return []
    ledger_rows = parse_ledger_rows()
    if registry.get("ledger_sha256") != sha256_file(LEDGER):
        errors.append("registry:ledger-sha")
    if not all(isinstance(item, dict) for item in findings):
        errors.append("registry:item-shape")
        return []
    ids = [item.get("id") for item in findings]
    source_ids = [item.get("source_finding_id") for item in findings]
    if ids != [f"R03-{number:04d}" for number in range(1, 61)]:
        errors.append("registry:ids")
    if (
        len(source_ids) != 60
        or not all(isinstance(value, str) for value in source_ids)
        or len(set(source_ids)) != 60
        or not all(
            isinstance(value, str) and re.fullmatch(r"R03-F-[0-9a-f]+", value)
            for value in source_ids
        )
    ):
        errors.append("registry:source-ids")
    expected_counts = {
        "total": len(findings),
        "p0": sum(item.get("severity") == "P0" for item in findings),
        "p1": sum(item.get("severity") == "P1" for item in findings),
        "passed": sum(item.get("status") == "已通过" for item in findings),
    }
    if registry.get("counts") != expected_counts or expected_counts != {
        "total": 60,
        "p0": 22,
        "p1": 38,
        "passed": 60,
    }:
        errors.append("registry:counts")
    if len(ledger_rows) != len(findings):
        errors.append("registry:ledger-row-count")
    finding_fields = {
        "id", "source_finding_id", "severity", "section", "summary", "status",
        "primary_work_package", "evidence", "verification_role",
    }
    evidence_fields = {"path", "sha256", "claim"}
    for index, item in enumerate(findings):
        source_id = item.get("source_finding_id", f"index-{index}")
        if set(item) != finding_fields:
            errors.append(f"{source_id}:fields")
        if index >= len(ledger_rows):
            errors.append(f"{source_id}:ledger-missing")
            continue
        row = ledger_rows[index]
        expected = {
            key: row[key]
            for key in ("id", "source_finding_id", "severity", "section", "summary", "status")
        }
        if any(item.get(key) != value for key, value in expected.items()):
            errors.append(f"{source_id}:ledger-mapping")
        if item.get("verification_role") != row["verification_role"]:
            errors.append(f"{source_id}:verification-role")
        expected_wp = f"WP{PRIMARY_WP.get(index + 1)}"
        if item.get("primary_work_package") != expected_wp:
            errors.append(f"{source_id}:primary-wp")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{source_id}:evidence-empty")
            continue
        if not all(isinstance(record, dict) for record in evidence):
            errors.append(f"{source_id}:evidence-shape")
            continue
        if evidence[0].get("path") != row["evidence_path"]:
            errors.append(f"{source_id}:ledger-evidence-path")
        for record in evidence:
            if set(record) != evidence_fields:
                errors.append(f"{source_id}:evidence-fields")
            if record.get("claim") != "completed-work-package-and-verification-record":
                errors.append(f"{source_id}:evidence-claim")
            path = safe_repo_file(record.get("path"))
            if (
                path is None
                or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))
                or sha256_file(path) != record.get("sha256")
            ):
                errors.append(f"{source_id}:evidence-drift")
    return findings


def validate_reviews(
    registry: dict[str, Any],
    findings: list[dict[str, Any]],
    errors: list[str],
) -> tuple[int, set[str]]:
    expected_files = {f"{slug}.json" for slug in SPECIALISTS}
    review_paths = sorted(REVIEWS.glob("*.json"))
    actual_files = {path.name for path in review_paths}
    if actual_files != expected_files or len(review_paths) != len(expected_files):
        errors.append("reviews:file-set")
    covered: set[str] = set()
    check_sets: list[frozenset[str]] = []
    registry_hash = sha256_file(REGISTRY)
    wp8_hash = sha256_file(WP8_COMPLETION)
    for slug, config in SPECIALISTS.items():
        path = REVIEWS / f"{slug}.json"
        if not path.is_file():
            continue
        review = json.loads(path.read_text(encoding="utf-8"))
        prefix = f"review:{path.name}"
        if set(review) != {
            "schema_version", "identity_type", "specialty_slug", "specialty",
            "registry_sha256", "wp8_completion_sha256",
            "specialty_evidence_sha256", "covered_source_finding_ids", "checks",
            "blocking_findings", "decision", "scope_limit",
        }:
            errors.append(f"{prefix}:fields")
        if review.get("schema_version") != "wp9-specialist-review-v1":
            errors.append(f"{prefix}:schema")
        if review.get("identity_type") != IDENTITY_TYPE:
            errors.append(f"{prefix}:identity")
        if (
            review.get("specialty_slug") != slug
            or review.get("specialty") != config["name"]
        ):
            errors.append(f"{prefix}:specialty")
        if (
            review.get("registry_sha256") != registry_hash
            or review.get("wp8_completion_sha256") != wp8_hash
        ):
            errors.append(f"{prefix}:binding-drift")
        expected_specialty_hash = sha256_file(
            CI_WORKFLOW
            if slug == "engineering-governance-reproducibility"
            else WP8_METHOD_VALIDATION
        )
        if review.get("specialty_evidence_sha256") != expected_specialty_hash:
            errors.append(f"{prefix}:specialty-evidence-drift")
        expected_coverage = {
            item["source_finding_id"]
            for item in findings
            if item.get("primary_work_package") in config["wps"]
        }
        raw_coverage = review.get("covered_source_finding_ids")
        if (
            not isinstance(raw_coverage, list)
            or not all(isinstance(value, str) for value in raw_coverage)
            or len(raw_coverage) != len(set(raw_coverage))
            or set(raw_coverage) != expected_coverage
        ):
            errors.append(f"{prefix}:coverage")
        else:
            covered.update(raw_coverage)
        checks = review.get("checks")
        expected_keys = COMMON_CHECKS | {config["key"]}
        if (
            not isinstance(checks, dict)
            or set(checks) != expected_keys
            or any(value is not True for value in checks.values())
        ):
            errors.append("reviews:template-degraded")
        else:
            check_sets.append(frozenset(checks))
        if review.get("decision") != "Approved" or review.get("blocking_findings") != []:
            errors.append(f"{prefix}:rejected")
        if review.get("scope_limit") != SCOPE_LIMIT:
            errors.append(f"{prefix}:scope-limit")
    if len(check_sets) != 4 or len(set(check_sets)) != 4:
        errors.append("reviews:template-degraded")
    all_ids = {item.get("source_finding_id") for item in findings}
    if covered != all_ids:
        errors.append("reviews:coverage")
    return len(review_paths), covered


def validate_wp8(errors: list[str]) -> dict[str, Any]:
    wp8 = json.loads(WP8_COMPLETION.read_text(encoding="utf-8"))
    if not (
        wp8.get("schema_version") == "wp8-synthetic-completion-v1"
        and wp8.get("status") == "passed"
        and wp8.get("validation_assertion") == "synthetic_prediction_verified"
        and wp8.get("wp8_complete") is True
        and wp8.get("wp9_start_allowed") is True
        and wp8.get("field_validated") is False
        and wp8.get("errors") == []
    ):
        errors.append("wp8:completion-boundary")
    bindings = wp8.get("bindings_sha256")
    if not isinstance(bindings, dict) or set(bindings) != set(WP8_BINDINGS):
        errors.append("wp8:binding-set")
    else:
        for name, path in WP8_BINDINGS.items():
            if not path.is_file() or bindings.get(name) != sha256_file(path):
                errors.append(f"wp8:binding-drift:{name}")
    method_validation = json.loads(WP8_METHOD_VALIDATION.read_text(encoding="utf-8"))
    method_records = method_validation.get("methods")
    if (
        method_validation.get("schema_version")
        != "wp8-method-synthetic-validation-v1"
        or method_validation.get("status") != "passed"
        or not isinstance(method_records, dict)
        or set(method_records) != EXPECTED_METHODS
    ):
        errors.append("wp8:method-validation-shape")
        method_records = {}
    completion_methods = wp8.get("methods")
    if (
        not isinstance(completion_methods, list)
        or len(completion_methods) != len(EXPECTED_METHODS)
        or {
            item.get("method")
            for item in completion_methods
            if isinstance(item, dict)
        }
        != EXPECTED_METHODS
    ):
        errors.append("wp8:completion-method-set")
        completion_methods = []
    completion_by_name = {
        item.get("method"): item
        for item in completion_methods
        if isinstance(item, dict) and isinstance(item.get("method"), str)
    }
    specialty_requirements = {
        "predict_reference_agreement",
        "sbc_at_least_400",
        "three_level_convergence",
    }
    for method in EXPECTED_METHODS:
        record = method_records.get(method)
        completion = completion_by_name.get(method)
        if not isinstance(record, dict) or not isinstance(completion, dict):
            continue
        required = record.get("required_checks")
        checks = record.get("checks")
        if (
            record.get("method") != method
            or record.get("status") != "passed"
            or not isinstance(required, list)
            or not isinstance(checks, dict)
            or not specialty_requirements.issubset(required)
            or any(
                not isinstance(checks.get(name), dict)
                or checks[name].get("status") != "passed"
                or checks[name].get("required") is not True
                for name in specialty_requirements
            )
        ):
            errors.append(f"wp8:specialty-evidence:{method}")
        expected_projection = {
            "method": method,
            "status": "Synthetic-validated",
            "required_checks": required,
            "field_validated": False,
        }
        if completion != expected_projection:
            errors.append(f"wp8:completion-projection:{method}")
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    if (
        "continue-on-error: true" in workflow
        or not re.search(
            r"- name: Run WP9 acceptance audit\s+"
            r"run: uv run --frozen python validation/wp9/validate_wp9\.py",
            workflow,
        )
        or any(
            fragment not in workflow
            for fragment in (
                "Run WP5 consistency gate",
                "validate-wp5.ps1",
                "Run WP7 signed evidence gate",
                "validate-wp7.ps1",
                "Run WP8 live synthetic gate",
                "validation/wp8/validate_wp8.py --phase synthetic",
            )
        )
    ):
        errors.append("ci:wp9-not-blocking")
    supplement = json.loads(WP8_SUPPLEMENT_MANIFEST.read_text(encoding="utf-8"))
    supplement_members = supplement.get("members")
    if (
        supplement.get("schema_version") != "wp8-synthetic-supplements-v1"
        or not isinstance(supplement_members, list)
        or len(supplement_members) != 3
    ):
        errors.append("wp8:supplement-manifest")
    else:
        seen: set[str] = set()
        for member in supplement_members:
            if not isinstance(member, dict):
                errors.append("wp8:supplement-member-shape")
                continue
            relative = member.get("path")
            path = safe_repo_file(relative)
            if (
                not isinstance(relative, str)
                or relative in seen
                or path is None
                or sha256_file(path) != member.get("sha256")
            ):
                errors.append(f"wp8:supplement-drift:{relative}")
            seen.add(relative)
    return wp8


def validate_final_gates(
    final_gates: dict[str, Any], errors: list[str]
) -> None:
    if set(final_gates) != {
        "schema_version", "evidence_kind", "generated_by", "generated_at_utc",
        "status", "environment", "gates", "release_acceptance",
    }:
        errors.append("final-gates:fields")
    if (
        final_gates.get("schema_version") != "wp9-final-gates-v1"
        or final_gates.get("evidence_kind") != "current-local-rerun"
        or final_gates.get("generated_by") != "validation/wp9/run_final_gates.py"
    ):
        errors.append("final-gates:identity")
    environment = final_gates.get("environment")
    if not isinstance(environment, dict):
        errors.append("final-gates:environment")
        return
    live_hashes = {
        "python_version_file_sha256": sha256_file(ROOT / ".python-version"),
        "pyproject_sha256": sha256_file(ROOT / "pyproject.toml"),
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        "runner_sha256": sha256_file(RUN_FINAL_GATES),
    }
    if any(environment.get(key) != value for key, value in live_hashes.items()):
        errors.append("final-gates:environment-drift")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", str(environment.get("baseline_commit", "")))
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(environment.get("tracked_diff_sha256", ""))
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(environment.get("status_paths_sha256", ""))
        )
    ):
        errors.append("final-gates:worktree-snapshot")
    if (
        environment.get("status") != "passed"
        or environment.get("uv") != "0.11.29"
        or environment.get("python") != "3.11.15"
        or environment.get("implementation") != "CPython"
        or environment.get("worktree_dirty") is not True
    ):
        errors.append("final-gates:environment-values")
    expected_gates = {
        "pytest", "governance", "wp5", "wp6_self_test",
        "wp7_self_test", "wp8_synthetic_completion", "wp9_acceptance",
    }
    gates = final_gates.get("gates")
    if not isinstance(gates, dict) or set(gates) != expected_gates:
        errors.append("final-gates:gate-set")
        return
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            errors.append(f"final-gates:{name}:shape")
            continue
        log_ref = gate.get("log")
        if not isinstance(log_ref, dict):
            errors.append(f"final-gates:{name}:log")
            continue
        log_path = safe_repo_file(log_ref.get("path"))
        if log_path is None or sha256_file(log_path) != log_ref.get("sha256"):
            errors.append(f"final-gates:{name}:log-drift")
            continue
        log = json.loads(log_path.read_text(encoding="utf-8"))
        portable_log = (
            log.get("cwd") == "."
            and log.get("output_normalization")
            == "repository-root-to-dot; user-home-redacted"
        )
        if (
            log.get("schema_version") != "wp9-gate-log-v1"
            or log.get("gate") != name
            or log.get("exit_code") != gate.get("exit_code")
            or log.get("argv") != gate.get("argv")
            or not portable_log
            or sha256_bytes(log.get("stdout", "").encode("utf-8"))
            != log.get("stdout_sha256")
            or sha256_bytes(log.get("stderr", "").encode("utf-8"))
            != log.get("stderr_sha256")
        ):
            errors.append(f"final-gates:{name}:log-content")
        derived_status = "passed" if gate.get("exit_code") == 0 else "blocked"
        if gate.get("status") != derived_status:
            errors.append(f"final-gates:{name}:status")
        if name == "pytest":
            output = log.get("stdout", "") + log.get("stderr", "")
            derived = {
                "passed": int(re.findall(r"(\d+) passed", output)[-1]),
                "skipped": int(re.findall(r"(\d+) skipped", output)[-1]),
                "warnings": int(re.findall(r"(\d+) warnings", output)[-1]),
            }
            if any(gate.get(key) != value for key, value in derived.items()):
                errors.append("final-gates:pytest-counts")
    blocking = [
        name for name, gate in gates.items() if gate.get("status") != "passed"
    ]
    release = final_gates.get("release_acceptance")
    if (
        not isinstance(release, dict)
        or release.get("blocking_gates") != blocking
        or release.get("status") != ("passed" if not blocking else "blocked")
        or final_gates.get("status") != ("passed" if not blocking else "blocked")
    ):
        errors.append("final-gates:blocking-derivation")
    bootstrap_ref = environment.get("bootstrap_log")
    if not isinstance(bootstrap_ref, dict):
        errors.append("final-gates:bootstrap-log")
    else:
        bootstrap_path = safe_repo_file(bootstrap_ref.get("path"))
        if (
            bootstrap_path is None
            or sha256_file(bootstrap_path) != bootstrap_ref.get("sha256")
        ):
            errors.append("final-gates:bootstrap-log-drift")
        else:
            bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
            if (
                bootstrap.get("schema_version")
                != "wp9-environment-bootstrap-v1"
                or bootstrap.get("uv_version") != "uv 0.11.29 (901092ee1 2026-07-15 x86_64-pc-windows-msvc)"
                or bootstrap.get("status") != "passed"
            ):
                errors.append("final-gates:bootstrap-log-content")
            for name in ("lock", "sync"):
                ref = bootstrap.get(name)
                path = (
                    safe_repo_file(ref.get("path"))
                    if isinstance(ref, dict)
                    else None
                )
                if (
                    path is None
                    or sha256_file(path) != ref.get("sha256")
                ):
                    errors.append(f"final-gates:bootstrap-{name}")
                    continue
                command = json.loads(path.read_text(encoding="utf-8"))
                if (
                    command.get("schema_version") != "wp9-gate-log-v1"
                    or command.get("gate") != f"bootstrap-{name}"
                    or command.get("exit_code") != 0
                ):
                    errors.append(f"final-gates:bootstrap-{name}-content")


def _audit() -> dict[str, Any]:
    errors: list[str] = []
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    findings = validate_registry(registry, errors)
    review_count, covered = validate_reviews(registry, findings, errors)
    validate_wp8(errors)
    final_gates = json.loads(FINAL_GATES.read_text(encoding="utf-8"))
    validate_final_gates(final_gates, errors)
    errors = list(dict.fromkeys(errors))
    return {
        "schema_version": "wp9-acceptance-audit-v1",
        "status": "passed" if not errors else "blocked",
        "counts": registry.get("counts", {}),
        "specialist_reviews": review_count,
        "review_coverage": len(covered),
        "wp8_completion_sha256": sha256_file(WP8_COMPLETION),
        "final_gates_sha256": sha256_file(FINAL_GATES),
        "final_gates_status": final_gates.get("status"),
        "final_gates_live_replay": (
            final_gates.get("evidence_kind") == "current-local-rerun"
        ),
        "errors": errors,
    }


def audit() -> dict[str, Any]:
    try:
        return _audit()
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {
            "schema_version": "wp9-acceptance-audit-v1",
            "status": "blocked",
            "counts": {},
            "specialist_reviews": 0,
            "review_coverage": 0,
            "wp8_completion_sha256": None,
            "final_gates_sha256": None,
            "final_gates_status": "blocked",
            "final_gates_live_replay": False,
            "errors": [f"audit:invalid-input:{type(exc).__name__}"],
        }


def supplement_member_paths() -> list[Path]:
    payload = json.loads(WP8_SUPPLEMENT_MANIFEST.read_text(encoding="utf-8"))
    members = payload.get("members", [])
    paths: list[Path] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        path = safe_repo_file(member.get("path"))
        if path is not None:
            paths.append(path)
    return paths


def expected_manifest_members() -> list[Path]:
    return [
        REGISTRY,
        LEDGER,
        REPORT,
        STATUS,
        CLAIM_MAP,
        ACCEPTANCE_REVIEW,
        FINAL_GATES,
        WP8_COMPLETION,
        *WP8_BINDINGS.values(),
        *supplement_member_paths(),
        CI_WORKFLOW,
        BUILD_REGISTRY,
        RUN_REVIEWS,
        VALIDATOR,
        RUN_FINAL_GATES,
        BUILD_WP8_COMPLETION,
        *sorted((WP9 / "gate-logs-v1").glob("*.json")),
        *(REVIEWS / f"{slug}.json" for slug in sorted(SPECIALISTS)),
    ]


def publish() -> dict[str, Any]:
    result = audit()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    final_gate_data = json.loads(FINAL_GATES.read_text(encoding="utf-8"))
    live_blockers = final_gate_data.get("release_acceptance", {}).get(
        "blocking_gates", []
    )
    package_passed = result["status"] == "passed"
    findings_summary = (
        "保存的 finding 证据登记：60/60；P0：22/22；P1：38/38；"
        "该登记不覆盖当前 live gate 失败。"
        if package_passed
        else "整改项登记值未被本次阻断审计接受为整体验收结论。"
    )
    specialist_summary = (
        "保存的四专项 review：4/4 Approved；同一生成器产生的自动化 AI 证据审查，"
        "`identity_type=automated-ai-specialist-evidence-review`；不是四名独立"
        "人类专家或四套独立工具，也不是现场、资源、法规或生产认证。"
        if package_passed
        else (
            "四专项：Blocked；保存的 review 身份仍为 "
            "`identity_type=automated-ai-specialist-evidence-review`，"
            "不得解释为独立人类专家签章或本次整体验收通过。"
        )
    )
    lines = [
        "# 整改落实报告03",
        "",
        "## 验收结论",
        "",
        f"- 本地证据审计：`{result['status']}`；不等同于 Git 持久化、远程 CI/证明或复审放行。",
        f"- {findings_summary}",
        "- 保存的 WP8 completion 登记：九类 `Synthetic-validated`；当前 live replay 阻断，且不声明 `Field-validated`。",
        f"- {specialist_summary}",
        "- `final-gates-v1.json` 登记本次锁定环境复跑；总门禁为 `blocked`，本地 WP9 证据包通过不覆盖 WP5/WP7/WP8 失败。",
        "",
        "## 逐项落实",
        "",
        "| ID | SourceFindingId | 等级 | 保存登记状态 | 主证据 |",
        "|---|---|---|---|---|",
    ]
    for item in registry["findings"]:
        evidence_path = item["evidence"][0]["path"] if item.get("evidence") else "MISSING"
        lines.append(
            f"| {item['id']} | {item['source_finding_id']} | "
            f"{item['severity']} | {item['status']} | `{evidence_path}` |"
        )
    _atomic_write(REPORT, "\n".join(lines) + "\n")
    local_status = "Passed" if result["status"] == "passed" else "Blocked"
    registry_lines = (
        [
            "- WP0–WP8 saved evidence registry：Done（不表示当前 live gates 通过）",
            "- WP9 saved findings：60/60 Passed",
            "- Saved P0：22/22 Passed",
            "- Saved P1：38/38 Passed",
            "- Saved specialist reviews：4/4 Approved（同源自动化 AI 证据审查；非人类签章）",
        ]
        if package_passed
        else [
            "- WP0–WP9 package：Blocked",
            "- Registry/review saved declarations：not accepted as a package-level pass",
            f"- Blocking errors：{'; '.join(result['errors'])}",
        ]
    )
    status_lines = [
        "# Evidence Status 03",
        "",
        "- Saved WP8 assertion：Synthetic-validated",
        "- Field-validated：False",
        "- WP8 evidence：`validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json`（仓库根相对路径）",
        *registry_lines,
        "- WP9 evidence：`_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp9/manifest-v1.json`",
        f"- Local evidence audit：{local_status}",
        f"- Current live gates：{final_gate_data.get('status', 'blocked').title()} "
        f"({', '.join(live_blockers)}); see `validation/wp9/final-gates-v1.json`",
        "- Release acceptance：Blocked pending live-gate repair, Git persistence, remote CI/attestation and any required human review",
        "",
    ]
    _atomic_write(STATUS, "\n".join(status_lines))
    members = expected_manifest_members()
    manifest = {
        "schema_version": "wp9-final-manifest-v1",
        "path_basis": "repo-root-relative",
        "status": result["status"],
        "members": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                **(
                    {
                        "location_note": (
                            "Repository-root validation/wp8 asset; "
                            "not under the research document directory."
                        )
                    }
                    if path == WP8_COMPLETION
                    else {}
                ),
            }
            for path in members
        ],
        "audit": result,
    }
    _atomic_write(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return result


def _verify_manifest() -> tuple[bool, list[str]]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "wp9-final-manifest-v1":
        errors.append("manifest:schema")
    if manifest.get("path_basis") != "repo-root-relative":
        errors.append("manifest:path-basis")
    members = manifest.get("members")
    if not isinstance(members, list):
        return False, errors + ["manifest:members"]
    if not all(isinstance(member, dict) for member in members):
        errors.append("manifest:member-shape")
    paths = [member.get("path") for member in members if isinstance(member, dict)]
    expected_paths = {
        path.relative_to(ROOT).as_posix() for path in expected_manifest_members()
    }
    if (
        not all(isinstance(path, str) for path in paths)
        or len(paths) != len(set(path for path in paths if isinstance(path, str)))
        or set(path for path in paths if isinstance(path, str)) != expected_paths
    ):
        errors.append("manifest:member-set")
    for member in members:
        if not isinstance(member, dict):
            errors.append("manifest:member-shape")
            continue
        relative = member.get("path")
        path = safe_repo_file(relative)
        if path is None:
            errors.append(f"manifest:unsafe-or-missing:{relative}")
        elif (
            path.stat().st_size != member.get("bytes")
            or sha256_file(path) != member.get("sha256")
        ):
            errors.append(f"manifest:drift:{relative}")
        if path == WP8_COMPLETION and "Repository-root validation/wp8 asset" not in str(
            member.get("location_note", "")
        ):
            errors.append("manifest:wp8-location-note")
    replay = audit()
    if manifest.get("audit") != replay:
        errors.append("manifest:audit-replay-mismatch")
    if manifest.get("status") != replay["status"]:
        errors.append("manifest:status")
    return not errors, list(dict.fromkeys(errors))


def verify_manifest() -> tuple[bool, list[str]]:
    try:
        return _verify_manifest()
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return False, [f"manifest:invalid-input:{type(exc).__name__}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Regenerate report, status, and manifest before verifying them.",
    )
    args = parser.parse_args()
    try:
        result = publish() if args.publish else audit()
        ok, errors = verify_manifest()
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        result = {
            "schema_version": "wp9-acceptance-audit-v1",
            "status": "blocked",
            "errors": [f"main:invalid-input:{type(exc).__name__}"],
        }
        ok, errors = False, result["errors"]
    print(
        json.dumps(
            {"audit": result, "manifest_ok": ok, "manifest_errors": errors},
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "passed" and ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
