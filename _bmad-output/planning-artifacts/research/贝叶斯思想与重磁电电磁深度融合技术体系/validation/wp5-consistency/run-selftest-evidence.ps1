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
$pointerPath = Join-Path $vroot 'active-output.json'
$fixturesPath = Join-Path $vroot 'selftest-fixture-manifest.json'
$rootPath = Join-Path $root 'WP5-consistency-input-root.sha256'
$rootAnchorPath = Join-Path $vroot 'WP5-consistency-root-anchor.sha256'
$validatorSnapshot = $null
$eventPath = $null

function Get-Sha256([string]$Path) {
    (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}
function Get-RootBinding {
    $lines = @(Get-Content -LiteralPath $rootPath)
    if ($lines.Count -ne 31 -or $lines[0] -cne '# WP5 consistency root v1' -or $lines[1] -cne '') {
        throw 'Self-test root identity invalid.'
    }
    $members = @($lines[2..30])
    foreach ($member in $members) {
        if ($member -cnotmatch '^([0-9a-f]{64})  (.+)$') { throw 'Self-test root member syntax invalid.' }
        $memberPath = [IO.Path]::GetFullPath((Join-Path $root $Matches[2]))
        $relative = [IO.Path]::GetRelativePath([IO.Path]::GetFullPath($root),$memberPath).Replace('\','/')
        if ($relative -cne $Matches[2] -or (Get-Sha256 $memberPath) -cne $Matches[1]) { throw 'Self-test root member binding invalid.' }
    }
    $memberText = ($members -join "`n") + "`n"
    $memberHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes($memberText))).ToLowerInvariant()
    $rootFileHash = Get-Sha256 $rootPath
    $anchorBytes = [IO.File]::ReadAllBytes($rootAnchorPath)
    $anchorText = [Text.UTF8Encoding]::new($false,$true).GetString($anchorBytes)
    if ($anchorBytes.Length -ne 65 -or $anchorText -cne ($rootFileHash + "`n")) { throw 'Self-test root anchor binding invalid.' }
    [pscustomobject]@{
        member_root_sha256 = $memberHash
        root_file_sha256 = $rootFileHash
        root_anchor_file_sha256 = Get-Sha256 $rootAnchorPath
    }
}
function Get-CurrentBinding {
    $pointerHash = Get-Sha256 $pointerPath
    $pointer = Get-Content -Raw -LiteralPath $pointerPath | ConvertFrom-Json -ErrorAction Stop
    if ($pointer.schema -cne 'wp5-active-output-v1' -or $pointer.version_path -cnotmatch '^versions/[0-9]{8}T[0-9]{9}Z-[0-9a-f]{32}$' -or $pointer.manifest_sha256 -cnotmatch '^[0-9a-f]{64}$') {
        throw 'Self-test candidate pointer identity invalid.'
    }
    $manifestPath = Join-Path $vroot ($pointer.version_path + '/manifest.json')
    $manifestHash = Get-Sha256 $manifestPath
    if ($manifestHash -cne $pointer.manifest_sha256) { throw 'Self-test candidate manifest binding invalid.' }
    $rootBinding = Get-RootBinding
    [pscustomobject]@{
        pointer = $pointer
        pointer_sha256 = $pointerHash
        manifest_sha256 = $manifestHash
        validator_sha256 = Get-Sha256 $validator
        fixture_manifest_sha256 = Get-Sha256 $fixturesPath
        member_root_sha256 = $rootBinding.member_root_sha256
        root_file_sha256 = $rootBinding.root_file_sha256
        root_anchor_file_sha256 = $rootBinding.root_anchor_file_sha256
    }
}
function Assert-SameBinding($Before,$After) {
    if ($Before.pointer_sha256 -cne $After.pointer_sha256 -or
        $Before.pointer.run_instance_id -cne $After.pointer.run_instance_id -or
        $Before.pointer.version_path -cne $After.pointer.version_path -or
        $Before.manifest_sha256 -cne $After.manifest_sha256 -or
        $Before.validator_sha256 -cne $After.validator_sha256 -or
        $Before.fixture_manifest_sha256 -cne $After.fixture_manifest_sha256 -or
        $Before.member_root_sha256 -cne $After.member_root_sha256 -or
        $Before.root_file_sha256 -cne $After.root_file_sha256 -or
        $Before.root_anchor_file_sha256 -cne $After.root_anchor_file_sha256) {
        throw 'Self-test source binding drifted during execution.'
    }
}
function Assert-OrdinalUnique([string[]]$Values, [string]$Message) {
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($value in @($Values)) {
        if ([string]::IsNullOrWhiteSpace($value) -or -not $seen.Add($value)) { throw $Message }
    }
}
function Write-NewAtomicFile([string]$Path,[byte[]]$Bytes) {
    if (Test-Path -LiteralPath $Path) { throw 'Refusing to overwrite immutable self-test evidence.' }
    $temp = Join-Path (Split-Path -Parent $Path) ('.tmp-' + [IO.Path]::GetFileName($Path) + '-' + [guid]::NewGuid().ToString('N'))
    try {
        $stream = [IO.File]::Open($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $stream.Write($Bytes,0,$Bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        [IO.File]::Move($temp,$Path)
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -Force -LiteralPath $temp }
    }
}

$before = Get-CurrentBinding
$pointer = $before.pointer
$fixtures = Get-Content -Raw -LiteralPath $fixturesPath | ConvertFrom-Json
$fixtureFields = @('id','stage','canonical_case','expected_exit','expected_rejections')
$fixtureOracle = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
if ($fixtures.schema -cne 'wp5-selftest-fixture-manifest-v3' -or @($fixtures.fixtures).Count -ne 300) {
    throw 'Fixture oracle manifest identity invalid.'
}
foreach ($fixture in @($fixtures.fixtures)) {
    $actualFields = @($fixture.PSObject.Properties.Name)
    $expectedRejections = @($fixture.expected_rejections)
    $validOracle = if ([int]$fixture.expected_exit -eq 0) {
        $expectedRejections.Count -eq 0
    } elseif ([int]$fixture.expected_exit -eq 1) {
        $expectedRejections.Count -eq 1 -and -not [string]::IsNullOrWhiteSpace([string]$expectedRejections[0])
    } else {
        $false
    }
    if ($actualFields.Count -ne $fixtureFields.Count -or
        @($fixtureFields | Where-Object { -not ($actualFields -ccontains $_) }).Count -ne 0 -or
        $fixture.stage -cnotin @('upstream-lineage','allowlist','registry','language-structure-boundary','publish','signoff','lineage-migration') -or
        -not ($fixture.canonical_case -is [string]) -or
        $fixture.canonical_case -cne $fixture.id -or
        -not $validOracle -or
        -not $fixtureOracle.TryAdd([string]$fixture.id,$fixture)) {
        throw "Fixture oracle manifest record invalid: $($fixture.id)"
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
    $ids = @($FixtureIds)
} else {
    $ids = @($stageIds)
}
if ($SmokeTest -and -not $hasExplicitFixtureSelection) { throw 'Smoke evidence requires a non-empty explicit fixture selection.' }

$eventPath = Join-Path ([IO.Path]::GetTempPath()) ('wp5-selftest-events-' + [guid]::NewGuid().ToString('N') + '.ndjson')
$validatorSnapshot = Join-Path ([IO.Path]::GetTempPath()) ('wp5-validator-snapshot-' + [guid]::NewGuid().ToString('N') + '.ps1')
try {
    [IO.File]::WriteAllBytes($validatorSnapshot,[IO.File]::ReadAllBytes($validator))
    if ((Get-Sha256 $validatorSnapshot) -cne $before.validator_sha256) { throw 'Self-test validator snapshot mismatch.' }
    $env:WP5_SELFTEST_EVENT_PATH = $eventPath
    if ($hasExplicitFixtureSelection) {
        $output = (& $validatorSnapshot -RootOverride $root -SelfTest -SelfTestStage $Stage -FixtureIds $ids 2>&1 | Out-String)
    } else {
        $output = (& $validatorSnapshot -RootOverride $root -SelfTest -SelfTestStage $Stage 2>&1 | Out-String)
    }
    $validatorExit = [int]$LASTEXITCODE
} finally {
    Remove-Item Env:WP5_SELFTEST_EVENT_PATH -ErrorAction SilentlyContinue
    if ($validatorSnapshot -and (Test-Path -LiteralPath $validatorSnapshot)) { Remove-Item -Force -LiteralPath $validatorSnapshot }
}

$after = Get-CurrentBinding
Assert-SameBinding $before $after
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
    $oracle = $fixtureOracle[[string]$ids[$i]]
    $eventExpected = @($caseResult.expected_rejections)
    $oracleExpected = @($oracle.expected_rejections)
    $oracleExact = [int]$caseResult.expected_exit -eq [int]$oracle.expected_exit -and
        ($eventExpected -join "`0") -ceq ($oracleExpected -join "`0") -and
        $eventExpected.Count -eq $oracleExpected.Count
    $validOutcome = if ([int]$oracle.expected_exit -eq 0) {
        [int]$caseResult.actual_exit -eq 0 -and [string]::IsNullOrEmpty([string]$caseResult.actual_rejection)
    } else {
        [int]$caseResult.actual_exit -ne 0 -and
        $oracleExpected.Count -eq 1 -and
        [string]$caseResult.actual_rejection -ceq [string]$oracleExpected[0]
    }
    $expectedCriterion = if ([int]$oracle.expected_exit -eq 0) { 'child accepts this positive fixture' } else { 'child rejects this fixture with one predeclared business assertion' }
    if ([string]$caseResult.fixture_id -cne $ids[$i] -or
        -not $oracleExact -or
        -not $validOutcome -or
        -not [bool]$caseResult.matched -or
        [string]$caseResult.success_criterion -cne $expectedCriterion -or
        -not ($caseResult.case -is [string]) -or
        $caseResult.case -cne $oracle.canonical_case -or
        [int64]$caseResult.duration_ms -lt 0) {
        throw "Self-test evidence result invalid: $($caseResult.case)"
    }
}

$fixtureResults = foreach ($caseResult in $caseResults) {
    [ordered]@{
        fixture_id = [string]$caseResult.fixture_id; case = [string]$caseResult.case
        expected_exit = [int]$caseResult.expected_exit; actual_exit = [int]$caseResult.actual_exit
        expected_rejections = @($caseResult.expected_rejections); actual_rejection = $caseResult.actual_rejection
        success_criterion = $caseResult.success_criterion; matched = [bool]$caseResult.matched
        duration_ms = [int64]$caseResult.duration_ms
    }
}

$resultDir = Join-Path (Join-Path $vroot 'release-evidence-v1') 'stages'; New-Item -ItemType Directory -Force $resultDir | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$prefix = if ($SmokeTest) { 'smoke-selftest-' } elseif ($hasExplicitFixtureSelection) { 'partial-selftest-' } else { 'selftest-' }
$file = ($prefix + '{0}-{1}-{2}.json') -f $pointer.run_instance_id, $Stage, $stamp
$path = Join-Path $resultDir $file
$payload = [ordered]@{
    schema = if ($SmokeTest) { 'wp5-selftest-smoke-evidence-v1' } elseif ($hasExplicitFixtureSelection) { 'wp5-selftest-partial-evidence-v1' } else { 'wp5-selftest-evidence-v1' }
    evidence_class = 'Post-publication self-test evidence; not an input to its referenced manifest'
    source_run_instance_id = $pointer.run_instance_id; source_version_path = $pointer.version_path
    source_manifest_sha256 = $before.manifest_sha256
    validator_sha256 = $before.validator_sha256
    fixture_manifest_sha256 = $before.fixture_manifest_sha256
    member_root_sha256 = $before.member_root_sha256
    root_file_sha256 = $before.root_file_sha256
    root_anchor_file_sha256 = $before.root_anchor_file_sha256
    stage = $Stage; fixture_count = $ids.Count; fixture_id_set = $ids; batch_role = if ($SmokeTest) { 'smoke' } else { 'stage' }
    fixture_results = @($fixtureResults); status = 'Passed'; completed_at_utc = [DateTime]::UtcNow.ToString('o')
    output_sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($output))).ToLowerInvariant()
    validator_exit = $validatorExit; pass_marker_count = $passMarkerCount
}
$payloadBytes = [Text.UTF8Encoding]::new($false).GetBytes((($payload | ConvertTo-Json -Depth 12) + "`n"))
Write-NewAtomicFile $path $payloadBytes
$hash = Get-Sha256 $path
Write-Output "PASS evidence=$file sha256=$hash stage=$Stage fixtures=$($ids.Count) source_manifest=$($pointer.manifest_sha256)"
