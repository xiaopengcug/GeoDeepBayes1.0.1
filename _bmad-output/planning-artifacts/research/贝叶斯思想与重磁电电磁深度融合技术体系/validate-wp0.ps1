param(
    [switch]$Generate,
    [switch]$Rebaseline,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'
$DocDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DocDir '..\..\..\..')).Path
$Review = Join-Path $DocDir '审查意见03.md'
$FormalEvidence = Join-Path $DocDir 'evidence-status.md'
$Inventory = Join-Path $DocDir '基线冻结03-inventory.csv'
$Hashes = Join-Path $DocDir '基线冻结03.sha256'
$Ledger = Join-Path $DocDir '整改台账03.md'
$ClaimMap = Join-Path $DocDir '主张-证据映射03.md'
$ClaimScan = Join-Path $DocDir '主张扫描03.csv'
$EvidenceDraft = Join-Path $DocDir 'evidence-status-03草案.md'
$TrustedFormalEvidenceSha256 = 'ddcc51f3251428ecd5cce990bf46655e543cb0d65d42dba829f746157e2b38da'

function Read-Utf8Lines([string]$Path) {
    [IO.File]::ReadAllLines($Path, [Text.Encoding]::UTF8)
}

function Read-Utf8Raw([string]$Path) {
    [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
}

function Relative-Path([string]$Path) {
    [IO.Path]::GetRelativePath($ProjectRoot, $Path).Replace('\', '/')
}

function Get-MandatoryTopFiles {
    $manifest = Join-Path $DocDir 'manifest.yaml'
    $required = @($manifest, (Join-Path $DocDir 'evidence-status.md'), (Join-Path $DocDir 'validate-governance.ps1'), (Join-Path $DocDir 'cited_refs.txt'))
    $inReleasePaths = $false
    foreach ($line in Read-Utf8Lines $manifest) {
        if ($line -match '^release_paths:\s*$') { $inReleasePaths = $true; continue }
        if ($inReleasePaths -and $line -match '^[A-Za-z_].*:\s*$') { break }
        if ($inReleasePaths -and $line -match '^\s*-\s*"([^"]+)"') { $required += Join-Path $DocDir $Matches[1] }
    }
    $required | Sort-Object -Unique
}

function Get-FreezeFiles {
    $items = [System.Collections.Generic.List[System.IO.FileInfo]]::new()
    foreach ($path in Get-MandatoryTopFiles) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $item = Get-Item -LiteralPath $path
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point rejected: $path" }
            $items.Add($item)
    }
    }
    foreach ($scope in @(
        @{ Path = (Join-Path $ProjectRoot 'src'); Ext = @('.py') },
        @{ Path = (Join-Path $ProjectRoot 'tests'); Ext = @('.py') },
        @{ Path = (Join-Path $DocDir 'contracts'); Ext = @('.json', '.py') },
        @{ Path = (Join-Path $DocDir 'validation\runs'); Ext = @() }
    )) {
        if (-not (Test-Path -LiteralPath $scope.Path)) { throw "Missing approved scope: $($scope.Path)" }
        Get-ChildItem -LiteralPath $scope.Path -Recurse -File |
            Where-Object { $scope.Ext.Count -eq 0 -or $_.Extension -in $scope.Ext } |
            ForEach-Object {
                if ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point rejected: $($_.FullName)" }
                $items.Add($_)
            }
    }
    $items | Sort-Object FullName -Unique
}

function Get-Category([string]$Relative) {
    if ($Relative -match '/0[0-7]-') { return 'main-text' }
    if ($Relative -match '/附录') { return 'appendix' }
    if ($Relative -match '/validation/runs/') { return 'run-package' }
    if ($Relative -match '/contracts/') { return 'contract' }
    if ($Relative -like 'src/*') { return 'source' }
    if ($Relative -like 'tests/*') { return 'test' }
    return 'governance-reference'
}

