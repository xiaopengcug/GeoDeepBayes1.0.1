[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $vroot)
$contract = Get-Content -Raw (Join-Path $vroot 'consistency-contract.json') | ConvertFrom-Json -Depth 100
$members = @($contract.documents.PSObject.Properties.Name + '贝叶斯三维反演测试算力需求说明.md' + 'validation/wp5-consistency/consistency-contract.json' + 'validation/wp5-consistency/claim-ledger.json' + 'validation/wp5-consistency/previous-claim-ledger.json' + 'WP5-upstream-allowlist.json' + 'validation/wp5-consistency/scope-registry.json' + 'validation/wp5-consistency/high-risk-classification.json' + 'validation/wp5-consistency/selftest-fixture-manifest.json' + 'validation/wp5-consistency/run-selftest-evidence.ps1' + 'validation/wp5-consistency/finalize-selftest-stage-evidence.ps1' + 'validation/wp5-consistency/publish-wp5-consistency.ps1' + 'validate-wp5.ps1' + 'ACTIVE_MANIFEST')
$rootFile = Join-Path $root 'WP5-consistency-input-root.sha256'
$rootLines = @('# WP5 consistency root v1','') + @($members | ForEach-Object { "$((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $_)).Hash.ToLowerInvariant())  $_" })
[IO.File]::WriteAllText($rootFile, (($rootLines -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
$memberLines = @($rootLines[2..($rootLines.Count - 1)])
$memberRoot = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes(($memberLines -join "`n") + "`n"))).ToLowerInvariant()
$fileRoot = (Get-FileHash -Algorithm SHA256 -LiteralPath $rootFile).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $vroot 'WP5-consistency-root-anchor.sha256'), "$fileRoot`n", [Text.UTF8Encoding]::new($false))
$active = Get-Content -Raw (Join-Path $vroot 'active-output.json') | ConvertFrom-Json -Depth 20
$signoffPath = Join-Path $root 'WP5-主编技术编辑与专项交叉复核独立签核.md'
$signoff = [IO.File]::ReadAllText($signoffPath)
$signoff = [regex]::Replace($signoff, '(?m)^- 输入版本：`.*`\s*$', "- 输入版本：``$($active.run_instance_id)``")
$signoff = [regex]::Replace($signoff, '(?m)^- manifest SHA-256：`.*`\s*$', "- manifest SHA-256：``$($active.manifest_sha256)``")
$signoff = [regex]::Replace($signoff, '(?m)^- 成员清单内容根SHA-256：`.*`\s*$', "- 成员清单内容根SHA-256：``$memberRoot``")
$signoff = [regex]::Replace($signoff, '(?m)^- 根清单文件SHA-256：`.*`\s*$', "- 根清单文件SHA-256：``$fileRoot``")
[IO.File]::WriteAllText($signoffPath, $signoff, [Text.UTF8Encoding]::new($false))
Write-Output "PASS run=$($active.run_instance_id) manifest=$($active.manifest_sha256) member_root=$memberRoot root=$fileRoot"
