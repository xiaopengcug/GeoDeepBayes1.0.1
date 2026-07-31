import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "validation/wp9/validate_wp9.py"
GENERATOR_SCRIPT = SCRIPT.with_name("run_specialist_reviews.py")
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("validate_wp9", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "run_specialist_reviews", GENERATOR_SCRIPT
)
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
assert GENERATOR_SPEC.loader
GENERATOR_SPEC.loader.exec_module(GENERATOR)


def copy_reviews(tmp_path: Path) -> Path:
    target = tmp_path / "reviews-v1"
    shutil.copytree(MODULE.REVIEWS, target)
    return target


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_wp9_live_audit_passes():
    result = MODULE.audit()
    assert result["status"] == "passed"
    assert result["counts"] == {"total": 60, "p0": 22, "p1": 38, "passed": 60}
    assert result["specialist_reviews"] == 4
    assert result["review_coverage"] == 60


def test_wp9_manifest_rejects_member_tamper(tmp_path, monkeypatch):
    original = MODULE.MANIFEST
    manifest = json.loads(original.read_text(encoding="utf-8"))
    manifest["members"][0]["sha256"] = "0" * 64
    target = tmp_path / "manifest.json"
    write_json(target, manifest)
    monkeypatch.setattr(MODULE, "MANIFEST", target)
    ok, errors = MODULE.verify_manifest()
    assert ok is False
    assert any(error.startswith("manifest:drift:") for error in errors)


def test_wp9_manifest_rejects_path_escape(tmp_path, monkeypatch):
    manifest = json.loads(MODULE.MANIFEST.read_text(encoding="utf-8"))
    manifest["members"][0]["path"] = "../outside"
    target = tmp_path / "manifest.json"
    write_json(target, manifest)
    monkeypatch.setattr(MODULE, "MANIFEST", target)
    ok, errors = MODULE.verify_manifest()
    assert ok is False
    assert "manifest:unsafe-or-missing:../outside" in errors


def test_reviews_have_distinct_required_specialty_checks():
    check_sets = []
    for slug, config in MODULE.SPECIALISTS.items():
        review = json.loads(
            (MODULE.REVIEWS / f"{slug}.json").read_text(encoding="utf-8")
        )
        assert review["specialty_slug"] == slug
        assert set(review["checks"]) == MODULE.COMMON_CHECKS | {config["key"]}
        assert all(value is True for value in review["checks"].values())
        check_sets.append(frozenset(review["checks"]))
    assert len(set(check_sets)) == 4


def test_wp9_audit_rejects_rejected_review(tmp_path, monkeypatch):
    reviews = copy_reviews(tmp_path)
    target = reviews / "geophysics-forward-physics.json"
    review = json.loads(target.read_text(encoding="utf-8"))
    review["decision"] = "Rejected"
    review["blocking_findings"] = ["synthetic-negative"]
    write_json(target, review)
    monkeypatch.setattr(MODULE, "REVIEWS", reviews)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert "review:geophysics-forward-physics.json:rejected" in result["errors"]
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert MODULE.main() == 4


def test_wp9_audit_rejects_homogeneous_or_missing_specialty_key(
    tmp_path, monkeypatch
):
    reviews = copy_reviews(tmp_path)
    target = reviews / "bayesian-uq-statistics.json"
    review = json.loads(target.read_text(encoding="utf-8"))
    review["checks"].pop("sbc_coverage_recorded")
    write_json(target, review)
    monkeypatch.setattr(MODULE, "REVIEWS", reviews)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert "reviews:template-degraded" in result["errors"]
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert MODULE.main() == 4


def test_wp9_audit_rejects_human_identity_mislabel(tmp_path, monkeypatch):
    reviews = copy_reviews(tmp_path)
    target = reviews / "numerical-discretization.json"
    review = json.loads(target.read_text(encoding="utf-8"))
    review["identity_type"] = "independent-human-specialist"
    write_json(target, review)
    monkeypatch.setattr(MODULE, "REVIEWS", reviews)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert "review:numerical-discretization.json:identity" in result["errors"]
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert MODULE.main() == 4


def test_wp9_registry_recomputes_counts_and_requires_evidence(
    tmp_path, monkeypatch
):
    registry = json.loads(MODULE.REGISTRY.read_text(encoding="utf-8"))
    registry["counts"]["p0"] = 0
    registry["findings"][0]["evidence"] = []
    target = tmp_path / "registry.json"
    write_json(target, registry)
    monkeypatch.setattr(MODULE, "REGISTRY", target)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert "registry:counts" in result["errors"]
    source_id = registry["findings"][0]["source_finding_id"]
    assert f"{source_id}:evidence-empty" in result["errors"]


def test_wp9_registry_rejects_ledger_hash_drift(tmp_path, monkeypatch):
    registry = json.loads(MODULE.REGISTRY.read_text(encoding="utf-8"))
    registry["ledger_sha256"] = "0" * 64
    target = tmp_path / "registry.json"
    write_json(target, registry)
    monkeypatch.setattr(MODULE, "REGISTRY", target)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert "registry:ledger-sha" in result["errors"]


