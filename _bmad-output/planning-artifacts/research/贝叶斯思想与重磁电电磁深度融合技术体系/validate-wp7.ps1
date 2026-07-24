param(
    [Parameter(Mandatory=$true)][string]$SyntheticRun,
    [Parameter(Mandatory=$true)][string]$Do27Run,
    [Parameter(Mandatory=$true)][string]$Signoff,
    [switch]$SelfTest
)
$ErrorActionPreference = 'Stop'
$validator = Join-Path $PSScriptRoot 'validation\wp7\validate_wp7.py'
$arguments = @('--synthetic-run', $SyntheticRun, '--do27-run', $Do27Run, '--signoff', $Signoff)
if ($SelfTest) { $arguments += '--self-test' }
& uv run --frozen python $validator @arguments
if ($LASTEXITCODE -ne 0) { throw 'WP7验证门失败' }
Write-Output "PASS WP7 self_test=$SelfTest"
