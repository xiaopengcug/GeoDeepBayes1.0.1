[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $here)
$ledgerPath = Join-Path $here 'claim-ledger.json'
$scopePath = Join-Path $here 'scope-registry.json'
$ledger = Get-Content -Raw -LiteralPath $ledgerPath | ConvertFrom-Json -Depth 100
$registry = Get-Content -Raw -LiteralPath $scopePath | ConvertFrom-Json -Depth 100

foreach ($property in @($registry.scopes.PSObject.Properties)) {
    $scopeName = $property.Name
    $scope = $property.Value
    if ($scope.scope_type -eq 'citation') { continue }
    $entries = @($ledger.entries | Where-Object { $_.scope -ceq $scopeName })
    if ($entries.Count -eq 0) { throw "scope is unused: $scopeName" }
    $documents = @($entries.document | Sort-Object -Unique)
    if ($documents.Count -ne 1) { throw "scope spans documents: $scopeName" }
    $document = $documents[0]
    $lines = @(Get-Content -LiteralPath (Join-Path $root $document))
    $anchor = [int](($entries | Measure-Object -Property span_start -Minimum).Minimum)
    $heading = 1
    for ($i = 1; $i -le $anchor; $i++) {
        if ($lines[$i - 1] -cmatch '^#{1,6}\s+\S') { $heading = $i }
    }
    $scope.source = "$document#L$heading"
}

[IO.File]::WriteAllText(
    $scopePath,
    (($registry | ConvertTo-Json -Depth 100) + "`n"),
    [Text.UTF8Encoding]::new($false)
)
Write-Output 'PASS reanchored scope-registry sources'
