[CmdletBinding()]
param(
    [ValidateSet('upstream-lineage','allowlist','registry','language-structure-boundary','publish','signoff','lineage-migration')]
    [string]$Stage,
    [string[]]$FixtureIds,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $vroot)
$validator = Join-Path $root 'validate-wp5.ps1'
$pointer = Get-Content -Raw (Join-Path $vroot 'active-output.json') | ConvertFrom-Json
$fixturesPath = Join-Path $vroot 'selftest-fixture-manifest.json'
$fixtures = Get-Content -Raw $fixturesPath | ConvertFrom-Json

function Assert-OrdinalUnique([string[]]$Values, [string]$Message) {
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($value in @($Values)) {
        if ([string]::IsNullOrWhiteSpace($value) -or -not $seen.Add($value)) { throw $Message }
    }
}

$stageIds = @($fixtures.fixtures | Where-Object { $_.stage -ceq $Stage } | ForEach-Object { [string]$_.id })
Assert-OrdinalUnique $stageIds 'Fixture evidence stage identity violation.'
$hasExplicitFixtureSelection = $PSBoundParameters.ContainsKey('FixtureIds') -and @($FixtureIds).Count -gt 0
if ($hasExplicitFixtureSelection) {
    Assert-OrdinalUnique @($FixtureIds) 'Fixture batch selection is not an explicit unique subset of the stage.'
    foreach ($fixtureId in @($FixtureIds)) {
        if (-not ($stageIds -ccontains $fixtureId)) { throw 'Fixture batch selection is not an explicit unique subset of the stage.' }
    }
    # The selected order is part of the observed event contract.
    $ids = @($FixtureIds)
} else {
    # Empty means the entire stage; it never means an empty batch.
    $ids = @($stageIds)
}
if ($SmokeTest -and -not $hasExplicitFixtureSelection) { throw 'Smoke evidence requires a non-empty explicit fixture selection.' }

$eventPath = Join-Path ([IO.Path]::GetTempPath()) ('wp5-selftest-events-' + [guid]::NewGuid().ToString('N') + '.ndjson')
try {
    $env:WP5_SELFTEST_EVENT_PATH = $eventPath
    if ($hasExplicitFixtureSelection) {
        $output = (& $validator -SelfTest -SelfTestStage $Stage -FixtureIds $ids 2>&1 | Out-String)
    } else {
        $output = (& $validator -SelfTest -SelfTestStage $Stage 2>&1 | Out-String)
    }
    $validatorExit = [int]$LASTEXITCODE
} finally {
    Remove-Item Env:WP5_SELFTEST_EVENT_PATH -ErrorAction SilentlyContinue
}

$passMarker = '(?m)^PASS self_test_stage=' + [regex]::Escape($Stage) + '\s*$'
$passMarkerCount = [regex]::Matches($output, $passMarker).Count
if ($validatorExit -ne 0 -or $passMarkerCount -ne 1) {
    Remove-Item -LiteralPath $eventPath -Force -ErrorAction SilentlyContinue
    throw "Self-test stage failed: $Stage exit=$validatorExit pass_markers=$passMarkerCount`n$output"
}

$caseResults = @()
if (Test-Path -LiteralPath $eventPath) {
    $caseResults = @(Get-Content -LiteralPath $eventPath | Where-Object { $_ -match '^SELFTEST_CASE_JSON=' } | ForEach-Object { $_.Substring('SELFTEST_CASE_JSON='.Length) | ConvertFrom-Json })
}
Remove-Item -LiteralPath $eventPath -Force -ErrorAction SilentlyContinue
if ($caseResults.Count -ne $ids.Count) { throw "Self-test evidence result count mismatch: expected $($ids.Count), actual $($caseResults.Count)." }
for ($i = 0; $i -lt $caseResults.Count; $i++) {
    $caseResult = $caseResults[$i]
$expected = @($caseResult.expected_rejections)
    $validOutcome = if ([int]$caseResult.expected_exit -eq 0) { [int]$caseResult.actual_exit -eq 0 -and $expected.Count -eq 0 } elseif ([int]$caseResult.expected_exit -eq 1) { [int]$caseResult.actual_exit -ne 0 -and $expected.Count -gt 0 -and ($expected -ccontains [string]$caseResult.actual_rejection) } else { $false }
    if ([string]$caseResult.fixture_id -cne $ids[$i] -or -not $validOutcome -or -not [bool]$caseResult.matched -or [int64]$caseResult.duration_ms -lt 0) {
        throw "Self-test evidence result invalid: $($caseResult.case)"
    }
}

$fixtureResults = foreach ($caseResult in $caseResults) {
    [ordered]@{
        fixture_id = $caseResult.fixture_id; case = $caseResult.case
        expected_exit = [int]$caseResult.expected_exit; actual_exit = [int]$caseResult.actual_exit
        expected_rejections = @($caseResult.expected_rejections); actual_rejection = $caseResult.actual_rejection
        success_criterion = $caseResult.success_criterion; matched = [bool]$caseResult.matched
        duration_ms = [int64]$caseResult.duration_ms
    }
}

$resultDir = Join-Path $vroot 'selftest-results'; New-Item -ItemType Directory -Force $resultDir | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$prefix = if ($SmokeTest) { 'smoke-selftest-' } elseif ($hasExplicitFixtureSelection) { 'partial-selftest-' } else { 'selftest-' }
$file = ($prefix + '{0}-{1}-{2}.json') -f $pointer.run_instance_id, $Stage, $stamp
$path = Join-Path $resultDir $file
if (Test-Path -LiteralPath $path) { throw 'Refusing to overwrite immutable self-test evidence.' }
$payload = [ordered]@{
    schema = if ($SmokeTest) { 'wp5-selftest-smoke-evidence-v1' } elseif ($hasExplicitFixtureSelection) { 'wp5-selftest-partial-evidence-v1' } else { 'wp5-selftest-evidence-v1' }
    evidence_class = 'Post-publication self-test evidence; not an input to its referenced manifest'
    source_run_instance_id = $pointer.run_instance_id; source_version_path = $pointer.version_path
    source_manifest_sha256 = $pointer.manifest_sha256
    validator_sha256 = (Get-FileHash -Algorithm SHA256 $validator).Hash.ToLowerInvariant()
    fixture_manifest_sha256 = (Get-FileHash -Algorithm SHA256 $fixturesPath).Hash.ToLowerInvariant()
    stage = $Stage; fixture_count = $ids.Count; fixture_id_set = $ids; batch_role = if ($SmokeTest) { 'smoke' } else { 'stage' }
    fixture_results = @($fixtureResults); status = 'Passed'; completed_at_utc = [DateTime]::UtcNow.ToString('o')
    output_sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($output))).ToLowerInvariant()
    validator_exit = $validatorExit; pass_marker_count = $passMarkerCount
}
[IO.File]::WriteAllText($path, (($payload | ConvertTo-Json -Depth 12) + "`n"), [Text.UTF8Encoding]::new($false))
$hash = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
Write-Output "PASS evidence=$file sha256=$hash stage=$Stage fixtures=$($ids.Count) source_manifest=$($pointer.manifest_sha256)"
