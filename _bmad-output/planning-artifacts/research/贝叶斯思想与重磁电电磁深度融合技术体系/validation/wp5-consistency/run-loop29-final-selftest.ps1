$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$log = Join-Path $env:TEMP 'wp5-loop29-final-selftest.log'
$exitFile = Join-Path $env:TEMP 'wp5-loop29-final-selftest.exit'
Remove-Item -LiteralPath $log,$exitFile -Force -ErrorAction SilentlyContinue
& (Join-Path $root 'validate-wp5.ps1') -SelfTest *> $log
[IO.File]::WriteAllText($exitFile, [string]$LASTEXITCODE, [Text.UTF8Encoding]::new($false))
