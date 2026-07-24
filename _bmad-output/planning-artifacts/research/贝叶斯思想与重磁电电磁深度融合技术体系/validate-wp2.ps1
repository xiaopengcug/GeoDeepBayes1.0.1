[CmdletBinding()]
param([switch]$SelfTest,[string]$OutputOverride='',[string]$DocumentRootOverride='',[string]$SourceRootOverride='')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$docRoot=if($DocumentRootOverride){$DocumentRootOverride}else{$root}
$toy = if($SourceRootOverride){$SourceRootOverride}else{Join-Path $root 'validation/wp2-toy'}
if($OutputOverride){$output=$OutputOverride}else{$ap=Join-Path $toy 'active-output.json';if(-not(Test-Path $ap)){throw 'active-output.json missing'};$ptr=Get-Content -Raw $ap|ConvertFrom-Json;if(-not($ptr.schema-eq'wp2-active-output-v1'-and$ptr.run_instance_id-match'^[0-9]{8}T[0-9]{9}Z-[0-9a-f]{32}$')){throw'active pointer schema/id错误'};if(-not($ptr.version_path-eq"versions/$($ptr.run_instance_id)"-and-not$ptr.version_path.Contains('..'))){throw'active pointer路径不安全'};$output=[IO.Path]::GetFullPath((Join-Path $toy $ptr.version_path));$vr=[IO.Path]::GetFullPath((Join-Path $toy 'versions')).TrimEnd('\')+'\';if(-not$output.StartsWith($vr,[StringComparison]::OrdinalIgnoreCase)){throw'active pointer逃逸versions'};if((Get-FileHash -Algorithm SHA256 (Join-Path $output 'manifest.json')).Hash.ToLowerInvariant()-ne$ptr.manifest_sha256){throw'active pointer manifest hash错误'}}

function Fail([string]$Message) { throw "WP2 validation failed: $Message" }
function Require([bool]$Condition, [string]$Message) { if (-not $Condition) { Fail $Message } }
function Require-Finite([double]$Value,[string]$Message) { Require (-not [double]::IsNaN($Value) -and -not [double]::IsInfinity($Value)) $Message }
function Matrix-Rank([object[]]$Rows,[double]$Tol=1e-10){
    $m=$Rows.Count;$n=$Rows[0].Count;$a=New-Object 'double[,]' $m,$n
    for($i=0;$i-lt$m;$i++){Require($Rows[$i].Count-eq$n)'矩阵行长不一致';for($j=0;$j-lt$n;$j++){$a[$i,$j]=[double]$Rows[$i][$j];Require-Finite $a[$i,$j]'矩阵含非有限值'}}
    $rank=0;$col=0
    while($rank-lt$m-and$col-lt$n){$pivot=$rank;for($i=$rank+1;$i-lt$m;$i++){if([Math]::Abs($a[$i,$col])-gt[Math]::Abs($a[$pivot,$col])){$pivot=$i}};if([Math]::Abs($a[$pivot,$col])-le$Tol){$col++;continue};for($j=$col;$j-lt$n;$j++){$t=$a[$rank,$j];$a[$rank,$j]=$a[$pivot,$j];$a[$pivot,$j]=$t};for($i=$rank+1;$i-lt$m;$i++){$f=$a[$i,$col]/$a[$rank,$col];for($j=$col;$j-lt$n;$j++){$a[$i,$j]-=$f*$a[$rank,$j]}};$rank++;$col++}
    return $rank
}
function Gram-Matrix([object[]]$Rows){$m=$Rows.Count;$r=$Rows[0].Count;$g=@();for($i=0;$i-lt$r;$i++){$row=@();for($j=0;$j-lt$r;$j++){$s=0.;for($k=0;$k-lt$m;$k++){$s+=[double]$Rows[$k][$i]*[double]$Rows[$k][$j]};$row+=$s};$g+=,@($row)};return $g}
function Is-Symmetric-SPD([object[]]$Rows,[double]$Tol=1e-10){$n=$Rows.Count;if($n-lt1){return $false};$l=New-Object 'double[,]' $n,$n;for($i=0;$i-lt$n;$i++){if($Rows[$i].Count-ne$n){return $false};for($j=0;$j-lt$n;$j++){if([Math]::Abs([double]$Rows[$i][$j]-[double]$Rows[$j][$i])-gt$Tol){return $false}}};for($i=0;$i-lt$n;$i++){for($j=0;$j-le$i;$j++){$s=[double]$Rows[$i][$j];for($k=0;$k-lt$j;$k++){$s-=$l[$i,$k]*$l[$j,$k]};if($i-eq$j){if($s-le$Tol){return $false};$l[$i,$j]=[Math]::Sqrt($s)}else{$l[$i,$j]=$s/$l[$j,$j]}}};return $true}
function VChol([object[]]$a){$n=$a.Count;$l=@();for($i=0;$i-lt$n;$i++){$l+=,@([double[]](0..($n-1)|%{0.}))};for($i=0;$i-lt$n;$i++){for($j=0;$j-le$i;$j++){$s=[double]$a[$i][$j];for($k=0;$k-lt$j;$k++){$s-=$l[$i][$k]*$l[$j][$k]};if($i-eq$j){if($s-le1e-12){Fail 'Cholesky非SPD'};$l[$i][$j]=[Math]::Sqrt($s)}else{$l[$i][$j]=$s/$l[$j][$j]}}};,$l}
function VSolve([object[]]$l,[double[]]$b){$n=$l.Count;$y=New-Object double[] $n;$x=New-Object double[] $n;for($i=0;$i-lt$n;$i++){$s=$b[$i];for($k=0;$k-lt$i;$k++){$s-=$l[$i][$k]*$y[$k]};$y[$i]=$s/$l[$i][$i]};for($i=$n-1;$i-ge0;$i--){$s=$y[$i];for($k=$i+1;$k-lt$n;$k++){$s-=$l[$k][$i]*$x[$k]};$x[$i]=$s/$l[$i][$i]};,$x}
function VInv([object[]]$l){$n=$l.Count;$o=@();for($i=0;$i-lt$n;$i++){$o+=,@([double[]](0..($n-1)|%{0.}))};for($j=0;$j-lt$n;$j++){$e=New-Object double[] $n;$e[$j]=1;$x=VSolve $l $e;for($i=0;$i-lt$n;$i++){$o[$i][$j]=$x[$i]}};,$o}
function Reject-Forbidden([string]$Text) {
    if ($Text -match 'det\s*\(\s*[Φ\\]?Phi_r\s*\)') { Fail '矩形POD基行列式残留' }
    if ($Text -match 'IG_k\s*\\approx.*log\s*\\frac\{p\(m\^\{\(s\)\}\s*\|\s*D\)\}\{p\(m\^\{\(s\)\}\s*\|\s*D_\{-k\}\)\}') {
        Fail 'LOMO遗漏证据项的后验比残留'
    }
}
function LogN([double]$x,[double]$sd){-0.5*[Math]::Log(2*[Math]::PI*$sd*$sd)-0.5*$x*$x/($sd*$sd)}
function VNextNormal([Random]$rng){[Math]::Sqrt(-2*[Math]::Log([Math]::Max($rng.NextDouble(),1e-15)))*[Math]::Cos(2*[Math]::PI*$rng.NextDouble())}
function VLogMeanExp([double[]]$x){$mx=($x|measure -Maximum).Maximum;$mx+[Math]::Log((($x|%{[Math]::Exp($_-$mx)}|measure -Average).Average))}
function QNorm([double]$p){$a=@(-39.6968302866538,220.946098424521,-275.928510446969,138.357751867269,-30.6647980661472,2.50662827745924);$b=@(-54.4760987982241,161.585836858041,-155.698979859887,66.8013118877197,-13.2806815528857);$c=@(-.00778489400243029,-.322396458041136,-2.40075827716184,-2.54973253934373,4.37466414146497,2.93816398269878);$d=@(.00778469570904146,.32246712907004,2.445134137143,3.75440866190742);if($p-lt.02425){$q=[math]::Sqrt(-2*[math]::Log($p));$nu=(((($c[0]*$q+$c[1])*$q+$c[2])*$q+$c[3])*$q+$c[4])*$q+$c[5];$de=((($d[0]*$q+$d[1])*$q+$d[2])*$q+$d[3])*$q+1;return $nu/$de};if($p-gt.97575){return -(QNorm (1-$p))};$q=$p-.5;$r=$q*$q;$nu=((((($a[0]*$r+$a[1])*$r+$a[2])*$r+$a[3])*$r+$a[4])*$r+$a[5])*$q;$de=(((($b[0]*$r+$b[1])*$r+$b[2])*$r+$b[3])*$r+$b[4])*$r+1;return $nu/$de}
function RNorm([double[]]$v){$n=$v.Count;$p=for($i=0;$i-lt$n;$i++){[pscustomobject]@{i=$i;v=$v[$i]}};$s=@($p|sort v);$o=New-Object double[] $n;$k=0;while($k-lt$n){$j=$k;while($j+1-lt$n-and$s[$j+1].v-eq$s[$k].v){$j++};$r=(($k+1)+($j+1))/2;$z=QNorm (($r-.375)/($n+.25));for($h=$k;$h-le$j;$h++){$o[$s[$h].i]=$z};$k=$j+1};,$o}
function VSplits([object[]]$rows,[string]$field,[switch]$rank,[switch]$fold){$v=[double[]]@($rows|%{[double]$_.$field});$so=@($v|sort);$med=$so[[int]($so.Count/2)];if($fold){$v=[double[]]@($v|%{[math]::Abs($_-$med)})};if($rank){$v=RNorm $v};$o=@();$off=0;foreach($c in ($rows.chain|sort -Unique)){$n=@($rows|?{[int]$_.chain-eq[int]$c}).Count;$h=[int]($n/2);$a=@($v[$off..($off+$n-1)]);$o+=,@([double[]]$a[0..($h-1)]);$o+=,@([double[]]$a[$h..(2*$h-1)]);$off+=$n};$o}
function VRhat([object[]]$sp){$n=$sp[0].Count;$mu=@($sp|%{($_|measure -Average).Average});$va=@($sp|%{$x=($_|measure -Average).Average;(($_|%{($_-$x)*($_-$x)}|measure -Sum).Sum)/($n-1)});$w=($va|measure -Average).Average;$gm=($mu|measure -Average).Average;$b=$n*(($mu|%{($_-$gm)*($_-$gm)}|measure -Sum).Sum)/($mu.Count-1);[math]::Sqrt((($n-1)/$n*$w+$b/$n)/$w)}
function VGTau([double[]]$rho){$pa=@();for($k=0;2*$k+1-lt$rho.Count;$k++){$x=$rho[2*$k]+$rho[2*$k+1];if($x-le0){break};if($pa.Count-and$x-gt$pa[-1]){$x=$pa[-1]};$pa+=$x};-1+2*(($pa|measure -Sum).Sum)}
function VEss([object[]]$sp){$m=$sp.Count;$n=$sp[0].Count;$mu=@($sp|%{($_|measure -Average).Average});$va=@($sp|%{$x=($_|measure -Average).Average;(($_|%{($_-$x)*($_-$x)}|measure -Sum).Sum)/($n-1)});$w=($va|measure -Average).Average;$gm=($mu|measure -Average).Average;$b=$n*(($mu|%{($_-$gm)*($_-$gm)}|measure -Sum).Sum)/($m-1);$vp=(($n-1)/$n)*$w+$b/$n;$rho=@(1.0);for($l=1;$l-lt$n;$l++){$vg=0.;foreach($a in $sp){for($i=0;$i-lt$n-$l;$i++){$vg+=($a[$i+$l]-$a[$i])*($a[$i+$l]-$a[$i])}};$vg/=($m*($n-$l));$rho+=1-$vg/(2*$vp)};$tau=VGTau ([double[]]$rho);if($tau-le0){return $m*$n};[math]::Min($m*$n,$m*$n/$tau)}
Require([Math]::Abs((QNorm .5))-lt1e-12-and[Math]::Abs((QNorm .975)-1.9599639861202)-lt1e-7)'逆正态参考夹具失败'
Require([Math]::Abs((VGTau ([double[]]@(1.0,0.6,-0.4,0.3,-0.2,0.1)))-2.2)-lt1e-12)'Geyer标准rho0+rho1配对参考夹具失败'
$legacyFixtureTau=1+2*((0.6-0.4)+(0.3-0.2))
Require([Math]::Abs($legacyFixtureTau-1.6)-lt1e-12-and[Math]::Abs((VGTau ([double[]]@(1.0,0.6,-0.4,0.3,-0.2,0.1)))-$legacyFixtureTau)-gt0.5)'Geyer夹具未区分旧rho1+rho2配对'
function Check-RjmcmcRecord($row) {
    foreach ($name in @('case','x','u','y','u_prime','log_target_x','log_target_y','j_forward','j_reverse','log_q_forward','log_q_reverse','log_forward','log_reverse','abs_jacobian','inverse_error')) {
        if (-not $row.PSObject.Properties.Name.Contains($name) -or [string]::IsNullOrWhiteSpace([string]$row.$name)) {
            Fail "RJMCMC记录缺字段 $name"
        }
    }
    Require ([Math]::Abs(([double]$row.log_forward + [double]$row.log_reverse)) -le 1e-12) '正反log接受率不互逆'
    $calc=[double]$row.log_target_y-[double]$row.log_target_x+[Math]::Log([double]$row.j_reverse)-[Math]::Log([double]$row.j_forward)+[double]$row.log_q_reverse-[double]$row.log_q_forward+[Math]::Log([double]$row.abs_jacobian)
    Require ([Math]::Abs($calc-[double]$row.log_forward)-le 1e-12) 'log流量不能由原始分量复算'
    $logFluxForward=[double]$row.log_target_x+[Math]::Log([double]$row.j_forward)+[double]$row.log_q_forward+[Math]::Min(0.0,$calc)
    $logFluxReverseInForwardMeasure=[double]$row.log_target_y+[Math]::Log([double]$row.j_reverse)+[double]$row.log_q_reverse+[Math]::Min(0.0,-$calc)+[Math]::Log([double]$row.abs_jacobian)
    Require([Math]::Abs($logFluxForward-$logFluxReverseInForwardMeasure)-le1e-12)'目标×j×q×accept正反流量不平衡'
    Require ([double]$row.inverse_error -le 1e-12) '逆映射误差超限'
    if ($row.case -eq 'unit_birth_death') { Require ([double]$row.abs_jacobian -eq 1.0) '单位Jacobian错误' }
    elseif ($row.case -eq 'nonunit_split_merge') { Require ([double]$row.abs_jacobian -eq 2.0) '非单位Jacobian错误' }
    else { Fail "未知RJMCMC case: $($row.case)" }
}

$doc03 = Get-Content -Raw -LiteralPath (Join-Path $docRoot '03-多方法深度融合的核心技术实现路径.md')
$doc02 = Get-Content -Raw -LiteralPath (Join-Path $docRoot '02-全方法深度融合的底层逻辑与理论总纲.md')
$app3 = Get-Content -Raw -LiteralPath (Join-Path $docRoot '附录3-算法选型与多方法组合决策树.md')
$app4 = Get-Content -Raw -LiteralPath (Join-Path $docRoot '附录4-核心算法性能基准测试计划与验收指标.md')
$compute = Get-Content -Raw -LiteralPath (Join-Path $docRoot '贝叶斯三维反演测试算力需求说明.md')
$consumerNames=@('02-全方法深度融合的底层逻辑与理论总纲.md','03-多方法深度融合的核心技术实现路径.md','05-工程化落地与效率优化方案.md','附录2-概率化反演结果应用规范与风险管控准则.md','附录3-算法选型与多方法组合决策树.md','附录4-核心算法性能基准测试计划与验收指标.md','附录9-一线工程师极简上手指南.md','附录10-项目实施进度计划与经费概算模板.md','附录11-分勘查阶段标准化操作手册.md','贝叶斯三维反演测试算力需求说明.md')
foreach($name in $consumerNames){
    $text=Get-Content -Raw -LiteralPath (Join-Path $docRoot $name)
    Require($text.Contains('diagnostic-contract.json')) "诊断消费者未引用唯一合同: $name"
    Require(-not($text-match '(?i)(R.?hat|ESS|MCSE|接受率).{0,30}(<|>|≤|≥)\s*\d')) "诊断消费者复制数值阈值: $name"
    Require(-not($text-match '(?i)(通过|采用|使用)\s*(薄化|thinn?ing).{0,30}(改善|提高|增加).{0,20}(收敛|ESS|有效样本)')) "薄化改善收敛/ESS误述: $name"
}
$discover=@(Get-ChildItem -File -LiteralPath $docRoot -Filter '*.md'|Where-Object{$_.Name-match '^(\d\d-|附录\d+-)'})
foreach($f in $discover){$text=Get-Content -Raw $f.FullName;if($text-match '(?i)(R.?hat|ESS|MCSE|接受率).{0,30}(<|>|≤|≥)\s*\d'){Require($text.Contains('diagnostic-contract.json'))"仓库发现消费者未引用合同: $($f.Name)";Fail "仓库发现消费者复制数值阈值: $($f.Name)"}}
Require($doc03.Contains('report-contract.json')-and$compute.Contains('report-contract.json'))'文档未引用机器报告合同'
Reject-Forbidden $doc03
Require ($doc03.Contains('sqrt{\det(\Phi_r^\mathsf T\Phi_r)}=1')) '缺POD Hausdorff体积因子'
Require ($doc03.Contains('RJMCMC唯一Green规范')) '缺唯一Green规范'
foreach ($term in @('j_\ell(x)','q_\ell(u\mid x)','\dim(x)+\dim(u)=\dim(y)+\dim(u'')','\left|\det D T_\ell(x,u)\right|')) {
    Require ($doc03.Contains($term)) "Green规范缺项 $term"
}
foreach ($term in @('design_eig','realized_information_gain','lomo_forward_kl','-\log Z_D+\log Z_{-k}')) {
    Require ($doc03.Contains($term)) "信息量合同缺项 $term"
}
Require (-not ($doc02 -match '\\tag\{2\.3-25\}')) '02章重复RJMCMC公式仍存在'
foreach($pair in @(@('02章',$doc02),@('03章',$doc03))){
    $tags=@([regex]::Matches($pair[1],'\\tag\{([^}]+)\}')|ForEach-Object{$_.Groups[1].Value})
    $dups=@($tags|Group-Object|Where-Object Count -gt 1)
    Require($dups.Count-eq0) "$($pair[0])公式tag重复"
}
Require(-not($doc02-match '\$\\hat\{R\}_\{1000\}\s*[<>]' -or $doc02-match 'ESS_\{1000\}\s*[<>]'))'02章残留绕过诊断合同的短链阈值'
Require($app3.Contains('数值表降格规则')-and$app4.Contains('Observed 硬门')-and$compute.Contains('提交日平台报价'))'性能/成本Hypothesis降格规则缺失'
foreach ($consumer in @($doc03,$app3,$app4,$compute)) {
    Require ($consumer.Contains('diagnostic-contract.json')) '诊断消费者未引用唯一合同'
}
foreach ($term in @('装配','预条件','Krylov','伴随','通信','I/O','高保真')) {
    Require ($doc03.Contains($term) -and $compute.Contains($term)) "成本账本缺项 $term"
}
Require ($doc03.Contains('数值 damping') -and $doc03.Contains('Empirical Bayes')) '正则化语义未统一'

$cfg = Get-Content -Raw -LiteralPath (Join-Path $output 'config.json') | ConvertFrom-Json
$contract = Get-Content -Raw -LiteralPath (Join-Path $output 'diagnostic-contract.json') | ConvertFrom-Json
$results = Get-Content -Raw -LiteralPath (Join-Path $output 'results.json') | ConvertFrom-Json
$manifest = Get-Content -Raw -LiteralPath (Join-Path $output 'manifest.json') | ConvertFrom-Json
$frozenFields=@('rank_normalized_split_rhat','folded_split_rhat','bulk_ess','tail_ess','relative_mcse','mode_visits_per_chain','failed_replicate_rate','status')
Require($contract.schema_version-eq'1.0.0'-and$contract.contract_id-eq'WP2-DIAGNOSTIC-CONTRACT-v1'-and(($contract.required_fields-join'|')-eq($frozenFields-join'|'))-and$contract.hard_gate-eq'all')'diagnostic contract schema/id/fields降级'
Require([double]$contract.thresholds.rank_normalized_split_rhat_max-le1.01-and[double]$contract.thresholds.bulk_ess_min-ge400-and[double]$contract.thresholds.tail_ess_min-ge400-and[double]$contract.thresholds.relative_mcse_max-le0.05-and[int]$contract.thresholds.required_mode_visits_per_chain-ge2-and[double]$contract.thresholds.failed_replicate_rate_max-le0.02)'diagnostic contract阈值被放宽'
Require ($cfg.run_id -eq $results.run_id -and $cfg.run_id -eq $manifest.run_id) 'run_id不一致'
$expectedFiles=@('config.json','diagnostic-chains.csv','diagnostic-contract.json','diagnostic-failure-chains.csv','diagnostic-failure-summary.json','diagnostic-replicates.csv','information-estimates.csv','report-contract.json','report.json','results.json','rjmcmc-chain.csv','rjmcmc-records.csv','stdout.log','stderr.log')
$actualNames=@($manifest.files.PSObject.Properties.Name|Sort-Object);Require(($actualNames-join'|')-eq(($expectedFiles|Sort-Object)-join'|'))'manifest文件白名单不精确'
Require($manifest.schema-eq'wp2-toy-manifest-v3'-and$manifest.command.executable-eq'pwsh'-and$manifest.command.script-eq'run-wp2-toy.ps1'-and(($manifest.command.arguments-join'|')-eq'-NoProfile|-File|wp2-toy-worker.ps1|-OutputStage|<stage>|-CapabilityToken|<redacted>')-and[int]$manifest.exit_code-eq0)'manifest schema/command/exit错误'
Require([datetime]$manifest.ended_utc-ge[datetime]$manifest.started_utc)'manifest起止时间错误'
foreach($stream in @('stdout','stderr')){Require($manifest.$stream.sha256-match'^[0-9a-f]{64}$'-and[long]$manifest.$stream.bytes-ge0)"manifest $stream 合同错误"}
foreach($stream in @('stdout','stderr')){Require($manifest.$stream.path-eq"$stream.log"-and$manifest.$stream.path-eq[IO.Path]::GetFileName($manifest.$stream.path)-and-not$manifest.$stream.path.Contains('..'))"manifest $stream 日志路径不安全";$sp=Join-Path $output $manifest.$stream.path;Require((Get-FileHash -Algorithm SHA256 $sp).Hash.ToLowerInvariant()-eq$manifest.$stream.sha256-and(Get-Item $sp).Length-eq[long]$manifest.$stream.bytes)"manifest $stream 日志哈希/长度错误"}
Require((Get-Content -Raw (Join-Path $output 'stdout.log')).Contains("PASS run_id=$($manifest.run_id)")-and(Get-Item (Join-Path $output 'stderr.log')).Length-eq0)'真实日志内容/run_id或stderr错误'
foreach($ef in @('pwsh','dotnet','os')){Require($manifest.environment.PSObject.Properties.Name.Contains($ef)-and-not[string]::IsNullOrWhiteSpace([string]$manifest.environment.$ef))"manifest环境缺$ef"}
$outputResolved=[IO.Path]::GetFullPath($output).TrimEnd('\')+'\'
foreach ($p in $manifest.files.PSObject.Properties) {
    Require($p.Name-eq[IO.Path]::GetFileName($p.Name)-and-not$p.Name.Contains('..'))'manifest不安全路径'
    $fp=[IO.Path]::GetFullPath((Join-Path $output $p.Name));Require($fp.StartsWith($outputResolved,[StringComparison]::OrdinalIgnoreCase))'manifest路径逃逸'
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $fp).Hash.ToLowerInvariant()
    Require ($actual -eq [string]$p.Value) "哈希不匹配 $($p.Name)"
}
Require($manifest.sources.Count-eq5)'manifest源码清单错误'
$sourceNames=@($manifest.sources|%{$_.path});Require((($sourceNames|Sort-Object -Unique).Count-eq5)-and(($sourceNames|Sort-Object)-join'|')-eq'config.json|diagnostic-contract.json|report-contract.json|run-wp2-toy.ps1|wp2-toy-worker.ps1')'manifest源码白名单/唯一性错误'
foreach($s in $manifest.sources){Require($s.path-eq[IO.Path]::GetFileName($s.path)-and-not$s.path.Contains('..')-and$s.sha256-match'^[0-9a-f]{64}$')'manifest源码路径/哈希错误';$sp=Join-Path $toy $s.path;Require((Get-FileHash -Algorithm SHA256 $sp).Hash.ToLowerInvariant()-eq$s.sha256)"源码哈希漂移 $($s.path)"}
foreach($name in @('config.json','diagnostic-contract.json','report-contract.json')){Require((Get-FileHash -Algorithm SHA256 (Join-Path $output $name)).Hash.ToLowerInvariant()-eq(Get-FileHash -Algorithm SHA256 (Join-Path $toy $name)).Hash.ToLowerInvariant())"output/source合同漂移: $name"}
$reportContract=Get-Content -Raw (Join-Path $output 'report-contract.json')|ConvertFrom-Json;$report=Get-Content -Raw (Join-Path $output 'report.json')|ConvertFrom-Json
Require($reportContract.schema-eq'wp2-report-contract-v1'-and(($reportContract.cost_stages-join'|')-eq'assembly|preconditioner|forward|adjoint|communication|io|diagnostics|storage'))'report contract最低schema/阶段被同步降级'
Require($report.schema-eq$reportContract.schema-and$report.manifest_ref-eq'manifest.json')'report schema/manifest_ref错误'
Require($report.cost.Count-eq$reportContract.cost_stages.Count)'成本阶段数量错误'
foreach($stage in $reportContract.cost_stages){$row=@($report.cost|?{$_.stage-eq$stage});Require($row.Count-eq1)"成本阶段缺失/重复: $stage";foreach($f in $reportContract.cost_required_fields){Require($row[0].PSObject.Properties.Name.Contains($f)-and-not[string]::IsNullOrWhiteSpace([string]$row[0].$f))"成本字段缺失: $stage/$f"};Require-Finite([double]$row[0].value)"成本值非有限: $stage";Require([double]$row[0].value-ge0-and[double]$row[0].tolerance-gt0-and[int]$row[0].iterations-ge0-and[int]$row[0].calls-ge0)'成本数值域错误';Require($row[0].unit-eq$reportContract.stage_units.$stage-and$reportContract.allowed_evidence_status-contains$row[0].evidence_status)'成本阶段单位/状态非法';if($row[0].evidence_status-eq'Observed'){Require($row[0].manifest_ref-eq'manifest.json')'Observed成本未绑定manifest'}}
foreach($f in $reportContract.regularization_required_fields){Require($report.regularization.PSObject.Properties.Name.Contains($f)-and-not[string]::IsNullOrWhiteSpace([string]$report.regularization.$f))"正则化字段缺失: $f"}
$cand=@($report.regularization.candidates|%{[double]$_});foreach($x in $cand){Require-Finite $x '正则化候选非有限';Require($x-gt0)'正则化候选超范围'};Require($cand.Count-ge2-and(@($cand|Sort-Object -Unique).Count-eq$cand.Count)-and$reportContract.allowed_evidence_status-contains$report.regularization.evidence_status-and$reportContract.selection_rule_ids-contains$report.regularization.selection_rule)'正则化候选/状态/选择规则非法'
Require($report.regularization.train_split-ne$report.regularization.validation_split-and$report.regularization.train_split-ne$report.regularization.test_split-and$report.regularization.validation_split-ne$report.regularization.test_split)'正则化splits不互斥'
if($report.regularization.evidence_status-eq'Observed'){Require($report.regularization.manifest_ref-eq'manifest.json')'Observed正则化未绑定manifest'}
Require((@($report.cost|?{$_.evidence_status-eq'Observed'}).Count)-eq0-and$report.regularization.evidence_status-ne'Observed')'WP2 toy当前包禁止Observed洗白'
$ph=$cfg.pod.phi;$hh=$cfg.pod.h;$mm0=$cfg.pod.m0;$pm=$cfg.pod.coefficient_prior_mean;$pc=$cfg.pod.coefficient_prior_covariance;$g11=0.;$g12=0.;$g22=0.;$hc1=0.;$hc2=0.;$hm0=0.
Require($ph.Count-eq$hh.Count-and$ph.Count-eq$mm0.Count-and$results.pod.basis_shape[0]-eq$ph.Count-and$results.pod.basis_shape[1]-eq$ph[0].Count)'POD config/结果维数错误'
$podRank=Matrix-Rank @($ph);$gramGeneral=Gram-Matrix @($ph);Require($podRank-eq$ph[0].Count-and[int]$cfg.pod.rank-eq$podRank-and[int]$results.pod.rank-eq$podRank)'POD config/result rank未由一般矩阵算法得到';Require(Is-Symmetric-SPD @($gramGeneral))'POD Gram非SPD';Require(Is-Symmetric-SPD @($pc))'POD prior非对称SPD'
$r=$ph[0].Count;$gl=VChol $gramGeneral;$gd=1.;for($i=0;$i-lt$r;$i++){$gd*=$gl[$i][$i]*$gl[$i][$i]};Require ([Math]::Abs([double]$results.pod.gram_determinant-$gd) -le 1e-12-and[Math]::Abs([double]$results.pod.hausdorff_volume_factor-[Math]::Sqrt($gd))-le1e-12) 'POD Gram/体积错误'
Require ([bool]$results.pod.coefficient_prior_proper) 'POD系数先验非proper'
Require (-not [bool]$results.pod.full_space_kl_reported) '违规报告奇异支撑全维KL'
$s2=[Math]::Pow([double]$cfg.pod.noise_sd,2);$pl=VChol @($pc);$pinv=VInv $pl;$hc=New-Object double[] $r;$hm0=0.;for($k=0;$k-lt$ph.Count;$k++){$hm0+=[double]$hh[$k]*[double]$mm0[$k];for($j=0;$j-lt$r;$j++){$hc[$j]+=[double]$hh[$k]*[double]$ph[$k][$j]}};$prec=@();for($i=0;$i-lt$r;$i++){$row=@();for($j=0;$j-lt$r;$j++){$row+=[double]$pinv[$i][$j]+$hc[$i]*$hc[$j]/$s2};$prec+=,@($row)};$pcl=VChol $prec;$postCov=VInv $pcl;$rhs=New-Object double[] $r;for($i=0;$i-lt$r;$i++){for($j=0;$j-lt$r;$j++){$rhs[$i]+=[double]$pinv[$i][$j]*[double]$pm[$j]};$rhs[$i]+=$hc[$i]*([double]$cfg.pod.observation-$hm0)/$s2};$postMean=VSolve $pcl $rhs;$expectedMean=$hm0;$expectedVar=$s2;for($i=0;$i-lt$r;$i++){$expectedMean+=$hc[$i]*$postMean[$i];Require([Math]::Abs([double]$results.pod.posterior_mean[$i]-$postMean[$i])-le1e-12)'POD后验均值错误';for($j=0;$j-lt$r;$j++){$expectedVar+=$hc[$i]*[double]$postCov[$i][$j]*$hc[$j];Require([Math]::Abs([double]$results.pod.posterior_covariance[$i][$j]-[double]$postCov[$i][$j])-le1e-12)'POD后验协方差错误'}}
Require ([Math]::Abs([double]$results.pod.predictive_mean-$expectedMean) -le 1e-12) 'POD预测均值不符解析值'
Require ([Math]::Abs([double]$results.pod.predictive_variance-$expectedVar) -le 1e-12) 'POD预测方差不符解析值'
$ppm=$hm0;$ppv=$s2;for($i=0;$i-lt$r;$i++){$ppm+=$hc[$i]*[double]$pm[$i];for($j=0;$j-lt$r;$j++){$ppv+=$hc[$i]*[double]$pc[$i][$j]*$hc[$j]}};$expectedLogZ=LogN ([double]$cfg.pod.observation-$ppm) ([Math]::Sqrt($ppv))
Require([Math]::Abs([double]$results.pod.log_z_r-$expectedLogZ)-le1e-12-and[Math]::Abs([double]$results.pod.z_r-[Math]::Exp($expectedLogZ))-le1e-12)'Gaussian Z_r错误'
Require([double]$results.pod.z_r-gt0-and[double]::IsFinite([double]$results.pod.z_r))'Z_r非正或非有限'
$allowedInfo = @('design_eig','realized_information_gain','lomo_forward_kl')
Require ($results.information_records.Count -eq 3) '三类信息量记录不完整'
foreach ($ir in $results.information_records) {
    Require ($allowedInfo.Contains([string]$ir.information_type)) "非法信息量类型 $($ir.information_type)"
    foreach ($field in @('target_variable','conditioning_set','direction','estimator','estimate','mcse')) {
        Require ($ir.PSObject.Properties.Name.Contains($field) -and -not [string]::IsNullOrWhiteSpace([string]$ir.$field)) "信息量记录缺字段 $field"
    }
}
$dirs=@{design_eig='posterior_to_prior';realized_information_gain='posterior_to_prior';lomo_forward_kl='full_to_leave_one_out'}
foreach($ir in $results.information_records){Require($ir.direction-eq$dirs[[string]$ir.information_type])'信息量direction非法';if($ir.information_type-eq'lomo_forward_kl'){Require($ir.PSObject.Properties.Name.Contains('log_z_full')-and$ir.PSObject.Properties.Name.Contains('log_z_leave_out'))'LOMO结构化logZ缺失'}else{Require($ir.PSObject.Properties.Name.Contains('log_z_baseline')-and$ir.PSObject.Properties.Name.Contains('log_z_updated'))'IG结构化logZ缺失'}}
$eig=0.5*[Math]::Log(2.0);$yr=[double]$cfg.information.realized_observation;$rig=0.5*(0.5+($yr/2)*($yr/2)-1-[Math]::Log(.5));$y1=[double]$cfg.information.lomo_observations[0];$y2=[double]$cfg.information.lomo_observations[1];$fm=($y1+$y2)/3;$lm=$y1/2;$lomo=.5*((1/3)/.5+($lm-$fm)*($lm-$fm)/.5-1+[Math]::Log(.5/(1/3)))
$infoCsv=Import-Csv -LiteralPath (Join-Path $output 'information-estimates.csv');Require($infoCsv.Count-eq60)'信息量逐重复记录数错误'
foreach($idx in 0..2){$ir=$results.information_records[$idx];$rr=@($infoCsv|?{$_.information_type-eq$ir.information_type});$vv=@($rr|%{Require([int]$_.outer_budget-eq[int]$ir.outer_budget-and[int]$_.inner_budget-eq[int]$ir.inner_budget)'信息量预算错';[double]$_.estimate});Require($vv.Count-eq[int]$ir.repeats-and(@($rr.seed|sort -Unique).Count-eq$vv.Count))'信息量重复数/独立seed错';$av=($vv|measure -Average).Average;$sd=[Math]::Sqrt((($vv|%{($_-$av)*($_-$av)}|measure -Sum).Sum)/($vv.Count-1));Require([Math]::Abs($av-[double]$ir.estimate)-le1e-12-and[Math]::Abs($sd/[Math]::Sqrt($vv.Count)-[double]$ir.mcse)-le1e-12)'信息量汇总/MCSE不可重算';$truth=@($eig,$rig,$lomo)[$idx];Require([Math]::Abs([double]$ir.analytic_truth-$truth)-le1e-12-and[Math]::Abs(([double]$ir.estimate-$truth)-[double]$ir.bias)-le1e-12)'信息量truth/bias错误';$expectedStatus=if([double]$ir.mcse-le[double]$ir.mcse_max-and[Math]::Abs([double]$ir.bias)-le[double]$ir.absolute_bias_max){'Passed'}else{'Failed'};Require($ir.status-eq$expectedStatus-and$expectedStatus-eq'Passed')'信息量MCSE/偏差hard gate失败'}
foreach($row in $infoCsv){Require-Finite ([double]$row.estimate) '信息量记录出现NaN/Infinity';Require([int]$row.outer_budget-gt0-and[int]$row.inner_budget-gt0)'信息量预算必须为正'}
$seedSets=@{};foreach($type in $allowedInfo){$rr=@($infoCsv|?{$_.information_type-eq$type});$seedSets[$type]=@($rr|%{[int]$_.seed});Require((@($rr.sample_path|Sort-Object -Unique).Count)-eq1)"信息量sample_path不唯一: $type";foreach($r in $rr){Require([int]$r.seed-ne[int]$r.evidence_seed-or$type-eq'design_eig')"信息量outer/evidence seed未分离: $type";if($type-eq'realized_information_gain'){Require([Math]::Abs(([double]$r.outer_mean_log_likelihood-[double]$r.log_z_hat)-[double]$r.estimate)-le1e-12)'RIG raw evidence不能重算estimate'};if($type-eq'lomo_forward_kl'){Require([int]$r.evidence_seed-ne[int]$r.second_evidence_seed-and-not[string]::IsNullOrWhiteSpace($r.log_z_hat)-and-not[string]::IsNullOrWhiteSpace($r.log_z_second_hat))'LOMO inner streams/raw evidence未分离';Require([Math]::Abs(([double]$r.outer_mean_log_likelihood+[double]$r.log_z_hat-[double]$r.log_z_second_hat)-[double]$r.estimate)-le1e-12)'LOMO raw evidence不能重算estimate'}}}
$ly1=[double]$cfg.information.lomo_observations[0];$ly2=[double]$cfg.information.lomo_observations[1];$lfm=($ly1+$ly2)/3;$lfv=1/3
foreach($rrow in @($infoCsv|?{$_.information_type-eq'lomo_forward_kl'})){$irng=[Random]::new([int]$rrow.evidence_seed);$lv=[double[]]@(for($j=0;$j-lt[int]$rrow.inner_budget;$j++){$th=VNextNormal $irng;LogN ($ly1-$th) 1});$irng=[Random]::new([int]$rrow.second_evidence_seed);$fv=[double[]]@(for($j=0;$j-lt[int]$rrow.inner_budget;$j++){$th=VNextNormal $irng;(LogN ($ly1-$th) 1)+(LogN ($ly2-$th) 1)});$irng=[Random]::new([int]$rrow.seed);$om=0.;for($o=0;$o-lt[int]$rrow.outer_budget;$o++){$th=$lfm+[Math]::Sqrt($lfv)*(VNextNormal $irng);$om+=LogN ($ly2-$th) 1};$om/=[int]$rrow.outer_budget;Require([Math]::Abs((VLogMeanExp $lv)-[double]$rrow.log_z_hat)-le1e-12-and[Math]::Abs((VLogMeanExp $fv)-[double]$rrow.log_z_second_hat)-le1e-12-and[Math]::Abs($om-[double]$rrow.outer_mean_log_likelihood)-le1e-12)'LOMO seed/raw evidence不可确定性重演'}
Require((@($seedSets.design_eig+$seedSets.realized_information_gain+$seedSets.lomo_forward_kl|Sort-Object -Unique).Count)-eq3*[int]$cfg.information.repeats)'三类信息量seed集合不互斥'
foreach($ir in $results.information_records){Require($ir.production_no_truth_strategy.Contains('doubled outer/inner budgets')-and$ir.production_no_truth_strategy.Contains('independent seeds'))'无解析真值预算加倍稳定性合同缺失'}
$lz0=LogN 0.0 ([Math]::Sqrt(2.0));$lzy=LogN $yr ([Math]::Sqrt(2.0));$lzLeave=LogN $y1 ([Math]::Sqrt(2.0));$lzFull=$lzLeave+(LogN ($y2-$lm) ([Math]::Sqrt(1.5)))
Require([Math]::Abs([double]$results.information_records[0].log_z_updated-$lz0)-le1e-12)'EIG logZ错误'
Require([Math]::Abs([double]$results.information_records[1].log_z_updated-$lzy)-le1e-12)'RIG logZ错误'
Require([Math]::Abs([double]$results.information_records[2].log_z_full-$lzFull)-le1e-12-and[Math]::Abs([double]$results.information_records[2].log_z_leave_out-$lzLeave)-le1e-12)'LOMO logZ错误'
Require($results.information_records[2].conditioning_set.Contains('y1,y2')-and$results.information_records[2].estimate-ne$results.information_records[1].estimate)'LOMO未与RIG区分'

$rows = Import-Csv -LiteralPath (Join-Path $output 'rjmcmc-records.csv')
Require ($rows.Count -eq 2*[int]$cfg.rjmcmc.records) 'RJMCMC逐例记录数错误'
$rows | ForEach-Object { Check-RjmcmcRecord $_ }
$obs=[double]$cfg.rjmcmc.observation;$noise=[double]$cfg.rjmcmc.noise_sd;$logM0=LogN $obs $noise
$mc=Import-Csv -LiteralPath (Join-Path $output 'rjmcmc-chain.csv');Require($mc.Count-eq40000)'跨模型链截断'
$prev=0;$step=0;foreach($s in $mc){Require([int]$s.step-eq$step)'跨模型链step不连续/未排序';Require(@(0,1)-contains[int]$s.current_state-and@(0,1)-contains[int]$s.proposed_state-and@(0,1)-contains[int]$s.next_state)'跨模型链state越界';Require(@('birth','death')-contains$s.move)'跨模型链move非法';Require-Finite([double]$s.proposal_theta)'跨模型链theta非有限';Require([int]$s.current_state-eq$prev)'跨模型链状态不连续';Require([double]$s.uniform-gt0-and[double]$s.uniform-lt1)'uniform不在(0,1)';$pll=LogN ($obs - [double]$s.proposal_theta) $noise;$expected=if($s.move-eq'birth'){$pll - $logM0}else{$logM0 - $pll};$expected=[Math]::Min(0.0,$expected);Require([Math]::Abs($expected-[double]$s.log_alpha)-le1e-12)'跨模型链log_alpha错误';$ea=([Math]::Log([double]$s.uniform)-lt$expected);Require($ea-eq[bool]::Parse($s.accepted))'跨模型链接受判定错误';$next=if($ea){[int]$s.proposed_state}else{[int]$s.current_state};Require($next-eq[int]$s.next_state)'跨模型链next_state错误';$prev=$next;$step++}
$nn=$mc.Count;$hit=@($mc|?{[int]$_.next_state-eq1}).Count;$ph=$hit/[double]$nn
Require([Math]::Abs($ph-[double]$results.rjmcmc.sampled_model_1_probability)-le1e-12)'模型占比错'
$bc=[int]$results.rjmcmc.batch_count;$bs=[int]$results.rjmcmc.batch_size;Require($bc*$bs-eq$nn-and$bc-ge20)'RJMCMC批均值预算不足';$bmv=@();for($bch=0;$bch-lt$bc;$bch++){$bmv+=(@($mc|select -Skip ($bch*$bs) -First $bs|%{[double]$_.next_state})|measure -Average).Average};$ba=($bmv|measure -Average).Average;$bsd=[Math]::Sqrt((($bmv|%{($_-$ba)*($_-$ba)}|measure -Sum).Sum)/($bc-1));$bmc=$bsd/[Math]::Sqrt($bc);$blo=$ph-2.02269092*$bmc;$bhi=$ph+2.02269092*$bmc
Require([Math]::Abs($bmc-[double]$results.rjmcmc.batch_means_mcse)-le1e-12)'RJMCMC批均值MCSE错'
Require($blo-le[double]$results.rjmcmc.analytic_model_1_probability-and[double]$results.rjmcmc.analytic_model_1_probability-le$bhi)'相关链批均值区间未覆盖解析概率'
$hbc=[int]$results.rjmcmc.doubled_batch_count;$hbs=[int]$results.rjmcmc.doubled_batch_size;$hb=@();for($i=0;$i-lt$hbc;$i++){$hb+=(@($mc|select -Skip ($i*$hbs) -First $hbs|%{[double]$_.next_state})|measure -Average).Average};$ha=($hb|measure -Average).Average;$hsd=[Math]::Sqrt((($hb|%{($_-$ha)*($_-$ha)}|measure -Sum).Sum)/($hbc-1));$hmc=$hsd/[Math]::Sqrt($hbc);$ratio=$hmc/$bmc;Require([Math]::Abs($ratio-[double]$results.rjmcmc.batch_mcse_stability_ratio)-le1e-12-and$ratio-gt.5-and$ratio-lt2)'RJMCMC批大小稳定性失败'
$chains = Import-Csv -LiteralPath (Join-Path $output 'diagnostic-chains.csv')
Require ($chains.Count -eq [int]$cfg.diagnostics.chains*[int]$cfg.diagnostics.draws) '诊断链记录数错误'
for ($c=0; $c -lt [int]$cfg.diagnostics.chains; $c++) {
    $vals = @($chains | Where-Object {[int]$_.chain -eq $c} | ForEach-Object {[double]$_.bimodal})
    Require (($vals | Where-Object {$_ -lt 0}).Count -gt 0 -and ($vals | Where-Object {$_ -gt 0}).Count -gt 0) "链$c未跨模态"
    $tails = @($chains | Where-Object {[int]$_.chain -eq $c} | ForEach-Object {[Math]::Abs([double]$_.heavy_tail)})
    Require (($tails | Measure-Object -Maximum).Maximum -gt 100) "链$c缺重尾"
}
$fc=Import-Csv -LiteralPath (Join-Path $output 'diagnostic-failure-chains.csv');Require($fc.Count-eq1200)'失败诊断链记录数错误'
$sticky=@($fc|?{$_.case-eq'sticky_bimodal'});foreach($c in 0..3){$v=@($sticky|?{[int]$_.chain-eq$c}|%{[double]$_.bimodal});Require(-not(($v|?{$_-lt0}).Count-gt0-and($v|?{$_-gt0}).Count-gt0))'sticky失败夹具意外跨模态'}
$scale=@($fc|?{$_.case-eq'scale_mismatch'});Require((VRhat (VSplits $scale 'bimodal' -rank -fold))-gt[double]$contract.thresholds.rank_normalized_split_rhat_max)'尺度错配夹具未触发folded Rhat'
$tailFail=@($fc|?{$_.case-eq'tail_unexplored'});Require((@($tailFail|%{[double]$_.heavy_tail}|sort -Unique).Count)-eq1)'尾部未探索夹具非恒定'
$failureSummary=Get-Content -Raw (Join-Path $output 'diagnostic-failure-summary.json')|ConvertFrom-Json;Require($failureSummary.Count-eq3)'失败诊断摘要数量错误'
foreach($fs in $failureSummary){foreach($f in @('case','seed','stage','error','exit_code','last_state','status','reason','rank_normalized_split_rhat','folded_split_rhat','bulk_ess','tail_ess','relative_mcse','mode_visits_per_chain','failed_replicate_rate')){Require($fs.PSObject.Properties.Name.Contains($f))"失败摘要缺字段 $($fs.case)/$f"};Require($fs.status-eq'Failed'-and$fs.reason.Count-ge1-and[int]$fs.exit_code-ne0)'失败摘要未Failed/无reason/exit';$cr=@($fc|?{$_.case-eq$fs.case});$xr=VRhat(VSplits $cr 'bimodal' -rank);$xf=VRhat(VSplits $cr 'bimodal' -rank -fold);$xb=VEss(VSplits $cr 'bimodal' -rank);$xu=@($cr|%{[double]$_.heavy_tail}|sort -Unique);$xt=if($xu.Count-lt2){0}else{$xb};$xv=@();foreach($cc in 0..3){$vv=@($cr|?{[int]$_.chain-eq$cc}|%{if([double]$_.bimodal-gt0){1}else{0}});$nv=0;for($ii=1;$ii-lt$vv.Count;$ii++){if($vv[$ii]-ne$vv[$ii-1]){$nv++}};$xv+=$nv};$xm=if($xb-gt0){1/[Math]::Sqrt($xb)}else{1};Require([Math]::Abs($xr-[double]$fs.rank_normalized_split_rhat)-le1e-12-and[Math]::Abs($xf-[double]$fs.folded_split_rhat)-le1e-12-and[Math]::Abs($xb-[double]$fs.bulk_ess)-le1e-12-and$xt-eq[double]$fs.tail_ess-and[Math]::Abs($xm-[double]$fs.relative_mcse)-le1e-12)'失败case指标非原链重算';$why=@();if($xr-gt[double]$contract.thresholds.rank_normalized_split_rhat_max){$why+='rank_rhat'};if($xf-gt[double]$contract.thresholds.rank_normalized_split_rhat_max){$why+='folded_rhat'};if($xb-lt[double]$contract.thresholds.bulk_ess_min){$why+='bulk_ess'};if($xt-lt[double]$contract.thresholds.tail_ess_min){$why+='tail_ess'};if($xm-gt[double]$contract.thresholds.relative_mcse_max){$why+='relative_mcse'};if(($xv|measure -Minimum).Minimum-lt[double]$contract.thresholds.required_mode_visits_per_chain){$why+='mode_visits'};if([double]$fs.failed_replicate_rate-gt[double]$contract.thresholds.failed_replicate_rate_max){$why+='failed_replicate_rate'};if($xu.Count-lt2){$why+='constant_tail'};Require(((@($fs.reason)|Sort-Object)-join'|')-eq(($why|Sort-Object)-join'|'))"failure reason非精确全集: $($fs.case)"}
$reps=Import-Csv -LiteralPath (Join-Path $output 'diagnostic-replicates.csv');Require($reps.Count-eq[int]$cfg.diagnostics.attempted_replicates)'诊断重复记录数错误';foreach($r in $reps){foreach($f in @('evidence_kind','seed','stage','status','error','exit_code','last_state')){Require($r.PSObject.Properties.Name.Contains($f))"诊断重复缺字段 $f"};Require(@('Passed','Failed')-contains$r.status)'诊断重复status非法';if($r.status-eq'Failed'){Require($r.evidence_kind-eq'fault_injection'-and[int]$r.exit_code-ne0-and-not[string]::IsNullOrWhiteSpace($r.error))'失败重复缺fault_injection证据'}else{Require($r.evidence_kind-eq'synthetic_control'-and[int]$r.exit_code-eq0)'成功重复证据/exit错误'}};$failed=@($reps|?{$_.status-eq'Failed'}).Count;$recomputedFailure=$failed/[double]$reps.Count
Require($failed-eq$failureSummary.Count-and$failed-eq[int]$manifest.failed_replicates)'failed repeats非失败摘要实际生成'
foreach($fs in $failureSummary){$rp=@($reps|?{$_.replicate-eq"failure-$($fs.case)"});Require($rp.Count-eq1-and[int]$rp[0].seed-eq[int]$fs.seed-and$rp[0].stage-eq$fs.stage-and$rp[0].error-eq$fs.error-and[int]$rp[0].exit_code-eq[int]$fs.exit_code-and$rp[0].last_state-eq$fs.last_state)'failure summary/replicate未精确关联'}
$d = $results.diagnostics
foreach ($field in $contract.required_fields) { Require ($d.PSObject.Properties.Name.Contains([string]$field)) "诊断缺字段 $field" }
$rs=VSplits @($chains) 'bimodal' -rank;$fs=VSplits @($chains) 'bimodal' -rank -fold;$rr=VRhat $rs;$rf=VRhat $fs;$be=VEss $rs;$hv=[double[]]@($chains|%{[double]$_.heavy_tail});$hs=@($hv|sort);$q05=$hs[[int][math]::Floor(.05*($hs.Count-1))];$q95=$hs[[int][math]::Floor(.95*($hs.Count-1))];$lr=@();$hr=@();$dr=@();foreach($x in $chains){$lr+=[pscustomobject]@{chain=$x.chain;x=if([double]$x.heavy_tail-le$q05){1}else{0}};$hr+=[pscustomobject]@{chain=$x.chain;x=if([double]$x.heavy_tail-ge$q95){1}else{0}};$dr+=[pscustomobject]@{chain=$x.chain;x=if([double]$x.bimodal-gt0){1}else{0}}};$te=[math]::Min((VEss (VSplits $lr 'x')),(VEss (VSplits $hr 'x')));$de=VEss (VSplits $dr 'x');$rm=[math]::Sqrt(.25/$de)/.5
Require([Math]::Abs($rr-[double]$d.rank_normalized_split_rhat)-le1e-12)'Rhat非原始链重算'
Require([Math]::Abs($rf-[double]$d.folded_split_rhat)-le1e-12)'folded Rhat非原始链重算'
Require([Math]::Abs($be-[double]$d.bulk_ess)-le1e-12-and[Math]::Abs($te-[double]$d.tail_ess)-le1e-12)'ESS非原始链重算'
Require([Math]::Abs($rm-[double]$d.relative_mcse)-le1e-9) "MCSE非原始链重算 expected=$rm actual=$($d.relative_mcse)"
Require ([double]$d.rank_normalized_split_rhat -le [double]$contract.thresholds.rank_normalized_split_rhat_max) 'Rhat硬门失败'
Require ([double]$d.bulk_ess -ge [double]$contract.thresholds.bulk_ess_min) 'bulk ESS硬门失败'
Require ([double]$d.tail_ess -ge [double]$contract.thresholds.tail_ess_min) 'tail ESS硬门失败'
Require ([double]$d.relative_mcse -le [double]$contract.thresholds.relative_mcse_max) 'MCSE硬门失败'
Require ([double]$d.failed_replicate_rate -le [double]$contract.thresholds.failed_replicate_rate_max) '失败率硬门失败'
Require([Math]::Abs([double]$d.failed_replicate_rate-$recomputedFailure)-le1e-12)'失败率未由逐重复记录重算'
$vis=@();foreach($c in 0..([int]$cfg.diagnostics.chains-1)){$v=@($chains|?{[int]$_.chain-eq$c}|%{if([double]$_.bimodal-gt0){1}else{0}});$nv=0;for($i=1;$i-lt$v.Count;$i++){if($v[$i]-ne$v[$i-1]){$nv++}};$vis+=$nv};Require (($vis -join ',') -eq (@($d.mode_visits_per_chain)-join ',')) '模态访问非原始链重算'
$calcStatus=if([Math]::Max($rr,$rf)-le[double]$contract.thresholds.rank_normalized_split_rhat_max-and$be-ge[double]$contract.thresholds.bulk_ess_min-and$te-ge[double]$contract.thresholds.tail_ess_min-and$rm-le[double]$contract.thresholds.relative_mcse_max-and($vis|measure -Minimum).Minimum-ge[double]$contract.thresholds.required_mode_visits_per_chain-and[double]$d.failed_replicate_rate-le[double]$contract.thresholds.failed_replicate_rate_max){'Passed'}else{'Failed'}
Require($d.status-eq$calcStatus)'status非原始诊断重算'
Require($results.diagnostics.status-eq'Passed'-and$calcStatus-eq'Passed')'正式package未通过全部hard gates'

if ($SelfTest) {
    $wrapper=Join-Path $toy 'run-wp2-toy.ps1';$before=(Get-FileHash -Algorithm SHA256 (Join-Path $toy 'active-output.json')).Hash
    $parentExe=(Get-Process -Id $PID).Path
    & $parentExe -NoProfile -File (Join-Path $toy 'wp2-toy-worker.ps1') -OutputStage (Join-Path $toy 'output') -CapabilityToken ('0'*64) *> $null;Require($LASTEXITCODE-ne0)'worker直接写output未被capability拒绝'
    foreach($flag in @('-InjectWorkerFailure','-InjectPublishInterruption')){& $parentExe -NoProfile -File $wrapper $flag *> $null;Require($LASTEXITCODE-ne0)"wrapper故障注入未返回非0: $flag";Require((Get-FileHash -Algorithm SHA256 (Join-Path $toy 'active-output.json')).Hash-eq$before)"wrapper故障破坏旧active pointer: $flag"}
    Set-Content -Encoding utf8 (Join-Path $toy '.publish-journal.json') '{'
    $psi=[Diagnostics.ProcessStartInfo]::new($parentExe);$psi.ArgumentList.Add('-NoProfile');$psi.ArgumentList.Add('-File');$psi.ArgumentList.Add($wrapper);$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$rp=[Diagnostics.Process]::Start($psi);while(-not$rp.HasExited){$pp=Get-Content -Raw (Join-Path $toy 'active-output.json')|ConvertFrom-Json;$mp=Join-Path $toy $pp.version_path 'manifest.json';Require((Test-Path $mp)-and(Get-FileHash -Algorithm SHA256 $mp).Hash.ToLowerInvariant()-eq$pp.manifest_sha256)'并发读观察到无效active pointer'};$null=$rp.StandardOutput.ReadToEnd();$re=$rp.StandardError.ReadToEnd();$rp.WaitForExit();$rc=$rp.ExitCode;$rp.Dispose();Require($rc-eq0-and-not(Test-Path (Join-Path $toy '.publish-journal.json')))"截断journal恢复/并发发布失败: $re"
    $attemptDirs=@(Get-ChildItem -Directory (Join-Path $toy 'attempts'));Require($attemptDirs.Count-ge2-and(@($attemptDirs|?{Test-Path (Join-Path $_.FullName 'stderr.log')}).Count)-ge2)'wrapper失败attempt日志未保留'
    $cases=@('target','j','q','jacobian','chain_continuity','uniform','direction','logz','zr','rhat','bulk_ess','tail_ess','mode','mcse','truncation','correlated_additivity','pod_spd','pod_rank','chain_step','move_enum','state_domain','theta_finite','folded','failure_rate','hard_gate_failed','info_status','source_path','manifest_exit','contract_drift','contract_downgrade','cost_contract','regularization_contract','consumer_threshold','stdout_hash','log_path','failure_summary','failure_reason','info_seed_collision','info_sample_path','info_evidence','observed_wash','cost_stage','cost_value','cost_unit','cost_tolerance','cost_iterations','cost_calls','cost_hardware','cost_status','reg_train','reg_validation','reg_test','reg_candidates','reg_rule','reg_boundary','reg_sensitivity','reg_omitted','reg_status')
    $rejected=0;$exe=(Get-Process -Id $PID).Path
    foreach($case in $cases){
        $tmp=Join-Path ([IO.Path]::GetTempPath()) ('wp2-fixture-'+[guid]::NewGuid().ToString('N'));Copy-Item -Recurse -LiteralPath $output -Destination $tmp
        $fixtureDocRoot='';$fixtureSourceRoot=''
        try{
            if($case-in @('cost_contract','regularization_contract','consumer_threshold')){
                $fixtureDocRoot=Join-Path ([IO.Path]::GetTempPath()) ('wp2-docfixture-'+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory $fixtureDocRoot|Out-Null
                foreach($name in @($consumerNames+'06-合成数据验证方案与验收设计.md')){Copy-Item -LiteralPath (Join-Path $root $name) -Destination (Join-Path $fixtureDocRoot $name)}
                if($case-eq'cost_contract'){$f=Join-Path $fixtureDocRoot '贝叶斯三维反演测试算力需求说明.md';(Get-Content -Raw $f).Replace('Krylov','KRYLOV_REMOVED')|Set-Content -Encoding utf8 $f}
                if($case-eq'regularization_contract'){$f=Join-Path $fixtureDocRoot '03-多方法深度融合的核心技术实现路径.md';(Get-Content -Raw $f).Replace('Empirical Bayes','EMPIRICAL_BAYES_REMOVED')|Set-Content -Encoding utf8 $f}
                if($case-eq'consumer_threshold'){$f=Join-Path $fixtureDocRoot '06-合成数据验证方案与验收设计.md';Add-Content -Encoding utf8 $f "`n运行期 Rhat < 1.2 即放行。"}
            }
            if($case-in @('target','j','q','jacobian')){
                $f=Join-Path $tmp 'rjmcmc-records.csv';$a=Import-Csv $f
                if($case-eq'target'){$a[0].log_target_y=[double]$a[0].log_target_y+1}
                if($case-eq'j'){$a[0].j_reverse=0.5}
                if($case-eq'q'){$a[0].log_q_forward=[double]$a[0].log_q_forward+1}
                if($case-eq'jacobian'){$z=$a|?{$_.case-eq'nonunit_split_merge'}|select -First 1;$z.abs_jacobian=1}
                $a|Export-Csv -NoTypeInformation -Encoding utf8 $f
            }elseif($case-in @('chain_continuity','uniform','truncation','chain_step','move_enum','state_domain','theta_finite')){
                $f=Join-Path $tmp 'rjmcmc-chain.csv';$a=Import-Csv $f
                if($case-eq'chain_continuity'){$a[1].current_state=1-[int]$a[1].current_state}
                if($case-eq'uniform'){$a[0].uniform=1.5}
                if($case-eq'chain_step'){$a[1].step=9}
                if($case-eq'move_enum'){$a[0].move='jump'}
                if($case-eq'state_domain'){$a[0].next_state=2}
                if($case-eq'theta_finite'){$a[0].proposal_theta='NaN'}
                if($case-eq'truncation'){$a|select -Skip 1|Export-Csv -NoTypeInformation -Encoding utf8 $f}else{$a|Export-Csv -NoTypeInformation -Encoding utf8 $f}
            }elseif($case-in @('tail_ess','mode')){
                $f=Join-Path $tmp 'diagnostic-chains.csv';$a=Import-Csv $f
                if($case-eq'tail_ess'){foreach($row in $a){$row.heavy_tail=0}}
                if($case-eq'mode'){foreach($row in $a){$row.bimodal=[Math]::Abs([double]$row.bimodal)}}
                $a|Export-Csv -NoTypeInformation -Encoding utf8 $f
            }elseif($case-in @('direction','logz','zr','rhat','bulk_ess','mcse','correlated_additivity','folded','failure_rate','hard_gate_failed','info_status')){
                $f=Join-Path $tmp 'results.json';$o=gc -Raw $f|ConvertFrom-Json
                if($case-eq'direction'){$o.information_records[0].direction='prior_to_posterior'}
                if($case-eq'logz'){$o.information_records[2].log_z_full=[double]$o.information_records[2].log_z_full+1}
                if($case-eq'zr'){$o.pod.z_r=-1}
                if($case-eq'rhat'){$o.diagnostics.rank_normalized_split_rhat=.5}
                if($case-eq'bulk_ess'){$o.diagnostics.bulk_ess=999999}
                if($case-eq'mcse'){$o.diagnostics.relative_mcse=.000001}
                if($case-eq'correlated_additivity'){$o.information_records[0].information_type='additive_contribution'}
                if($case-eq'folded'){$o.diagnostics.folded_split_rhat=.5}
                if($case-eq'failure_rate'){$o.diagnostics.failed_replicate_rate=0}
                if($case-eq'hard_gate_failed'){$o.diagnostics.status='Failed'}
                if($case-eq'info_status'){$o.information_records[0].mcse_max=0;$o.information_records[0].status='Passed'}
                $o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f
            }elseif($case-in @('pod_spd','pod_rank','contract_downgrade')){
                $f=Join-Path $tmp 'config.json';$o=gc -Raw $f|ConvertFrom-Json;if($case-eq'pod_spd'){$o.pod.coefficient_prior_covariance[1][0]=0.1}elseif($case-eq'pod_rank'){$o.pod.rank=2};$o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f
                if($case-eq'contract_downgrade'){Copy-Item -Force (Join-Path $toy 'config.json') (Join-Path $tmp 'config.json');$f=Join-Path $tmp 'diagnostic-contract.json';$o=gc -Raw $f|ConvertFrom-Json;$o.thresholds.rank_normalized_split_rhat_max=1.2;$o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f}
                $fixtureSourceRoot=Join-Path ([IO.Path]::GetTempPath()) ('wp2-sourcefixture-'+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory $fixtureSourceRoot|Out-Null
                foreach($name in @('run-wp2-toy.ps1','wp2-toy-worker.ps1','config.json','diagnostic-contract.json','report-contract.json')){Copy-Item -LiteralPath (Join-Path (Join-Path $root 'validation/wp2-toy') $name) -Destination (Join-Path $fixtureSourceRoot $name)}
                if($case-eq'contract_downgrade'){Copy-Item -Force -LiteralPath $f -Destination (Join-Path $fixtureSourceRoot 'diagnostic-contract.json')}else{Copy-Item -Force -LiteralPath $f -Destination (Join-Path $fixtureSourceRoot 'config.json')}
            }elseif($case-in @('failure_summary','failure_reason')){
                $f=Join-Path $tmp 'diagnostic-failure-summary.json';$o=gc -Raw $f|ConvertFrom-Json;$o[0].status='Passed';$o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f
                if($case-eq'failure_reason'){$o=gc -Raw $f|ConvertFrom-Json;$o[0].status='Failed';$o[0].reason=@('mode_visits');$o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f}
            }elseif($case-eq'info_seed_collision'){
                $f=Join-Path $tmp 'information-estimates.csv';$a=Import-Csv $f;$l=$a|?{$_.information_type-eq'lomo_forward_kl'}|select -First 1;$l.second_evidence_seed=$l.evidence_seed;$a|Export-Csv -NoTypeInformation -Encoding utf8 $f
            }elseif($case-in @('info_sample_path','info_evidence')){
                $f=Join-Path $tmp 'information-estimates.csv';$a=Import-Csv $f;$l=$a|?{$_.information_type-eq'lomo_forward_kl'}|select -First 1;if($case-eq'info_sample_path'){$l.sample_path='posterior_single_observation'}else{$l.log_z_second_hat=[double]$l.log_z_second_hat+1};$a|Export-Csv -NoTypeInformation -Encoding utf8 $f
            }elseif($case-in @('cost_stage','cost_value','cost_unit','cost_tolerance','cost_iterations','cost_calls','cost_hardware','cost_status','reg_train','reg_validation','reg_test','reg_candidates','reg_rule','reg_boundary','reg_sensitivity','reg_omitted','reg_status')){
                $f=Join-Path $tmp 'report.json';$o=gc -Raw $f|ConvertFrom-Json
                if($case-eq'cost_stage'){$o.cost[0].stage=''}
                if($case-eq'cost_value'){$o.cost[0].value='NaN'}
                if($case-eq'cost_unit'){$o.cost[0].unit='widget'}
                if($case-eq'cost_tolerance'){$o.cost[0].tolerance=0}
                if($case-eq'cost_iterations'){$o.cost[0].iterations=-1}
                if($case-eq'cost_calls'){$o.cost[0].calls=-1}
                if($case-eq'cost_hardware'){$o.cost[0].hardware=''}
                if($case-eq'cost_status'){$o.cost[0].evidence_status='Claimed'}
                if($case-eq'reg_train'){$o.regularization.train_split=''}
                if($case-eq'reg_validation'){$o.regularization.validation_split=''}
                if($case-eq'reg_test'){$o.regularization.test_split=''}
                if($case-eq'reg_candidates'){$o.regularization.candidates=@(0.1)}
                if($case-eq'reg_rule'){$o.regularization.selection_rule=''}
                if($case-eq'reg_boundary'){$o.regularization.boundary_policy=''}
                if($case-eq'reg_sensitivity'){$o.regularization.sensitivity_analysis=''}
                if($case-eq'reg_omitted'){$o.regularization.omitted_uncertainty=''}
                if($case-eq'reg_status'){$o.regularization.evidence_status='Claimed'}
                $o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f
            }elseif($case-eq'observed_wash'){
                $f=Join-Path $tmp 'report.json';$o=gc -Raw $f|ConvertFrom-Json;$o.cost[0].evidence_status='Observed';$o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f
            }elseif($case-eq'contract_drift'){
                $f=Join-Path $tmp 'diagnostic-contract.json';$o=gc -Raw $f|ConvertFrom-Json;$o.contract_id='DRIFT';$o|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $f
            }
            $mf=Join-Path $tmp 'manifest.json';$mo=gc -Raw $mf|ConvertFrom-Json
            foreach($p in $mo.files.PSObject.Properties){$p.Value=(Get-FileHash -Algorithm SHA256 (Join-Path $tmp $p.Name)).Hash.ToLowerInvariant()}
            if($case-in @('pod_spd','pod_rank')){($mo.sources|?{$_.path-eq'config.json'}).sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $fixtureSourceRoot 'config.json')).Hash.ToLowerInvariant()};if($case-eq'contract_downgrade'){($mo.sources|?{$_.path-eq'diagnostic-contract.json'}).sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $fixtureSourceRoot 'diagnostic-contract.json')).Hash.ToLowerInvariant()}
            if($case-eq'source_path'){$mo.sources[0].path='../run-wp2-toy.ps1'}
            if($case-eq'manifest_exit'){$mo.exit_code=7}
            if($case-eq'stdout_hash'){$mo.stdout.sha256='0'*64}
            if($case-eq'log_path'){$mo.stdout.path='../stdout.log'}
            $mo|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 $mf
            $args=@('-NoProfile','-File',$MyInvocation.MyCommand.Path,'-OutputOverride',$tmp);if($fixtureDocRoot){$args+=@('-DocumentRootOverride',$fixtureDocRoot)};if($fixtureSourceRoot){$args+=@('-SourceRootOverride',$fixtureSourceRoot)}
            & $exe @args *> $null
            if($LASTEXITCODE-ne0){$rejected++}
        }finally{Remove-Item -Recurse -Force -LiteralPath $tmp;if($fixtureDocRoot-and(Test-Path $fixtureDocRoot)){Remove-Item -Recurse -Force -LiteralPath $fixtureDocRoot};if($fixtureSourceRoot-and(Test-Path $fixtureSourceRoot)){Remove-Item -Recurse -Force -LiteralPath $fixtureSourceRoot}}
    }
    Require($rejected-eq$cases.Count) "SelfTest生产入口仅拒绝$rejected/$($cases.Count)类真实fixture篡改"
}

$global:LASTEXITCODE=0
Write-Output "PASS run_id=$($cfg.run_id) rjmcmc_records=$($rows.Count) chains=$($chains.Count) self_test=$SelfTest"
