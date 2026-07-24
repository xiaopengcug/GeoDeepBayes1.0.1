[CmdletBinding()]
param(
    [string]$LedgerPath = (Join-Path $PSScriptRoot 'claim-ledger.json'),
    [string]$OutputPath = (Join-Path $PSScriptRoot 'claim-ledger.loop28.text-migration.json')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Get-NormalizedSha256([string]$Text) {
    $normalized = ($Text.Trim() -replace '\s+', ' ')
    [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($normalized))).ToLowerInvariant()
}

function Get-ExactOld($entry) {
    [ordered]@{
        id = $entry.id
        old_text_sha256 = $entry.text_sha256
        document = $entry.document
        span_start = $entry.span_start
        span_end = $entry.span_end
    }
}

function Get-FenceEnd([string[]]$Lines, [int]$Start, [string]$Id) {
    if ($Lines[$Start - 1] -notmatch '^```') { throw "replacement code start fence: $Id" }
    for ($line = $Start + 1; $line -le $Lines.Count; $line++) {
        if ($Lines[$line - 1] -cmatch '^```\s*$') { return $line }
    }
    throw "replacement code end fence: $Id"
}

if (-not (Test-Path -LiteralPath $LedgerPath)) { throw "ledger not found: $LedgerPath" }
$ledger = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json -Depth 100
$replaceIds = @(
    'CLM-DOC-02-0006','CLM-DOC-02-0007','CLM-DOC-03-0014','CODE-DOC-03-0001',
    'CODE-DOC-06-0001','CODE-DOC-06-0002','CODE-DOC-06-0003','CODE-DOC-06-0004',
    'CODE-DOC-06-0005','CODE-DOC-06-0006','CODE-DOC-06-0007','CODE-DOC-06-0008',
    'CODE-DOC-06-0009','CODE-DOC-06-0010','CODE-DOC-06-0011','CODE-DOC-06-0012',
    'CLM-COMPUTE-PLAN-0008','CLM-COMPUTE-PLAN-0013','CLM-COMPUTE-PLAN-0014',
    'CLM-COMPUTE-PLAN-0015','CLM-COMPUTE-PLAN-0016','CLM-COMPUTE-PLAN-0017',
    'CLM-COMPUTE-PLAN-0018','CLM-COMPUTE-PLAN-0024','CLM-COMPUTE-PLAN-0028',
    'CLM-COMPUTE-PLAN-0029','CLM-COMPUTE-PLAN-0030','CLM-COMPUTE-PLAN-0031'
)
$tombstoneIds = @(
    'CLM-DOC-02-0003','CLM-DOC-02-0004','CLM-DOC-03-0012','CLM-DOC-03-0046',
    'CLM-DOC-03-0048','CLM-DOC-03-0049','CLM-DOC-03-0050','CLM-DOC-03-0052',
    'CLM-DOC-03-0053','CLM-DOC-03-0054','CLM-DOC-03-0055','CLM-DOC-04-0002',
    'CLM-DOC-04-0005','CLM-DOC-04-0006'
)
$allIds = @($replaceIds + $tombstoneIds)
if (@($allIds | Sort-Object -Unique).Count -ne 42) { throw 'migration exact id count' }
$entries = [Collections.Generic.List[object]]::new()
foreach ($id in $replaceIds) {
    $old = @($ledger.entries | Where-Object { $_.id -ceq $id })
    if ($old.Count -ne 1) { throw "replacement active id: $id" }
    $new = $old[0] | Select-Object *
    $lines = @(Get-Content -LiteralPath (Join-Path $root $new.document))
    if ($new.kind -ceq 'code') {
        $new.span_end = Get-FenceEnd $lines ([int]$new.span_start) $id
        if ($id -ceq 'CODE-DOC-06-0006') {
            $new.symbols = @('electrode_config','homogeneous_model','test_homogeneous_half_space_response','test_jacobian_directional_derivative','test_reciprocity_principle','TestDCForwardSolver')
            $new.tests = @('test_homogeneous_half_space_response','test_jacobian_directional_derivative','test_reciprocity_principle','TestDCForwardSolver')
        }
    }
    if ([int]$new.span_start -lt 1 -or [int]$new.span_end -lt [int]$new.span_start -or [int]$new.span_end -gt $lines.Count) { throw "replacement span: $id" }
    $new.text_sha256 = Get-NormalizedSha256 ($lines[([int]$new.span_start - 1)..([int]$new.span_end - 1)] -join "`n")
    $entries.Add([ordered]@{ id = $id; disposition = 'replacement'; old = Get-ExactOld $old[0]; new_entry = $new; reason = 'current text retains the reviewed claim or interface at the registered location; fields are retained except independently parsed code metadata.' })
}
foreach ($id in $tombstoneIds) {
    $old = @($ledger.entries | Where-Object { $_.id -ceq $id })
    if ($old.Count -ne 1) { throw "tombstone active id: $id" }
    $entries.Add([ordered]@{ id = $id; disposition = 'tombstone'; old = Get-ExactOld $old[0]; reason = 'removed' })
}
$out = [ordered]@{
    schema = 'wp5-ledger-text-migration-v1'
    source_ledger_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $LedgerPath).Hash.ToLowerInvariant()
    replacements = $replaceIds.Count
    tombstones = $tombstoneIds.Count
    entries = @($entries)
}
[IO.File]::WriteAllText($OutputPath, (($out | ConvertTo-Json -Depth 32) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "PASS migration=$OutputPath replacements=$($replaceIds.Count) tombstones=$($tombstoneIds.Count)"