function Get-ReviewFindings {
    $lines = Read-Utf8Lines $Review
    $section = ''
    $sectionOrdinal = 0
    $ordinal = 0
    $rows = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^###\s+(.+)$') { $section = $Matches[1]; $sectionOrdinal++; $ordinal = 0; continue }
        if ($lines[$i] -match '^\d+\.\s+\*\*(P[01])｜(.+?)。\*\*\s*(.*)$') {
            $ordinal++
            $level = $Matches[1]
            $summary = $Matches[2].Trim()
            $body = $Matches[3]
            $anchors = ([regex]::Matches($body, '`([^`]+)`') | ForEach-Object { $_.Groups[1].Value }) -join '；'
            if ([string]::IsNullOrWhiteSpace($anchors)) { $anchors = "审查意见03.md:$($i + 1)" }
            $role = if ($summary -match 'TEM|CSAMT|WFEM|物性|深度|噪声|MT|化极|电阻率|异常阈值|分辨率') {
                '地球物理/岩石物理'
            } elseif ($summary -match '概率|似然|先验|PPC|覆盖|不确定性|资源量|ENPV|风险') {
                '贝叶斯/UQ/决策'
            } elseif ($summary -match 'POD|RJMCMC|KL|信息增益|复杂度|条件数|诊断|离散化') {
                '算法与数值推断'
            } elseif ($summary -match 'CI|代码|工程|TRL|日志|证据|性能表|Planned') {
                '工程架构/证据治理'
            } else { '主编/专项负责人' }
            $keyMaterial = "$level|$summary|$anchors"
            $stableDigest = [Convert]::ToHexString(
                [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($keyMaterial))
            ).ToLower().Substring(0, 12)
            $rows += [pscustomobject]@{
                SourceFindingId = "R03-F-$stableDigest"
                Level = $level
                Section = $section
                SourceLine = $i + 1
                Anchors = $anchors
                Summary = $summary
                OwnerRole = $role
                Status = 'Open'
                PlannedEvidence = 'null (由对应WP生成)'
                Verifier = '对应专项独立复审人'
                SplitBasis = 'not-split'
            }
        }
    }
    $rows
}

$ClaimPatterns = [ordered]@{
    THEORY_SELF_CONSISTENT = '理论框架自洽|框架已自洽|理论.{0,6}已自洽'
    FIVE_METHODS = '支持\s*[五5]\s*种方法联合|五方法联合|五类.{0,6}联合|具备.{0,8}五法联合|全方法.{0,8}(已实现|支持|闭环)'
    GPU_IMPLEMENTED = 'GPU.{0,12}(已实现|实现完成|并行完成)|已实现.{0,12}GPU'
    FULL_APPLICATION = '可全面应用'
    MINEABLE_RESOURCE = '可采资源量'
    WEEK_TO_HOUR = '周级.{0,10}小时级'
    ORDERS_SPEEDUP = '[1１]\s*[-—–至到]\s*[3３]\s*个?数量级|orders?\s+of\s+magnitude|\d+(\.\d+)?\s*[×xX倍]\s*(加速|提升)'
    SOLVED_PAIN = '解决了?.{0,12}(痛点|问题)'
}

