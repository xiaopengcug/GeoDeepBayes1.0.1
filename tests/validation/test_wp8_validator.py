import importlib.util
import json
import hashlib
import subprocess
import time
import sys
import types
import pytest
from pathlib import Path

import numpy as np
SCRIPT = Path(__file__).parents[2] / "validation/wp8/validate_wp8.py"
SPEC = importlib.util.spec_from_file_location("validate_wp8", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)
AUDIT_SCRIPT = SCRIPT.with_name("audit_field_contracts.py")
AUDIT_SPEC = importlib.util.spec_from_file_location("audit_field_contracts", AUDIT_SCRIPT)
AUDIT_MODULE = importlib.util.module_from_spec(AUDIT_SPEC)
assert AUDIT_SPEC.loader
AUDIT_SPEC.loader.exec_module(AUDIT_MODULE)


def test_required_repository_assets_are_canonical_and_complete():
    expected = (
        "validation/wp8/contracts/field-preregistration-scaffold.schema.json",
        "validation/wp8/contracts/wp8-feasibility.schema.json",
        "validation/wp8/datasets.json",
        "validation/wp8/evidence/wp8-1-start.json",
        "validation/wp8/field/preregistration-scaffold-v1.json",
        "validation/wp8/preregistration/wp8-0-v1.json",
        "validation/wp8/synthetic/method-validation-policy-v1.json",
        "validation/wp8/synthetic/readiness.json",
    )
    assets = MODULE.required_repository_assets()

    assert assets == expected
    assert assets == tuple(sorted(set(assets)))
    assert all(
        not Path(path).is_absolute() and Path(path).as_posix() == path
        for path in assets
    )
    assert all(".." not in Path(path).parts for path in assets)
    assert all((MODULE.ROOT / path).is_file() for path in assets)
    assert {
        MODULE.DATASETS,
        MODULE.PREREG,
        MODULE.REGISTRATION_SCHEMA,
        MODULE.WP8_1_START,
        MODULE.FIELD_PREREGISTRATION_SCAFFOLD,
        MODULE.FIELD_PREREGISTRATION_SCHEMA,
        MODULE.METHOD_VALIDATION_POLICY,
        MODULE.SYNTHETIC_READINESS,
    } == {MODULE.ROOT / path for path in assets}


def test_merkle_root_changes_with_member():
    members = [{"path": "a", "sha256": "1"}, {"path": "b", "sha256": "2"}]
    before = MODULE.merkle_root(members)
    members[1]["sha256"] = "3"
    assert MODULE.merkle_root(members) != before


def test_protected_manifest_rejects_tamper(tmp_path):
    MODULE.write_json(tmp_path / "decision.json", {"status": "failed"})
    MODULE.write_json(tmp_path / "protected-manifest.json", MODULE.protected_manifest(tmp_path))
    assert MODULE.verify_protected(tmp_path) == (True, [])
    MODULE.write_json(tmp_path / "decision.json", {"status": "passed"})
    ok, errors = MODULE.verify_protected(tmp_path)
    assert ok is False
    assert errors == ["tampered:decision.json"]


def test_protected_manifest_rejects_path_traversal(tmp_path):
    MODULE.write_json(
        tmp_path / "protected-manifest.json",
        {
            "schema_version": "wp8-protected-manifest-v1",
            "members": [{"path": "../decision.json", "bytes": 1, "sha256": "0"}],
        },
    )
    ok, errors = MODULE.verify_protected(tmp_path)
    assert ok is False
    assert errors == ["unsafe-path:../decision.json"]


def test_active_pointer_rejects_drift(tmp_path):
    MODULE.write_json(tmp_path / "decision.json", {"status": "failed"})
    MODULE.write_json(tmp_path / "protected-manifest.json", MODULE.protected_manifest(tmp_path))
    MODULE.write_json(
        tmp_path / "ACTIVE_MANIFEST.json",
        {"protected_manifest_sha256": MODULE.sha256_file(tmp_path / "protected-manifest.json")},
    )
    assert MODULE.verify_active_pointer(tmp_path) == (True, "")
    MODULE.write_json(tmp_path / "decision.json", {"status": "passed"})
    # Protected member drift and pointer drift are orthogonal checks.
    assert MODULE.verify_protected(tmp_path)[0] is False
    MODULE.write_json(
        tmp_path / "ACTIVE_MANIFEST.json", {"protected_manifest_sha256": "0" * 64}
    )
    assert MODULE.verify_active_pointer(tmp_path) == (False, "active pointer drift")


