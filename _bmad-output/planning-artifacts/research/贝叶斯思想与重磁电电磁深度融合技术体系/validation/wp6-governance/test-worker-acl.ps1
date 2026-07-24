$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw '该测试只支持Windows' }

$suffix = [Guid]::NewGuid().ToString('N').Substring(0, 10)
$workerName = "wp6w$suffix"
$passwordPlain = "W!p6-$suffix-Aa1"
$securePassword = ConvertTo-SecureString $passwordPlain -AsPlainText -Force
$credential = [PSCredential]::new("$env:COMPUTERNAME\$workerName", $securePassword)
$testRoot = Join-Path ([IO.Path]::GetTempPath()) "wp6-acl-$suffix"
$versions = Join-Path $testRoot 'versions'
$stage = Join-Path $versions ('.stage-' + [Guid]::NewGuid().ToString('N'))
$supervisor = [Security.Principal.WindowsIdentity]::GetCurrent().Name

try {
    & net user $workerName $passwordPlain /add /y | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '无法创建临时worker身份' }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    & (Join-Path $PSScriptRoot 'set-worker-stage-acl.ps1') `
        -VersionsRoot $versions -Stage $stage `
        -WorkerIdentity "$env:COMPUTERNAME\$workerName" `
        -SupervisorIdentity $supervisor

    $rootProbe = Join-Path $versions 'forbidden.txt'
    $stageProbe = Join-Path $stage 'allowed.txt'
    $rootProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList "/c echo denied>$rootProbe" `
        -Credential $credential -Wait -PassThru -WindowStyle Hidden
    if ($rootProcess.ExitCode -eq 0 -or (Test-Path -LiteralPath $rootProbe)) {
        throw 'worker能够写入versions根'
    }
    $stageProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList "/c echo allowed>$stageProbe" `
        -Credential $credential -Wait -PassThru -WindowStyle Hidden
    if ($stageProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $stageProbe)) {
        throw 'worker无法写入直属stage'
    }
    Write-Output 'PASS Windows distinct-SID ACL isolation'
} finally {
    & net user $workerName /delete 2>$null | Out-Null
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = (Resolve-Path -LiteralPath $testRoot).Path
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw '拒绝清理非临时目录'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
