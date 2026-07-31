import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]
RESEARCH = (
    ROOT
    / "_bmad-output/planning-artifacts/research"
    / "贝叶斯思想与重磁电电磁深度融合技术体系"
)
VROOT = RESEARCH / "validation/wp5-consistency"


def _run_pwsh(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pwsh", "-NoProfile", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )


def test_materialized_fixture_manifest_freezes_all_oracles(tmp_path: Path):
    materializer = tmp_path / "materialize-selftest-fixture-manifest.ps1"
    shutil.copy2(VROOT / materializer.name, materializer)

    completed = _run_pwsh("-File", str(materializer), cwd=tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    manifest = json.loads(
        (tmp_path / "selftest-fixture-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == "wp5-selftest-fixture-manifest-v3"
    assert len(manifest["fixtures"]) == 300
    assert len({item["id"] for item in manifest["fixtures"]}) == 300
    assert (tmp_path / "selftest-fixture-manifest.json").read_bytes().count(b"\r") == 0

    for fixture in manifest["fixtures"]:
        assert list(fixture) == [
            "id",
            "stage",
            "canonical_case",
            "expected_exit",
            "expected_rejections",
        ]
        assert fixture["canonical_case"] == fixture["id"]
        if fixture["expected_exit"] == 0:
            assert fixture["expected_rejections"] == []
        else:
            assert fixture["expected_exit"] == 1
            assert len(fixture["expected_rejections"]) == 1
            assert fixture["expected_rejections"][0]

    by_id = {item["id"]: item for item in manifest["fixtures"]}
    assert by_id["FXT-LINEAGE-MIGRATION-007"]["expected_exit"] == 0
    assert by_id["FXT-LINEAGE-MIGRATION-007"]["expected_rejections"] == []
    assert by_id["FXT-SIGNOFF-011"]["expected_rejections"] == [
        "final reviews unique review id"
    ]
    assert by_id["FXT-SIGNOFF-014"]["expected_rejections"] == [
        "final review release evidence binding"
    ]
    assert by_id["FXT-SIGNOFF-026"]["expected_rejections"] == [
        "final reviews authorization frozen binding"
    ]
    assert by_id["FXT-SIGNOFF-027"]["expected_rejections"] == [
        "final reviews authorization amendment binding"
    ]
    assert by_id["FXT-SIGNOFF-028"]["expected_rejections"] == [
        "release evidence stage hash"
    ]
    assert by_id["FXT-LINEAGE-MIGRATION-103"]["expected_rejections"] == [
        "POD orthogonal-complement projection contract"
    ]
    assert by_id["FXT-LINEAGE-MIGRATION-104"]["expected_rejections"] == [
        "RJMCMC Green acceptance-ratio contract"
    ]
    assert by_id["FXT-LINEAGE-MIGRATION-154"]["expected_rejections"] == [
        "POD rank-deficient economic SVD contract"
    ]


def test_scientific_formula_guards_are_span_bound_and_have_dedicated_mutations():
    validator = (RESEARCH / "validate-wp5.ps1").read_text(encoding="utf-8")
    builder = (VROOT / "build-loop33-ledger-migration.ps1").read_text(
        encoding="utf-8"
    )

    assert "DOC03-POD-EYM-3.1-7B" in validator
    assert "POD orthogonal-complement projection contract" in validator
    assert "薄SVD下可以删除正交补项" in validator
    assert "DOC03-RJMCMC-GREEN-3.3-2" in validator
    assert "RJMCMC Green acceptance-ratio contract" in validator
    assert "$new='\\pi(y)'" in validator

    assert "CLM-DOC-03-0005" in builder
    assert "CLM-DOC-03-0007" in builder
    assert "POD projection span" in builder
    assert "RJMCMC Green span" in builder


def _runner_fixture(tmp_path: Path, event_rejection: str) -> tuple[Path, str]:
    research = tmp_path / "research"
    vroot = research / "validation/wp5-consistency"
    run_id = "20260730T010101001Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    version = vroot / f"versions/{run_id}"
    version.mkdir(parents=True)
    runner = vroot / "run-selftest-evidence.ps1"
    shutil.copy2(VROOT / runner.name, runner)
    shutil.copy2(VROOT / "selftest-fixture-manifest.json", vroot)

    manifest = version / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    import hashlib

    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (vroot / "active-output.json").write_text(
        json.dumps(
            {
                "schema": "wp5-active-output-v1",
                "run_instance_id": run_id,
                "version_path": f"versions/{run_id}",
                "manifest_sha256": manifest_hash,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    fixture_id = "FXT-ALLOWLIST-006"
    fake_validator = research / "validate-wp5.ps1"
    fake_validator.write_text(
        """
param(
 [string]$RootOverride,
 [switch]$SelfTest,
 [string]$SelfTestStage,
 [string[]]$FixtureIds
)
$rejection = '__EVENT_REJECTION__'
$record = [ordered]@{
 fixture_id = 'FXT-ALLOWLIST-006'
 case = 'FXT-ALLOWLIST-006'
 expected_exit = 1
 actual_exit = 1
 expected_rejections = @($rejection)
 actual_rejection = $rejection
 success_criterion = 'child rejects this fixture with one predeclared business assertion'
 matched = $true
 duration_ms = 1
}
[IO.File]::AppendAllText(
 $env:WP5_SELFTEST_EVENT_PATH,
 ('SELFTEST_CASE_JSON=' + ($record | ConvertTo-Json -Compress) + "`n"),
 [Text.UTF8Encoding]::new($false)
)
Write-Output 'PASS self_test_stage=allowlist'
exit 0
""".replace("__EVENT_REJECTION__", event_rejection),
        encoding="utf-8",
    )
    root_template = (RESEARCH / "WP5-consistency-input-root.sha256").read_text(
        encoding="utf-8"
    )
    members = [line.split("  ", 1)[1] for line in root_template.splitlines()[2:]]
    for relative in members:
        destination = research / relative
        if destination.exists():
            continue
        source = RESEARCH / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    member_lines = [
        f"{hashlib.sha256((research / item).read_bytes()).hexdigest()}  {item}"
        for item in members
    ]
    root_text = "# WP5 consistency root v1\n\n" + "\n".join(member_lines) + "\n"
    root_path = research / "WP5-consistency-input-root.sha256"
    root_path.write_text(root_text, encoding="utf-8", newline="\n")
    root_hash = hashlib.sha256(root_path.read_bytes()).hexdigest()
    (vroot / "WP5-consistency-root-anchor.sha256").write_text(
        root_hash + "\n", encoding="utf-8", newline="\n"
    )
    return runner, fixture_id


def test_runner_rejects_self_consistent_event_that_disagrees_with_manifest_oracle(
    tmp_path: Path,
):
    runner, fixture_id = _runner_fixture(tmp_path, "wrong but self-consistent")
    completed = _run_pwsh(
        "-File",
        str(runner),
        "-Stage",
        "allowlist",
        "-FixtureIds",
        fixture_id,
        "-SmokeTest",
        cwd=tmp_path,
    )
    assert completed.returncode != 0
    assert "Self-test evidence result invalid: FXT-ALLOWLIST-006" in (
        completed.stdout + completed.stderr
    )


def test_runner_accepts_event_only_when_it_matches_manifest_oracle(tmp_path: Path):
    runner, fixture_id = _runner_fixture(tmp_path, "allowlist frozen constants")
    completed = _run_pwsh(
        "-File",
        str(runner),
        "-Stage",
        "allowlist",
        "-FixtureIds",
        fixture_id,
        "-SmokeTest",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = list(
        (
            tmp_path
            / "research/validation/wp5-consistency/release-evidence-v1/stages"
        ).glob("smoke-selftest-*.json")
    )
    assert len(evidence) == 1
    payload = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert payload["fixture_results"][0]["expected_rejections"] == [
        "allowlist frozen constants"
    ]


def test_validator_wrapper_never_synthesizes_or_overwrites_oracle():
    validator = (RESEARCH / "validate-wp5.ps1").read_text(encoding="utf-8")
    assert "$oracle=$selfTestFixtureOracle[[string]$fixtureId]" in validator
    assert "$expectedExit=if($proc.ExitCode" not in validator
    assert "$expectedRejections=@($actualRejection)" not in validator
    assert "$expectedRejections=@($script:selfTestExpectedRejections)" not in validator


def test_actual_containment_helper_rejects_existing_link_escape(tmp_path: Path):
    probe = tmp_path / "probe-containment.ps1"
    probe.write_text(
        r"""
param([string]$Validator,[string]$Work)
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Validator,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'validator parse failed'}
foreach($name in @('Req','TestContainedPath','GetCanonicalPath','GetContainedFullPath')){
 $fn=@($ast.FindAll({param($node) $node-is[Management.Automation.Language.FunctionDefinitionAst]-and$node.Name-ceq$name},$true))
 if($fn.Count-ne1){throw "function lookup failed: $name"}
 Invoke-Expression $fn[0].Extent.Text
}
$base=Join-Path $Work 'root';$inside=Join-Path $base 'inside';$outside=Join-Path $Work 'outside'
New-Item -ItemType Directory -Force -Path $inside,$outside|Out-Null
[IO.File]::WriteAllText((Join-Path $inside 'member.json'),'{}')
[IO.File]::WriteAllText((Join-Path $outside 'member.json'),'{}')
$linkType=if($IsWindows){'Junction'}else{'SymbolicLink'}
$insideLink=Join-Path $base 'inside-link';$escapeLink=Join-Path $base 'escape-link'
New-Item -ItemType $linkType -Path $insideLink -Target $inside|Out-Null
New-Item -ItemType $linkType -Path $escapeLink -Target $outside|Out-Null
$null=GetContainedFullPath $base (Join-Path $insideLink 'member.json') 'inside link'
$caught=$false
try{$null=GetContainedFullPath $base (Join-Path $escapeLink 'member.json') 'link escape'}catch{$caught=$_.Exception.Message.Contains('WP5 validation failed: link escape')}
if(-not$caught){throw 'existing link escape was accepted'}
Write-Output 'PASS canonical containment'
""",
        encoding="utf-8",
    )
    completed = _run_pwsh(
        "-File",
        str(probe),
        "-Validator",
        str(RESEARCH / "validate-wp5.ps1"),
        "-Work",
        str(tmp_path / "work"),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS canonical containment" in completed.stdout
