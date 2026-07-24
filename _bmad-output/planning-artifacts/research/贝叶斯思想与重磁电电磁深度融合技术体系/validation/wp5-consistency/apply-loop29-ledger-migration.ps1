[CmdletBinding()]
param(
    [string]$LedgerPath = (Join-Path $PSScriptRoot 'claim-ledger.json'),
    [string]$MigrationPath = (Join-Path $PSScriptRoot 'claim-ledger.loop29.text-migration.json')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
function Fail([string]$Message) { throw "WP5 loop29 migration failed: $Message" }
function Get-NormalizedSha256([string]$Text) {
    $normalized = ($Text.Trim() -replace '\s+', ' ')
    [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($normalized))).ToLowerInvariant()
}
function ExactNames($Object, [string[]]$Expected, [string]$Label) {
    $actual = @($Object.PSObject.Properties.Name | Sort-Object)
    if (Compare-Object $actual @($Expected | Sort-Object)) { Fail "$Label exact schema" }
}
function OldMatches($Entry, $Old, [string]$Label) {
    ExactNames $Old @('id','old_text_sha256','document','span_start','span_end') "$Label old"
    if ($Entry.id -cne $Old.id -or $Entry.text_sha256 -cne $Old.old_text_sha256 -or $Entry.document -cne $Old.document -or $Entry.span_start -ne $Old.span_start -or $Entry.span_end -ne $Old.span_end) { Fail "$Label old binding" }
}
function Write-AtomicJson([string]$Path, $Object) {
    $tmp = $Path + '.tmp-' + [guid]::NewGuid().ToString('N')
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Object | ConvertTo-Json -Depth 32) + "`n")
        $stream = [IO.File]::Open($tmp, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        Move-Item -LiteralPath $tmp -Destination $Path -Force
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    }
}

if (-not (Test-Path -LiteralPath $LedgerPath) -or -not (Test-Path -LiteralPath $MigrationPath)) { Fail 'input missing' }
$ledgerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $LedgerPath).Hash.ToLowerInvariant()
$ledger = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json -Depth 100
$migration = Get-Content -Raw -LiteralPath $MigrationPath | ConvertFrom-Json -Depth 100
ExactNames $migration @('schema','source_ledger_sha256','replacements','tombstones','entries') 'migration'
if ($migration.schema -cne 'wp5-ledger-text-migration-v1' -or $migration.source_ledger_sha256 -cne $ledgerHash) { Fail 'source ledger binding' }
if (@($migration.entries).Count -ne 46 -or [int]$migration.replacements -ne 19 -or [int]$migration.tombstones -ne 27) { Fail 'migration cardinality' }
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$tombIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($t in @($ledger.tombstones)) { [void]$tombIds.Add([string]$t.id) }
foreach ($m in @($migration.entries)) {
    ExactNames $m $(if ($m.disposition -ceq 'replacement') { @('id','disposition','old','new_entry','reason') } else { @('id','disposition','old','reason') }) "migration $($m.id)"
    if (-not $seen.Add([string]$m.id) -or $m.disposition -notin @('replacement','tombstone') -or [string]::IsNullOrWhiteSpace($m.reason)) { Fail "migration entry $($m.id)" }
    $current = @($ledger.entries | Where-Object { $_.id -ceq $m.id })
    if ($current.Count -ne 1) { Fail "migration active id $($m.id)" }
    OldMatches $current[0] $m.old "migration $($m.id)"
    if ($m.disposition -ceq 'tombstone') {
        if ($m.reason -cne 'removed' -or $tombIds.Contains([string]$m.id)) { Fail "migration tombstone $($m.id)" }
        continue
    }
    $new = $m.new_entry
    $expectedNames = @($current[0].PSObject.Properties.Name)
    ExactNames $new $expectedNames "migration replacement $($m.id)"
    if ($new.id -cne $m.id -or $new.document -cne $current[0].document -or $new.kind -cne $current[0].kind) { Fail "migration replacement identity $($m.id)" }
    foreach ($property in $expectedNames) {
        if ($property -in @('text_sha256','span_start','span_end')) { continue }
        $left = $current[0].$property | ConvertTo-Json -Depth 20 -Compress
        $right = $new.$property | ConvertTo-Json -Depth 20 -Compress
        if ($left -cne $right) { Fail "migration replacement field $($m.id)/$property" }
    }
    $lines = @(Get-Content -LiteralPath (Join-Path $root $new.document))
    if ($null -eq $new.span_start -or $null -eq $new.span_end -or [int]$new.span_start -lt 1 -or [int]$new.span_end -lt [int]$new.span_start -or [int]$new.span_end -gt $lines.Count) { Fail "migration replacement span $($m.id)" }
    $actualHash = Get-NormalizedSha256 ($lines[([int]$new.span_start - 1)..([int]$new.span_end - 1)] -join "`n")
    if ($actualHash -cne $new.text_sha256) { Fail "migration replacement hash $($m.id)" }
}
if (@($migration.entries | Where-Object { $_.disposition -ceq 'replacement' }).Count -ne [int]$migration.replacements -or @($migration.entries | Where-Object { $_.disposition -ceq 'tombstone' }).Count -ne [int]$migration.tombstones) { Fail 'migration disposition counts' }

$next = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json -Depth 100
foreach ($m in @($migration.entries | Where-Object { $_.disposition -ceq 'replacement' })) {
    $target = @($next.entries | Where-Object { $_.id -ceq $m.id })
    if ($target.Count -ne 1) { Fail "apply replacement $($m.id)" }
    $index = [array]::IndexOf(@($next.entries), $target[0])
    $next.entries[$index] = $m.new_entry
}
foreach ($m in @($migration.entries | Where-Object { $_.disposition -ceq 'tombstone' })) {
    $next.entries = @($next.entries | Where-Object { $_.id -cne $m.id })
    $next.tombstones = @($next.tombstones) + @([pscustomobject][ordered]@{ id=$m.old.id; old_text_sha256=$m.old.old_text_sha256; document=$m.old.document; span_start=$m.old.span_start; span_end=$m.old.span_end })
}
foreach ($name in @($next.counts.PSObject.Properties.Name)) {
    $records = @($next.entries | Where-Object { $_.document -ceq $name })
    $next.counts.$name.claims = @($records | Where-Object { $_.kind -ceq 'claim' }).Count
    $next.counts.$name.code_blocks = @($records | Where-Object { $_.kind -ceq 'code' }).Count
}
if (@($next.entries).Count -ne 372 -or @($next.tombstones).Count -ne 676 -or (@($next.entries).Count + @($next.tombstones).Count) -ne 1048) { Fail 'output cardinality' }
foreach ($entry in @($next.entries)) { if ($null -eq $entry.span_start -or $null -eq $entry.span_end -or [int]$entry.span_start -lt 1 -or [int]$entry.span_end -lt [int]$entry.span_start) { Fail "output empty span $($entry.id)" } }
$next.previous_ledger_sha256 = $ledgerHash
Write-AtomicJson $LedgerPath $next
Write-Output "PASS active=$(@($next.entries).Count) tombstones=$(@($next.tombstones).Count)"