function Get-ReleaseDocs {
    Get-MandatoryTopFiles |
        Where-Object { $_ -like '*.md' -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        ForEach-Object { Get-Item -LiteralPath $_ } |
        Sort-Object Name
}

function Get-ClaimHits {
    $hits = @()
    foreach ($file in Get-ReleaseDocs) {
        $lines = Read-Utf8Lines $file.FullName
        for ($i = 0; $i -lt $lines.Count; $i++) {
            foreach ($entry in $ClaimPatterns.GetEnumerator()) {
                if ($lines[$i] -match $entry.Value) {
                    $hits += [pscustomobject]@{
                        PatternId = $entry.Key
                        Path = Relative-Path $file.FullName
                        Line = $i + 1
                        TextSha256 = [Convert]::ToHexString(
                            [Security.Cryptography.SHA256]::HashData(
                                [Text.Encoding]::UTF8.GetBytes($lines[$i])
                            )
                        ).ToLower()
                        Disposition = 'WP5_DIRECT_DOWNGRADE'
                        EvidenceId = 'none'
                    }
                }
            }
            if ($lines[$i] -match '(?i)\bObserved\b|实测|观测值|已验证|已通过') {
                $hits += [pscustomobject]@{
                    PatternId = 'OBSERVED_FIELD'
                    Path = Relative-Path $file.FullName
                    Line = $i + 1
                    TextSha256 = [Convert]::ToHexString(
                        [Security.Cryptography.SHA256]::HashData(
                            [Text.Encoding]::UTF8.GetBytes($lines[$i])
                        )
                    ).ToLower()
                    Disposition = 'WP5_VERIFY_PLANNED_EMPTY'
                    EvidenceId = 'none'
                }
            }
        }
    }
    $hits | Sort-Object Path, Line, PatternId
}

function Get-EvidenceIds([string]$Path) {
    $ids = @()
    foreach ($line in Read-Utf8Lines $Path) {
        if ($line -match '^\|\s*(EVD-[A-Z0-9-]+)\s*\|') { $ids += $Matches[1] }
    }
    $ids | Sort-Object -Unique
}

function Write-Utf8([string]$Path, [string]$Content) {
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

if ($Generate) {
    if ((Test-Path -LiteralPath $Inventory) -and -not $Rebaseline) {
        throw 'Baseline already exists. Verification never overwrites it; use -Rebaseline only with explicit human authorization.'
    }
    $freezeTime = (Get-Date).ToUniversalTime().ToString('o')
    $inventoryRows = @()
    foreach ($missing in Get-MandatoryTopFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }) {
        $inventoryRows += [pscustomobject]@{
            path = Relative-Path $missing
            category = 'mandatory'
            size_bytes = ''
            frozen_at_utc = $freezeTime
            status = 'missing'
            sha256 = ''
            reason = 'required by manifest/release governance'
        }
    }
    foreach ($file in Get-FreezeFiles) {
        $rel = Relative-Path $file.FullName
        $before = Get-Item -LiteralPath $file.FullName
        $digest = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()
        $after = Get-Item -LiteralPath $file.FullName
        if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc -ne $after.LastWriteTimeUtc) {
            throw "File changed while freezing: $rel"
        }
        $inventoryRows += [pscustomobject]@{
            path = $rel
            category = Get-Category $rel
            size_bytes = $after.Length
            frozen_at_utc = $freezeTime
            status = 'present'
            sha256 = $digest
            reason = ''
        }
    }
    foreach ($policy in @(
        @{path='policy:archive/**';reason='archived versions excluded'},
        @{path='policy:validation/do27/source/**';reason='vendored upstream source excluded'},
        @{path='policy:validation/do27/work/**';reason='reproducible work directories excluded'},
        @{path='policy:**/__pycache__/**';reason='generated cache excluded'}
    )) {
        $inventoryRows += [pscustomobject]@{
            path=$policy.path;category='exclusion-policy';size_bytes='';frozen_at_utc=$freezeTime;
            status='excluded';sha256='';reason=$policy.reason
        }
    }
    $inventoryRows | Export-Csv -LiteralPath $Inventory -NoTypeInformation -Encoding utf8
    Write-Utf8 $Hashes (($inventoryRows | Where-Object status -eq 'present' | ForEach-Object { "$($_.sha256)  $($_.path)" }) -join "`n")

    $findings = Get-ReviewFindings
    $ledgerText = @"
# 《审查意见03》整改台账

生成时间（UTC）：$freezeTime  
状态：WP0治理基线；所有问题初始为`Open`。  
来源规则：每行由《审查意见03》中显式编号且标注P0/P1的发现生成；`SourceFindingId`是稳定源主键，不以台账行数替代覆盖核验。

| ID | SourceFindingId | 拆分依据 | 等级 | 审查章节 | 原文行 | 原定位 | 问题摘要 | 责任角色 | 状态 | 计划证据路径 | 验证角色 |
|---|---|---|---|---|---:|---|---|---|---|---|---|
"@
    $idx = 0
    foreach ($row in $findings) {
        $idx++
        $ledgerText += "`n| R03-$('{0:D4}' -f $idx) | $($row.SourceFindingId) | $($row.SplitBasis) | $($row.Level) | $($row.Section) | $($row.SourceLine) | $($row.Anchors.Replace('|','/')) | $($row.Summary.Replace('|','/')) | $($row.OwnerRole) | $($row.Status) | $($row.PlannedEvidence) | $($row.Verifier) |"
    }
    $ledgerText += "`n`n总数：$($findings.Count)；P0：$(($findings | Where-Object Level -eq 'P0').Count)；P1：$(($findings | Where-Object Level -eq 'P1').Count)。`n"
    Write-Utf8 $Ledger $ledgerText

    $hits = Get-ClaimHits
    $hits | Export-Csv -LiteralPath $ClaimScan -NoTypeInformation -Encoding utf8
    $formalIds = Get-EvidenceIds $FormalEvidence
    $mapText = @"
# 主张—证据映射03

状态：WP0治理基线；正文实际降级由WP5执行。  
扫描时间（UTC）：$freezeTime  
结构化全量命中：`主张扫描03.csv`（$($hits.Count)行）。

## 证据等级边界

- `Hypothesis`：只允许候选机制和待检验假设。
- `Planned`：只允许计划、目标和预注册协议。
- `Open-data-run`：只允许数据摄取、完整性和格式质量。
- `Synthetic-run`：只允许指定代码、配置和合成任务内的检查。
- `Field-validated`：只允许指定矿区与留出设计内的现场结果。
- `Failed/Blocked`：只允许失败边界或阻塞事实。

## 正式Evidence ID对账

| Evidence ID | WP0审计状态 | 当前允许范围 | 禁止外推 |
|---|---|---|---|
"@
    foreach ($id in $formalIds) {
        $audit = if ($id -in @('EVD-SYNTH-001','EVD-ALGO-002')) { 'DISPUTED_PENDING_WP7' } else { 'REGISTERED_NOT_UPGRADED' }
        $allow = switch ($id) {
            'EVD-OPEN-001' { '公开数据摄取/完整性/格式' }
            'EVD-SYNTH-001' { 'DO-27降阶双单物理兼容运行事实；不允许对外成果主张直至WP7复核' }
            'EVD-ALGO-002' { '小型重磁算子与诊断单测事实；不允许全维/联合外推' }
            default { '保持正式登记中的Hypothesis/Planned边界' }
        }
        $forbid = if ($id -eq 'EVD-OPEN-001') { '反演精度、现场有效' } elseif ($id -in @('EVD-SYNTH-001','EVD-ALGO-002')) { 'PGI、联合、DC/EM、现场、全尺度、性能承诺' } else { '已验证、已达标或更高证据等级' }
        $mapText += "`n| $id | $audit | $allow | $forbid |"
    }
    $mapText += @"

## 禁用/降级主张

| Pattern ID | 处置 | 恢复条件 |
|---|---|---|
| THEORY_SELF_CONSISTENT | WP5改为“理论草案，P0整改中” | 全部P0四专项复审通过 |
| FIVE_METHODS | WP5改为“设计目标” | 五方法可执行联合证据 |
| GPU_IMPLEMENTED | WP5改为Planned | GPU代码、测试与基准 |
| FULL_APPLICATION | WP5改为“待验证应用” | 多矿区现场留出 |
| MINEABLE_RESOURCE | WP5删除或改条件情景 | 合规资源模型与签署 |
| WEEK_TO_HOUR / ORDERS_SPEEDUP | WP5改为目标 | 等信息/等算力实测 |
| SOLVED_PAIN | WP5改为“拟解决” | 现场与完整联合证据 |

## Observed治理

`主张扫描03.csv`中的`OBSERVED_FIELD`行全部交由WP5核对：Planned行的Observed必须为空；无run-id、代码/配置哈希和退出码不得使用“通过/优秀/已验证”。
"@
    Write-Utf8 $ClaimMap $mapText

    $formal = Read-Utf8Raw $FormalEvidence
    $formalHash = (Get-FileHash -LiteralPath $FormalEvidence -Algorithm SHA256).Hash.ToLower()
    $formalBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($FormalEvidence))
    $draft = @"