def _write_start_record(path):
    MODULE.write_json(
        path,
        {
            "schema_version": "wp8-1-synthetic-completion-authorization-v2",
            "status": "synthetic-completion-authorized",
            "authorization": {
                "kind": "explicit-user-risk-acceptance",
                "field_data_required_for_wp8_completion": False,
                "synthetic_completion_allowed": True,
            },
            "feasibility_decision": {
                "status": "failed",
                "passed_methods": 6,
                "total_methods": 9,
                "wp8_1_allowed": False,
                "reason_code": "WP8_0_NOT_ALL_NINE_PASSED",
            },
            "authorized_scope": [
                "public-interface-implementation",
                "operator-implementation",
                "synthetic-development-and-validation",
                "synthetic-substitutes-for-known-gaps",
                "training-only-power-analysis",
                "wp8-synthetic-completion",
                "wp9-start",
            ],
            "prohibited_until_formal_gates_pass": [
                "formal-field-test-unsealing",
                "field-validated-claim",
            ],
        },
    )


def _copy_synthetic_fixture(tmp_path, monkeypatch):
    pristine_validation = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    monkeypatch.setattr(
        MODULE,
        "run_method_synthetic_validation",
        lambda: json.loads(json.dumps(pristine_validation)),
    )
    source = MODULE.SYNTHETIC_SUPPLEMENTS
    target = tmp_path / "supplements-v1"
    target.mkdir()
    for path in source.iterdir():
        (target / path.name).write_bytes(path.read_bytes())
    start = tmp_path / "wp8-1-start.json"
    _write_start_record(start)
    monkeypatch.setattr(MODULE, "WP8_1_START", start)
    monkeypatch.setattr(MODULE, "SYNTHETIC_SUPPLEMENTS", target)
    monkeypatch.setattr(MODULE, "SYNTHETIC_MANIFEST", target / "manifest.json")
    return target, start


def test_synthetic_phase_accepts_only_development_substitutes(tmp_path, monkeypatch):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "passed"
    assert report["use"] == "wp8-synthetic-completion"
    assert report["wp8_completion_allowed"] is True
    assert report["wp9_start_allowed"] is True
    assert report["formal_feasibility"] == {
        "passed_methods": 6,
        "total_methods": 9,
        "wp8_1_allowed": False,
    }
    assert report["field_phase"] == "not-required-for-synthetic-completion"
    assert report["field_validated_claim_created"] is False
    assert {item["method"] for item in report["members"]} == {
        "sip_fdip",
        "csamt",
        "wfem",
    }
    assert report["method_validation"]["status"] == "passed"
    assert report["method_validation"]["field_validation_eligible"] is False


