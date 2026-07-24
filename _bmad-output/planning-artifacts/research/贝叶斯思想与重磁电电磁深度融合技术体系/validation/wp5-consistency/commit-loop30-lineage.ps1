[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Get-Sha([string]$path) {
    (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
}
function Read-Json([string]$path) {
    Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
}
function Write-Json([object]$value, [string]$path) {
    [System.IO.File]::WriteAllText($path, ($value | ConvertTo-Json -Depth 100), [System.Text.UTF8Encoding]::new($false))
}
function Set-Property([object]$target, [string]$name, [object]$value) {
    $target | Add-Member -NotePropertyName $name -NotePropertyValue $value -Force
}

$ledgerPath = Join-Path $root 'claim-ledger.json'
$ledgerAnchorPath = Join-Path $root 'claim-ledger.loop30-anchor.json'
$scopePath = Join-Path $root 'scope-registry.json'
$scopeAnchorPath = Join-Path $root 'scope-registry.loop30-anchor.json'
$riskPath = Join-Path $root 'high-risk-classification.json'
$riskAnchorPath = Join-Path $root 'high-risk-classification.loop30-anchor.json'
$migrationPath = Join-Path $root 'claim-ledger.loop30.text-migration.json'

$ledgerHash = Get-Sha $ledgerPath
if ($ledgerHash -ne (Get-Sha $ledgerAnchorPath)) { throw 'Loop30 ledger anchor differs from the active ledger.' }

Copy-Item -LiteralPath $scopePath -Destination $scopeAnchorPath -Force
Copy-Item -LiteralPath $riskPath -Destination $riskAnchorPath -Force

$ledger = Read-Json $ledgerPath
$scope = Read-Json $scopePath
$risk = Read-Json $riskPath
$migration = Read-Json $migrationPath

$ledgerLineagePath = Join-Path $root 'ledger-lineage.json'
$ledgerLineage = Read-Json $ledgerLineagePath
Set-Property $ledgerLineage.anchors 'loop30' ([pscustomobject]@{
    path = 'claim-ledger.loop30-anchor.json'; sha256 = $ledgerHash
    active_count = @($ledger.entries).Count; tombstone_count = @($ledger.tombstones).Count
})
Set-Property $ledgerLineage.migrations 'loop30' ([pscustomobject]@{
    from = 'loop29'; to = 'loop30'; path = 'claim-ledger.loop30.text-migration.json'
    sha256 = Get-Sha $migrationPath
    replacements = @($migration.entries | Where-Object disposition -eq 'replacement').Count
    tombstones = @($migration.entries | Where-Object disposition -eq 'tombstone').Count
})
Write-Json $ledgerLineage $ledgerLineagePath

$scopeLineagePath = Join-Path $root 'scope-registry-lineage.json'
$scopeLineage = Read-Json $scopeLineagePath
Set-Property $scopeLineage.generations 'loop30' ([pscustomobject]@{
    path = 'scope-registry.loop30-anchor.json'; sha256 = Get-Sha $scopeAnchorPath
    scope_count = @($scope.scopes.PSObject.Properties).Count; ledger_path = 'claim-ledger.loop30-anchor.json'; ledger_sha256 = $ledgerHash
})
Write-Json $scopeLineage $scopeLineagePath

$riskLineagePath = Join-Path $root 'high-risk-classification-lineage.json'
$riskLineage = Read-Json $riskLineagePath
Set-Property $riskLineage.generations 'loop30' ([pscustomobject]@{
    path = 'high-risk-classification.loop30-anchor.json'; sha256 = Get-Sha $riskAnchorPath
    rule_ids = @($risk.rules.id)
})
Write-Json $riskLineage $riskLineagePath

Write-Output "PASS loop30 ledger=$ledgerHash migration=$((Get-Sha $migrationPath)) scope=$((Get-Sha $scopeAnchorPath)) risk=$((Get-Sha $riskAnchorPath))"
