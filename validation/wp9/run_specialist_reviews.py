#!/usr/bin/env python
"""Run four isolated, deterministic WP9 specialist evidence reviews."""
from __future__ import annotations

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
REGISTRY = RESEARCH / "validation/wp9/finding-registry-v1.json"
OUTPUT = RESEARCH / "validation/wp9/reviews-v1"
WP8_COMPLETION = ROOT / "validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json"
WP8_METHOD_VALIDATION = (
    ROOT / "validation/wp8/evidence/feasibility-v1"
    / "wp8-1-method-synthetic-validation-v1.json"
)
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
EXPECTED_METHODS = {
    "gravity", "magnetic", "dc", "tdip", "sip_fdip",
    "tem", "mt_amt", "csamt", "wfem",
}

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
        "specialty_key": "forward_unit_consistent",
    },
    "bayesian-uq-statistics": {
        "name": "贝叶斯/UQ与统计设计",
        "wps": {"WP1", "WP4", "WP8"},
        "specialty_key": "sbc_coverage_recorded",
    },
    "numerical-discretization": {
        "name": "算法数值与离散化",
        "wps": {"WP2", "WP7", "WP8"},
        "specialty_key": "discretization_converged",
    },
    "engineering-governance-reproducibility": {
        "name": "工程架构、数据治理与可复现性",
        "wps": {"WP5", "WP6", "WP7", "WP8"},
        "specialty_key": "gates_blocked_on_fail",
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, body: str) -> None:
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


def frontmatter_status(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8-sig")
    match = re.match(r"^---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        return None
    status = re.search(
        r"^status:\s*['\"]?([^'\"\r\n]+)['\"]?\s*$",
        match.group("body"),
        re.MULTILINE,
    )
    return status.group(1).strip() if status else None


def method_checks(wp8: dict[str, Any]) -> list[set[str]]:
    methods = wp8.get("methods")
    if (
        not isinstance(methods, list)
        or len(methods) != len(EXPECTED_METHODS)
        or {
            method.get("method")
            for method in methods
            if isinstance(method, dict)
        }
        != EXPECTED_METHODS
    ):
        return []
    checks: list[set[str]] = []
    for method in methods:
        required = method.get("required_checks") if isinstance(method, dict) else None
        if (
            not isinstance(required, list)
            or not all(isinstance(item, str) for item in required)
            or method.get("status") != "Synthetic-validated"
            or method.get("field_validated") is not False
        ):
            return []
        checks.append(set(required))
    return checks


def specialty_check(slug: str, wp8: dict[str, Any]) -> bool:
    checks = method_checks(wp8)
    if not checks:
        return False
    if slug == "geophysics-forward-physics":
        return all("predict_reference_agreement" in item for item in checks)
    if slug == "bayesian-uq-statistics":
        return all("sbc_at_least_400" in item for item in checks)
    if slug == "numerical-discretization":
        return all("three_level_convergence" in item for item in checks)
    if slug == "engineering-governance-reproducibility":
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        return (
            "continue-on-error: true" not in workflow
            and "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in workflow
            and "Run unit tests" in workflow
            and "Run WP9 acceptance audit" in workflow
            and "uv run --frozen python validation/wp9/validate_wp9.py" in workflow
            and "Run WP5 consistency gate" in workflow
            and "validate-wp5.ps1" in workflow
            and "Run WP7 signed evidence gate" in workflow
            and "validate-wp7.ps1" in workflow
            and "Run WP8 live synthetic gate" in workflow
            and "validation/wp8/validate_wp8.py --phase synthetic" in workflow
        )
    return False


def _run() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    wp8 = json.loads(WP8_COMPLETION.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expected_files = {f"{slug}.json" for slug in SPECIALISTS}
    extras = {path.name for path in OUTPUT.glob("*.json")} - expected_files
    if extras:
        print(json.dumps({"reviews": 0, "approved": False, "errors": ["unexpected-review-files"]}))
        return 4
    all_ok = True
    rendered: dict[Path, str] = {}
    for slug, config in SPECIALISTS.items():
        findings = [
            item for item in registry["findings"]
            if item["primary_work_package"] in config["wps"]
        ]
        errors = []
        for finding in findings:
            evidence_records = finding.get("evidence")
            if not isinstance(evidence_records, list) or not evidence_records:
                errors.append(f"{finding['source_finding_id']}:missing-evidence")
                continue
            for evidence in evidence_records:
                path = safe_repo_file(evidence.get("path"))
                if path is None:
                    errors.append(f"{finding['source_finding_id']}:missing-evidence")
                elif sha256_file(path) != evidence["sha256"]:
                    errors.append(f"{finding['source_finding_id']}:hash-drift")
                elif frontmatter_status(path) != "done":
                    errors.append(f"{finding['source_finding_id']}:wp-not-done")
        if "WP8" in config["wps"] and not (
            wp8.get("status") == "passed"
            and wp8.get("wp8_complete") is True
            and wp8.get("field_validated") is False
            and wp8.get("validation_assertion") == "synthetic_prediction_verified"
        ):
            errors.append("WP8:synthetic-boundary-invalid")
        specialty_ok = specialty_check(slug, wp8)
        if not specialty_ok:
            errors.append(f"{slug}:{config['specialty_key']}:failed")
        checks = {
            "evidence_exists": not any("missing-evidence" in e for e in errors),
            "evidence_hashes_match": not any("hash-drift" in e for e in errors),
            "work_packages_done": not any("wp-not-done" in e for e in errors),
            "synthetic_not_field_claim": "WP8:synthetic-boundary-invalid" not in errors,
            config["specialty_key"]: specialty_ok,
        }
        assert set(checks) == COMMON_CHECKS | {config["specialty_key"]}
        review = {
            "schema_version": "wp9-specialist-review-v1",
            "identity_type": IDENTITY_TYPE,
            "specialty_slug": slug,
            "specialty": config["name"],
            "registry_sha256": sha256_file(REGISTRY),
            "wp8_completion_sha256": sha256_file(WP8_COMPLETION),
            "specialty_evidence_sha256": (
                sha256_file(CI_WORKFLOW)
                if slug == "engineering-governance-reproducibility"
                else sha256_file(WP8_METHOD_VALIDATION)
            ),
            "covered_source_finding_ids": [
                item["source_finding_id"] for item in findings
            ],
            "checks": checks,
            "blocking_findings": errors,
            "decision": "Approved" if not errors else "Rejected",
            "scope_limit": SCOPE_LIMIT,
        }
        rendered[OUTPUT / f"{slug}.json"] = (
            json.dumps(review, ensure_ascii=False, indent=2) + "\n"
        )
        all_ok &= not errors
    for path, body in rendered.items():
        atomic_write(path, body)
    print(json.dumps({"reviews": len(SPECIALISTS), "approved": all_ok}))
    return 0 if all_ok else 4


def main() -> int:
    try:
        return _run()
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        print(
            json.dumps(
                {
                    "reviews": 0,
                    "approved": False,
                    "errors": [f"invalid-input:{type(exc).__name__}"],
                }
            )
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
