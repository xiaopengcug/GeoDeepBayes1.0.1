import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[2]
    / "validation"
    / "wp8"
    / "build_synthetic_completion.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("build_synthetic_completion", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def _passed_audit():
    methods = {
        method: {"status": "passed", "required_checks": ["reference", "adversarial"]}
        for method in MODULE.validate_wp8.METHOD_NAMES
    }
    return {
        "status": "passed",
        "wp8_completion_allowed": True,
        "wp9_start_allowed": True,
        "field_validated_claim_created": False,
        "formal_feasibility": {
            "passed_methods": 6,
            "total_methods": 9,
            "wp8_1_allowed": False,
        },
        "method_validation": {"methods": methods},
        "errors": [],
    }


def test_completion_allows_wp9_without_field_claim(monkeypatch):
    monkeypatch.setattr(MODULE.validate_wp8, "audit_synthetic_phase", _passed_audit)
    payload = MODULE.build_completion()
    assert payload["status"] == "passed"
    assert payload["wp8_complete"] is True
    assert payload["wp9_start_allowed"] is True
    assert payload["field_validated"] is False
    assert payload["validation_assertion"] == "synthetic_prediction_verified"
    assert len(payload["methods"]) == 9
    assert MODULE.verify_completion(payload) == (True, [])


def test_completion_fails_closed_if_any_method_blocks(monkeypatch):
    audit = _passed_audit()
    audit["method_validation"]["methods"]["wfem"]["status"] = "blocked"
    monkeypatch.setattr(
        MODULE.validate_wp8, "audit_synthetic_phase", lambda: audit
    )
    payload = MODULE.build_completion()
    assert payload["status"] == "blocked"
    assert payload["wp8_complete"] is False
    assert payload["wp9_start_allowed"] is False


def test_completion_rejects_field_claim_and_tamper(monkeypatch):
    monkeypatch.setattr(MODULE.validate_wp8, "audit_synthetic_phase", _passed_audit)
    payload = MODULE.build_completion()
    tampered = json.loads(json.dumps(payload))
    tampered["field_validated"] = True
    ok, errors = MODULE.verify_completion(tampered)
    assert ok is False
    assert "completion:semantic-replay-mismatch" in errors
    assert "completion:field-claim-forbidden" in errors
