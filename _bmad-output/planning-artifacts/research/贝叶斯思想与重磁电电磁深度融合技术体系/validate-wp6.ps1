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

Push-Location $ProjectRoot
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error '未找到固定环境工具uv'
    }
    & uv lock --check
    if ($LASTEXITCODE -ne 0) { throw 'uv.lock与pyproject.toml不一致' }

    & uv run --frozen python $Validator @argsList
    if ($LASTEXITCODE -ne 0) { throw 'WP6治理门失败' }

    if (-not $SkipTests) {
        & uv run --frozen pytest -q
        if ($LASTEXITCODE -ne 0) { throw '单元测试失败' }
    }
    Write-Output "PASS WP6 self_test=$SelfTest release=$Release"
} finally {
    Pop-Location
}
