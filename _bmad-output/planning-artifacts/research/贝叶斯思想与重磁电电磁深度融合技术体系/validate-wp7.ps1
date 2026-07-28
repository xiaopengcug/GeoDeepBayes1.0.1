param(
    [Parameter(Mandatory=$true)][string]$SyntheticRun,
    [Parameter(Mandatory=$true)][string]$Do27Run,
    [Parameter(Mandatory=$true)][string]$Signoff,
    [switch]$SelfTest
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$validator = Join-Path $PSScriptRoot 'validation\wp7\validate_wp7.py'
$arguments = @('--synthetic-run', $SyntheticRun, '--do27-run', $Do27Run, '--signoff', $Signoff)
if ($SelfTest) { $arguments += '--self-test' }
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$uvExecutable = if ($uvCommand) { $uvCommand.Source } else { (Get-Command python -ErrorAction Stop).Source }
$uvPrefix = if ($uvCommand) { @() } else { @('-m', 'uv') }
if (-not $uvCommand) {
    $null = & $uvExecutable @uvPrefix --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw '未找到固定环境工具 uv（PATH 或 python -m uv）' }
}
& $uvExecutable @uvPrefix run --project $ProjectRoot --frozen python $validator @arguments
if ($LASTEXITCODE -ne 0) { throw 'WP7验证门失败' }
Write-Output "PASS WP7 self_test=$SelfTest"
