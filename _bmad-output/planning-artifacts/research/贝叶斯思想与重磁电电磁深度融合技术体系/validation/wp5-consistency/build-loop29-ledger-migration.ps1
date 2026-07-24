[CmdletBinding()]
param(
    [string]$LedgerPath = (Join-Path $PSScriptRoot 'claim-ledger.json'),
    [string]$CandidatePath = (Join-Path $PSScriptRoot 'claim-ledger.loop29.candidate.json'),
    [string]$OutputPath = (Join-Path $PSScriptRoot 'claim-ledger.loop29.text-migration.json')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
function Get-NormalizedSha256([string]$Text) {
    $normalized = ($Text.Trim() -replace '\s+', ' ')
    [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($normalized))).ToLowerInvariant()
}
function Get-Old($entry) { [ordered]@{ id=$entry.id; old_text_sha256=$entry.text_sha256; document=$entry.document; span_start=$entry.span_start; span_end=$entry.span_end } }

$tombstoneIds = @(
    'CLM-DOC-02-0030','CLM-DOC-02-0031','CLM-DOC-02-0032',
    'CLM-DOC-A3-0012','CLM-DOC-A3-0017','CLM-DOC-A3-0021','CLM-DOC-A3-0024','CLM-DOC-A3-0026',
    'CLM-DOC-A3-0041','CLM-DOC-A3-0045','CLM-DOC-A3-0046','CLM-DOC-A3-0050','CLM-DOC-A3-0054',
    'CLM-DOC-A13-0003','CLM-DOC-A13-0005','CLM-DOC-A13-0006','CLM-DOC-A13-0007','CLM-DOC-A13-0008','CLM-DOC-A13-0009','CLM-DOC-A13-0010',
    'CLM-DOC-03-0025','CODE-DOC-03-0001','CLM-DOC-A11-0007','CLM-DOC-A11-0008',
    'CLM-DOC-A11-0032','CLM-DOC-A11-0033','CLM-DOC-A11-0050'
)
$unresolvedPath = Join-Path $PSScriptRoot 'claim-ledger.loop29.unresolved.json'
if (-not (Test-Path -LiteralPath $LedgerPath) -or -not (Test-Path -LiteralPath $CandidatePath) -or -not (Test-Path -LiteralPath $unresolvedPath)) { throw 'loop29 inputs missing' }
$ledger = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json -Depth 100
$candidate = Get-Content -Raw -LiteralPath $CandidatePath | ConvertFrom-Json -Depth 100
$unresolved = Get-Content -Raw -LiteralPath $unresolvedPath | ConvertFrom-Json -Depth 100
$ids = @($unresolved.unresolved.id)
if ($ids.Count -ne 46 -or @($ids | Sort-Object -Unique).Count -ne 46) { throw 'loop29 unresolved identity' }
if (@($tombstoneIds | Sort-Object -Unique).Count -ne 27 -or @($tombstoneIds | Where-Object { $_ -notin $ids }).Count) { throw 'loop29 tombstone identity' }
$entries = [Collections.Generic.List[object]]::new()
foreach ($id in $ids) {
    $old = @($ledger.entries | Where-Object { $_.id -ceq $id })
    if ($old.Count -ne 1) { throw "loop29 active identity: $id" }
    if ($id -in $tombstoneIds) {
        $entries.Add([ordered]@{ id=$id; disposition='tombstone'; old=(Get-Old $old[0]); reason='removed' })
        continue
    }
    $new = @($candidate.entries | Where-Object { $_.id -ceq $id })
    if ($new.Count -ne 1) { throw "loop29 candidate identity: $id" }
    $new = $new[0] | Select-Object *
    $lines = @(Get-Content -LiteralPath (Join-Path $root $new.document))
    if ($new.span_start -lt 1 -or $new.span_end -lt $new.span_start -or $new.span_end -gt $lines.Count) { throw "loop29 span: $id" }
    $hash = Get-NormalizedSha256 ($lines[($new.span_start - 1)..($new.span_end - 1)] -join "`n")
    if ($hash -cne $new.text_sha256) { throw "loop29 replacement requires explicit current span/hash: $id" }
    $entries.Add([ordered]@{ id=$id; disposition='replacement'; old=(Get-Old $old[0]); new_entry=$new; reason='current reviewed text is byte-normalization identical at the registered span; this explicit migration resolves ambiguous duplicate headings or multi-line fences without moving identity.' })
}
$out = [ordered]@{
    schema='wp5-ledger-text-migration-v1'; source_ledger_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $LedgerPath).Hash.ToLowerInvariant();
    replacements=@($entries | Where-Object disposition -ceq 'replacement').Count; tombstones=@($entries | Where-Object disposition -ceq 'tombstone').Count; entries=@($entries)
}
[IO.File]::WriteAllText($OutputPath, (($out | ConvertTo-Json -Depth 32) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "PASS migration=$OutputPath replacements=$($out.replacements) tombstones=$($out.tombstones)"
