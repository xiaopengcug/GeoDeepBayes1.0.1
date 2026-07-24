[CmdletBinding()]
param(
    [string]$RiskPath = (Join-Path $PSScriptRoot 'high-risk-classification.json'),
    [string]$LedgerPath = (Join-Path $PSScriptRoot 'claim-ledger.json')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$risk = Get-Content -Raw -LiteralPath $RiskPath | ConvertFrom-Json -Depth 100
$ledger = Get-Content -Raw -LiteralPath $LedgerPath | ConvertFrom-Json -Depth 100
$keep = [Collections.Generic.List[object]]::new()
foreach ($rule in @($risk.rules)) {
    $lines = @(Get-Content -LiteralPath (Join-Path $root $rule.document))
    $hits = @()
    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -cmatch $rule.pattern) { $hits += $i + 1 } }
    if ($hits.Count -ne 1) { throw "WP5 loop29 risk match: $($rule.id)" }
    $users = @($ledger.entries | Where-Object { $_.document -ceq $rule.document -and $_.span_start -eq $hits[0] -and $_.claim_type -ceq $rule.claim_type })
    if ($users.Count -eq 1) { $keep.Add($rule) }
    elseif ($users.Count -ne 0) { throw "WP5 loop29 risk multiplicity: $($rule.id)" }
}
$next = [ordered]@{ schema = 'wp5-high-risk-classification-v1'; rules = @($keep) }
[IO.File]::WriteAllText($RiskPath, (($next | ConvertTo-Json -Depth 16) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "PASS rules=$($keep.Count)"