# 证据状态登记03草案

> **非权威、待复核。** 下方BEGIN_FORMAL_COPY至END_FORMAL_COPY是生成时正式 evidence-status.md 的逐字副本；正式文件未被本草案覆盖。

- 生成时间（UTC）：$freezeTime
- 正式副本SHA-256：$formalHash
- 正式副本Base64（用于逐字节复核）：$formalBase64

<!-- BEGIN_FORMAL_COPY -->
$formal
<!-- END_FORMAL_COPY -->

## WP0逐字段建议差异（尚未批准）

| Evidence ID | 目标字段 | 当前值 | 建议值 | 原因 | 正式修改前置条件 |
|---|---|---|---|---|---|
| EVD-SYNTH-001 | 主张类别与位置 | DO-27同源重磁数据现代SimPEG降阶兼容验证 | DO-27同源数据降阶双单物理LSQR兼容运行 | 非PGI、非联合、非贝叶斯，且best alpha需重审 | WP7 DO-27-v2与证据治理审批 |
| EVD-SYNTH-001 | 升级验证条件 | 当前正式文本 | 增加solver/data-fit/model-recovery分离门槛 | stop_code不等于模型有效 | WP7预注册完成 |
| EVD-ALGO-002 | 主张类别与位置 | matrix-free算子梯度、MCMC诊断与端到端链路 | 拆分算子/诊断单测与局部4维重力链 | 当前运行包不足以重算链诊断或证明全维覆盖 | WP7 synthetic-block-v2 |
| EVD-ALGO-002 | 当前状态 | Synthetic-run | DISPUTED_PENDING_WP7（草案审计标记，不是正式状态词） | 缺draws、warmup、接受率、种子、输出哈希 | 独立复算与审批 |
"@
    Write-Utf8 $EvidenceDraft $draft
}

