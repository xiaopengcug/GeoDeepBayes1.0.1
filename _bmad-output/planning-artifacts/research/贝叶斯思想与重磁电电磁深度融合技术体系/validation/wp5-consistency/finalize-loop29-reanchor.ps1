[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $vroot)
$ledgerPath = Join-Path $vroot 'claim-ledger.json'
$intermediatePath = Join-Path $vroot 'claim-ledger.loop29-intermediate-anchor.json'
$migrationPath = Join-Path $vroot 'claim-ledger.loop29.final-migration.json'
$lineagePath = Join-Path $vroot 'ledger-lineage.json'

function Fail([string]$Message) { throw "WP5 loop29 final reanchor failed: $Message" }
function Get-NormalizedSha256([string]$Text) {
    $normalized = ($Text.Trim() -replace '\s+', ' ')
    [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($normalized))).ToLowerInvariant()
}
function Get-FileSha256([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Write-AtomicJson([string]$Path, $Object) {
    $temporary = "$Path.tmp-$([guid]::NewGuid().ToString('N'))"
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Object | ConvertTo-Json -Depth 100) + "`n")
        [IO.File]::WriteAllBytes($temporary, $bytes)
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
}
function Copy-ExactOrFail([string]$Source, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) {
        if ((Get-FileSha256 $Source) -cne (Get-FileSha256 $Destination)) { Fail "existing anchor differs: $Destination" }
    } else {
        [IO.File]::Copy($Source, $Destination, $false)
    }
}

if (-not (Test-Path -LiteralPath $ledgerPath)) { Fail 'current ledger missing' }
$sourceHash = Get-FileSha256 $ledgerPath
$source = Get-Content -Raw -LiteralPath $ledgerPath | ConvertFrom-Json -Depth 100
if (@($source.entries).Count -ne 372 -or @($source.tombstones).Count -ne 676) { Fail 'intermediate cardinality' }
Copy-ExactOrFail $ledgerPath $intermediatePath

$lineCache = @{}
function Get-Lines([string]$Document) {
    if (-not $lineCache.ContainsKey($Document)) { $lineCache[$Document] = @(Get-Content -LiteralPath (Join-Path $root $Document)) }
    $lineCache[$Document]
}
$migrationEntries = [Collections.Generic.List[object]]::new()
$nextEntries = [Collections.Generic.List[object]]::new()
$nextTombstones = [Collections.Generic.List[object]]::new()
foreach ($t in @($source.tombstones)) { $nextTombstones.Add($t) }
$uniqueMoves = 0
$tombstones = 0
foreach ($entry in @($source.entries)) {
    $lines = Get-Lines $entry.document
    $boundHash = if ($entry.span_end -le $lines.Count) { Get-NormalizedSha256 ($lines[([int]$entry.span_start - 1)..([int]$entry.span_end - 1)] -join "`n") } else { $null }
    if ($boundHash -ceq $entry.text_sha256) { $nextEntries.Add($entry); continue }
    $matches = [Collections.Generic.List[int]]::new()
    for ($line = 1; $line -le $lines.Count; $line++) {
        if ((Get-NormalizedSha256 $lines[$line - 1]) -ceq $entry.text_sha256) { $matches.Add($line) }
    }
    $old = [ordered]@{ id=$entry.id; old_text_sha256=$entry.text_sha256; document=$entry.document; span_start=$entry.span_start; span_end=$entry.span_end }
    if ($matches.Count -eq 1) {
        $replacement = $entry | Select-Object *
        $replacement.span_start = $matches[0]
        $replacement.span_end = $matches[0]
        $replacement.text_sha256 = Get-NormalizedSha256 $lines[$matches[0] - 1]
        $migrationEntries.Add([ordered]@{ id=$entry.id; disposition='replacement'; old=$old; new_entry=$replacement; reason='unique current single-line SHA-256 reanchor' })
        $nextEntries.Add($replacement)
        $uniqueMoves++
    } elseif ($matches.Count -eq 0) {
        $migrationEntries.Add([ordered]@{ id=$entry.id; disposition='tombstone'; old=$old; reason='removed from current document; no current SHA-256 match' })
        $nextTombstones.Add([pscustomobject][ordered]@{ id=$entry.id; old_text_sha256=$entry.text_sha256; document=$entry.document; span_start=$entry.span_start; span_end=$entry.span_end })
        $tombstones++
    } else {
        Fail "ambiguous current SHA-256 match requires authored map: $($entry.id)=$($matches -join ',')"
    }
}
if (($uniqueMoves + $tombstones) -ne 34) { Fail "unexpected final mapping cardinality replacement=$uniqueMoves tombstone=$tombstones" }
$migration = [ordered]@{ schema='wp5-ledger-text-migration-v1'; source_ledger_sha256=$sourceHash; replacements=$uniqueMoves; tombstones=$tombstones; entries=@($migrationEntries) }
Write-AtomicJson $migrationPath $migration

