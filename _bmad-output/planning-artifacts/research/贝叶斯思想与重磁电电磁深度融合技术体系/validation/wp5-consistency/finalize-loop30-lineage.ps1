[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$vroot=$PSScriptRoot;$root=Split-Path -Parent (Split-Path -Parent $vroot)
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function WriteJson([string]$p,$o){[IO.File]::WriteAllText($p,(($o|ConvertTo-Json -Depth 100)+"`n"),[Text.UTF8Encoding]::new($false))}
function CopyAnchor([string]$source,[string]$dest){Copy-Item -LiteralPath $source -Destination $dest -Force}
$ledger=Join-Path $vroot 'claim-ledger.json';$ledgerAnchor=Join-Path $vroot 'claim-ledger.loop30-anchor.json';$scope=Join-Path $vroot 'scope-registry.json';$scopeAnchor=Join-Path $vroot 'scope-registry.loop30-anchor.json';$risk=Join-Path $vroot 'high-risk-classification.json';$riskAnchor=Join-Path $vroot 'high-risk-classification.loop30-anchor.json';
if((Sha $ledger)-cne(Sha $ledgerAnchor)){throw 'loop30 ledger anchor drift'}
CopyAnchor $scope $scopeAnchor;CopyAnchor $risk $riskAnchor
$lineage=Get-Content -Raw (Join-Path $vroot 'ledger-lineage.json')|ConvertFrom-Json -Depth 100
$loop29LedgerAnchor=Join-Path $vroot 'claim-ledger.loop29-anchor.json';$loop29Ledger=Get-Content -Raw $loop29LedgerAnchor|ConvertFrom-Json -Depth 100
$lineage.anchors.loop29.path='claim-ledger.loop29-anchor.json';$lineage.anchors.loop29.sha256=Sha $loop29LedgerAnchor;$lineage.anchors.loop29.active_count=@($loop29Ledger.entries).Count;$lineage.anchors.loop29.tombstone_count=@($loop29Ledger.tombstones).Count
$lineage.anchors|Add-Member -Force NoteProperty loop30 ([ordered]@{path='claim-ledger.loop30-anchor.json';sha256=(Sha $ledgerAnchor);active_count=@((Get-Content -Raw $ledgerAnchor|ConvertFrom-Json -Depth 100).entries).Count;tombstone_count=@((Get-Content -Raw $ledgerAnchor|ConvertFrom-Json -Depth 100).tombstones).Count})
$mig=Join-Path $vroot 'claim-ledger.loop30.text-migration.json';$m=Get-Content -Raw $mig|ConvertFrom-Json -Depth 100
$lineage.migrations|Add-Member -Force NoteProperty loop30 ([ordered]@{from='loop29';to='loop30';path='claim-ledger.loop30.text-migration.json';sha256=(Sha $mig);replacements=[int]$m.replacements;tombstones=[int]$m.tombstones})
WriteJson (Join-Path $vroot 'ledger-lineage.json') $lineage
$scopeLineage=Get-Content -Raw (Join-Path $vroot 'scope-registry-lineage.json')|ConvertFrom-Json -Depth 100;$scopeObject=Get-Content -Raw $scopeAnchor|ConvertFrom-Json -Depth 100
$loop29ScopeAnchor=Join-Path $vroot 'scope-registry.loop29-anchor.json';$loop29Scope=Get-Content -Raw $loop29ScopeAnchor|ConvertFrom-Json -Depth 100
$scopeLineage.generations.loop29.path='scope-registry.loop29-anchor.json';$scopeLineage.generations.loop29.sha256=Sha $loop29ScopeAnchor;$scopeLineage.generations.loop29.scope_count=@($loop29Scope.scopes.PSObject.Properties).Count;$scopeLineage.generations.loop29.ledger_path='claim-ledger.loop29-anchor.json';$scopeLineage.generations.loop29.ledger_sha256=Sha $loop29LedgerAnchor
$scopeLineage.generations|Add-Member -Force NoteProperty loop30 ([ordered]@{path='scope-registry.loop30-anchor.json';sha256=(Sha $scopeAnchor);scope_count=@($scopeObject.scopes.PSObject.Properties).Count;ledger_path='claim-ledger.loop30-anchor.json';ledger_sha256=(Sha $ledgerAnchor)})
WriteJson (Join-Path $vroot 'scope-registry-lineage.json') $scopeLineage
$riskLineage=Get-Content -Raw (Join-Path $vroot 'high-risk-classification-lineage.json')|ConvertFrom-Json -Depth 100;$riskObject=Get-Content -Raw $riskAnchor|ConvertFrom-Json -Depth 100
$loop29RiskAnchor=Join-Path $vroot 'high-risk-classification.loop29-anchor.json';$loop29Risk=Get-Content -Raw $loop29RiskAnchor|ConvertFrom-Json -Depth 100
$riskLineage.generations.loop29.path='high-risk-classification.loop29-anchor.json';$riskLineage.generations.loop29.sha256=Sha $loop29RiskAnchor;$riskLineage.generations.loop29.rule_ids=@($loop29Risk.rules.id)
$riskLineage.generations|Add-Member -Force NoteProperty loop30 ([ordered]@{path='high-risk-classification.loop30-anchor.json';sha256=(Sha $riskAnchor);rule_ids=@($riskObject.rules.id)})
WriteJson (Join-Path $vroot 'high-risk-classification-lineage.json') $riskLineage
$vp=Join-Path $root 'validate-wp5.ps1';$t=[IO.File]::ReadAllText($vp)
$t=$t.Replace("'7ea220daa97a5e7c362e8b40e61e30d26c0a8dd8361cb4853b5730883a3f4a8d'","'f9fd4eab64ef02e77c2290bb6bf17b8ee898f311a0540806ef173f04506d8e3b'")
$t=$t.Replace("@('pod','calibration','depth','resource')","@('pod','calibration','depth','resource','c02-gn-hessian','c03-rjmcmc-interface','a3-pod-hardware-boundary','a11-borehole-observation','a13-curie-source-contract')")
$t=$t.Replace("@('loop28','loop29-intermediate','loop29'))","@('loop28','loop29-intermediate','loop29','loop30'))")
$t=$t.Replace("@('loop27','loop28','loop29-reanchor','loop29-intermediate','loop29'))","@('loop27','loop28','loop29-reanchor','loop29-intermediate','loop29','loop30'))")
$t=$t.Replace("$name-ceq'loop29'-and$m.from-ceq'loop29-intermediate'","$name-ceq'loop29'-and$m.from-ceq'loop29-intermediate')-or($name-ceq'loop30'-and$m.from-ceq'loop29'")
$t=$t.Replace("$loop29Intermediate=ReadLedgerAnchor 'loop29-intermediate';Req","$loop29Intermediate=ReadLedgerAnchor 'loop29-intermediate';$loop30=ReadLedgerAnchor 'loop30';Req")
$t=$t.Replace("$lineage.anchors.loop29.sha256)'loop29 current ledger anchor'","$lineage.anchors.loop30.sha256)'loop30 current ledger anchor'")
$t=$t.Replace("$ledger.previous_ledger_sha256-ceq$lineage.anchors.'loop29-intermediate'.sha256","$ledger.previous_ledger_sha256-ceq$lineage.anchors.loop29.sha256")
$t=$t.Replace("AssertTombstoneContinuity $loop29Intermediate $ledger 'loop29'","AssertTombstoneContinuity $loop29Intermediate $ledger 'loop29';AssertTombstoneContinuity $ledger $loop30 'loop30'")
$t=$t.Replace("AssertMigration 'loop29' $loop29Intermediate $ledger","AssertMigration 'loop29' $loop29Intermediate $ledger;AssertMigration 'loop30' $ledger $loop30")
$t=$t.Replace("loop29 current ledger anchor","loop30 current ledger anchor")
[IO.File]::WriteAllText($vp,$t,[Text.UTF8Encoding]::new($false))
Write-Output "PASS loop30 anchors ledger=$(Sha $ledgerAnchor) scope=$(Sha $scopeAnchor) risk=$(Sha $riskAnchor)"
