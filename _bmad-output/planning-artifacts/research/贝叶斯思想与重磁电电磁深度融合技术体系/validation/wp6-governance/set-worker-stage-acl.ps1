param(
    [Parameter(Mandatory)][string]$VersionsRoot,
    [Parameter(Mandatory)][string]$Stage,
    [Parameter(Mandatory)][string]$WorkerIdentity,
    [Parameter(Mandatory)][string]$SupervisorIdentity,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Windows ACL门只能在Windows执行' }
if ($WorkerIdentity.Equals($SupervisorIdentity, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'worker与supervisor必须使用不同Windows身份'
}
$root = (Resolve-Path -LiteralPath $VersionsRoot).Path
$stagePath = (Resolve-Path -LiteralPath $Stage).Path
if ([IO.Path]::GetDirectoryName($stagePath) -ne $root) { throw 'stage必须是versions根的直属子目录' }
if ([IO.Path]::GetFileName($stagePath) -notmatch '^\.stage-[0-9a-f]{32}$') {
    throw 'stage名称不符合受控格式'
}
if ((Get-Item -LiteralPath $stagePath).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
    throw 'stage不得是reparse point'
}

if (-not $VerifyOnly) {
    $rootAcl = Get-Acl -LiteralPath $root
    $rootAcl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($SupervisorIdentity, 'SYSTEM')) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'
        )
        $rootAcl.AddAccessRule($rule)
    }
    $readRule = [Security.AccessControl.FileSystemAccessRule]::new(
        $WorkerIdentity, 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow'
    )
    $rootAcl.AddAccessRule($readRule)
    Set-Acl -LiteralPath $root -AclObject $rootAcl

    $stageAcl = Get-Acl -LiteralPath $stagePath
    $stageAcl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($SupervisorIdentity, 'SYSTEM')) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'
        )
        $stageAcl.AddAccessRule($rule)
    }
    $workerRule = [Security.AccessControl.FileSystemAccessRule]::new(
        $WorkerIdentity, 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow'
    )
    $stageAcl.AddAccessRule($workerRule)
    Set-Acl -LiteralPath $stagePath -AclObject $stageAcl
}

$effective = Get-Acl -LiteralPath $stagePath
$workerRules = @($effective.Access | Where-Object {
    $_.IdentityReference.Value -eq $WorkerIdentity -and
    $_.AccessControlType -eq 'Allow' -and
    ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::Modify)
})
if ($workerRules.Count -eq 0) { throw 'worker未获得stage Modify权限' }
$rootEffective = Get-Acl -LiteralPath $root
$rootWrite = @($rootEffective.Access | Where-Object {
    $_.IdentityReference.Value -eq $WorkerIdentity -and
    $_.AccessControlType -eq 'Allow' -and
    ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::Write)
})
if ($rootWrite.Count -gt 0) { throw 'worker仍拥有versions根写权限' }
Write-Output "PASS worker=$WorkerIdentity supervisor=$SupervisorIdentity stage=$stagePath"
