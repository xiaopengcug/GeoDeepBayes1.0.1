#!/usr/bin/env python
"""Build and verify the fail-closed WP8 synthetic-completion artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import validate_wp8

ROOT = Path(__file__).resolve().parents[2]
WP8 = Path(__file__).resolve().parent
EVIDENCE = WP8 / "evidence" / "feasibility-v1"
OUTPUT = EVIDENCE / "wp8-synthetic-completion-v1.json"

BOUND_INPUTS = {
    "authorization": WP8 / "evidence" / "wp8-1-start.json",
    "method_validation": EVIDENCE / "wp8-1-method-synthetic-validation-v1.json",
    "supplement_manifest": WP8 / "synthetic" / "supplements-v1" / "manifest.json",
    "method_policy": WP8 / "synthetic" / "method-validation-policy-v1.json",
    "synthetic_readiness": WP8 / "synthetic" / "readiness.json",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_completion() -> dict[str, Any]:
    audit = validate_wp8.audit_synthetic_phase()
    methods = audit.get("method_validation", {}).get("methods", {})
    method_records = []
    for method in validate_wp8.METHOD_NAMES:
        record = methods.get(method, {})
        method_records.append(
            {
                "method": method,
                "status": "Synthetic-validated"
                if record.get("status") == "passed"
                else "blocked",
                "required_checks": record.get("required_checks", []),
                "field_validated": False,
            }
        )
    passed = (
        audit.get("status") == "passed"
        and audit.get("wp8_completion_allowed") is True
        and audit.get("wp9_start_allowed") is True
        and audit.get("field_validated_claim_created") is False
        and len(method_records) == 9
        and all(item["status"] == "Synthetic-validated" for item in method_records)
    )
    return {
        "schema_version": "wp8-synthetic-completion-v1",
        "status": "passed" if passed else "blocked",
        "validation_assertion": "synthetic_prediction_verified",
        "field_validated": False,
        "field_data_required": False,
        "wp8_complete": passed,
        "wp9_start_allowed": passed,
        "formal_field_feasibility": audit.get("formal_feasibility"),
        "methods": method_records,
        "bindings_sha256": {
            name: sha256_file(path) for name, path in BOUND_INPUTS.items()
        },
        "errors": list(audit.get("errors", [])),
    }


def verify_completion(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    live = build_completion()
    if payload != live:
        errors.append("completion:semantic-replay-mismatch")
    if payload.get("validation_assertion") != "synthetic_prediction_verified":
        errors.append("completion:assertion-invalid")
    if payload.get("field_validated") is not False:
        errors.append("completion:field-claim-forbidden")
    if payload.get("wp8_complete") is not True:
        errors.append("completion:wp8-not-complete")
    if payload.get("wp9_start_allowed") is not True:
        errors.append("completion:wp9-blocked")
    return not errors, errors


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(body)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    payload = build_completion()
    if args.write:
        write_atomic(OUTPUT, payload)
    ok, errors = verify_completion(payload)
    print(json.dumps({"artifact": str(OUTPUT), "ok": ok, "errors": errors}))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