$next = $source | Select-Object *
$next.entries = @($nextEntries)
$next.tombstones = @($nextTombstones)
foreach ($property in @($next.counts.PSObject.Properties.Name)) {
    $records = @($next.entries | Where-Object { $_.document -ceq $property })
    $next.counts.$property.claims = @($records | Where-Object { $_.kind -ceq 'claim' }).Count
    $next.counts.$property.code_blocks = @($records | Where-Object { $_.kind -ceq 'code' }).Count
}
if (@($next.entries).Count -ne (372 - $tombstones) -or @($next.tombstones).Count -ne (676 + $tombstones) -or (@($next.entries).Count + @($next.tombstones).Count) -ne 1048) { Fail 'final cardinality' }
$next.previous_ledger_sha256 = $sourceHash
Write-AtomicJson $ledgerPath $next
$finalHash = Get-FileSha256 $ledgerPath

$lineage = Get-Content -Raw -LiteralPath $lineagePath | ConvertFrom-Json -Depth 100
if ($lineage.schema -cne 'wp5-ledger-lineage-v1') { Fail 'lineage schema' }
$oldFinal = $lineage.anchors.loop29
if ($oldFinal.sha256 -cne $sourceHash -or $oldFinal.path -cne 'claim-ledger.json') { Fail 'lineage intermediate binding' }
$oldMigration = $lineage.migrations.loop29
$anchors = [ordered]@{}
foreach ($name in @('loop27','loop28','loop29-reanchor')) { $anchors[$name] = $lineage.anchors.$name }
$anchors['loop29-intermediate'] = [ordered]@{ path='claim-ledger.loop29-intermediate-anchor.json'; sha256=$sourceHash; active_count=372; tombstone_count=676 }
$anchors['loop29'] = [ordered]@{ path='claim-ledger.json'; sha256=$finalHash; active_count=@($next.entries).Count; tombstone_count=@($next.tombstones).Count }
$migrations = [ordered]@{}
$migrations['loop28'] = $lineage.migrations.loop28
$migrations['loop29-intermediate'] = [ordered]@{ from='loop29-reanchor'; to='loop29-intermediate'; path=$oldMigration.path; sha256=$oldMigration.sha256; replacements=$oldMigration.replacements; tombstones=$oldMigration.tombstones }
$migrations['loop29'] = [ordered]@{ from='loop29-intermediate'; to='loop29'; path='claim-ledger.loop29.final-migration.json'; sha256=(Get-FileSha256 $migrationPath); replacements=$uniqueMoves; tombstones=$tombstones }
Write-AtomicJson $lineagePath ([ordered]@{ schema='wp5-ledger-lineage-v1'; anchors=$anchors; migrations=$migrations })
Write-Output "PASS intermediate=$sourceHash final=$finalHash active=$(@($next.entries).Count) tombstones=$(@($next.tombstones).Count) replacements=$uniqueMoves"