def test_wp9_manifest_rejects_missing_and_duplicate_members(tmp_path, monkeypatch):
    manifest = json.loads(MODULE.MANIFEST.read_text(encoding="utf-8"))
    manifest["members"].pop()
    manifest["members"].append(dict(manifest["members"][0]))
    target = tmp_path / "manifest.json"
    write_json(target, manifest)
    monkeypatch.setattr(MODULE, "MANIFEST", target)
    ok, errors = MODULE.verify_manifest()
    assert ok is False
    assert "manifest:member-set" in errors


def test_wp9_default_cli_is_read_only():
    before = {
        path: path.read_bytes()
        for path in (MODULE.REPORT, MODULE.STATUS, MODULE.MANIFEST)
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=SCRIPT.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(path.read_bytes() == body for path, body in before.items())


def test_wp9_blocked_audit_maps_to_exit_code_four(monkeypatch):
    monkeypatch.setattr(
        MODULE,
        "audit",
        lambda: {"schema_version": "test", "status": "blocked", "errors": ["x"]},
    )
    monkeypatch.setattr(MODULE, "verify_manifest", lambda: (True, []))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert MODULE.main() == 4


def test_specialty_evidence_is_replayed_not_trusted(tmp_path, monkeypatch):
    method_validation = json.loads(
        MODULE.WP8_METHOD_VALIDATION.read_text(encoding="utf-8")
    )
    method_validation["methods"]["gravity"]["checks"]["sbc_at_least_400"][
        "status"
    ] = "failed"
    target = tmp_path / "method-validation.json"
    write_json(target, method_validation)
    bindings = dict(MODULE.WP8_BINDINGS)
    bindings["method_validation"] = target
    monkeypatch.setattr(MODULE, "WP8_METHOD_VALIDATION", target)
    monkeypatch.setattr(MODULE, "WP8_BINDINGS", bindings)
    errors = []
    MODULE.validate_wp8(errors)
    assert "wp8:specialty-evidence:gravity" in errors


def test_specialist_generator_rejects_missing_check_and_duplicate_method(
    tmp_path, monkeypatch
):
    wp8 = json.loads(GENERATOR.WP8_COMPLETION.read_text(encoding="utf-8"))
    wp8["methods"][0]["required_checks"].remove("sbc_at_least_400")
    assert GENERATOR.specialty_check("bayesian-uq-statistics", wp8) is False
    wp8 = json.loads(GENERATOR.WP8_COMPLETION.read_text(encoding="utf-8"))
    wp8["methods"][1]["method"] = wp8["methods"][0]["method"]
    assert GENERATOR.method_checks(wp8) == []
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "- name: Run WP9 acceptance audit\n"
        "  continue-on-error: true\n"
        "  run: uv run --frozen python validation/wp9/validate_wp9.py\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(GENERATOR, "CI_WORKFLOW", workflow)
    assert (
        GENERATOR.specialty_check(
            "engineering-governance-reproducibility",
            json.loads(GENERATOR.WP8_COMPLETION.read_text(encoding="utf-8")),
        )
        is False
    )


def test_registry_rejects_primary_wp_tamper_and_malformed_item(
    tmp_path, monkeypatch
):
    registry = json.loads(MODULE.REGISTRY.read_text(encoding="utf-8"))
    registry["findings"][0]["primary_work_package"] = "WP1"
    target = tmp_path / "registry-primary-wp.json"
    write_json(target, registry)
    monkeypatch.setattr(MODULE, "REGISTRY", target)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert f"{registry['findings'][0]['source_finding_id']}:primary-wp" in result[
        "errors"
    ]
    registry["findings"][0] = ["not-an-object"]
    write_json(target, registry)
    result = MODULE.audit()
    assert result["status"] == "blocked"
    assert "registry:item-shape" in result["errors"]


def test_blocked_publish_does_not_claim_passed_or_approved(
    tmp_path, monkeypatch
):
    report = tmp_path / "report.md"
    status = tmp_path / "status.md"
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    monkeypatch.setattr(MODULE, "REPORT", report)
    monkeypatch.setattr(MODULE, "STATUS", status)
    monkeypatch.setattr(MODULE, "MANIFEST", manifest)
    monkeypatch.setattr(MODULE, "expected_manifest_members", lambda: [report, status])
    monkeypatch.setattr(
        MODULE,
        "audit",
        lambda: {
            "schema_version": "wp9-acceptance-audit-v1",
            "status": "blocked",
            "counts": {},
            "specialist_reviews": 4,
            "review_coverage": 60,
            "wp8_completion_sha256": None,
            "final_gates_sha256": None,
            "final_gates_status": "blocked",
            "final_gates_live_replay": False,
            "errors": ["review:synthetic:rejected"],
        },
    )
    MODULE.publish()
    summary = report.read_text(encoding="utf-8").split("## 逐项落实", 1)[0]
    status_text = status.read_text(encoding="utf-8")
    assert "Passed" not in summary
    assert "Approved" not in summary
    assert "Passed" not in status_text
    assert "Approved" not in status_text
    assert "Blocked" in status_text
