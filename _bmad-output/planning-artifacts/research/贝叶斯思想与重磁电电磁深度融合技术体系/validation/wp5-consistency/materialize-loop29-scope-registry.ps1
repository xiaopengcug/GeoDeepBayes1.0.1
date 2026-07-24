[CmdletBinding()]
param(
    [string]$RegistryPath = (Join-Path $PSScriptRoot 'scope-registry.json'),
    [string]$LedgerPath = (Join-Path $PSScriptRoot 'claim-ledger.json')
)

$ErrorActionPreference = 'Stop'
$registry = Get-Content -Raw -LiteralPath $RegistryPath | ConvertFrom-Json -Depth 100
$ledger = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json -Depth 100
$used = @($ledger.entries.scope | Where-Object { $_ -match '#' } | Sort-Object -Unique)
$nextScopes = [ordered]@{}
foreach ($name in $used) {
    $entry = $registry.scopes.PSObject.Properties[$name]
    if ($null -eq $entry) { throw "WP5 loop29 scope missing: $name" }
    if ($entry.Value.scope_type -ne 'citation') {
        $users = @($ledger.entries | Where-Object { $_.scope -ceq $name })
        if ($users.Count -eq 0) { throw "WP5 loop29 scope has no user: $name" }
        $doc = [string]$users[0].document
        if (@($users.document | Sort-Object -Unique).Count -ne 1) { throw "WP5 loop29 scope multi-document: $name" }
        $lines = @(Get-Content -LiteralPath (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) $doc))
        $start = [int](($users | Measure-Object -Property span_start -Minimum).Minimum)
        $heading = $null
        for ($i = [Math]::Min($start - 1, $lines.Count - 1); $i -ge 0; $i--) {
            if ($lines[$i] -match '^#{1,6}\s+\S') { $heading = $i + 1; break }
        }
        if ($null -eq $heading) { $heading = 1 }
        $entry.Value.source = "$doc#L$heading"
    }
    $nextScopes[$name] = $entry.Value
}
$next = [ordered]@{ schema = 'wp5-scope-registry-v1'; scopes = $nextScopes }
[IO.File]::WriteAllText($RegistryPath, (($next | ConvertTo-Json -Depth 16) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "PASS scopes=$($used.Count)"
