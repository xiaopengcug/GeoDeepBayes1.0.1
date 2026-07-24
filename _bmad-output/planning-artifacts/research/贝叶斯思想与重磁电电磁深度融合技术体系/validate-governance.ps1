param(
    [string]$Root = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
$errors = [System.Collections.Generic.List[string]]::new()
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$manifestPath = Join-Path $Root 'manifest.yaml'
$manifest = Get-Content -LiteralPath $manifestPath -Raw

$entries = [regex]::Matches($manifest, '\{path: "([^"]+)", sha256: "([0-9a-f]{64})"\}')
foreach ($entry in $entries) {
    $name = $entry.Groups[1].Value
    $expected = $entry.Groups[2].Value
    $path = Join-Path $Root $name
    if (-not (Test-Path -LiteralPath $path)) {
        $errors.Add("missing path: $name")
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { $errors.Add("hash mismatch: $name") }
}

$familyBlock = $manifest.Substring($manifest.IndexOf('version_families:'))
$familyCount = [regex]::Matches($familyBlock, '(?m)^  [a-z0-9_]+:$').Count
$canonicalCount = [regex]::Matches($familyBlock, '(?m)^    canonical:').Count
if ($familyCount -ne $canonicalCount) { $errors.Add('each version family must have exactly one canonical') }

$releaseMatch = [regex]::Match($manifest, '(?m)^release_paths:\s*\r?\n(?<body>(?:  - [^\r\n]+\r?\n)+)')
$releasePaths = @([regex]::Matches($releaseMatch.Groups['body'].Value, '"([^"]+)"') | ForEach-Object { $_.Groups[1].Value })
$archivedPaths = @(
    'archive/附录7-知识产权布局与成果转化规划.md',
    'archive/附录7-知识产权布局与成果转化规划_更新版.md',
    'archive/附录7-知识产权布局与成果转化规划_增强版.md',
    'archive/参考文献.md',
    'archive/贝叶斯三维反演测试算力需求说明-01.md'
)
foreach ($path in $releasePaths) {
    if ($path -in $archivedPaths) { $errors.Add("archived path in release_paths: $path") }
    if (-not (Test-Path -LiteralPath (Join-Path $Root $path))) { $errors.Add("release path missing: $path") }
}
$derivedPaths = @(
    'cited_refs.txt','evidence-status.md','validate-governance.ps1',
    'contracts/data-contract.schema.json','contracts/operator-capability.schema.json',
    'contracts/evidence-run.schema.json','contracts/operator-capabilities.json',
    'contracts/validate_contracts.py','validation/validate_open_data.py',
    'validation/runs/open-data-20260717-03/run-manifest.json',
    'validation/runs/open-data-20260717-03/results.json',
    'validation/runs/open-data-20260717-03/integrity.json',
    'validation/do27/requirements.lock.txt','validation/do27/run_do27_validation.py',
    'validation/runs/do27-simpeg-20260717-05/metrics.json',
    'validation/runs/do27-simpeg-20260717-05/environment.json',
    'validation/runs/do27-simpeg-20260717-05/config.json',
    'validation/runs/do27-simpeg-20260717-05/stdout.json',
    'validation/runs/do27-simpeg-20260717-05/stderr.txt',
    'validation/runs/do27-simpeg-20260717-05/run-manifest.json',
    'validation/runs/do27-simpeg-20260717-06/metrics.json',
    'validation/runs/do27-simpeg-20260717-06/environment.json',
    'validation/runs/do27-simpeg-20260717-06/config.json',
    'validation/runs/do27-simpeg-20260717-06/stdout.json',
    'validation/runs/do27-simpeg-20260717-06/stderr.txt',
    'validation/runs/do27-simpeg-20260717-06/run-manifest.json',
    'validation/runs/synthetic-block-20260717/metrics.json',
    'validation/runs/synthetic-block-20260717/run-manifest.json',
    '整改落实报告01.md',
    '整改落实报告02.md'
)
$declaredCanonical = @($entries | ForEach-Object { $_.Groups[1].Value } |
    Where-Object { $_ -notin $archivedPaths -and $_ -notin $derivedPaths } | Sort-Object -Unique)
$releaseUnique = @($releasePaths | Sort-Object -Unique)
if (@(Compare-Object $declaredCanonical $releaseUnique).Count -ne 0) {
    $errors.Add('document_groups canonical set and release_paths are inconsistent')
}
if (@($releasePaths | Where-Object { $_ -in $archivedPaths }).Count -gt 0) {
    $errors.Add('canonical and archived sets are not disjoint')
}

$refs = @([regex]::Matches((Get-Content -LiteralPath (Join-Path $Root '参考文献_更新版.md') -Raw), '(?m)^\[(\d+)\]') | ForEach-Object { [int]$_.Groups[1].Value })
$cited = @(Get-Content -LiteralPath (Join-Path $Root 'cited_refs.txt') | ForEach-Object { [int]$_ })
foreach ($id in $cited) {
    if ($id -notin $refs -or $id -in @(0,2700,3300)) { $errors.Add("invalid cited ref: $id") }
}

$evidence = Get-Content -LiteralPath (Join-Path $Root 'evidence-status.md') -Raw
foreach ($field in @('evidence_id','metric / unit','source / run','owner / date','writeback target','exact_anchor','source_span')) {
    if (-not $evidence.Contains($field)) { $errors.Add("evidence field missing: $field") }
}
$ids = @([regex]::Matches($evidence, 'EVD-[A-Z]+-\d{3}') | ForEach-Object { $_.Value } | Sort-Object -Unique)
if ($ids.Count -lt 10) { $errors.Add('insufficient stable evidence IDs') }

$archivedSet = @(
    'archive/附录7-知识产权布局与成果转化规划.md',
    'archive/附录7-知识产权布局与成果转化规划_更新版.md',
    'archive/附录7-知识产权布局与成果转化规划_增强版.md',
    'archive/参考文献.md',
    'archive/贝叶斯三维反演测试算力需求说明-01.md'
)
foreach ($name in $releasePaths | Where-Object { $_.EndsWith('.md') -and $_ -notin $archivedSet }) {
    $text = Get-Content -LiteralPath (Join-Path $Root $name) -Raw
    if (([regex]::Matches($text, '```').Count % 2) -ne 0) { $errors.Add("odd code fence: $name") }
    if (([regex]::Matches($text, '\$\$').Count % 2) -ne 0) { $errors.Add("odd display math: $name") }
}

$appendixText = (Get-ChildItem -LiteralPath $Root -Filter '附录*.md' | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"
$banned = [ordered]@{
    resource_estimate = '资源量估算'
    p50_to_metal = '基于P50.{0,30}(金属量|资源量)'
    posterior_confidence = '后验.{0,12}置信区间|置信区间.{0,12}后验'
    pod_arithmetic = '"POD_bases"\s*:\s*\d+\s*-\s*\d+'
    terrain_optional = 'terrain\.dat.{0,10}可选'
    gravity_depth_good = '重磁.{0,20}深度分辨率好|深度分辨率好.{0,20}重磁'
    data_dependent_prior = '若反演结果稳定，逐步提高先验权重|数据质量低，提高先验权重'
    bare_logn = '(?<!_)LogN\('
}
foreach ($key in $banned.Keys) {
    if ([regex]::IsMatch($appendixText, $banned[$key])) { $errors.Add("banned term: $key") }
}

$legacyRootFiles = @(
    '附录7-知识产权布局与成果转化规划.md',
    '附录7-知识产权布局与成果转化规划_更新版.md',
    '附录7-知识产权布局与成果转化规划_增强版.md',
    '参考文献.md',
    '贝叶斯三维反演测试算力需求说明-01.md',
    '06-合成数据验证案例.md',
    '附录4-核心算法性能基准测试报告.md',
    '附录5-真实矿区复盘验证案例.md'
)
foreach ($name in $legacyRootFiles) {
    if (Test-Path -LiteralPath (Join-Path $Root $name)) { $errors.Add("legacy file remains in release root: $name") }
}
$declaredArchived = @([regex]::Matches($manifest, '(?:path:\s*|-\s*)"?(archive/[^",\]\r\n]+)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
$actualArchived = @(Get-ChildItem -LiteralPath (Join-Path $Root 'archive') -File | ForEach-Object { "archive/$($_.Name)" } | Sort-Object -Unique)
if (@(Compare-Object $declaredArchived $actualArchived).Count -ne 0) {
    $errors.Add('archive directory and manifest archived paths are inconsistent')
}

$canonicalText = ($releasePaths | Where-Object { $_.EndsWith('.md') } | ForEach-Object {
    Get-Content -LiteralPath (Join-Path $Root $_) -Raw
}) -join "`n"
$contentBanned = [ordered]@{
    perfect_fusion = '完美地结合'
    forced_coupling = '强制(不同方法反演的地质体边界|矿体边界).{0,12}(一致|重合)'
    unsupported_gain = '定位准确率提升25%-30%'
    complete_decision_map = '实现了从.{0,30}到.{0,30}的完整映射'
}
foreach ($key in $contentBanned.Keys) {
    if ([regex]::IsMatch($canonicalText, $contentBanned[$key])) { $errors.Add("canonical banned claim: $key") }
}

$openRun = Join-Path $Root 'validation/runs/open-data-20260717-03/run-manifest.json'
if (-not (Test-Path -LiteralPath $openRun)) {
    $errors.Add('open data evidence run missing')
} else {
    $run = Get-Content -LiteralPath $openRun -Raw | ConvertFrom-Json
    if ($run.status -ne 'Open-data-run') { $errors.Add('open data run status invalid') }
    if ($run.evidence_id -ne 'EVD-OPEN-001') { $errors.Add('open data evidence id invalid') }
    if ($run.approval.decision -ne 'pending') { $errors.Add('unapproved open data run must remain pending') }
    foreach ($item in @($run.inputs) + @($run.outputs)) {
        $candidate = if ([System.IO.Path]::IsPathRooted($item.path)) { $item.path } else {
            $fromOpenData = Join-Path (Resolve-Path (Join-Path $Root '..\open-data')) $item.path
            $fromValidation = Join-Path (Join-Path $Root 'validation') $item.path
            if (Test-Path -LiteralPath $fromOpenData) { $fromOpenData } else { $fromValidation }
        }
        if (-not (Test-Path -LiteralPath $candidate)) { $errors.Add("run artifact missing: $($item.path)"); continue }
        $actualHash = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $item.sha256) { $errors.Add("run artifact hash mismatch: $($item.path)") }
    }
    $runScript = Join-Path $Root "validation/$($run.script.path)"
    if (-not (Test-Path -LiteralPath $runScript)) { $errors.Add('run script missing') }
    elseif ((Get-FileHash -LiteralPath $runScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $run.script.sha256) { $errors.Add('run script hash mismatch') }
    $resultsPath = Join-Path $Root 'validation/runs/open-data-20260717-03/results.json'
    $results = Get-Content -LiteralPath $resultsPath -Raw | ConvertFrom-Json
    if ($results.synthetic_run -ne $false -or $results.field_validated -ne $false) { $errors.Add('open data run illegally upgraded evidence') }
    if ($results.selected_checks.do27.inversion_validation_status -ne 'blocked') { $errors.Add('DO-27 inversion block state drifted') }
}

$do27RunPath = Join-Path $Root 'validation/runs/do27-simpeg-20260717-06/run-manifest.json'
if (-not (Test-Path -LiteralPath $do27RunPath)) {
    $errors.Add('DO-27 validation evidence missing')
} else {
    $do27Run = Get-Content -LiteralPath $do27RunPath -Raw | ConvertFrom-Json
    # 审查意见02 / G: DO-27 磁法经 iter_lim(2000)+alpha 扩展修复后收敛 (stop_code=2),
    # evidence 由 Failed 升级 Synthetic-run（降阶兼容验证，仍非 PGI 复现）
    if ($do27Run.status -ne 'Synthetic-run' -or $do27Run.evidence_id -ne 'EVD-SYNTH-001') {
        $errors.Add('DO-27 evidence identity/status invalid')
    }
    $do27MetricsPath = Join-Path $Root 'validation/runs/do27-simpeg-20260717-06/metrics.json'
    $do27Metrics = Get-Content -LiteralPath $do27MetricsPath -Raw | ConvertFrom-Json
    if ($do27Metrics.original_pgi_reproduced -ne $false) { $errors.Add('DO-27 original PGI claim drifted') }
    if ($do27Metrics.forward.all_finite -ne $true) { $errors.Add('DO-27 forward contains non-finite values') }
    if ($do27Metrics.gravity_inverse.best.converged -ne $true) { $errors.Add('DO-27 required gravity inversion did not converge') }
    if ($do27Metrics.magnetic_inverse.best.converged -ne $true -or $do27Metrics.magnetic_inverse.best.stop_code -notin @(1, 2)) {
        $errors.Add('DO-27 magnetic convergence boundary drifted')
    }
    $magneticCheck = @($do27Run.checks | Where-Object { $_.name -eq 'magnetic-forward-and-inverse' })
    if ($magneticCheck.Count -ne 1 -or $magneticCheck[0].status -ne 'passed') {
        $errors.Add('DO-27 magnetic manifest check contradicts convergence')
    }
    if ($do27Run.approval.decision -ne 'approved') { $errors.Add('DO-27 synthetic run must be approved') }
    $do27Environment = Get-Content -LiteralPath (Join-Path $Root 'validation/runs/do27-simpeg-20260717-06/environment.json') -Raw | ConvertFrom-Json
    $lockVersions = @{}
    Get-Content -LiteralPath (Join-Path $Root 'validation/do27/requirements.lock.txt') | ForEach-Object {
        if ($_ -match '^([^=]+)==(.+)$') { $lockVersions[$matches[1].ToLowerInvariant()] = $matches[2] }
    }
    foreach ($package in @('simpeg','discretize','numpy','scipy')) {
        if ($do27Environment.$package -ne $lockVersions[$package]) { $errors.Add("DO-27 runtime/lock mismatch: $package") }
    }
    if ($do27Environment.executable -notlike '*\.venv-do27\Scripts\python.exe') { $errors.Add('DO-27 runner did not use isolated interpreter') }
    $do27InputRoot = Join-Path $Root 'validation/do27/work/run-06'
    $do27Archive = Resolve-Path (Join-Path $Root '..\open-data\mining_geophysics\Zenodo_DO27_kimberlite_gravity_magnetic_joint_inversion_synthetic\simpeg-research_Astic-2020-JointInversion-1.0.0.zip')
    foreach ($item in $do27Run.inputs) {
        $candidate = if ($item.path -eq 'simpeg-research_Astic-2020-JointInversion-1.0.0.zip') {
            $do27Archive
        } else {
            Join-Path $do27InputRoot $item.path
        }
        if (-not (Test-Path -LiteralPath $candidate)) { $errors.Add("DO-27 input missing: $($item.path)"); continue }
        if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
            $errors.Add("DO-27 input hash mismatch: $($item.path)")
        }
    }
    foreach ($item in $do27Run.outputs) {
        $candidate = Join-Path (Join-Path $Root 'validation/runs') $item.path
        if (-not (Test-Path -LiteralPath $candidate)) { $errors.Add("DO-27 output missing: $($item.path)"); continue }
        if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
            $errors.Add("DO-27 output hash mismatch: $($item.path)")
        }
    }
    $do27Script = Join-Path $Root "validation/do27/$($do27Run.script.path)"
    if (-not (Test-Path -LiteralPath $do27Script)) { $errors.Add('DO-27 script missing') }
    elseif ((Get-FileHash -LiteralPath $do27Script -Algorithm SHA256).Hash.ToLowerInvariant() -ne $do27Run.script.sha256) {
        $errors.Add('DO-27 script hash mismatch')
    }
}

$contractOutput = & uv run --project $ProjectRoot --frozen python (Join-Path $Root 'contracts/validate_contracts.py') 2>&1
if ($LASTEXITCODE -ne 0) { $errors.Add("contract validation failed: $contractOutput") }

$refLines = Get-Content -LiteralPath (Join-Path $Root '参考文献_更新版.md')
$normalizedRefs = @{}
foreach ($line in $refLines) {
    $match = [regex]::Match($line, '^\[\d+\]\s*(.+)$')
    if (-not $match.Success) { continue }
    $key = ([regex]::Replace($match.Groups[1].Value.ToLowerInvariant(), '[^\p{L}\p{N}]+', ''))
    if ($normalizedRefs.ContainsKey($key)) { $errors.Add("duplicate normalized reference: $line") }
    else { $normalizedRefs[$key] = $true }
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output "PASS entries=$($entries.Count) release_paths=$($releasePaths.Count) evidence_ids=$($ids.Count) cited_refs=$($cited.Count)"
