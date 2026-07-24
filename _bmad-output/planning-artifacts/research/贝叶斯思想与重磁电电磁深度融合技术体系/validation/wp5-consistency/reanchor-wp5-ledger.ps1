[CmdletBinding()]
param(
    [string]$LedgerPath = (Join-Path $PSScriptRoot 'claim-ledger.json'),
    [string]$OutputPath = (Join-Path $PSScriptRoot 'claim-ledger.candidate.json'),
    [string]$UnresolvedPath = (Join-Path $PSScriptRoot 'claim-ledger.unresolved.json'),
    [string]$MigrationPath = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Get-NormalizedSha256([string]$Text) {
    $normalized = ($Text.Trim() -replace '\s+', ' ')
    [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($normalized))).ToLowerInvariant()
}

function Write-AtomicUtf8Json([string]$Path, $Object) {
    $directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force $directory | Out-Null
    $temporary = Join-Path $directory ('.' + [IO.Path]::GetFileName($Path) + '.tmp-' + [guid]::NewGuid().ToString('N'))
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Object | ConvertTo-Json -Depth 32) + "`n")
        $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } finally {
        if (Test-Path $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

if (-not (Test-Path -LiteralPath $LedgerPath)) { throw "ledger not found: $LedgerPath" }
$ledger = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json
$candidate = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json
$migrationById = @{}
$activeIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($entry in @($ledger.entries)) {
    if (-not $activeIds.Add([string]$entry.id)) { throw "ledger duplicate active id: $($entry.id)" }
    if ($null -eq $entry.span_start -or $null -eq $entry.span_end -or [int]$entry.span_start -lt 1 -or [int]$entry.span_end -lt [int]$entry.span_start) {
        throw "ledger invalid active span: $($entry.id)"
    }
}
if ($MigrationPath) {
    if (-not (Test-Path -LiteralPath $MigrationPath)) { throw "migration not found: $MigrationPath" }
    $migration = Get-Content -Raw -LiteralPath $MigrationPath | ConvertFrom-Json
    if ($migration.schema -cne 'wp5-ledger-reanchor-migration-v1') { throw 'migration schema' }
    foreach ($item in @($migration.entries)) {
        $fields = @($item.PSObject.Properties.Name | Sort-Object)
        $expected = @('document','id','new_span_end','new_span_start','old_span_end','old_span_start','reason' | Sort-Object)
        if (Compare-Object $fields $expected) { throw 'migration exact fields' }
        if ($migrationById.ContainsKey($item.id)) { throw 'migration duplicate id' }
        if (-not $activeIds.Contains([string]$item.id)) { throw "migration inactive id: $($item.id)" }
        $migrationById[$item.id] = $item
    }
}
$lineHashesByDocument = @{}

foreach ($document in @($ledger.entries.document | Sort-Object -Unique)) {
    $path = Join-Path $root $document
    if (-not (Test-Path -LiteralPath $path)) { throw "document not found: $document" }
    $lines = @(Get-Content -LiteralPath $path)
    $index = @{}
    for ($lineNumber = 1; $lineNumber -le $lines.Count; $lineNumber++) {
        $hash = Get-NormalizedSha256 $lines[$lineNumber - 1]
        if (-not $index.ContainsKey($hash)) { $index[$hash] = [System.Collections.Generic.List[int]]::new() }
        $index[$hash].Add($lineNumber)
    }
    $lineHashesByDocument[$document] = $index
}

$unresolved = [System.Collections.Generic.List[object]]::new()
$updated = 0
foreach ($entry in $candidate.entries) {
    $matchValue = $lineHashesByDocument[$entry.document][$entry.text_sha256]
    $matches = if ($null -eq $matchValue) { @() } else { @($matchValue.ToArray()) }
    if ($matches.Count -eq 1) {
        if ($entry.span_start -ne $matches[0] -or $entry.span_end -ne $matches[0]) {
            $entry.span_start = $matches[0]
            $entry.span_end = $matches[0]
            $updated++
        }
    } else {
        $mapped = $migrationById[$entry.id]
        $canUseMap = $null -ne $mapped -and
            $mapped.document -ceq $entry.document -and
            $mapped.old_span_start -eq $entry.span_start -and
            $mapped.old_span_end -eq $entry.span_end -and
            $mapped.reason -ceq 'unchanged original span hashes exactly' -and
            $mapped.new_span_start -eq $entry.span_start -and
            $mapped.new_span_end -eq $entry.span_end -and
            $entry.span_start -eq $entry.span_end
        if ($canUseMap) {
            $originalLines = @(Get-Content -LiteralPath (Join-Path $root $entry.document))
            if ($entry.span_start -le $originalLines.Count) {
                $originalHash = Get-NormalizedSha256 $originalLines[$entry.span_start - 1]
                $canUseMap = $originalHash -ceq $entry.text_sha256
            } else {
                $canUseMap = $false
            }
        }
        if ($canUseMap) { continue }
        $unresolved.Add([ordered]@{
            id = $entry.id
            kind = $entry.kind
            document = $entry.document
            claim_type = $entry.claim_type
            original_span_start = $entry.span_start
            original_span_end = $entry.span_end
            match_count = $matches.Count
            candidate_lines = @($matches)
        })
    }
}

foreach ($entry in $candidate.entries) {
    if ($null -eq $entry.span_start -or $null -eq $entry.span_end -or [int]$entry.span_start -lt 1 -or [int]$entry.span_end -lt [int]$entry.span_start) {
        throw "candidate invalid active span: $($entry.id)"
    }
}

$report = [ordered]@{
    schema = 'wp5-ledger-reanchor-report-v1'
    input_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $LedgerPath).Hash.ToLowerInvariant()
    migration_sha256 = if ($MigrationPath) { (Get-FileHash -Algorithm SHA256 -LiteralPath $MigrationPath).Hash.ToLowerInvariant() } else { $null }
    candidate_sha256 = $null
    entry_count = @($candidate.entries).Count
    updated_unique_single_line_entries = $updated
    unresolved_count = $unresolved.Count
    policy = 'Only a unique current single-line SHA-256 match may move span_start/span_end; all other records remain unchanged in candidate and are reported.'
    unresolved = @($unresolved)
}
Write-AtomicUtf8Json $OutputPath $candidate
$report.candidate_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath).Hash.ToLowerInvariant()
Write-AtomicUtf8Json $UnresolvedPath $report
Write-Output "candidate=$OutputPath entries=$($report.entry_count) updated=$updated unresolved=$($unresolved.Count) input_sha256=$($report.input_sha256) candidate_sha256=$($report.candidate_sha256)"
if ($unresolved.Count -gt 0) { exit 2 }
