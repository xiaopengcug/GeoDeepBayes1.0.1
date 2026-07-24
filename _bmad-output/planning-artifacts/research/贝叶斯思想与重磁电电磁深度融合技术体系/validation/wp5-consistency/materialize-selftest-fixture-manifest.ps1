[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$stages = [ordered]@{
    'upstream-lineage' = 33
    'allowlist' = 9
    'registry' = 10
    'language-structure-boundary' = 31
    'publish' = 16
    'signoff' = 19
    'lineage-migration' = 113
}
$fixtures = [Collections.Generic.List[object]]::new()
foreach ($pair in $stages.GetEnumerator()) {
    $prefix = ($pair.Key -replace '[^A-Za-z0-9]', '-').ToUpperInvariant()
    for ($ordinal = 1; $ordinal -le [int]$pair.Value; $ordinal++) {
        $fixtures.Add([ordered]@{
            id = ('FXT-{0}-{1:D3}' -f $prefix, $ordinal)
            stage = $pair.Key
        })
    }
}
if ($fixtures.Count -ne 231 -or @($fixtures.id | Sort-Object -Unique).Count -ne 231) { throw 'Fixture manifest identity violation.' }
$payload = [ordered]@{
    schema = 'wp5-selftest-fixture-manifest-v1'
    fixtures = @($fixtures)
}
$path = Join-Path $PSScriptRoot 'selftest-fixture-manifest.json'
[IO.File]::WriteAllText($path, (($payload | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
Write-Output "PASS fixtures=$($fixtures.Count) stages=$($stages.Count) path=$path"