$failures = [System.Collections.Generic.List[string]]::new()
foreach ($required in @($Inventory,$Hashes,$Ledger,$ClaimMap,$ClaimScan,$EvidenceDraft)) {
    if (-not (Test-Path -LiteralPath $required)) { $failures.Add("missing artifact: $required") }
}

if ($failures.Count -eq 0) {
    $inv = Import-Csv -LiteralPath $Inventory
    $expectedHeaders = @('path','category','size_bytes','frozen_at_utc','status','sha256','reason')
    $actualHeaders = @($inv[0].PSObject.Properties.Name)
    if (Compare-Object $expectedHeaders $actualHeaders) { $failures.Add('inventory schema mismatch') }
    $expected = @(Get-FreezeFiles | ForEach-Object { (Relative-Path $_.FullName).Normalize([Text.NormalizationForm]::FormC) })
    $actualPresent = @($inv | Where-Object status -eq 'present' | ForEach-Object { $_.path.Normalize([Text.NormalizationForm]::FormC) })
    if (($actualPresent | ForEach-Object { $_.ToLowerInvariant() } | Sort-Object -Unique).Count -ne $actualPresent.Count) { $failures.Add('duplicate inventory path') }
    if (Compare-Object ($expected | Sort-Object) ($actualPresent | Sort-Object)) { $failures.Add('inventory scope mismatch') }
    $timestamps = @($inv.frozen_at_utc | Sort-Object -Unique)
    if ($timestamps.Count -ne 1) { $failures.Add('inventory must use one freeze timestamp') }
    try {
        $parsedFreeze = [DateTimeOffset]::ParseExact($timestamps[0], 'o', [Globalization.CultureInfo]::InvariantCulture)
        if ($parsedFreeze.Offset -ne [TimeSpan]::Zero) { $failures.Add('freeze timestamp is not UTC') }
    } catch { $failures.Add('invalid freeze timestamp') }
    $allowedCategories = @('main-text','appendix','run-package','contract','source','test','governance-reference','mandatory','exclusion-policy')
    foreach ($row in $inv) {
        if ($row.category -notin $allowedCategories) { $failures.Add("unknown category: $($row.category)") }
        if ($row.status -eq 'missing') { $failures.Add("required file missing: $($row.path)"); continue }
        if ($row.status -eq 'excluded') {
            if ([string]::IsNullOrWhiteSpace($row.reason)) { $failures.Add("excluded row missing reason: $($row.path)") }
            continue
        }
        if ($row.status -ne 'present') { $failures.Add("unknown inventory status: $($row.status)"); continue }
        $full = Join-Path $ProjectRoot ($row.path -replace '/', '\')
        $resolved = [IO.Path]::GetFullPath($full)
        $rootPrefix = $ProjectRoot.TrimEnd('\') + '\'
        if (-not $resolved.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) { $failures.Add("path escape: $($row.path)"); continue }
        if (-not (Test-Path -LiteralPath $resolved)) { $failures.Add("missing file: $($row.path)"); continue }
        if ((Get-Item -LiteralPath $resolved).Attributes -band [IO.FileAttributes]::ReparsePoint) { $failures.Add("reparse point: $($row.path)") }
        if ((Get-Item -LiteralPath $resolved).Length -ne [long]$row.size_bytes) { $failures.Add("size mismatch: $($row.path)") }
        if ((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { $failures.Add("hash mismatch: $($row.path)") }
        if ([string]::IsNullOrWhiteSpace($row.category) -or [string]::IsNullOrWhiteSpace($row.frozen_at_utc)) { $failures.Add("metadata missing: $($row.path)") }
    }
    $hashLines = @(Read-Utf8Lines $Hashes)
    $expectedHashLines = @($inv | Where-Object status -eq 'present' | ForEach-Object { "$($_.sha256)  $($_.path)" })
    if (Compare-Object $expectedHashLines $hashLines -SyncWindow 0) { $failures.Add('sha256 content mismatch') }
    foreach ($line in $hashLines) {
        if ($line -notmatch '^[0-9a-f]{64}  [^/\\].+|^[0-9a-f]{64}  _bmad-output/.+|^[0-9a-f]{64}  (src|tests)/.+') {
            $failures.Add("invalid sha256 line: $line")
        }
    }

    $source = Get-ReviewFindings
    $ledgerIds = @()
    $ledgerRows = @{}
    foreach ($line in Read-Utf8Lines $Ledger) {
        if ($line -match '^\|\s*R03-\d+\s*\|') {
            $cells = @($line.Split('|') | ForEach-Object { $_.Trim() })
            if ($cells.Count -lt 14) { $failures.Add("malformed ledger row: $line"); continue }
            $id = $cells[1]; $sourceId = $cells[2]
            if ($ledgerRows.ContainsKey($id)) { $failures.Add("duplicate ledger id: $id") }
            $ledgerRows[$id] = $cells
            $ledgerIds += $sourceId
            foreach ($pos in 1..12) {
                if ([string]::IsNullOrWhiteSpace($cells[$pos])) { $failures.Add("blank ledger field $pos in $id") }
            }
            $expectedSource = $source | Where-Object SourceFindingId -eq $sourceId
            if ($expectedSource.Count -ne 1) { $failures.Add("unknown ledger source: $sourceId") }
            else {
                if ($cells[3] -ne 'not-split') { $failures.Add("invalid split basis: $id") }
                if ($cells[4] -ne $expectedSource.Level) { $failures.Add("ledger level mismatch: $id") }
                if ($cells[5] -ne $expectedSource.Section) { $failures.Add("ledger section mismatch: $id") }
                if ($cells[6] -ne [string]$expectedSource.SourceLine) { $failures.Add("ledger source line mismatch: $id") }
                if ($cells[9] -ne $expectedSource.OwnerRole -or $cells[10] -ne 'Open' -or $cells[12] -ne $expectedSource.Verifier) { $failures.Add("ledger governance field mismatch: $id") }
            }
        }
    }
    if (($ledgerIds | Sort-Object -Unique).Count -ne $ledgerIds.Count) { $failures.Add('duplicate source finding id') }
    if (Compare-Object ($source.SourceFindingId | Sort-Object) ($ledgerIds | Sort-Object)) { $failures.Add('ledger source coverage mismatch') }

    $formalIds = @(Get-EvidenceIds $FormalEvidence)
    $mapIds = @(Get-EvidenceIds $ClaimMap)
    if (Compare-Object $formalIds $mapIds) { $failures.Add('evidence id mapping mismatch') }
    foreach ($line in Read-Utf8Lines $ClaimMap) {
        if ($line -match '^\|\s*(EVD-[A-Z0-9-]+)\s*\|') {
            $cells = @($line.Split('|') | ForEach-Object { $_.Trim() })
            if ($cells.Count -lt 6 -or [string]::IsNullOrWhiteSpace($cells[2]) -or [string]::IsNullOrWhiteSpace($cells[3]) -or [string]::IsNullOrWhiteSpace($cells[4])) {
                $failures.Add("incomplete evidence mapping: $($Matches[1])")
            }
            if ($Matches[1] -in @('EVD-SYNTH-001','EVD-ALGO-002')) {
                if ($cells[2] -ne 'DISPUTED_PENDING_WP7' -or $cells[4] -notmatch '联合' -or $cells[4] -notmatch '现场') {
                    $failures.Add("unsafe disputed evidence mapping: $($Matches[1])")
                }
            }
        }
    }

    $freshHits = @(Get-ClaimHits)
    $savedHits = @(Import-Csv -LiteralPath $ClaimScan)
    $freshKeys = @($freshHits | ForEach-Object { "$($_.PatternId)|$($_.Path)|$($_.Line)|$($_.TextSha256)|$($_.Disposition)|$($_.EvidenceId)" })
    $savedKeys = @($savedHits | ForEach-Object { "$($_.PatternId)|$($_.Path)|$($_.Line)|$($_.TextSha256)|$($_.Disposition)|$($_.EvidenceId)" })
    if (Compare-Object ($freshKeys | Sort-Object) ($savedKeys | Sort-Object)) { $failures.Add('claim scan mismatch') }
    foreach ($row in $savedHits) {
        if ($row.Disposition -notin @('WP5_DIRECT_DOWNGRADE','WP5_VERIFY_PLANNED_EMPTY')) { $failures.Add("invalid claim disposition: $($row.Path):$($row.Line)") }
        if ($row.EvidenceId -ne 'none' -and $row.EvidenceId -notin $formalIds) { $failures.Add("invalid claim evidence id: $($row.EvidenceId)") }
    }

    $formalCurrentHash = (Get-FileHash -LiteralPath $FormalEvidence -Algorithm SHA256).Hash.ToLower()
    if ($formalCurrentHash -ne $TrustedFormalEvidenceSha256) { $failures.Add('formal evidence changed from trusted pre-WP0 digest') }
    $draftRaw = Read-Utf8Raw $EvidenceDraft
    if ($draftRaw -notmatch '正式副本SHA-256：([0-9a-f]{64})' -or $Matches[1] -ne $formalCurrentHash) { $failures.Add('draft formal hash mismatch') }
    if ($draftRaw -notmatch '正式副本Base64（用于逐字节复核）：([A-Za-z0-9+/=]+)') {
        $failures.Add('formal evidence base64 missing')
    } else {
        try {
            $decoded = [Convert]::FromBase64String($Matches[1])
            if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$decoded, [byte[]][IO.File]::ReadAllBytes($FormalEvidence))) { $failures.Add('formal evidence byte copy mismatch') }
        } catch { $failures.Add('formal evidence base64 invalid') }
    }
    if ($draftRaw -notmatch '(?s)<!-- BEGIN_FORMAL_COPY -->\r?\n(.*?)\r?\n<!-- END_FORMAL_COPY -->') {
        $failures.Add('formal evidence copy markers missing')
    }
}

if ($SelfTest) {
    $cases = @(
        @{ Name='hash-content'; Path=$Hashes; Mutate={
            param($text) ([regex]::Replace($text, '^[0-9a-f]{64}', ('0' * 64), 1))
        }},
        @{ Name='inventory-row'; Path=$Inventory; Mutate={
            param($text) $parts = @($text -split "`r?`n"); (($parts[0]) + $parts[2..($parts.Count-1)]) -join "`n"
        }},
        @{ Name='ledger-owner'; Path=$Ledger; Mutate={
            param($text) ([regex]::Replace($text, '\| ([^|]+) \| Open \|', '|  | Open |', 1))
        }},
        @{ Name='claim-disposition'; Path=$ClaimScan; Mutate={
            param($text) $text.Replace('WP5_DIRECT_DOWNGRADE','APPROVED')
        }},
        @{ Name='evidence-copy'; Path=$EvidenceDraft; Mutate={
            param($text) ([regex]::Replace($text, '正式副本Base64（用于逐字节复核）：.', '正式副本Base64（用于逐字节复核）：!', 1))
        }}
    )
    foreach ($case in $cases) {
        $original = [IO.File]::ReadAllBytes($case.Path)
        try {
            $text = [Text.Encoding]::UTF8.GetString($original)
            $mutated = & $case.Mutate $text
            [IO.File]::WriteAllText($case.Path, $mutated, [Text.UTF8Encoding]::new($false))
            & (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File $PSCommandPath *> $null
            if ($LASTEXITCODE -eq 0) { $failures.Add("negative self-test was not rejected: $($case.Name)") }
        } finally {
            [IO.File]::WriteAllBytes($case.Path, $original)
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

$invCount = (Import-Csv -LiteralPath $Inventory).Count
$findingCount = (Get-ReviewFindings).Count
$claimCount = (Import-Csv -LiteralPath $ClaimScan).Count
$evidenceCount = (Get-EvidenceIds $FormalEvidence).Count
Write-Output "PASS inventory=$invCount findings=$findingCount claim_hits=$claimCount evidence_ids=$evidenceCount self_test=$SelfTest"
