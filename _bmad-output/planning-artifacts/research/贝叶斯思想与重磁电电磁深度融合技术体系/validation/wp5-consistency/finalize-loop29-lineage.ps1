[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $vroot)
function Get-Sha([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Write-Json([string]$Path, $Object) { [IO.File]::WriteAllText($Path, (($Object | ConvertTo-Json -Depth 100) + "`n"), [Text.UTF8Encoding]::new($false)) }
function Fail([string]$Message) { throw "WP5 loop29 lineage finalization failed: $Message" }

$scopePath = Join-Path $vroot 'scope-registry.json'
$scopeIntermediatePath = Join-Path $vroot 'scope-registry.loop29-intermediate-anchor.json'
$scopeLineagePath = Join-Path $vroot 'scope-registry-lineage.json'
$scopeLineage = Get-Content -Raw $scopeLineagePath | ConvertFrom-Json -Depth 100
$oldScope = $scopeLineage.generations.loop29
if ($oldScope.sha256 -cne (Get-Sha $scopeIntermediatePath)) { Fail 'scope intermediate hash' }
$scopeCurrent = Get-Content -Raw $scopePath | ConvertFrom-Json -Depth 100
$scopeGenerations = [ordered]@{ loop28=$scopeLineage.generations.loop28 }
$scopeGenerations['loop29-intermediate'] = [ordered]@{ path='scope-registry.loop29-intermediate-anchor.json'; sha256=(Get-Sha $scopeIntermediatePath); scope_count=@($scopeCurrent.scopes.PSObject.Properties).Count; ledger_path='claim-ledger.loop29-intermediate-anchor.json'; ledger_sha256=(Get-Sha (Join-Path $vroot 'claim-ledger.loop29-intermediate-anchor.json')) }
$scopeGenerations['loop29'] = [ordered]@{ path='scope-registry.json'; sha256=(Get-Sha $scopePath); scope_count=@($scopeCurrent.scopes.PSObject.Properties).Count; ledger_path='claim-ledger.json'; ledger_sha256=(Get-Sha (Join-Path $vroot 'claim-ledger.json')) }
Write-Json $scopeLineagePath ([ordered]@{ schema='wp5-scope-registry-lineage-v1'; generations=$scopeGenerations })

$riskPath = Join-Path $vroot 'high-risk-classification.json'
$riskIntermediatePath = Join-Path $vroot 'high-risk-classification.loop29-intermediate-anchor.json'
$riskLineagePath = Join-Path $vroot 'high-risk-classification-lineage.json'
$riskLineage = Get-Content -Raw $riskLineagePath | ConvertFrom-Json -Depth 100
$oldRisk = $riskLineage.generations.loop29
if ($oldRisk.sha256 -cne (Get-Sha $riskIntermediatePath)) { Fail 'risk intermediate hash' }
$riskCurrent = Get-Content -Raw $riskPath | ConvertFrom-Json -Depth 100
$riskGenerations = [ordered]@{ loop28=$riskLineage.generations.loop28 }
$riskGenerations['loop29-intermediate'] = [ordered]@{ path='high-risk-classification.loop29-intermediate-anchor.json'; sha256=(Get-Sha $riskIntermediatePath); rule_ids=@($riskCurrent.rules.id) }
$riskGenerations['loop29'] = [ordered]@{ path='high-risk-classification.json'; sha256=(Get-Sha $riskPath); rule_ids=@($riskCurrent.rules.id) }
Write-Json $riskLineagePath ([ordered]@{ schema='wp5-risk-registry-lineage-v1'; generations=$riskGenerations })

$validatorPath = Join-Path $root 'validate-wp5.ps1'
$text = [IO.File]::ReadAllText($validatorPath)
$text = $text.Replace("@('loop27','loop28','loop29-reanchor','loop29'))-and-not(Compare-Object @(`$lineage.migrations", "@('loop27','loop28','loop29-reanchor','loop29-intermediate','loop29'))-and-not(Compare-Object @(`$lineage.migrations")
$text = $text.Replace("@('loop28','loop29')))'ledger lineage schema'", "@('loop28','loop29-intermediate','loop29')))'ledger lineage schema'")
$text = $text.Replace("@('loop27','loop28','loop29-reanchor','loop29')){`$a=", "@('loop27','loop28','loop29-reanchor','loop29-intermediate','loop29')){`$a=")
$text = $text.Replace("@('loop28','loop29')){`$m=", "@('loop28','loop29-intermediate','loop29')){`$m=")
$text = $text.Replace("(($name-ceq'loop28'-and`$m.from-ceq'loop27')-or(`$name-ceq'loop29'-and`$m.from-ceq'loop29-reanchor'))", "(($name-ceq'loop28'-and`$m.from-ceq'loop27')-or(`$name-ceq'loop29-intermediate'-and`$m.from-ceq'loop29-reanchor')-or(`$name-ceq'loop29'-and`$m.from-ceq'loop29-intermediate'))")
$text = $text.Replace('(($name-ceq''loop28''-and$m.from-ceq''loop27'')-or($name-ceq''loop29''-and$m.from-ceq''loop29-reanchor''))', '(($name-ceq''loop28''-and$m.from-ceq''loop27'')-or($name-ceq''loop29-intermediate''-and$m.from-ceq''loop29-reanchor'')-or($name-ceq''loop29''-and$m.from-ceq''loop29-intermediate''))')
$text = $text.Replace("`$loop29Reanchor=ReadLedgerAnchor 'loop29-reanchor';Req", "`$loop29Reanchor=ReadLedgerAnchor 'loop29-reanchor';`$loop29Intermediate=ReadLedgerAnchor 'loop29-intermediate';Req")
$text = $text.Replace("`$ledger.previous_ledger_sha256-ceq`$lineage.anchors.'loop29-reanchor'.sha256-and`$loop29Reanchor.previous_ledger_sha256-ceq`$lineage.anchors.loop28.sha256", "`$ledger.previous_ledger_sha256-ceq`$lineage.anchors.'loop29-intermediate'.sha256-and`$loop29Intermediate.previous_ledger_sha256-ceq`$lineage.anchors.'loop29-reanchor'.sha256-and`$loop29Reanchor.previous_ledger_sha256-ceq`$lineage.anchors.loop28.sha256")
$text = $text.Replace("AssertTombstoneContinuity `$loop28 `$loop29Reanchor 'loop29-reanchor';AssertTombstoneContinuity `$loop29Reanchor `$ledger 'loop29'", "AssertTombstoneContinuity `$loop28 `$loop29Reanchor 'loop29-reanchor';AssertTombstoneContinuity `$loop29Reanchor `$loop29Intermediate 'loop29-intermediate';AssertTombstoneContinuity `$loop29Intermediate `$ledger 'loop29'")
$text = $text.Replace("AssertMigration 'loop28' `$loop27 `$loop28;AssertMigration 'loop29' `$loop29Reanchor `$ledger", "AssertMigration 'loop28' `$loop27 `$loop28;AssertMigration 'loop29-intermediate' `$loop29Reanchor `$loop29Intermediate;AssertMigration 'loop29' `$loop29Intermediate `$ledger")
$text = $text.Replace("@('loop28','loop29')))'scope lineage schema'", "@('loop28','loop29-intermediate','loop29')))'scope lineage schema'")
$text = $text.Replace("@('loop28','loop29')){`$g=`$scopeLineage", "@('loop28','loop29-intermediate','loop29')){`$g=`$scopeLineage")
$text = $text.Replace("@('loop28','loop29')))'risk lineage schema'", "@('loop28','loop29-intermediate','loop29')))'risk lineage schema'")
$text = $text.Replace("@('loop28','loop29')){`$g=`$riskLineage", "@('loop28','loop29-intermediate','loop29')){`$g=`$riskLineage")
[IO.File]::WriteAllText($validatorPath, $text, [Text.UTF8Encoding]::new($false))
Write-Output 'PASS lineage and validator upgraded for loop29 final chain'
