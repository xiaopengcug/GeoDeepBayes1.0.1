import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
RESEARCH = (
    ROOT
    / "_bmad-output/planning-artifacts/research"
    / "贝叶斯思想与重磁电电磁深度融合技术体系"
)
WP9_SCRIPT = ROOT / "validation/wp9/validate_wp9.py"
SPEC = importlib.util.spec_from_file_location("review03_wp9", WP9_SCRIPT)
WP9 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(WP9)
PERSISTENCE_SCRIPT = ROOT / "validation/wp9/build_persistence_plan.py"
PERSISTENCE_SPEC = importlib.util.spec_from_file_location(
    "review03_persistence", PERSISTENCE_SCRIPT
)
PERSISTENCE = importlib.util.module_from_spec(PERSISTENCE_SPEC)
assert PERSISTENCE_SPEC.loader
PERSISTENCE_SPEC.loader.exec_module(PERSISTENCE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


WP5_STAGES = {
    "upstream-lineage": 33,
    "allowlist": 9,
    "registry": 25,
    "language-structure-boundary": 31,
    "publish": 20,
    "signoff": 28,
    "lineage-migration": 154,
}
WP5_RUN = "20260730T010101001Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _wp5_result(fixture_id: str, duration_ms: int = 1) -> dict:
    return {
        "fixture_id": fixture_id,
        "case": fixture_id,
        "expected_exit": 0,
        "actual_exit": 0,
        "expected_rejections": [],
        "actual_rejection": "",
        "success_criterion": "child accepts this positive fixture",
        "matched": True,
        "duration_ms": duration_ms,
    }


def _wp5_evidence(
    stage: str,
    fixture_ids: list[str],
    *,
    schema: str = "wp5-selftest-evidence-v1",
    duration_ms: int = 1,
) -> dict:
    return {
        "schema": schema,
        "evidence_class": (
            "Post-publication self-test evidence; not an input to its referenced manifest"
        ),
        "source_run_instance_id": WP5_RUN,
        "source_version_path": f"versions/{WP5_RUN}",
        "source_manifest_sha256": "b" * 64,
        "validator_sha256": "",
        "fixture_manifest_sha256": "",
        "member_root_sha256": "",
        "root_file_sha256": "",
        "root_anchor_file_sha256": "",
        "stage": stage,
        "fixture_count": len(fixture_ids),
        "fixture_id_set": fixture_ids,
        "batch_role": "stage",
        "fixture_results": [
            _wp5_result(fixture_id, duration_ms) for fixture_id in fixture_ids
        ],
        "status": "Passed",
        "completed_at_utc": "2026-07-30T01:02:03Z",
        "output_sha256": "c" * 64,
        "validator_exit": 0,
        "pass_marker_count": 1,
    }


def _wp5_root_binding_fixture(research: Path) -> dict[str, str]:
    template = (RESEARCH / "WP5-consistency-input-root.sha256").read_text(
        encoding="utf-8"
    )
    members = [line.split("  ", 1)[1] for line in template.splitlines()[2:]]
    assert len(members) == 29
    for relative in members:
        member = research / relative
        if not member.exists():
            member.parent.mkdir(parents=True, exist_ok=True)
            member.write_text("# root fixture\n", encoding="utf-8")
    member_lines = [f"{sha256(research / item)}  {item}" for item in members]
    root_text = "# WP5 consistency root v1\n\n" + "\n".join(member_lines) + "\n"
    root_path = research / "WP5-consistency-input-root.sha256"
    root_path.write_text(root_text, encoding="utf-8", newline="\n")
    member_root = hashlib.sha256(
        ("\n".join(member_lines) + "\n").encode("utf-8")
    ).hexdigest()
    root_file = sha256(root_path)
    anchor = research / "validation/wp5-consistency/WP5-consistency-root-anchor.sha256"
    anchor.write_text(root_file + "\n", encoding="utf-8", newline="\n")
    return {
        "member_root_sha256": member_root,
        "root_file_sha256": root_file,
        "root_anchor_file_sha256": sha256(anchor),
    }


def _wp5_release_script_fixture(tmp_path: Path) -> tuple[Path, dict[str, list[str]]]:
    research = tmp_path / "research"
    vroot = research / "validation/wp5-consistency"
    stages = vroot / "release-evidence-v1/stages"
    stages.mkdir(parents=True)
    validator = research / "validate-wp5.ps1"
    validator.write_text("# validator fixture\n", encoding="utf-8")
    shutil.copy2(
        RESEARCH / "validation/wp5-consistency/materialize-release-evidence.ps1",
        vroot / "materialize-release-evidence.ps1",
    )
    _write_json(
        vroot / "active-output.json",
        {
            "schema": "wp5-active-output-v1",
            "run_instance_id": WP5_RUN,
            "version_path": f"versions/{WP5_RUN}",
            "manifest_sha256": "b" * 64,
        },
    )
    ids_by_stage = {
        stage: [f"FXT-{stage.upper()}-{index:03d}" for index in range(count)]
        for stage, count in WP5_STAGES.items()
    }
    fixture_manifest = _write_json(
        vroot / "selftest-fixture-manifest.json",
        {
            "schema": "wp5-selftest-fixture-manifest-v3",
            "fixtures": [
                {
                    "id": fixture_id,
                    "stage": stage,
                    "canonical_case": fixture_id,
                    "expected_exit": 0,
                    "expected_rejections": [],
                }
                for stage, fixture_ids in ids_by_stage.items()
                for fixture_id in fixture_ids
            ],
        },
    )
    validator_hash = sha256(validator)
    fixture_hash = sha256(fixture_manifest)
    root_binding = _wp5_root_binding_fixture(research)
    for stage, fixture_ids in ids_by_stage.items():
        evidence = _wp5_evidence(stage, fixture_ids)
        evidence["validator_sha256"] = validator_hash
        evidence["fixture_manifest_sha256"] = fixture_hash
        evidence.update(root_binding)
        _write_json(
            stages / f"selftest-{WP5_RUN}-{stage}-20260730T010101001Z.json",
            evidence,
        )
    return vroot, ids_by_stage


def _reference_closure_fixture(tmp_path: Path):
    research = tmp_path / "research"
    wp9 = research / "validation/wp9"
    wp2 = research / "validation/wp2-toy"
    wp5 = research / "validation/wp5-consistency"

    diagnostic = _write_json(wp2 / "diagnostic-contract.json", {"kind": "diagnostic"})
    wp2_source = wp2 / "run.ps1"
    wp2_source.parent.mkdir(parents=True, exist_ok=True)
    wp2_source.write_text("run", encoding="utf-8")
    wp2_result = _write_json(
        wp2 / "versions/20260728T010203004Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/result.json",
        {"passed": True},
    )
    wp2_manifest = _write_json(
        wp2
        / "versions/20260728T010203004Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/manifest.json",
        {
            "schema": "wp2-toy-manifest-v3",
            "files": {"result.json": sha256(wp2_result)},
            "sources": [{"path": "run.ps1", "sha256": sha256(wp2_source)}],
        },
    )
    wp2_pointer = _write_json(
        wp2 / "active-output.json",
        {
            "schema": "wp2-active-output-v1",
            "run_instance_id": (
                "20260728T010203004Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
            "version_path": (
                "versions/20260728T010203004Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
            "manifest_sha256": sha256(wp2_manifest),
        },
    )

    document = research / "chapter.md"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text("chapter", encoding="utf-8")
    scan = _write_json(
        wp5
        / "versions/20260728T020304005Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/scan.json",
        {
            "schema": "wp5-consistency-scan-v1",
            "documents": {"chapter.md": sha256(document)},
        },
    )
    claim_ledger = _write_json(
        wp5 / "claim-ledger.json",
        {
            "schema": "wp5-claim-ledger-v1",
            "sources": {
                "wp2-active": {
                    "path": "validation/wp2-toy/active-output.json",
                    "sha256": sha256(wp2_pointer),
                }
            },
        },
    )
    wp5_source = wp5 / "publish.ps1"
    wp5_source.write_text("publish", encoding="utf-8")
    wp5_manifest = _write_json(
        wp5
        / "versions/20260728T020304005Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/manifest.json",
        {
            "schema": "wp5-consistency-manifest-v1",
            "files": {"scan.json": sha256(scan)},
            "sources": {
                "claim-ledger.json": sha256(claim_ledger),
                "publish.ps1": sha256(wp5_source),
            },
        },
    )
    _write_json(
        wp5 / "active-output.json",
        {
            "schema": "wp5-active-output-v1",
            "run_instance_id": (
                "20260728T020304005Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ),
            "version_path": (
                "versions/20260728T020304005Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ),
            "manifest_sha256": sha256(wp5_manifest),
        },
    )

    _write_json(
        research / "contracts/contract-registry.json",
        {
            "contracts": {
                "diagnostics": {
                    "canonical_path": "validation/wp2-toy/diagnostic-contract.json",
                    "sha256": sha256(diagnostic),
                }
            }
        },
    )
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    finding_registry = _write_json(
        wp9 / "finding-registry-v1.json",
        {
            "schema_version": "wp9-finding-registry-v1",
            "findings": [
                {
                    "evidence": [
                        {
                            "path": "evidence.md",
                            "sha256": sha256(evidence),
                        }
                    ]
                }
            ],
        },
    )
    producer_asset = _write_json(tmp_path / "producer/input.json", [{"source": 1}])
    _write_json(
        tmp_path / "validation/wp8/evidence/feasibility-v1/producer-manifest.json",
        {
            "schema_version": "wp8-producer-manifest-v1",
            "members": [
                {
                    "path": "producer/input.json",
                    "sha256": sha256(producer_asset),
                }
            ],
        },
    )
    return {
        "root": tmp_path,
        "research": research,
        "wp9": wp9,
        "diagnostic": diagnostic,
        "document": document,
        "wp2_pointer": wp2_pointer,
        "wp2_result": wp2_result,
        "wp2_source": wp2_source,
        "finding_registry": finding_registry,
        "evidence": evidence,
        "producer_asset": producer_asset,
    }


def test_wp9_manifest_declares_and_enforces_repo_root_paths():
    ok, errors = WP9.verify_manifest()
    assert (ok, errors) == (True, [])
    manifest = json.loads(WP9.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["path_basis"] == "repo-root-relative"
    members = {item["path"]: item for item in manifest["members"]}
    wp8_path = "validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json"
    assert members[wp8_path]["location_note"].startswith(
        "Repository-root validation/wp8 asset"
    )
    assert any(path.startswith("_bmad-output/") for path in members)


def test_wp5_active_pointer_resolves_to_bound_manifest():
    active = (RESEARCH / "ACTIVE_MANIFEST").read_text(encoding="utf-8").strip()
    pointer = json.loads(
        (RESEARCH / "validation/wp5-consistency/active-output.json").read_text(
            encoding="utf-8"
        )
    )
    assert active == pointer["manifest_sha256"]
    assert pointer["schema"] == "wp5-active-output-v1"
    target = RESEARCH / "validation/wp5-consistency" / pointer["version_path"] / "manifest.json"
    target_manifest = json.loads(target.read_text(encoding="utf-8"))
    assert sha256(target) == active
    assert target_manifest["schema"] == "wp5-consistency-manifest-v1"
    assert target_manifest["run_instance_id"] == pointer["run_instance_id"]
    assert target_manifest["status"] == "Passed"


def test_wp5_corrected_pointer_is_bound_to_authorized_six_role_reviews():
    active_hash = sha256(RESEARCH / "ACTIVE_MANIFEST")
    root_text = (RESEARCH / "WP5-consistency-input-root.sha256").read_text(
        encoding="utf-8"
    )
    recorded = re.search(r"(?m)^([0-9a-f]{64})  ACTIVE_MANIFEST$", root_text)
    assert recorded
    assert recorded.group(1) == active_hash
    review_dir = RESEARCH / "validation/wp5-consistency/final-root-reviews-v1"
    review_manifest_path = review_dir / "reviews-manifest.json"
    review_manifest = json.loads(review_manifest_path.read_text(encoding="utf-8"))
    roles = [
        "主编",
        "技术编辑",
        "地球物理复核",
        "贝叶斯/UQ复核",
        "算法数值复核",
        "工程架构复核",
    ]
    assert review_manifest["exact_roles"] == roles
    assert [item["role"] for item in review_manifest["reviews"]] == roles
    assert all(item["decision"] == "Approved" for item in review_manifest["reviews"])
    summary = (
        RESEARCH / "WP5-主编技术编辑与专项交叉复核独立签核.md"
    ).read_text(encoding="utf-8")
    assert sha256(review_manifest_path) in summary
    assert "automated-ai-final-root-review" in summary


def test_wp5_final_review_check_sets_are_role_distinct():
    review_dir = RESEARCH / "validation/wp5-consistency/final-root-reviews-v1"
    review_manifest = json.loads(
        (review_dir / "reviews-manifest.json").read_text(encoding="utf-8")
    )
    seen_check_sets = {}
    for record in review_manifest["reviews"]:
        review = json.loads(
            (review_dir / record["path"]).read_text(encoding="utf-8")
        )
        normalized = tuple(
            sorted(" ".join(check.split()).casefold() for check in review["checks"])
        )
        assert len(normalized) >= 3
        assert len(normalized) == len(set(normalized))
        assert normalized not in seen_check_sets, (
            f"cross-role checks copied in full: "
            f"{seen_check_sets.get(normalized)} and {record['role']}"
        )
        seen_check_sets[normalized] = record["role"]


def test_wp5_final_gate_evidence_chain_is_in_persistence_inputs(tmp_path):
    required = set(PERSISTENCE._wp5_final_gate_evidence_inputs())
    root_inputs = set(PERSISTENCE._wp5_root_inputs())
    assert len(root_inputs) == 30
    assert {
        (
            RESEARCH
            / "validation/wp5-consistency/selftest-fixture-manifest.json"
        ).relative_to(PERSISTENCE.ROOT).as_posix(),
        (
            RESEARCH / "validation/wp5-consistency/run-selftest-evidence.ps1"
        ).relative_to(PERSISTENCE.ROOT).as_posix(),
        (
            RESEARCH
            / "validation/wp5-consistency/finalize-selftest-stage-evidence.ps1"
        ).relative_to(PERSISTENCE.ROOT).as_posix(),
    } <= root_inputs
    vroot = RESEARCH / "validation/wp5-consistency"
    review_dir = vroot / "final-root-reviews-v1"
    review_manifest = json.loads(
        (review_dir / "reviews-manifest.json").read_text(encoding="utf-8")
    )
    expected = {
        (review_dir / record["path"]).relative_to(PERSISTENCE.ROOT).as_posix()
        for record in review_manifest["reviews"]
    }
    envelope = vroot / review_manifest["release_evidence"]["path"]
    expected.add(envelope.relative_to(PERSISTENCE.ROOT).as_posix())
    envelope_payload = json.loads(envelope.read_text(encoding="utf-8"))
    for stage in envelope_payload["stages"]:
        stage_path = envelope.parent / stage["path"]
        expected.add(stage_path.relative_to(PERSISTENCE.ROOT).as_posix())
        stage_payload = json.loads(stage_path.read_text(encoding="utf-8"))
        for partial in stage_payload.get("partial_evidence", []):
            expected.add(
                (stage_path.parent / partial["path"])
                .relative_to(PERSISTENCE.ROOT)
                .as_posix()
            )
    assert expected <= required

    temporary_research = tmp_path / "research"
    temporary_vroot = temporary_research / "validation/wp5-consistency"
    shutil.copytree(review_dir, temporary_vroot / "final-root-reviews-v1")
    shutil.copytree(envelope.parent, temporary_vroot / "release-evidence-v1")
    temporary_manifest_path = (
        temporary_vroot / "final-root-reviews-v1/reviews-manifest.json"
    )
    temporary_manifest = json.loads(
        temporary_manifest_path.read_text(encoding="utf-8")
    )
    temporary_manifest["reviews"][1]["path"] = "./main-editor.json"
    temporary_manifest["reviews"][1]["sha256"] = temporary_manifest["reviews"][0][
        "sha256"
    ]
    _write_json(temporary_manifest_path, temporary_manifest)
    with pytest.raises(ValueError, match="non-canonical WP5 final review path"):
        PERSISTENCE._wp5_final_gate_evidence_inputs(
            root=tmp_path,
            research=temporary_research,
        )


def test_wp5_materializer_selects_equivalent_retry_and_rejects_conflict(tmp_path):
    vroot, ids_by_stage = _wp5_release_script_fixture(tmp_path)
    stage_dir = vroot / "release-evidence-v1/stages"
    finalized_path = (
        stage_dir / f"selftest-{WP5_RUN}-allowlist-20260730T010101001Z.json"
    )
    finalized = json.loads(finalized_path.read_text(encoding="utf-8"))
    partial = deepcopy(finalized)
    partial["schema"] = "wp5-selftest-partial-evidence-v1"
    partial_path = _write_json(
        stage_dir
        / f"partial-selftest-{WP5_RUN}-allowlist-20260730T010101000Z.json",
        partial,
    )
    finalized["schema"] = "wp5-selftest-finalized-evidence-v1"
    finalized["evidence_class"] = (
        "Finalized from exact, non-overlapping partial evidence; "
        "not an input to its referenced manifest"
    )
    finalized["partial_evidence"] = [
        {"path": partial_path.name, "sha256": sha256(partial_path)}
    ]
    partial_root = (
        f"{finalized['partial_evidence'][0]['sha256']}  {partial_path.name}\n"
    )
    finalized["output_sha256"] = hashlib.sha256(
        partial_root.encode("utf-8")
    ).hexdigest()
    _write_json(finalized_path, finalized)

    first = stage_dir / f"selftest-{WP5_RUN}-publish-20260730T010101001Z.json"
    retry_payload = json.loads(first.read_text(encoding="utf-8"))
    retry_payload["completed_at_utc"] = "2026-07-30T02:02:03Z"
    retry_payload["output_sha256"] = "d" * 64
    for result in retry_payload["fixture_results"]:
        result["duration_ms"] = 99
    retry = _write_json(
        stage_dir / f"selftest-{WP5_RUN}-publish-20260730T020202002Z.json",
        retry_payload,
    )

    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(vroot / "materialize-release-evidence.ps1")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    envelope = json.loads(
        (vroot / "release-evidence-v1/envelope.json").read_text(encoding="utf-8")
    )
    publish = next(item for item in envelope["stages"] if item["stage"] == "publish")
    allowlist = next(
        item for item in envelope["stages"] if item["stage"] == "allowlist"
    )
    assert publish["path"].endswith(first.name)
    assert allowlist["path"].endswith(finalized_path.name)

    conflict = json.loads(retry.read_text(encoding="utf-8"))
    conflict["fixture_results"][0]["case"] = "different-but-oracle-valid"
    _write_json(retry, conflict)
    rejected = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(vroot / "materialize-release-evidence.ps1")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    assert rejected.returncode != 0
    assert "oracle" in rejected.stdout + rejected.stderr
    assert len(ids_by_stage["publish"]) == WP5_STAGES["publish"]


@pytest.mark.parametrize("evidence_kind", ["direct", "finalized-partial"])
def test_wp5_materializer_rejects_manifest_oracle_tamper(tmp_path, evidence_kind):
    vroot, _ = _wp5_release_script_fixture(tmp_path)
    stage_dir = vroot / "release-evidence-v1/stages"
    stage = "publish" if evidence_kind == "direct" else "allowlist"
    evidence_path = (
        stage_dir / f"selftest-{WP5_RUN}-{stage}-20260730T010101001Z.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    def tamper(result):
        result["expected_exit"] = 1
        result["actual_exit"] = 1
        result["expected_rejections"] = ["internally-consistent-but-not-oracle"]
        result["actual_rejection"] = "internally-consistent-but-not-oracle"
        result["success_criterion"] = (
            "child rejects this fixture with one predeclared business assertion"
        )

    if evidence_kind == "direct":
        tamper(evidence["fixture_results"][0])
        _write_json(evidence_path, evidence)
    else:
        partial = deepcopy(evidence)
        partial["schema"] = "wp5-selftest-partial-evidence-v1"
        tamper(partial["fixture_results"][0])
        partial_path = _write_json(
            stage_dir
            / f"partial-selftest-{WP5_RUN}-{stage}-20260730T010101000Z.json",
            partial,
        )
        evidence["schema"] = "wp5-selftest-finalized-evidence-v1"
        evidence["evidence_class"] = (
            "Finalized from exact, non-overlapping partial evidence; "
            "not an input to its referenced manifest"
        )
        evidence["partial_evidence"] = [
            {"path": partial_path.name, "sha256": sha256(partial_path)}
        ]
        evidence["output_sha256"] = hashlib.sha256(
            f"{sha256(partial_path)}  {partial_path.name}\n".encode("utf-8")
        ).hexdigest()
        _write_json(evidence_path, evidence)

    rejected = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(vroot / "materialize-release-evidence.ps1")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    assert rejected.returncode != 0
    assert "oracle" in rejected.stdout + rejected.stderr
    assert not (vroot / "release-evidence-v1/envelope.json").exists()


def test_wp5_finalizer_deduplicates_partial_retry_and_emits_provenance(tmp_path):
    research = tmp_path / "research"
    vroot = research / "validation/wp5-consistency"
    stage_dir = vroot / "release-evidence-v1/stages"
    stage_dir.mkdir(parents=True)
    validator = research / "validate-wp5.ps1"
    validator.write_text("# validator fixture\n", encoding="utf-8")
    shutil.copy2(
        RESEARCH / "validation/wp5-consistency/finalize-selftest-stage-evidence.ps1",
        vroot / "finalize-selftest-stage-evidence.ps1",
    )
    _write_json(
        vroot / "active-output.json",
        {
            "schema": "wp5-active-output-v1",
            "run_instance_id": WP5_RUN,
            "version_path": f"versions/{WP5_RUN}",
            "manifest_sha256": "b" * 64,
        },
    )
    fixture_ids = ["FXT-PUBLISH-001", "FXT-PUBLISH-002"]
    fixture_manifest = _write_json(
        vroot / "selftest-fixture-manifest.json",
        {
            "schema": "wp5-selftest-fixture-manifest-v3",
            "fixtures": [
                {
                    "id": fixture_id,
                    "stage": "publish",
                    "canonical_case": fixture_id,
                    "expected_exit": 0,
                    "expected_rejections": [],
                }
                for fixture_id in fixture_ids
            ]
            + [
                {
                    "id": f"FXT-REGISTRY-{index:03d}",
                    "stage": "registry",
                    "canonical_case": f"FXT-REGISTRY-{index:03d}",
                    "expected_exit": 0,
                    "expected_rejections": [],
                }
                for index in range(1, 299)
            ],
        },
    )
    validator_hash = sha256(validator)
    fixture_hash = sha256(fixture_manifest)
    root_binding = _wp5_root_binding_fixture(research)

    def write_partial(name: str, ids: list[str], duration_ms: int) -> Path:
        payload = _wp5_evidence(
            "publish",
            ids,
            schema="wp5-selftest-partial-evidence-v1",
            duration_ms=duration_ms,
        )
        payload["validator_sha256"] = validator_hash
        payload["fixture_manifest_sha256"] = fixture_hash
        payload.update(root_binding)
        return _write_json(stage_dir / name, payload)

    first = write_partial(
        f"partial-selftest-{WP5_RUN}-publish-20260730T010101001Z.json",
        [fixture_ids[0]],
        1,
    )
    write_partial(
        f"partial-selftest-{WP5_RUN}-publish-20260730T010101002Z.json",
        [fixture_ids[0]],
        99,
    )
    second = write_partial(
        f"partial-selftest-{WP5_RUN}-publish-20260730T010101003Z.json",
        [fixture_ids[1]],
        2,
    )
    other_stage = _wp5_evidence(
        "registry",
        ["FXT-REGISTRY-001"],
        schema="wp5-selftest-partial-evidence-v1",
        duration_ms=3,
    )
    other_stage["validator_sha256"] = validator_hash
    other_stage["fixture_manifest_sha256"] = fixture_hash
    other_stage.update(root_binding)
    _write_json(
        stage_dir
        / f"partial-selftest-{WP5_RUN}-registry-20260730T010101004Z.json",
        other_stage,
    )
    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(vroot / "finalize-selftest-stage-evidence.ps1"),
            "-Stage",
            "publish",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    outputs = sorted(stage_dir.glob(f"selftest-{WP5_RUN}-publish-*.json"))
    assert len(outputs) == 1
    finalized = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert finalized["schema"] == "wp5-selftest-finalized-evidence-v1"
    assert finalized["fixture_id_set"] == fixture_ids
    assert finalized["batch_role"] == "stage"
    assert finalized["validator_exit"] == 0
    assert finalized["pass_marker_count"] == 1
    assert [item["path"] for item in finalized["partial_evidence"]] == [
        first.name,
        second.name,
    ]
    root_text = "".join(
        f"{item['sha256']}  {item['path']}\n"
        for item in finalized["partial_evidence"]
    )
    assert finalized["output_sha256"] == hashlib.sha256(
        root_text.encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "failure_kind", ["oracle-tamper", "wrong-canonical-case", "object-case"]
)
def test_wp5_finalizer_rejects_invalid_partial_without_output(
    tmp_path, failure_kind
):
    research = tmp_path / "research"
    vroot = research / "validation/wp5-consistency"
    stage_dir = vroot / "release-evidence-v1/stages"
    stage_dir.mkdir(parents=True)
    validator = research / "validate-wp5.ps1"
    validator.write_text("# validator fixture\n", encoding="utf-8")
    shutil.copy2(
        RESEARCH / "validation/wp5-consistency/finalize-selftest-stage-evidence.ps1",
        vroot / "finalize-selftest-stage-evidence.ps1",
    )
    _write_json(
        vroot / "active-output.json",
        {
            "schema": "wp5-active-output-v1",
            "run_instance_id": WP5_RUN,
            "version_path": f"versions/{WP5_RUN}",
            "manifest_sha256": "b" * 64,
        },
    )
    target_id = "FXT-PUBLISH-001"
    fixture_manifest = _write_json(
        vroot / "selftest-fixture-manifest.json",
        {
            "schema": "wp5-selftest-fixture-manifest-v3",
            "fixtures": [
                {
                    "id": target_id,
                    "stage": "publish",
                    "canonical_case": target_id,
                    "expected_exit": 0,
                    "expected_rejections": [],
                }
            ]
            + [
                {
                    "id": f"FXT-REGISTRY-{index:03d}",
                    "stage": "registry",
                    "canonical_case": f"FXT-REGISTRY-{index:03d}",
                    "expected_exit": 0,
                    "expected_rejections": [],
                }
                for index in range(1, 300)
            ],
        },
    )
    validator_hash = sha256(validator)
    fixture_hash = sha256(fixture_manifest)
    root_binding = _wp5_root_binding_fixture(research)

    def write_partial(name: str, case: object, *, tampered: bool = False):
        payload = _wp5_evidence(
            "publish",
            [target_id],
            schema="wp5-selftest-partial-evidence-v1",
        )
        payload["validator_sha256"] = validator_hash
        payload["fixture_manifest_sha256"] = fixture_hash
        payload.update(root_binding)
        payload["fixture_results"][0]["case"] = case
        if tampered:
            result = payload["fixture_results"][0]
            result["expected_exit"] = 1
            result["actual_exit"] = 1
            result["expected_rejections"] = ["not-the-manifest-oracle"]
            result["actual_rejection"] = "not-the-manifest-oracle"
            result["success_criterion"] = (
                "child rejects this fixture with one predeclared business assertion"
            )
        _write_json(stage_dir / name, payload)

    write_partial(
        f"partial-selftest-{WP5_RUN}-publish-20260730T010101001Z.json",
        (
            {"polluted": True}
            if failure_kind == "object-case"
            else "wrong-case"
            if failure_kind == "wrong-canonical-case"
            else target_id
        ),
        tampered=failure_kind == "oracle-tamper",
    )

    rejected = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(vroot / "finalize-selftest-stage-evidence.ps1"),
            "-Stage",
            "publish",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    assert rejected.returncode != 0
    assert "oracle" in rejected.stdout + rejected.stderr
    assert not list(stage_dir.glob(f"selftest-{WP5_RUN}-publish-*.json"))


def test_wp5_validator_persisted_evidence_keeps_both_oracle_guards():
    source = (RESEARCH / "validate-wp5.ps1").read_text(encoding="utf-8")
    function = re.search(
        r"function ValidateReleaseEvidence\(\$candidatePointer\)\{(?P<body>.*?)"
        r"\n\}\nfunction ValidateFinalRootReviews",
        source,
        flags=re.DOTALL,
    )
    assert function
    body = function.group("body")
    assert (
        "AssertFixtureResultOracle $evidence.fixture_results[$resultIndex] "
        "$stageFixtures[$resultIndex] 'release evidence'"
    ) in body
    assert (
        "AssertFixtureResultOracle $partial.fixture_results[$partialIndex] "
        "$selfTestFixtureOracle[$partialId] 'release evidence partial'"
    ) in body
    assert body.count("AssertFixtureResultOracle") == 2
    oracle_function = re.search(
        r"function AssertFixtureResultOracle\(\$result,\$oracle,"
        r"\[string\]\$prefix\)\{.*?\n\}\nfunction ValidateReleaseEvidence",
        source,
        flags=re.DOTALL,
    )
    assert oracle_function
    function_text = oracle_function.group(0).removesuffix(
        "function ValidateReleaseEvidence"
    )
    oracle = {
        "id": "FXT-TEST-001",
        "stage": "publish",
        "expected_exit": 0,
        "expected_rejections": [],
    }
    tampered = _wp5_result("FXT-TEST-001")
    tampered.update(
        {
            "expected_exit": 1,
            "actual_exit": 1,
            "expected_rejections": ["internally-consistent-but-not-oracle"],
            "actual_rejection": "internally-consistent-but-not-oracle",
            "success_criterion": (
                "child rejects this fixture with one predeclared business assertion"
            ),
        }
    )
    script = (
        "function Req($c,[string]$m){if(-not$c){throw $m}}\n"
        + function_text
        + "\n$result='"
        + json.dumps(tampered, ensure_ascii=False)
        + "'|ConvertFrom-Json;"
        + "$oracle='"
        + json.dumps(oracle, ensure_ascii=False)
        + "'|ConvertFrom-Json;"
        + "AssertFixtureResultOracle $result $oracle 'persisted';"
    )
    rejected = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    assert rejected.returncode != 0
    assert "persisted fixture oracle" in rejected.stdout + rejected.stderr


def test_wp5_after_replace_bootstrap_failure_removes_new_candidate():
    source = (
        RESEARCH / "validation/wp5-consistency/publish-wp5-consistency.ps1"
    ).read_text(encoding="utf-8")
    branch = re.search(
        r"if\(\$InjectFailure-ceq'AfterReplace'\)\{(?P<body>.*?)"
        r"throw 'WP5 injected failure AfterReplace'",
        source,
        flags=re.DOTALL,
    )
    assert branch
    body = branch.group("body")
    assert "elseif(-not$hadActive-and(Test-Path -LiteralPath $active))" in body
    assert "Remove-Item -Force -LiteralPath $active" in body
    assert "Remove-Item -Recurse -Force -LiteralPath $dest" in body
    assert "Remove-Item -Force -LiteralPath $journalPath" in body


@pytest.mark.parametrize("extra_args", [["-SkipSignoff"], []])
def test_wp5_final_gate_passes_on_runner_platform(extra_args):
    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(RESEARCH / "validate-wp5.ps1"),
            *extra_args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_chapter05_correction_matches_file_manifest_and_acceptance_review():
    expected = sha256(RESEARCH / "05-工程化落地与效率优化方案.md")
    manifest = (RESEARCH / "manifest.yaml").read_text(encoding="utf-8")
    registered = re.search(
        r'path: "05-工程化落地与效率优化方案\.md", sha256: "([0-9a-f]{64})"',
        manifest,
    )
    assert registered and registered.group(1) == expected
    correction = (RESEARCH / "验收审查意见03.md").read_text(encoding="utf-8")
    assert expected in correction
    assert "旧 `bf4565da…` 仅为失效历史记录" in correction


def test_published_status_keeps_release_blocked_and_ai_boundary():
    report = (RESEARCH / "整改落实报告03.md").read_text(encoding="utf-8")
    status = (RESEARCH / "evidence-status-03.md").read_text(encoding="utf-8")
    assert "不等同于 Git 持久化、远程 CI/证明或复审放行" in report
    assert "identity_type=automated-ai-specialist-evidence-review" in report
    assert "Release acceptance：Blocked" in status
    assert "Local evidence audit：Passed" in status


def test_current_locked_rerun_keeps_failed_gates_blocking():
    final_gates = json.loads(WP9.FINAL_GATES.read_text(encoding="utf-8"))
    assert final_gates["evidence_kind"] == "current-local-rerun"
    assert final_gates["status"] == "blocked"
    assert final_gates["environment"]["status"] == "passed"
    assert final_gates["environment"]["uv"] == "0.11.29"
    assert final_gates["environment"]["python"] == "3.11.15"
    pytest_gate = final_gates["gates"]["pytest"]
    assert pytest_gate["status"] == (
        "passed" if pytest_gate["exit_code"] == 0 else "blocked"
    )
    if pytest_gate["status"] == "passed":
        assert pytest_gate["passed"] >= 421
        assert pytest_gate["skipped"] == 1
        assert pytest_gate["warnings"] >= 119
    assert pytest_gate["argv"][-3:] == ["-m", "pytest", "-q"]
    blocking_gates = final_gates["release_acceptance"]["blocking_gates"]
    assert "wp5" in blocking_gates
    assert final_gates["gates"]["wp7_self_test"]["status"] == "passed"
    assert final_gates["gates"]["wp8_synthetic_completion"]["status"] == "passed"
    assert all(
        final_gates["gates"][name]["status"] == "blocked"
        for name in blocking_gates
    )
    assert blocking_gates == [
        name
        for name, gate in final_gates["gates"].items()
        if gate["status"] != "passed"
    ]
    review = (RESEARCH / "验收审查意见03.md").read_text(encoding="utf-8")
    assert f"{pytest_gate['passed']} passed、{pytest_gate['skipped']} skipped" in review
    assert "method-validation:semantic-replay-mismatch" in review
    assert "pod_basis" in review
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for fragment in (
        "Run WP5 consistency gate",
        "Run WP7 signed evidence gate",
        "Run WP8 live synthetic gate",
        "Regenerate deterministic WP8 supplements",
        "OPENBLAS_NUM_THREADS",
        "validate-wp5.ps1",
        "validate-wp7.ps1",
        "validation/wp8/generate_synthetic_supplements.py",
        "validation/wp8/validate_wp8.py --phase synthetic",
    ):
        assert fragment in workflow
    for mutate in ("pytest-count", "gate-status", "blocking-set", "lock-hash"):
        payload = deepcopy(final_gates)
        if mutate == "pytest-count":
            payload["gates"]["pytest"]["passed"] = 999
        elif mutate == "gate-status":
            payload["gates"]["wp5"]["status"] = "passed"
        elif mutate == "blocking-set":
            payload["release_acceptance"]["blocking_gates"] = []
        else:
            payload["environment"]["uv_lock_sha256"] = "0" * 64
        errors = []
        WP9.validate_final_gates(payload, errors)
        assert errors, mutate


def test_repository_asset_ignore_policy():
    ignored = [
        ".agents/probe",
        ".specify/probe",
        ".tmp-wp8-midu-inspect/probe",
        "validation/wp8/data/zenodo-pycsamt-v1/extracted/"
        "WEgeophysics-pyCSAMT-c5e9c58/pycsamt/epsg.npy",
        "validation/wp8/synthetic/supplements-v1/csamt.npz",
        "validation/wp8/synthetic/supplements-v1/sip_fdip.npz",
        "validation/wp8/synthetic/supplements-v1/wfem.npz",
    ]
    required = [
        "_bmad-output/planning-artifacts/research/open-data/mining_geophysics/"
        "Zenodo_DO27_kimberlite_gravity_magnetic_joint_inversion_synthetic/"
        "simpeg-research_Astic-2020-JointInversion-1.0.0.zip",
        "validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json",
        "validation/wp9/validate_wp9.py",
    ]
    for path in ignored:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", "--", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0, path
    for path in required:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", "--", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 1, path


def test_wp8_wp9_persistence_plan_is_read_only_and_fail_closed():
    plan = PERSISTENCE.build_plan()
    counts = plan["classification_counts"]
    assert plan["manifest_binding"]["closure"] == "passed"
    assert (
        counts["manifest_members"]
        == plan["manifest_binding"]["declared_members"]
        == plan["manifest_binding"]["resolved_members"]
    )
    assert counts["required_generated_artifacts"] == 3
    assert counts["required_but_ignored_unresolved"] == 0
    assert counts["scan_failures"] == 0
    assert plan["authorization"]["operations_performed_by_builder"] == []
    assert plan["authorization"]["git_add_commit_push_pr"] == "not-authorized"
    assert plan["authorization"]["observed_head_contains_frozen_baseline"] is True
    assert plan["authorization"]["observed_staged_required_paths"] == sorted(
        set(plan["required_git"]) & PERSISTENCE._staged_paths()
    )
    assert plan["local_preparation"] == (
        "blocked"
        if plan["authorization"]["observed_staged_required_paths"]
        else "passed"
    )
    assert plan["release_ready"] is False
    assert plan["remote_attestation_verified"] is False
    final_gates = json.loads(PERSISTENCE.FINAL_GATES.read_text(encoding="utf-8"))
    assert plan["live_gate_snapshot"]["blocking_gates"] == final_gates[
        "release_acceptance"
    ]["blocking_gates"]


def test_persistence_plan_includes_complete_shallow_wp8_python_surface():
    controls = set(PERSISTENCE._control_inputs({"paths": []}))
    expected = {
        path.relative_to(PERSISTENCE.ROOT).as_posix()
        for path in (PERSISTENCE.ROOT / "validation/wp8").glob("*.py")
    }
    assert expected
    assert expected <= controls


def test_fixed_point_reference_closure_follows_all_supported_hash_edges(tmp_path):
    fixture = _reference_closure_fixture(tmp_path)
    closure = PERSISTENCE._derive_reference_closure(
        root=fixture["root"],
        research=fixture["research"],
        wp9=fixture["wp9"],
    )
    paths = set(closure["paths"])
    expected = {
        path.relative_to(tmp_path).as_posix()
        for path in (
            fixture["diagnostic"],
            fixture["document"],
            fixture["wp2_pointer"],
            fixture["wp2_result"],
            fixture["wp2_source"],
            fixture["evidence"],
            fixture["producer_asset"],
        )
    }
    assert closure["status"] == "passed"
    assert expected <= paths
    assert {
        "wp6-diagnostic-registry",
        "active-output-manifest",
        "active-manifest-file",
        "active-manifest-source",
        "wp5-scan-document",
        "wp5-claim-ledger-source",
        "wp9-finding-evidence",
        "wp8-producer-manifest-member",
    } <= {edge["relation"] for edge in closure["edges"]}
    assert re.fullmatch(r"[0-9a-f]{64}", closure["edges_sha256"])


@pytest.mark.parametrize(
    ("relative", "expected_hash", "message"),
    [
        ("missing.json", "0" * 64, "reference target missing"),
        ("../outside.json", "0" * 64, "escapes repository root"),
        ("evidence.md", "0" * 64, "reference hash drift"),
    ],
)
def test_fixed_point_reference_closure_fails_closed(
    tmp_path, relative, expected_hash, message
):
    fixture = _reference_closure_fixture(tmp_path)
    registry = json.loads(
        fixture["finding_registry"].read_text(encoding="utf-8")
    )
    registry["findings"][0]["evidence"][0] = {
        "path": relative,
        "sha256": expected_hash,
    }
    _write_json(fixture["finding_registry"], registry)
    with pytest.raises(ValueError, match=message):
        PERSISTENCE._derive_reference_closure(
            root=fixture["root"],
            research=fixture["research"],
            wp9=fixture["wp9"],
        )


def test_fixed_point_reference_closure_rejects_conflicting_hashes(tmp_path):
    fixture = _reference_closure_fixture(tmp_path)
    registry = json.loads(
        fixture["finding_registry"].read_text(encoding="utf-8")
    )
    registry["findings"][0]["evidence"][0] = {
        "path": fixture["diagnostic"].relative_to(tmp_path).as_posix(),
        "sha256": "0" * 64,
    }
    _write_json(fixture["finding_registry"], registry)
    with pytest.raises(ValueError, match="conflicting reference hashes"):
        PERSISTENCE._derive_reference_closure(
            root=fixture["root"],
            research=fixture["research"],
            wp9=fixture["wp9"],
        )


def test_persistence_uses_dynamic_active_versions_and_wp8_asset_inventory():
    assert not any(
        "/validation/wp5-consistency/versions/" in path
        for path in PERSISTENCE.CONTROL_DIRECTORIES
    )
    required_assets = set(PERSISTENCE._required_wp8_repository_assets())
    controls = set(PERSISTENCE._control_inputs({"paths": []}))
    assert PERSISTENCE.WP7_DO27_ARCHIVE in controls
    assert required_assets <= controls
    assert {
        "validation/wp8/field/preregistration-scaffold-v1.json",
        "validation/wp8/synthetic/method-validation-policy-v1.json",
        "validation/wp8/evidence/wp8-1-start.json",
    } <= required_assets


def test_head_closure_verification_requires_persisted_matching_records():
    plan = {
        "records": [
            {
                "path": "bound.json",
                "classification": "required-git",
                "tracked_in_head": True,
                "head_matches_worktree": True,
            }
        ],
        "reference_closure": {"status": "passed", "paths": ["bound.json"]},
        "required_but_ignored_unresolved": [],
        "repository_scope_scan": {"status": "passed"},
        "deterministic_generation": {"status": "passed"},
        "authorization": {
            "observed_head_contains_frozen_baseline": True,
            "observed_staged_required_paths": [],
        },
    }
    assert PERSISTENCE._head_closure_errors(plan) == []
    plan["records"][0]["tracked_in_head"] = False
    plan["records"][0]["head_matches_worktree"] = False
    errors = PERSISTENCE._head_closure_errors(plan)
    assert "required Git paths are absent from HEAD" in errors
    assert "required Git paths differ between HEAD and worktree" in errors


def test_repository_scope_allows_only_controlled_wp7_versions():
    from tools.validate_repository_scope import ABSOLUTE_PATH, permitted_forbidden_path

    assert ABSOLUTE_PATH.search('path = "/' + 'home/runner/private.json"')
    assert not ABSOLUTE_PATH.search(
        '"terms": "https://www2.gov.bc.ca/gov/content/home/disclaimer"'
    )

    prefix = (
        "/_bmad-output/planning-artifacts/research/"
        "贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp7/versions/"
    )
    assert permitted_forbidden_path(
        prefix + "synthetic-block-v6-20260724/raw-chains.npz"
    )
    assert permitted_forbidden_path(prefix + "do27-v4-20260724/raw-numerics.npz")
    assert not permitted_forbidden_path(prefix + "unreviewed-v99/raw.npz")
    assert permitted_forbidden_path(
        "/_bmad-output/planning-artifacts/research/open-data/mining_geophysics/"
        "Zenodo_DO27_kimberlite_gravity_magnetic_joint_inversion_synthetic/"
        "simpeg-research_Astic-2020-JointInversion-1.0.0.zip"
    )
    assert not permitted_forbidden_path(
        "/_bmad-output/planning-artifacts/research/open-data/mining_geophysics/"
        "unreviewed.zip"
    )
    assert not permitted_forbidden_path("/validation/wp8/versions/raw.npz")
    wp1_output = (
        "/_bmad-output/planning-artifacts/research/"
        "贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp1-toy/output/"
    )
    for member in ("prior-predictive.csv", "ranks.csv", "results.json"):
        assert permitted_forbidden_path(wp1_output + member)
    assert not permitted_forbidden_path(wp1_output + "unreviewed.json")


def test_persistence_plan_rejects_manifest_member_drift(tmp_path, monkeypatch):
    manifest = json.loads(PERSISTENCE.MANIFEST.read_text(encoding="utf-8"))
    manifest["members"][0]["sha256"] = "0" * 64
    target = tmp_path / "drifted-manifest.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(PERSISTENCE, "MANIFEST", target)
    with pytest.raises(ValueError, match="manifest member drift"):
        PERSISTENCE.build_plan()


def test_persistence_plan_rejects_incomplete_manifest(tmp_path, monkeypatch):
    manifest = json.loads(PERSISTENCE.MANIFEST.read_text(encoding="utf-8"))
    manifest["members"].pop()
    target = tmp_path / "incomplete-manifest.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(PERSISTENCE, "MANIFEST", target)
    with pytest.raises(ValueError, match="manifest member set"):
        PERSISTENCE.build_plan()


def test_persistence_plan_rejects_path_escape():
    with pytest.raises(ValueError, match="escapes repository root"):
        PERSISTENCE._record(
            "../../outside-repository",
            tracked=set(),
            staged=set(),
            generated_paths=set(),
            source="injected-test",
        )


def test_persistence_plan_blocks_unresolved_ignored_required_path(monkeypatch):
    real_ignore_rule = PERSISTENCE._ignore_rule

    def injected_ignore_rule(relative):
        if relative == "tools/validate_repository_scope.py":
            return "injected-ignore-rule"
        return real_ignore_rule(relative)

    monkeypatch.setattr(PERSISTENCE, "_ignore_rule", injected_ignore_rule)
    plan = PERSISTENCE.build_plan()
    assert plan["local_preparation"] == "blocked"
    assert "tools/validate_repository_scope.py" in plan[
        "required_but_ignored_unresolved"
    ]
    assert any("no approved distribution rule" in item for item in plan["blockers"])


def test_persistence_plan_rejects_supplement_hash_drift():
    manifest = json.loads(
        PERSISTENCE.SUPPLEMENT_MANIFEST.read_text(encoding="utf-8")
    )
    manifest["members"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="supplement hash drift"):
        PERSISTENCE._validate_supplement_manifest(manifest)

    replay = PERSISTENCE._verify_deterministic_generation(manifest)
    assert replay["status"] == "blocked"
    assert replay["matches_declared_hashes"] is False


def test_persistence_git_probes_fail_closed(monkeypatch):
    monkeypatch.setattr(
        PERSISTENCE,
        "_run_git",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 128, stdout=b"", stderr=b"injected git failure"
        ),
    )
    with pytest.raises(RuntimeError, match="injected git failure"):
        PERSISTENCE._tracked_paths()
    with pytest.raises(RuntimeError, match="injected git failure"):
        PERSISTENCE._staged_paths()
    with pytest.raises(RuntimeError, match="injected git failure"):
        PERSISTENCE._ignore_rule("validation/wp9/validate_wp9.py")
    with pytest.raises(RuntimeError, match="injected git failure"):
        PERSISTENCE._git_is_ancestor("0" * 40)

    monkeypatch.setattr(
        PERSISTENCE,
        "_run_git",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout=b"not-a-commit\n", stderr=b""
        ),
    )
    with pytest.raises(RuntimeError, match="invalid commit"):
        PERSISTENCE._git_head()


def test_persistence_head_blob_uses_long_path_safe_git_plumbing(monkeypatch):
    calls = []

    def fake_run_git(*args, input_bytes=None):
        calls.append(args)
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=0,
            stdout=b"long-path-evidence",
            stderr=b"",
        )

    monkeypatch.setattr(PERSISTENCE, "_run_git", fake_run_git)
    expected = hashlib.sha256(b"long-path-evidence").hexdigest()
    long_path = "a/" + ("b" * 300) + ".json"

    assert PERSISTENCE._head_blob_sha256(long_path) == expected
    assert calls == [("cat-file", "blob", f"HEAD:{long_path}")]


def test_persistence_output_is_repo_scoped_and_atomic(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="inside the repository"):
        PERSISTENCE._resolve_output(ROOT.parent / "outside-persistence-plan.json")

    target = tmp_path / "plan.json"
    target.write_text("old", encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(PERSISTENCE.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failure"):
        PERSISTENCE._atomic_write(target, "new")
    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_persistence_scan_covers_markdown_and_blocked_cli_exit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(PERSISTENCE, "ROOT", tmp_path)
    markdown = tmp_path / "probe.md"
    probe = "leaked " + "H:" + "\\private\\secret\\file.txt"
    markdown.write_text(probe, encoding="utf-8")
    scan = PERSISTENCE._scan_text(markdown)
    assert scan["absolute_path"] is True
    assert PERSISTENCE._plan_exit_code({"local_preparation": "blocked"}) == 4
    assert PERSISTENCE._plan_exit_code({"local_preparation": "passed"}) == 0