def test_semantic_replay_alone_catches_finite_structurally_valid_metric_change(
    tmp_path, monkeypatch
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    metrics = evidence["methods"]["gravity"]["checks"][
        "predict_reference_agreement"
    ]["metrics"]
    metrics["relative_error"] = metrics["threshold"] * 0.5
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["errors"] == ["method-validation:semantic-replay-mismatch"]


def test_semantic_replay_accepts_environment_and_solver_noise():
    recorded = {
        "provenance_bindings": {
            "runtime": {
                "platform": "Windows-10-build-a",
                "machine": "AMD64",
                "python": "3.11.15",
            }
        },
        "metrics": {
            "relative_error": 2.1e-7,
            "threshold": 5e-6,
            "environment_qualification": {"logical_cpu_count": 16},
        },
        "status": "passed",
    }
    replayed = {
        "provenance_bindings": {
            "runtime": {
                "platform": "Linux-kernel-b",
                "machine": "x86_64",
                "python": "3.11.15",
            }
        },
        "metrics": {
            "relative_error": np.float64(1.35e-7),
            "threshold": 5e-6,
            "environment_qualification": {"logical_cpu_count": 12},
        },
        "status": "passed",
    }
    assert MODULE._semantic_replay_equal(recorded, replayed)


def test_semantic_replay_accepts_linux_windows_taylor_order_tail_drift():
    recorded = {
        "metrics": {
            "observed_orders": [1.998555807894014, 1.9992859858380885],
            "minimum_order": 1.8,
        },
        "status": "passed",
    }
    replayed = {
        "metrics": {
            "observed_orders": [1.9985559629963823, 1.9992876827202783],
            "minimum_order": 1.8,
        },
        "status": "passed",
    }
    below_gate = {
        "metrics": {
            "observed_orders": [1.9985559629963823, 1.79],
            "minimum_order": 1.8,
        },
        "status": "passed",
    }
    assert MODULE._semantic_replay_equal(recorded, replayed)
    assert not MODULE._semantic_replay_equal(recorded, below_gate)


def test_semantic_replay_rejects_decision_relevant_numeric_change():
    recorded = {
        "metrics": {"relative_error": 1e-8, "threshold": 1e-6},
        "status": "passed",
    }
    replayed = {
        "metrics": {"relative_error": 5e-7, "threshold": 1e-6},
        "status": "passed",
    }
    assert not MODULE._semantic_replay_equal(recorded, replayed)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda evidence: evidence["methods"].__setitem__("gravity", []),
        lambda evidence: evidence["methods"]["gravity"]["checks"].__setitem__(
            "taylor_remainder_order", []
        ),
        lambda evidence: evidence["methods"]["gravity"]["checks"][
            "method_adversarial_suite"
        ].__setitem__("metrics", []),
        lambda evidence: evidence["methods"]["gravity"]["checks"].__setitem__(
            "sbc_at_least_400", []
        ),
        lambda evidence: evidence["methods"]["gravity"]["checks"].__setitem__(
            "within_method_5x5_performance", []
        ),
    ],
)
def test_malformed_nested_method_evidence_blocks_without_exception(
    tmp_path, monkeypatch, mutate
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8"))
    mutate(evidence)
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("normalization_scale", "1.0"),
        ("scale_aware_exact_tolerance", []),
        ("normalized_remainders", [0.0, "bad", 0.0]),
        ("observed_orders", [2.0, "bad"]),
    ],
)
def test_taylor_metric_type_attacks_fail_closed(
    tmp_path, monkeypatch, field, value
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8"))
    metrics = evidence["methods"]["gravity"]["checks"]["taylor_remainder_order"]["metrics"]
    metrics[field] = value
    if field == "observed_orders":
        metrics["order_kind"] = "observed_remainder_orders"
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "gravity:taylor-check-invalid" in report["errors"]


def test_provenance_path_escape_blocks_with_real_correctly_hashed_file(
    tmp_path, monkeypatch
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    outside = tmp_path / "real-outside-root.py"
    outside.write_bytes(b"real file with a correct digest outside validator ROOT\n")
    evidence = json.loads(MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8"))
    evidence["provenance_bindings"]["files_sha256"][str(outside.resolve())] = (
        hashlib.sha256(outside.read_bytes()).hexdigest()
    )
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "method-validation:dependency-path-escape" in report["errors"]
    assert "method-validation:dependency-hash-mismatch" not in report["errors"]


def test_live_replay_exception_is_reported_as_blocked(tmp_path, monkeypatch):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        MODULE, "run_method_synthetic_validation",
        lambda: (_ for _ in ()).throw(RuntimeError("replay failed")),
    )
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "method-validation:semantic-replay-failed" in report["errors"]


def test_policy_drift_blocks_even_when_evidence_policy_hash_is_regenerated(
    tmp_path, monkeypatch
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    policy = json.loads(MODULE.METHOD_VALIDATION_POLICY.read_text(encoding="utf-8"))
    policy["readiness_reason"] = "mutated but internally consistent"
    policy_path = tmp_path / "policy.json"
    MODULE.write_json(policy_path, policy)
    evidence = json.loads(MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8"))
    evidence["provenance_bindings"]["files_sha256"][
        "validation/wp8/synthetic/method-validation-policy-v1.json"
    ] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    evidence_path = tmp_path / "method-validation.json"
    MODULE.write_json(evidence_path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_VALIDATION_POLICY", policy_path)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", evidence_path)
    monkeypatch.setattr(
        MODULE, "run_method_synthetic_validation",
        lambda: json.loads(json.dumps(evidence)),
    )
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "method-validation-policy:contract-drift" in report["errors"]


def test_sbc_internal_inconsistency_is_recomputed_and_blocked(tmp_path, monkeypatch):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8"))
    evidence["methods"]["gravity"]["checks"]["sbc_at_least_400"]["metrics"][
        "counts"
    ][0] += 1
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert "gravity:sbc-invalid" in report["errors"]


def test_performance_reported_ratio_is_recomputed_and_blocked(tmp_path, monkeypatch):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8"))
    evidence["methods"]["gravity"]["checks"]["within_method_5x5_performance"][
        "metrics"
    ]["median_warm_scaling_ratio"] = 1.0
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert "gravity:performance-benchmark-invalid" in report["errors"]


def test_field_preregistration_scaffold_tamper_remains_blocked(tmp_path, monkeypatch):
    payload = json.loads(
        MODULE.FIELD_PREREGISTRATION_SCAFFOLD.read_text(encoding="utf-8")
    )
    payload["all_nine_feasibility_passed"] = True
    payload["status"] = "ready"
    path = tmp_path / "field-scaffold.json"
    MODULE.write_json(path, payload)
    monkeypatch.setattr(MODULE, "FIELD_PREREGISTRATION_SCAFFOLD", path)
    report = MODULE.audit_field_preregistration_scaffold()
    assert report["status"] == "blocked"
    assert report["reason_code"] == "FIELD_PREREGISTRATION_SCAFFOLD_INVALID"
    assert report["field_validated_claim_created"] is False


def test_field_schema_and_payload_synchronized_tamper_rejected_by_compiled_anchors(
    tmp_path, monkeypatch
):
    payload = json.loads(MODULE.FIELD_PREREGISTRATION_SCAFFOLD.read_text())
    schema = json.loads(MODULE.FIELD_PREREGISTRATION_SCHEMA.read_text())
    payload["status"] = "ready"
    schema["properties"]["status"] = {"const": "ready"}
    payload_path = tmp_path / "payload.json"
    schema_path = tmp_path / "schema.json"
    MODULE.write_json(payload_path, payload)
    MODULE.write_json(schema_path, schema)
    monkeypatch.setattr(MODULE, "FIELD_PREREGISTRATION_SCAFFOLD", payload_path)
    monkeypatch.setattr(MODULE, "FIELD_PREREGISTRATION_SCHEMA", schema_path)
    report = MODULE.audit_field_preregistration_scaffold()
    assert report["status"] == "blocked"
    assert report["reason_code"] == "FIELD_PREREGISTRATION_SCAFFOLD_INVALID"


def test_fully_self_signed_nine_of_nine_cannot_bypass_live_replay(
    tmp_path, monkeypatch
):
    decision = {
        "schema_version": "wp8-feasibility-v1", "phase": "feasibility",
        "status": "passed", "wp8_1_allowed": True,
        "methods": [{"method": method, "status": "passed"} for method in MODULE.METHOD_NAMES],
        "generated_at_utc": "forged", "reason_code": "ALL_NINE_FEASIBLE",
    }
    decision_path = tmp_path / "decision.json"
    MODULE.write_json(decision_path, decision)
    decision_digest = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    protected = {"members": [{
        "path": "decision.json", "bytes": decision_path.stat().st_size,
        "sha256": decision_digest,
    }]}
    protected_path = tmp_path / "protected-manifest.json"
    MODULE.write_json(protected_path, protected)
    payload = json.loads(MODULE.FIELD_PREREGISTRATION_SCAFFOLD.read_bytes())
    payload.update({
        "all_nine_feasibility_passed": True, "status": "ready",
        "reason_code": "ALL_NINE_FEASIBLE",
        "feasibility_decision_sha256": decision_digest,
        "protected_manifest_sha256": hashlib.sha256(protected_path.read_bytes()).hexdigest(),
    })
    schema = json.loads(MODULE.FIELD_PREREGISTRATION_SCHEMA.read_bytes())
    schema["properties"]["all_nine_feasibility_passed"] = {"const": True}
    schema["properties"]["status"] = {"const": "ready"}
    schema["properties"]["reason_code"] = {"const": "ALL_NINE_FEASIBLE"}
    payload_path, schema_path = tmp_path / "payload.json", tmp_path / "schema.json"
    MODULE.write_json(payload_path, payload)
    MODULE.write_json(schema_path, schema)
    monkeypatch.setattr(MODULE, "FIELD_PREREGISTRATION_SCAFFOLD", payload_path)
    monkeypatch.setattr(MODULE, "FIELD_PREREGISTRATION_SCHEMA", schema_path)
    monkeypatch.setattr(MODULE, "EVIDENCE", tmp_path)
    monkeypatch.setattr(
        MODULE, "EXPECTED_FIELD_PREREGISTRATION_PAYLOAD_SHA256",
        hashlib.sha256(payload_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        MODULE, "EXPECTED_FIELD_PREREGISTRATION_SCHEMA_SHA256",
        hashlib.sha256(schema_path.read_bytes()).hexdigest(),
    )
    report = MODULE.audit_field_preregistration_scaffold()
    assert report["status"] == "blocked"
    assert report["reason_code"] == "LIVE_REPLAY_MISMATCH"


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired("authoritative-replay", 180),
        RuntimeError("authoritative replay worker failed with exit 137"),
    ],
)
def test_field_replay_timeout_and_nonzero_worker_fail_closed(monkeypatch, failure):
    def fail(_generated_at):
        raise failure
    monkeypatch.setattr(MODULE, "_bounded_authoritative_feasibility", fail)
    report = MODULE.audit_field_preregistration_scaffold()
    assert report["status"] == "blocked"
    assert report["reason_code"] == "FIELD_PREREGISTRATION_SCAFFOLD_INVALID"
    assert report["field_validated_claim_created"] is False


def test_bounded_replay_directly_kills_and_reaps_on_communicate_timeout():
    class Process:
        returncode = None
        killed = False
        calls = 0
        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("worker", timeout)
            return "", ""
        def kill(self):
            self.killed = True
    process = Process()
    with pytest.raises(subprocess.TimeoutExpired):
        MODULE._bounded_authoritative_feasibility(
            "x", popen_factory=lambda *args, **kwargs: process,
            platform_name="posix",
        )
    assert process.killed is True
    assert process.calls == 2


def test_bounded_replay_pre_ready_timeout_kills_and_reaps():
    class SlowStdout:
        def readline(self):
            time.sleep(0.05)
            return "READY\n"
    class Process:
        stdout = SlowStdout()
        killed = False
        reaped = False
        def kill(self):
            self.killed = True
        def communicate(self, timeout=None):
            self.reaped = True
            return "", ""
    process = Process()
    with pytest.raises(subprocess.TimeoutExpired):
        MODULE._bounded_authoritative_feasibility(
            "x", popen_factory=lambda *args, **kwargs: process,
            platform_name="nt", timeout_seconds=0.001,
        )
    assert process.killed and process.reaped


def test_bounded_replay_directly_rejects_nonzero_worker():
    class Process:
        returncode = 137
        def communicate(self, timeout=None):
            return "", "oom"
    with pytest.raises(RuntimeError, match="exit 137"):
        MODULE._bounded_authoritative_feasibility(
            "x", popen_factory=lambda *args, **kwargs: Process(),
            platform_name="posix",
        )


def test_live_replay_direct_input_budget_fails_before_audit():
    with pytest.raises(RuntimeError, match="input byte budget"):
        MODULE._live_authoritative_feasibility(
            "x", maximum_input_bytes=0
        )


@pytest.mark.parametrize(
    ("stage", "message"),
    [
        ("create", "WINDOWS_JOB_CREATE_FAILED"),
        ("set", "WINDOWS_JOB_SET_LIMIT_FAILED"),
        ("assign", "WINDOWS_JOB_ASSIGN_FAILED"),
    ],
)
def test_windows_job_installer_stage_failures_kill_reap_and_close(stage, message):
    class Function:
        def __init__(self, value):
            self.value = value
        def __call__(self, *args):
            return self.value
    class Kernel:
        CreateJobObjectW = Function(0 if stage == "create" else 2**40 + 7)
        SetInformationJobObject = Function(stage != "set")
        AssignProcessToJobObject = Function(stage != "assign")
        def __init__(self):
            self.closed = []
            owner = self
            class CloseFunction(Function):
                def __call__(self, handle):
                    owner.closed.append(handle)
                    return True
            self.CloseHandle = CloseFunction(True)
    kernel = Kernel()
    class Process:
        _handle = 2**45 + 9
        killed = reaped = False
        def kill(self): self.killed = True
        def communicate(self): self.reaped = True; return "", ""
    process = Process()
    with pytest.raises(RuntimeError, match=message):
        MODULE._install_windows_memory_job(process, kernel32=kernel)
    assert process.killed and process.reaped
    assert (not kernel.closed) if stage == "create" else kernel.closed == [2**40 + 7]


def test_posix_preexec_sets_exact_address_space_limit(monkeypatch):
    captured = {}
    class Process:
        returncode = 137
        def communicate(self, timeout=None): return "", "stopped"
    def factory(*args, **kwargs):
        captured["preexec_fn"] = kwargs["preexec_fn"]
        return Process()
    calls = []
    fake_resource = types.SimpleNamespace(
        RLIMIT_AS=99,
        setrlimit=lambda kind, limits: calls.append((kind, limits)),
    )
    monkeypatch.setitem(sys.modules, "resource", fake_resource)
    with pytest.raises(RuntimeError, match="exit 137"):
        MODULE._bounded_authoritative_feasibility(
            "x", popen_factory=factory, platform_name="posix"
        )
    captured["preexec_fn"]()
    assert calls == [(99, (512 * 1024 * 1024, 512 * 1024 * 1024))]


@pytest.mark.parametrize("failure", ["none", "write", "flush"])
def test_windows_worker_stdin_failures_close_job_and_reap(monkeypatch, failure):
    class Stream:
        def write(self, value):
            if failure == "write":
                raise OSError("write failed")
        def flush(self):
            if failure == "flush":
                raise OSError("flush failed")
        def close(self): pass
    class Stdout:
        def readline(self): return "READY\n"
    class Process:
        stdout = Stdout()
        stdin = None if failure == "none" else Stream()
        killed = reaped = False
        def kill(self): self.killed = True
        def communicate(self, timeout=None):
            self.reaped = True
            return "", ""
    class Kernel:
        def __init__(self): self.closed = []
        def CloseHandle(self, handle): self.closed.append(handle)
    process, kernel = Process(), Kernel()
    monkeypatch.setattr(
        MODULE, "_install_windows_memory_job",
        lambda process: (2**40 + 5, kernel),
    )
    with pytest.raises((RuntimeError, OSError)):
        MODULE._bounded_authoritative_feasibility(
            "x", popen_factory=lambda *args, **kwargs: process,
            platform_name="nt",
        )
    assert process.killed and process.reaped
    assert kernel.closed == [2**40 + 5]


def test_field_budget_raw_overflow_never_probes_or_opens_zip(monkeypatch):
    class PathLike:
        def stat(self): return types.SimpleNamespace(st_size=11)
    calls = []
    monkeypatch.setattr(
        AUDIT_MODULE.zipfile, "is_zipfile",
        lambda path: calls.append("probe") or True,
    )
    monkeypatch.setattr(
        AUDIT_MODULE.zipfile, "ZipFile",
        lambda path: calls.append("open"),
    )
    with pytest.raises(ValueError, match="raw input"):
        AUDIT_MODULE.validate_input_budget([PathLike()], 10)
    assert calls == []


def test_field_budget_expanded_overflow_reads_only_central_directory(monkeypatch):
    class PathLike:
        def stat(self): return types.SimpleNamespace(st_size=5)
    events = []
    class Archive:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def infolist(self):
            events.append("central-directory")
            return [types.SimpleNamespace(file_size=6)]
        def open(self, *args):
            raise AssertionError("member content must not be opened")
    monkeypatch.setattr(AUDIT_MODULE.zipfile, "is_zipfile", lambda path: True)
    monkeypatch.setattr(AUDIT_MODULE.zipfile, "ZipFile", lambda path: Archive())
    with pytest.raises(ValueError, match="expanded input"):
        AUDIT_MODULE.validate_input_budget([PathLike()], 10)
    assert events == ["central-directory"]


@pytest.mark.parametrize("cleanup_failure", ["kill", "reap"])
def test_job_install_preserves_original_error_and_closes_once(cleanup_failure):
    class Function:
        def __init__(self, callback): self.callback = callback
        def __call__(self, *args): return self.callback(*args)
    closed = []
    handle = 2**40 + 19
    class Kernel:
        CreateJobObjectW = Function(lambda *args: handle)
        SetInformationJobObject = Function(lambda *args: False)
        AssignProcessToJobObject = Function(lambda *args: True)
        CloseHandle = Function(lambda value: closed.append(value) or True)
    class Process:
        _handle = 2**45 + 1
        def kill(self):
            if cleanup_failure == "kill": raise OSError("kill failed")
        def communicate(self):
            if cleanup_failure == "reap": raise OSError("reap failed")
            return "", ""
    with pytest.raises(RuntimeError, match="WINDOWS_JOB_SET_LIMIT_FAILED"):
        MODULE._install_windows_memory_job(Process(), kernel32=Kernel())
    assert closed == [handle]


def test_central_static_audit_rejects_mendeley_training_as_field_eligible(
    tmp_path, monkeypatch
):
    contract = json.loads(
        MODULE.MENDELEY_HEAVY_METAL_SIP_CONTRACT.read_text(encoding="utf-8")
    )
    contract["field_validation_eligible"] = True
    path = tmp_path / "mendeley-contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(MODULE, "MENDELEY_HEAVY_METAL_SIP_CONTRACT", path)
    with pytest.raises(RuntimeError, match="public SIP/FDIP search evidence drift"):
        MODULE.audit_static_paths()


@pytest.mark.parametrize(
    ("path_parts", "value"),
    [
        (("scope",), "field"),
        (("status",), "passed"),
        (("formal_power_status",), "passed"),
        (("structure_audit_passed",), False),
        (("errors",), ["forged"]),
        (("partition", "response_content_members_opened_by_this_audit"), ["AX.raw"]),
        (("approved_sha256", "design"), "0" * 64),
        (("approved_sha256", "raw"), "0" * 64),
        (("paired_power_inputs", "validated_registry_count"), 1),
        (("partition", "approved_line_count"), 20),
        (("partition", "authorized_training_lines"), ["CG"]),
        (("partition", "sealed_lines"), ["AX"]),
        (("partition", "missing_training_members"), ["CG"]),
        (("inference_hierarchy", "training_observations_reported"), 341),
        (("inference_hierarchy", "training_lines"), 5),
        (("inference_hierarchy", "training_sites"), 2),
        (("design_reconciliation", "formal_independent_cluster_proven_upper_bound"), 2),
        (("design_reconciliation", "sealed_packaged_line_upper_bound_not_independence_evidence"), 14),
        (("formal_power_gate_passes",), True),
        (("paired_crps_computed",), True),
        (("paired_power_inputs", "minimum_computable_conditions", "cluster_and_correlation_model_frozen"), True),
        (("paired_power_inputs", "minimum_computable_conditions", "required_independent_cluster_count_derived_by_frozen_power_method"), True),
        (("paired_power_inputs", "minimum_computable_conditions", "two_frozen_methods_named_and_versioned"), True),
        (("paired_power_inputs", "minimum_computable_conditions", "same_information_and_compute_budget"), True),
        (("paired_power_inputs", "minimum_computable_conditions", "paired_out_of_sample_predictions_cover_all_training_lines"), True),
        (("paired_power_inputs", "minimum_computable_conditions", "paired_crps_artifact_hash_registered"), True),
        (("field_validation_eligible",), True),
        (("design_reconciliation", "formal_cluster_gate_passes"), True),
    ],
)
def test_central_controlled_source_audit_rejects_big_chino_readiness_tamper(
    tmp_path, monkeypatch, path_parts, value
):
    readiness = json.loads(
        MODULE.BIG_CHINO_CSAMT_POWER_READINESS.read_text(encoding="utf-8")
    )
    target = readiness
    for key in path_parts[:-1]:
        target = target[key]
    target[path_parts[-1]] = value
    path = tmp_path / "big-chino-power.json"
    path.write_text(json.dumps(readiness), encoding="utf-8")
    monkeypatch.setattr(MODULE, "BIG_CHINO_CSAMT_POWER_READINESS", path)
    with pytest.raises(RuntimeError, match="USGS Big Chino CSAMT evidence drift"):
        MODULE.audit_controlled_source_paths()


def test_synthetic_phase_blocks_failed_required_method_check(tmp_path, monkeypatch):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    evidence["methods"]["wfem"]["checks"]["jvp_jtp_adjoint"]["status"] = "failed"
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "wfem:method-validation-failed" in report["errors"]


def test_synthetic_phase_requires_csamt_convergence(
    tmp_path, monkeypatch
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    evidence["methods"]["csamt"]["checks"]["three_level_convergence"][
        "status"
    ] = "unsupported"
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "csamt:method-validation-failed" in report["errors"]


def test_synthetic_phase_rejects_laundered_reference_metric(
    tmp_path, monkeypatch
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    evidence["methods"]["csamt"]["checks"]["predict_reference_agreement"][
        "metrics"
        ]["absolute_log_amplitude_error"] = 0.7
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "csamt:method-validation-metrics-invalid" in report["errors"]


@pytest.mark.parametrize(
    ("block", "mutate", "expected_error"),
    [
        (
            "method_adversarial_suite",
            lambda metrics: metrics["scenarios"].pop("frequency_order_contract"),
            "sip_fdip:adversarial-suite-invalid",
        ),
        (
            "sbc_at_least_400",
            lambda metrics: metrics.update({"pvalue": 0.0}),
            "sip_fdip:sbc-invalid",
        ),
        (
            "within_method_5x5_performance",
            lambda metrics: metrics["records"].pop(),
            "sip_fdip:performance-benchmark-invalid",
        ),
    ],
)
def test_synthetic_phase_rejects_tampered_required_development_blocks(
    tmp_path, monkeypatch, block, mutate, expected_error
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    mutate(evidence["methods"]["sip_fdip"]["checks"][block]["metrics"])
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert expected_error in report["errors"]


def test_synthetic_phase_requires_all_nine_method_validation_records(
    tmp_path, monkeypatch
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    evidence["methods"].pop("gravity")
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "method-validation:contract-mismatch" in report["errors"]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda evidence: evidence.update({"producer_source_sha256": "0" * 64}),
            "method-validation:producer-source-hash-mismatch",
        ),
        (
            lambda evidence: evidence["methods"]["gravity"].update(
                {"method": "magnetic"}
            ),
            "gravity:method-validation-failed",
        ),
        (
            lambda evidence: evidence["methods"]["gravity"]["checks"][
                "predict_reference_agreement"
            ].update({"reference_id": "geoana-magnetic-prism-v1"}),
            "gravity:method-identity-crosswire",
        ),
        (
            lambda evidence: evidence["methods"]["tem"]["checks"][
                "taylor_remainder_order"
            ]["metrics"].update({"observed_order": float("nan")}),
            "method-validation:contract-mismatch",
        ),
        (
            lambda evidence: evidence["methods"]["dc"]["checks"][
                "within_method_5x5_performance"
            ]["metrics"]["records"][0].update({"elapsed_ns": 6_000_000_000}),
            "dc:performance-benchmark-invalid",
        ),
    ],
)
def test_synthetic_phase_rejects_identity_hash_numeric_and_performance_tamper(
    tmp_path, monkeypatch, mutation, expected
):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    evidence = json.loads(
        MODULE.METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
    )
    mutation(evidence)
    path = tmp_path / "method-validation.json"
    MODULE.write_json(path, evidence)
    monkeypatch.setattr(MODULE, "METHOD_SYNTHETIC_EVIDENCE", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert expected in report["errors"]


def test_synthetic_phase_rejects_readiness_drift(tmp_path, monkeypatch):
    _copy_synthetic_fixture(tmp_path, monkeypatch)
    readiness = json.loads(MODULE.SYNTHETIC_READINESS.read_text(encoding="utf-8"))
    readiness["methods"]["gravity"]["status"] = "complete"
    path = tmp_path / "readiness.json"
    MODULE.write_json(path, readiness)
    monkeypatch.setattr(MODULE, "SYNTHETIC_READINESS", path)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "synthetic-readiness:contract-drift" in report["errors"]


def test_synthetic_phase_rejects_invalid_start_record(tmp_path, monkeypatch):
    _, start = _copy_synthetic_fixture(tmp_path, monkeypatch)
    record = json.loads(start.read_text(encoding="utf-8"))
    record["feasibility_decision"]["wp8_1_allowed"] = True
    MODULE.write_json(start, record)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "start-record:contract-mismatch" in report["errors"]
    assert report["field_validated_claim_created"] is False


@pytest.mark.parametrize("invalid_json_value", [None, [], "bad", 7, True])
def test_synthetic_phase_blocks_non_object_start_json(
    tmp_path, monkeypatch, invalid_json_value
):
    _, start = _copy_synthetic_fixture(tmp_path, monkeypatch)
    MODULE.write_json(start, invalid_json_value)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "start-record:invalid-type" in report["errors"]


@pytest.mark.parametrize("invalid_json_value", [None, [], "bad", 7, True])
def test_synthetic_phase_blocks_non_object_manifest_json(
    tmp_path, monkeypatch, invalid_json_value
):
    target, _ = _copy_synthetic_fixture(tmp_path, monkeypatch)
    MODULE.write_json(target / "manifest.json", invalid_json_value)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "manifest:invalid-type" in report["errors"]


def test_synthetic_phase_rejects_contradictory_authorization(tmp_path, monkeypatch):
    _, start = _copy_synthetic_fixture(tmp_path, monkeypatch)
    record = json.loads(start.read_text(encoding="utf-8"))
    record["authorized_scope"].append("field-validated-claim")
    MODULE.write_json(start, record)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "start-record:contract-mismatch" in report["errors"]


def test_synthetic_phase_requires_all_formal_prohibitions(tmp_path, monkeypatch):
    _, start = _copy_synthetic_fixture(tmp_path, monkeypatch)
    record = json.loads(start.read_text(encoding="utf-8"))
    record["prohibited_until_formal_gates_pass"].remove("field-validated-claim")
    MODULE.write_json(start, record)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "start-record:contract-mismatch" in report["errors"]


def test_synthetic_phase_rejects_member_hash_drift(tmp_path, monkeypatch):
    target, _ = _copy_synthetic_fixture(tmp_path, monkeypatch)
    with (target / "wfem.npz").open("ab") as stream:
        stream.write(b"\n")
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "wfem:sha256-mismatch" in report["errors"]


def test_synthetic_phase_rejects_contract_drift_even_with_rehashed_member(
    tmp_path, monkeypatch
):
    target, _ = _copy_synthetic_fixture(tmp_path, monkeypatch)
    path = target / "csamt.npz"
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["field_validation_eligible"] = np.array(True)
    np.savez_compressed(path, **arrays)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    member = next(item for item in manifest["members"] if item["method"] == "csamt")
    member["sha256"] = MODULE.sha256_file(path)
    MODULE.write_json(manifest_path, manifest)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "csamt:contract-mismatch" in report["errors"]


def test_synthetic_phase_rejects_rehashed_seed_drift(tmp_path, monkeypatch):
    target, _ = _copy_synthetic_fixture(tmp_path, monkeypatch)
    path = target / "sip_fdip.npz"
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["seed"] = np.array(9999)
    np.savez_compressed(path, **arrays)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    member = next(item for item in manifest["members"] if item["method"] == "sip_fdip")
    member["sha256"] = MODULE.sha256_file(path)
    member["content_digest"] = MODULE._synthetic_content_digest(arrays)
    MODULE.write_json(manifest_path, manifest)
    report = MODULE.audit_synthetic_phase()
    assert report["status"] == "blocked"
    assert "sip_fdip:contract-mismatch" in report["errors"]


def test_zenodo_license_requires_open_access_and_identifier(tmp_path, monkeypatch):
    path = tmp_path / "record.json"
    MODULE.write_json(path, {"metadata": {"access_right": "open", "license": {"id": "cc-by-4.0"}}})
    monkeypatch.setattr(MODULE, "OPEN_DATA", tmp_path)
    result = MODULE.license_evidence(
        {"license_evidence_path": "record.json", "license_evidence_type": "zenodo_license"},
        None,
    )
    assert result["passed"] is True


def test_fgdc_license_requires_explicit_no_constraints(tmp_path, monkeypatch):
    path = tmp_path / "record.xml"
    path.write_text(
        "<metadata><idinfo><accconst>None.</accconst><useconst>None. Cite source.</useconst></idinfo></metadata>",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "OPEN_DATA", tmp_path)
    result = MODULE.license_evidence(
        {"license_evidence_path": "record.xml", "license_evidence_type": "fgdc_constraints"},
        None,
    )
    assert result["passed"] is True


def test_contract_concepts_cover_exactly_nine_methods():
    assert set(MODULE.CONTRACT_CONCEPTS) == set(MODULE.METHOD_NAMES)


def test_solver_inventory_never_treats_dependency_as_verified_solver():
    inventory = MODULE.audit_solver_paths()
    assert set(inventory["methods"]) == set(MODULE.METHOD_NAMES)
    assert all(item["status"] != "passed" for item in inventory["methods"].values())
    assert inventory["independent_reference_status"] == "blocked"
