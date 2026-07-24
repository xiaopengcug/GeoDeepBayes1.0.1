[CmdletBinding()]
param(
  [ValidateSet('upstream-lineage','allowlist','registry','language-structure-boundary','publish','signoff','lineage-migration')]
  [string]$Stage
)

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$resultDir = Join-Path $vroot 'selftest-results'
$pointer = Get-Content -Raw (Join-Path $vroot 'active-output.json') | ConvertFrom-Json
$fixturesPath = Join-Path $vroot 'selftest-fixture-manifest.json'
$fixtures = Get-Content -Raw $fixturesPath | ConvertFrom-Json
$validator = Join-Path (Split-Path -Parent (Split-Path -Parent $vroot)) 'validate-wp5.ps1'
$ids = @($fixtures.fixtures | Where-Object { $_.stage -ceq $Stage } | ForEach-Object { [string]$_.id })
$fixtureManifestHash = (Get-FileHash -Algorithm SHA256 $fixturesPath).Hash.ToLowerInvariant()
$validatorHash = (Get-FileHash -Algorithm SHA256 $validator).Hash.ToLowerInvariant()

function Assert-ExactNames($Object, [string[]]$Names, [string]$Label) {
  $actual = @($Object.PSObject.Properties.Name)
  if ($actual.Count -ne $Names.Count -or (Compare-Object -CaseSensitive $actual $Names)) { throw "$Label exact schema" }
}
function Assert-OrdinalExact([string[]]$Actual, [string[]]$Expected, [string]$Label) {
  if ($Actual.Count -ne $Expected.Count) { throw $Label }
  for ($i = 0; $i -lt $Expected.Count; $i++) { if ($Actual[$i] -cne $Expected[$i]) { throw $Label } }
}
function Assert-OrdinalUnique([string[]]$Values, [string]$Label) {
  $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  foreach ($value in @($Values)) { if ([string]::IsNullOrWhiteSpace($value) -or -not $seen.Add($value)) { throw $Label } }
}

$partialNames = @('schema','evidence_class','source_run_instance_id','source_version_path','source_manifest_sha256','validator_sha256','fixture_manifest_sha256','stage','fixture_count','fixture_id_set','batch_role','fixture_results','status','completed_at_utc','output_sha256','validator_exit','pass_marker_count')
$resultNames = @('fixture_id','case','expected_exit','actual_exit','expected_rejections','actual_rejection','success_criterion','matched','duration_ms')
$partials = @()
foreach ($file in @(Get-ChildItem -LiteralPath $resultDir -File -Filter 'partial-selftest-*.json')) {
  $item = Get-Content -Raw -LiteralPath $file.FullName | ConvertFrom-Json
  # Historical immutable evidence is not a candidate for this active output.  Filter it
  # by the immutable bindings before applying the current partial-evidence schema.
  if ($item.source_run_instance_id -cne $pointer.run_instance_id -or $item.source_version_path -cne $pointer.version_path -or $item.source_manifest_sha256 -cne $pointer.manifest_sha256 -or $item.fixture_manifest_sha256 -cne $fixtureManifestHash -or $item.validator_sha256 -cne $validatorHash) { continue }
  Assert-ExactNames $item $partialNames ('partial '+$file.Name)
  if ($item.schema -cne 'wp5-selftest-partial-evidence-v1' -or $item.batch_role -cne 'stage' -or $item.stage -cne $Stage -or $item.source_run_instance_id -cne $pointer.run_instance_id -or $item.source_version_path -cne $pointer.version_path -or $item.source_manifest_sha256 -cne $pointer.manifest_sha256 -or $item.fixture_manifest_sha256 -cne $fixtureManifestHash -or $item.validator_sha256 -cne $validatorHash -or $item.status -cne 'Passed' -or [int]$item.validator_exit -ne 0 -or [int]$item.pass_marker_count -ne 1) { continue }
  $partialIds = @($item.fixture_id_set | ForEach-Object { [string]$_ })
  $resultIds = @($item.fixture_results | ForEach-Object { [string]$_.fixture_id })
  if ([int]$item.fixture_count -ne $partialIds.Count) { throw "partial fixture_count $($file.Name)" }
  Assert-OrdinalUnique $partialIds "partial fixture_id_set $($file.Name)"
  Assert-OrdinalExact $resultIds $partialIds "partial result id order $($file.Name)"
  foreach ($result in @($item.fixture_results)) {
    Assert-ExactNames $result $resultNames ('partial result '+$file.Name)
    $expected = @($result.expected_rejections); $validOutcome = if ([int]$result.expected_exit -eq 0) { [int]$result.actual_exit -eq 0 -and $expected.Count -eq 0 } elseif ([int]$result.expected_exit -eq 1) { [int]$result.actual_exit -ne 0 -and $expected.Count -gt 0 -and ($expected -ccontains [string]$result.actual_rejection) } else { $false }; if (-not $validOutcome -or -not [bool]$result.matched -or [int64]$result.duration_ms -lt 0) { throw "partial unmatched fixture $($result.fixture_id)" }
  }
  $partials += [pscustomobject]@{ path=$file.Name; sha256=(Get-FileHash -Algorithm SHA256 $file.FullName).Hash.ToLowerInvariant(); data=$item }
}

$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$results = @()
foreach ($partial in $partials) {
  foreach ($result in @($partial.data.fixture_results)) {
    if (-not $seen.Add([string]$result.fixture_id)) { throw "Partial evidence duplicate fixture $($result.fixture_id)" }
    $results += $result
  }
}
Assert-OrdinalUnique $ids 'stage fixture identity violation'
$resultIds = @($results | ForEach-Object { [string]$_.fixture_id })
if ($resultIds.Count -ne $ids.Count) { throw 'Partial evidence does not exactly cover the stage fixture set.' }
$stageSet = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal); foreach ($id in $ids) { [void]$stageSet.Add($id) }
foreach ($id in $resultIds) { if (-not $stageSet.Contains($id)) { throw 'Partial evidence does not exactly cover the stage fixture set.' } }

$ordered = @(); foreach ($id in $ids) { $ordered += @($results | Where-Object { $_.fixture_id -ceq $id }) }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$file = 'selftest-{0}-{1}-{2}.json' -f $pointer.run_instance_id, $Stage, $stamp
$path = Join-Path $resultDir $file
if (Test-Path -LiteralPath $path) { throw 'Refusing to overwrite final evidence.' }
$payload = [ordered]@{
  schema='wp5-selftest-evidence-v1'; evidence_class='Finalized from exact, non-overlapping partial evidence; not an input to its referenced manifest'
  source_run_instance_id=$pointer.run_instance_id; source_version_path=$pointer.version_path; source_manifest_sha256=$pointer.manifest_sha256
  validator_sha256=$validatorHash; fixture_manifest_sha256=$fixtureManifestHash; stage=$Stage; fixture_count=$ids.Count
  partial_evidence=@($partials | ForEach-Object { [ordered]@{path=$_.path;sha256=$_.sha256} }); fixture_results=$ordered; status='Passed'; completed_at_utc=[DateTime]::UtcNow.ToString('o')
}
[IO.File]::WriteAllText($path,(($payload|ConvertTo-Json -Depth 20)+"`n"),[Text.UTF8Encoding]::new($false))
Write-Output "PASS evidence=$file sha256=$((Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()) stage=$Stage fixtures=$($ids.Count) source_manifest=$($pointer.manifest_sha256)"
