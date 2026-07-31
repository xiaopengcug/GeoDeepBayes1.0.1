param(
    [switch]$SelfTest,
    [switch]$Release,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$Validator = Join-Path $PSScriptRoot 'validation\wp6-governance\validate_wp6.py'
$argsList = @()
if ($SelfTest) { $argsList += '--self-test' }
if ($Release) { $argsList += '--release' }
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$uvExecutable = if ($uvCommand) { $uvCommand.Source } else { (Get-Command python -ErrorAction Stop).Source }
$uvPrefix = if ($uvCommand) { @() } else { @('-m', 'uv') }
if (-not $uvCommand) {
    $null = & $uvExecutable @uvPrefix --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw '未找到固定环境工具 uv（PATH 或 python -m uv）' }
}

Push-Location $ProjectRoot
try {
    & $uvExecutable @uvPrefix lock --check
    if ($LASTEXITCODE -ne 0) { throw 'uv.lock与pyproject.toml不一致' }

    & $uvExecutable @uvPrefix run --frozen python $Validator @argsList
    if ($LASTEXITCODE -ne 0) { throw 'WP6治理门失败' }

    if (-not $SkipTests) {
        & $uvExecutable @uvPrefix run --frozen pytest -q
        if ($LASTEXITCODE -ne 0) { throw '单元测试失败' }
    }
    Write-Output "PASS WP6 self_test=$SelfTest release=$Release"
} finally {
    Pop-Location
}
