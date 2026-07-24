param([switch]$SelfTest,[switch]$AllowPendingSignoff)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @{
  f02='02-全方法深度融合的底层逻辑与理论总纲.md'
  f03='03-多方法深度融合的核心技术实现路径.md'
  a2='附录2-概率化反演结果应用规范与风险管控准则.md'
  a4='附录4-核心算法性能基准测试计划与验收指标.md'
  a5='附录5-真实矿区验证方案.md'
  a12='附录12-全深度概率立方体可视化工具.md'
  a14='附录14-地质先验知识库.md'
}
$text=@{}; foreach($k in $files.Keys){$p=Join-Path $root $files[$k]; if(!(Test-Path $p)){throw "missing $p"}; $text[$k]=Get-Content -Raw $p}
function Need([string]$s,[string]$v,[string]$label){if(!$s.Contains($v)){throw "missing:$label"}}
function Validate-ToyPackage([string]$base){
  $op=Join-Path $base 'output';$mp=Join-Path $op 'manifest.json';$rp=Join-Path $op 'results.json';$cp=Join-Path $op 'ranks.csv';$pp=Join-Path $op 'prior-predictive.csv'
  $config=Join-Path $base 'config.json';$wrapper=Join-Path $base 'run-wp1-toy.ps1';$worker=Join-Path $base 'invoke-wp1-toy-worker.ps1'
  foreach($p in @($config,$wrapper,$worker,$mp,$rp,$cp,$pp)){if(!(Test-Path $p)){throw "toy missing:$p"}}
  $cfg=Get-Content -Raw $config|ConvertFrom-Json;$m=Get-Content -Raw $mp|ConvertFrom-Json;$r=Get-Content -Raw $rp|ConvertFrom-Json;$rows=@(Import-Csv $cp);$priorRows=@(Import-Csv $pp)
  function Check-FiniteConfig($x,[string]$path){
    if($null-eq$x){throw "config null:$path"}
    if($x-is[double]-or$x-is[float]-or$x-is[decimal]){if([double]::IsNaN([double]$x)-or[double]::IsInfinity([double]$x)){throw "config nonfinite:$path"};return}
    if($x-is[int]-or$x-is[long]){return}
    if($x-is[string]){return}
    if($x-is[Collections.IEnumerable]){$i=0;foreach($v in $x){Check-FiniteConfig $v "$path[$i]";$i++};return}
    foreach($p in $x.PSObject.Properties){Check-FiniteConfig $p.Value "$path.$($p.Name)"}
  }
  Check-FiniteConfig $cfg 'config'
  if($m.exit_code-ne0-or$m.status-ne'Synthetic-run'-or$r.status-ne'Synthetic-run'){throw 'toy manifest/result status invalid'}
  foreach($x in @($cfg.repetitions,$r.repetitions,$m.repetitions)){if([int]$x-ne400){throw 'toy R mismatch'}}
  foreach($x in @($cfg.prior_predictive_n,$r.prior_predictive_n,$m.prior_predictive_n)){if([int]$x-ne10000){throw 'toy prior N mismatch'}}
  foreach($x in @($cfg.posterior_draws,$r.posterior_draws,$m.posterior_draws)){if([int]$x-ne1000){throw 'toy draws mismatch'}}
  if(($cfg|ConvertTo-Json -Depth 20 -Compress)-ne($r.config_snapshot|ConvertTo-Json -Depth 20 -Compress)-or($cfg|ConvertTo-Json -Depth 20 -Compress)-ne($m.config_snapshot|ConvertTo-Json -Depth 20 -Compress)){throw 'config snapshot mismatch'}
  $pairs=@{config=$config;wrapper=$wrapper;worker=$worker;results=$rp;ranks=$cp;prior_predictive=$pp}
  foreach($k in $pairs.Keys){$got=(Get-FileHash $pairs[$k] -Algorithm SHA256).Hash.ToLower();if($got-ne$m.sha256.$k){throw "toy hash mismatch:$k"}}
  $anchor=Join-Path (Split-Path $base -Parent) 'wp1-toy-root-anchor.sha256'
  if(!(Test-Path $anchor)){throw 'root anchor missing'};$parts=(Get-Content -Raw $anchor).Trim()-split'\s+'
  if($parts.Count-lt2-or$parts[1]-ne'wp1-toy/output/manifest.json'-or$parts[0]-ne((Get-FileHash $mp -Algorithm SHA256).Hash.ToLower())){throw 'root anchor mismatch'}
  if([string]::IsNullOrWhiteSpace($cfg.run_id)-or$cfg.run_id-notmatch'^[A-Z0-9][A-Z0-9-]{7,63}$'){throw 'run_id format'}
  $required=@('run_id','toy','variant','parameter','rep','seed','status','truth','obs1','obs2','rank','hit_90','hit_95')
  foreach($v in $required){if($rows[0].PSObject.Properties.Name-notcontains$v){throw "CSV field missing:$v"}}
  $keys=@('corr_t/main/m','corr_t/adversarial/m','shared_xi/main/m','shared_xi/main/xi','shared_xi/adversarial/m')
  function VW([int]$k,[int]$n){$z=1.95996398454;$p=$k/$n;$den=1+$z*$z/$n;$ctr=($p+$z*$z/(2*$n))/$den;$half=$z*[math]::Sqrt($p*(1-$p)/$n+$z*$z/(4*$n*$n))/$den;@(($ctr-$half),($ctr+$half))}
  $sumAttempt=0;$sumOK=0;$sumFail=0;$expectedRecords=@{}
  foreach($key in $keys){$p=$key-split'/';$x=@($rows|Where-Object{$_.toy-eq$p[0]-and$_.variant-eq$p[1]-and$_.parameter-eq$p[2]});if($x.Count-ne400){throw "CSV truncated/duplicate:$key"}
    $seen=@{};foreach($q in $x){if($q.run_id-ne$cfg.run_id){throw 'CSV run_id mismatch'};$id=[int]$q.rep;if($seen.ContainsKey($id)){throw "duplicate rep:$key/$id"};$seen[$id]=1
      $rootSeed=if($q.toy-eq'corr_t'){[int]$cfg.corr_t.seed}else{[int]$cfg.shared_xi.seed};$expected=$rootSeed+$id;if([int]$q.seed-ne$expected){throw "seed mismatch:$key/$id"}
      if($q.status-eq'ok'){foreach($v in @($q.truth,$q.obs1,$q.obs2,$q.rank,$q.hit_90,$q.hit_95)){if($v-eq''-or[double]::IsNaN([double]$v)-or[double]::IsInfinity([double]$v)){throw "non-finite CSV:$key/$id"}};if([int]$q.rank-lt0-or[int]$q.rank-gt1000-or"$([int]$q.rank)"-ne$q.rank){throw 'rank bounds/integer'};if($q.hit_90-notin@('0','1')-or$q.hit_95-notin@('0','1')){throw 'hit domain'}}elseif($q.status-ne'failed'){throw 'unknown row status'}
    }
    $ok=@($x|Where-Object status -eq 'ok');$fail=$x.Count-$ok.Count;$bins=New-Object int[] 20;foreach($q in $ok){$bins[[math]::Min(19,[int][math]::Floor(([int]$q.rank)*20/1001))]++}
    $s=@($r.summaries|Where-Object model -eq $key);if($s.Count-ne1){throw "summary identity:$key"};$s=$s[0]
    if([int]$s.attempted-ne$x.Count-or[int]$s.succeeded-ne$ok.Count-or[int]$s.failed-ne$fail-or($s.rank_bins-join',')-ne($bins-join',')){throw "summary count mismatch:$key"}
    $expected=$ok.Count/20;$chi=0.0;foreach($n in $bins){$chi+=($n-$expected)*($n-$expected)/$expected}
    if([math]::Abs([double]$s.rank_chi_square-$chi)-gt1e-12){throw "rank chi-square mismatch:$key"}
    foreach($lev in @(90,95)){$hits=@($ok|Where-Object {$_."hit_$lev"-eq'1'}).Count;$est=$hits/$ok.Count;$wi=VW $hits $ok.Count;if([math]::Abs([double]$s."interval_estimate_$lev"-$est)-gt1e-12-or[math]::Abs([double]$s."interval_wilson95_$lev"[0]-$wi[0])-gt1e-12-or[math]::Abs([double]$s."interval_wilson95_$lev"[1]-$wi[1])-gt1e-12){throw "coverage mismatch:$key/$lev"};$expectedRecords["$key|coverage|$lev"]=[pscustomobject]@{type='parameter_interval_coverage';nominal=$lev/100;statistic='interval_hit_rate';estimate=$est;interval=$wi}}
    $expectedRecords["$key|sbc"]=[pscustomobject]@{type='sbc_rank';nominal=$null;statistic='rank_chi_square';estimate=$chi;interval=$null}
    $sumAttempt+=$x.Count;$sumOK+=$ok.Count;$sumFail+=$fail
  }
  if([int]$r.attempted-ne$sumAttempt-or[int]$r.succeeded-ne$sumOK-or[int]$r.failed-ne$sumFail){throw 'global attempted/succeeded/failed mismatch'}
  foreach($t in @('corr_t','shared_xi')){$pr=@($priorRows|Where-Object toy -eq $t);if($pr.Count-ne10000-or(@($pr.sample|Sort-Object -Unique)).Count-ne10000){throw "prior rows:$t"};foreach($ch in @('channel1','channel2')){$vals=[double[]]@($pr.$ch);[array]::Sort($vals);$mean=($vals|Measure-Object -Average).Average;$z=$r.prior_predictive.$t.$ch;if([int]$z.n-ne10000-or[math]::Abs($z.mean-$mean)-gt1e-12){throw "prior mean:$t/$ch"};foreach($q in @(@('q01',.01),@('q05',.05),@('q50',.5),@('q95',.95),@('q99',.99))){$got=$vals[[int][math]::Floor([double]$q[1]*9999)];if([math]::Abs([double]$z.($q[0])-$got)-gt1e-12){throw "prior quantile:$t/$ch/$($q[0])"}}}}
  $fields=@('calibration_type','nominal_level','sampling_unit','split_id','statistic','estimate','uncertainty_interval','sharpness','status','evidence_id','run_id')
  if($r.calibration_records.Count-ne15){throw 'calibration record count'};$seenRecords=@{}
  foreach($rec in $r.calibration_records){
    foreach($f in $fields){if($rec.PSObject.Properties.Name-notcontains$f){throw "calibration field:$f"}}
    $rk=if($rec.calibration_type-eq'parameter_interval_coverage'){"$($rec.split_id)|coverage|$([int]([double]$rec.nominal_level*100))"}elseif($rec.calibration_type-eq'sbc_rank'){"$($rec.split_id)|sbc"}else{throw 'calibration type'}
    if(!$expectedRecords.ContainsKey($rk)-or$seenRecords.ContainsKey($rk)){throw "calibration matrix:$rk"};$seenRecords[$rk]=1;$e=$expectedRecords[$rk]
    if($rec.calibration_type-ne$e.type-or$rec.statistic-ne$e.statistic-or$rec.sampling_unit-ne'SBC repetition'-or$rec.status-ne'Synthetic-run'-or$rec.evidence_id-ne'WP1-TOY'-or$rec.run_id-ne$cfg.run_id-or$null-ne$rec.sharpness){throw "calibration metadata:$rk"}
    if($null-eq$e.nominal){if($null-ne$rec.nominal_level-or$null-ne$rec.uncertainty_interval){throw "calibration null semantics:$rk"}}else{if([math]::Abs([double]$rec.nominal_level-[double]$e.nominal)-gt1e-12-or$rec.uncertainty_interval.Count-ne2-or[math]::Abs([double]$rec.uncertainty_interval[0]-[double]$e.interval[0])-gt1e-12-or[math]::Abs([double]$rec.uncertainty_interval[1]-[double]$e.interval[1])-gt1e-12){throw "calibration interval:$rk"}}
    if([math]::Abs([double]$rec.estimate-[double]$e.estimate)-gt1e-12){throw "calibration estimate:$rk"}
  }
  if($seenRecords.Count-ne$expectedRecords.Count){throw 'calibration matrix incomplete'}
  # Config-level finite/SPD gate.
  $S=$cfg.corr_t.sigma;$a=[double]$S[0][0];$b=[double]$S[0][1];$c=[double]$S[1][0];$d=[double]$S[1][1]
  foreach($v in @($a,$b,$c,$d,[double]$cfg.corr_t.nu,[double]$cfg.shared_xi.xi_sd)){if([double]::IsNaN($v)-or[double]::IsInfinity($v)){throw 'config nonfinite'}}
  if([math]::Abs($b-$c)-gt1e-12-or$a-le0-or$a*$d-$b*$b-le1e-10){throw 'config Sigma non-SPD/ill-conditioned'}
  if($cfg.corr_t.grid_min-ge$cfg.corr_t.grid_max-or$cfg.corr_t.grid_count-lt101-or$cfg.corr_t.nu-le0-or$cfg.shared_xi.a.Count-ne2-or$cfg.shared_xi.b.Count-ne2-or$cfg.shared_xi.noise_sd.Count-ne2-or@($cfg.shared_xi.noise_sd|Where-Object{$_-le0}).Count){throw 'config dimensions/domain'}
}
function Section([string]$s,[string]$start,[string]$end){
  $i=$s.IndexOf($start); if($i -lt 0){throw "section start missing:$start"}
  $j=$s.IndexOf($end,$i+$start.Length); if($j -lt 0){throw "section end missing:$end"}
  $s.Substring($i,$j-$i)
}
function Validate-TargetSections([string]$s02,[string]$s03,[string]$a4,[string]$a5){
  if(([regex]::Matches($s02,'#### 2\.3\.1')).Count-ne1){throw 'duplicate/missing 2.3.1 heading'}
  foreach($v in @('p(m\mid z,\Theta)','p(\xi\mid\Theta)','p(d\mid m,z,\xi,\delta,\delta_{\rm surr},\lambda,\Theta,h)')){if(!$s02.Contains($v)){throw "DAG/joint factor missing:$v"}}
  $sidCounts=@{'interpretation:campaign:v1'=2;'property-db:campaign:v1'=2;'borehole-conditioning:campaign:v1'=1;'geophysics-observation:campaign:v1'=1}
  foreach($sid in $sidCounts.Keys){if(([regex]::Matches($s02,[regex]::Escape($sid))).Count-ne$sidCounts[$sid]){throw "source-id duplicate/missing:$sid"}}
  $bad02=@(
    '\$\\eta\$表示跨方法共享',
    '确保了噪声参数估计的收敛性',
    '5\s*[-—]\s*10次迭代',
    '下界\s*(?:>=|≥|\\geq)[^\r\n]{0,20}保证后验\s*proper',
    'p\(m\|\\theta\)\s*=\s*p_\{?str',
    '\\prod_\{i=1\}\^\{N_k\}[^\r\n]{0,150}\\Gamma',
    '从根本上解决',
    'p\(m,z,\\xi,\\delta_\{1:K\},\\Theta\\mid\s*[dD]\)',
    '\$\\lambda\$\s*\|\s*正数/正向量',
    'p_\{geo\}[^\r\n]{0,100}钻孔数据作为硬数据',
    'p\(\\delta_\{\\rm surr\}\\mid\\Theta\)',
    'x=\(m,z,h\)',
    '\\xi[^\r\n]{0,60}(?:处理|岩石物理)nuisance',
    'p\(d,m,z,\\xi,\\delta,\\delta_\{\\rm surr\},\\lambda,\\Theta\\mid h\)',
    '可通过互相关分析从实测数据中估计'
  )
  foreach($r in $bad02){if($s02 -match $r){throw "02 residual:$r"}}
  $bad03=@('浅部（0-1500m）','90%以上的实测数据落在对应包络内','PPC检验覆盖率','可加性（容斥展开）','数据质量越高、与模型相关性越强')
  foreach($r in $bad03){if($s03 -match [regex]::Escape($r)){throw "03 residual:$r"}}
  foreach($v in @('R=400','1000个posterior draws','SigmaA=[[1.0,0.7],[0.7,1.0]]','a=[1.0,0.6]','b=[0.8,-0.5]','Wilson 95%','共同失败规则')){if(!$a4.Contains($v)){throw "a4 incomplete:$v"}}
  if($a5 -match '预测区间覆盖率\s*\|\s*真值落95%CI的比例'){throw 'a5 legacy coverage row'}
  foreach($v in @('完整钻孔为最小cluster','邻孔的测井、岩芯物性、编录、化验、地质解释','探索性例外','不得为满足门槛补写/虚构钻孔')){if(!$a5.Contains($v)){throw "a5 missing:$v"}}
}
$sec02=Section $text.f02 '#### 2.3.1' '#### 2.3.4'
$sec03=Section $text.f03 '### 3.4 ' '### 3.5 '
Validate-TargetSections $sec02 $sec03 $text.a4 $text.a5
$toy=Join-Path $root 'validation/wp1-toy'
Validate-ToyPackage $toy
$signRoot=Join-Path $root 'WP1-signoff-input-root.sha256';if(!(Test-Path $signRoot)){throw 'signoff input root missing'}
$sl=@(Get-Content $signRoot);$decl=($sl|Where-Object{$_-match'^root  '})-replace'^root  ',''
$entries=@($sl|Where-Object{$_-match'^[0-9a-f]{64}  '}|ForEach-Object{$p=$_ -split'  ',2;[pscustomobject]@{hash=$p[0];path=$p[1]}}|Sort-Object path)
$rootLines=@();foreach($e in $entries){$fp=Join-Path $root $e.path;if(!(Test-Path $fp)){throw "signoff input missing:$($e.path)"};$h=(Get-FileHash $fp -Algorithm SHA256).Hash.ToLower();if($h-ne$e.hash){throw "signoff input drift:$($e.path)"};$rootLines+="$h  $($e.path)"}
$bytes=[Text.Encoding]::UTF8.GetBytes(($rootLines-join"`n")+"`n");$sha=[Security.Cryptography.SHA256]::Create();$calc=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLower()
if($decl-ne$calc){throw 'signoff input root mismatch'}
$signoffFiles=@('WP1-贝叶斯UQ独立代理签核.md','WP1-地球物理独立代理签核.md')
foreach($name in $signoffFiles){
  $sp=Join-Path $root $name
  if(!(Test-Path $sp)){if($AllowPendingSignoff){continue}else{throw "signoff missing:$name"}}
  $st=Get-Content -Raw $sp
  if($AllowPendingSignoff){continue}
  if($st-notmatch '(?m)^>\s*状态：\*\*PASS\*\*|(?m)^-\s*结论：\*\*PASS\*\*'){throw "signoff not PASS:$name"}
  if($st-notmatch [regex]::Escape($decl)){throw "signoff root binding mismatch:$name"}
}
foreach($v in @('WP1统一定义','\eta_{\rm IP}','单一标量','T_h(d^{raw})','[Re,Im]','TDIP','SIP/FDIP','TEM','MT/AMT/CSAMT','WFEM','Cole–Cole','由WP3方法契约确定','F_k^h(m,z,\xi)','\xi_g','\xi_a','\xi_t','\mid h,D_{\rm val}','\Theta_{\rm surr}\subset\Theta','x=(m,z,\xi,h)','绝不再次进入$p(d\mid\cdots)$','不得再次进入$B$','不得再把$\Sigma_{kl}^{cross}$额外叠加一次','M_kK_uM_l^\mathsf T','无共址、同批次','GP(0,K_\delta)','高保真验证残差','唯一联合分解','Cholesky','Full Bayes','Empirical Bayes','source-id规则','S_z\cap S_m')){Need $text.f02 $v "02/$v"}
foreach($v in @('observation','parameter','model_discrepancy','surrogate','scenario','ppc','holdout_predictive_calibration','sbc_rank','parameter_interval_coverage','field_prediction_interval_coverage')){Need $text.f03 $v "03/$v"}
foreach($k in @('a2','a5','a12')){foreach($v in @('calibration_type','nominal_level','sampling_unit','split_id','uncertainty_interval','sharpness','evidence_id','run_id')){Need $text[$k] $v "$k/$v"}}
foreach($v in @('WP1-TOY-CORR-T','2026071701','WP1-TOY-SHARED-XI','2026071702','prior predictive','SBC','对抗模型','Planned')){Need $text.a4 $v "a4/$v"}
foreach($v in @('标准化参数尺度','proper超先验','source-id','不得重复使用既有数据')){Need $text.a14 $v "a14/$v"}
if($text.a14 -match '\|\s*(强约束|中等约束|弱约束).*\|\s*0\.[1-9]'){throw 'legacy prior weight remains in governing table'}
if($text.a4 -notmatch 'SigmaA=\[\[([0-9.]+),([0-9.]+)\],\[([0-9.]+),([0-9.]+)\]\]'){throw 'toy SigmaA not parseable'}
$a=[double]$Matches[1];$b=[double]$Matches[2];$bt=[double]$Matches[3];$c=[double]$Matches[4]
if([math]::Abs($b-$bt) -gt 1e-12 -or $a -le 0 -or ($a*$c-$b*$b) -le 0){throw 'documented toy SigmaA is not SPD'}
if($SelfTest){
  $caught=0
  foreach($case in @(
    @{a=$sec02+'`n$\eta$表示跨方法共享nuisance';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`n从根本上解决传统权重问题';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`np(m,z,\xi,\delta_{1:K},\Theta\mid D)';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`n$\lambda$ | 正数/正向量';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02;b=$sec03+'`n可加性（容斥展开）';d=$text.a4;c=$text.a5},
    @{a=$sec02;b=$sec03;d=($text.a4 -replace 'R=400','R=40');c=$text.a5},
    @{a=$sec02;b=$sec03;d=($text.a4 -replace 'SigmaA=\[\[1.0,0.7\],\[0.7,1.0\]\]','SigmaA=[[1.0,2.0],[2.0,1.0]]');c=$text.a5},
    @{a=$sec02;b=$sec03;d=$text.a4;c=$text.a5+'`n| 预测区间覆盖率 | 真值落95%CI的比例 |'},
    @{a=$sec02+'`np(\delta_{\rm surr}\mid\Theta)';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`nx=(m,z,h)';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`n$\xi$表示处理或岩石物理nuisance';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=($sec02 -replace '\\mid h,D_\{\\rm val\}','\mid h');b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`n可通过互相关分析从实测数据中估计';b=$sec03;d=$text.a4;c=$text.a5}
    @{a=($sec02 -replace [regex]::Escape('p(\xi\mid\Theta)'),'p_xi_REMOVED');b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`nproperty-db:campaign:v1';b=$sec03;d=$text.a4;c=$text.a5},
    @{a=$sec02+'`n#### 2.3.1';b=$sec03;d=$text.a4;c=$text.a5}
  )){
    try {
      Validate-TargetSections $case.a $case.b $case.d $case.c
      if($case.d -match 'SigmaA=\[\[([0-9.]+),([0-9.]+)\],\[([0-9.]+),([0-9.]+)\]\]'){
        $x=[double]$Matches[1];$y=[double]$Matches[2];$w=[double]$Matches[3];$z=[double]$Matches[4]
        if([math]::Abs($y-$w)-gt 1e-12 -or $x*$z-$y*$y-le 0){throw 'negative SPD'}
      }
    } catch {$caught++}
  }
  if($caught -ne 16){throw "self-test negatives not rejected: $caught/16"}
  function Sync-Fixture([string]$tb){
    $mp=Join-Path $tb 'output/manifest.json';$m=Get-Content -Raw $mp|ConvertFrom-Json
    $m.sha256.config=(Get-FileHash (Join-Path $tb 'config.json') -Algorithm SHA256).Hash.ToLower()
    $m.sha256.results=(Get-FileHash (Join-Path $tb 'output/results.json') -Algorithm SHA256).Hash.ToLower()
    $m.sha256.ranks=(Get-FileHash (Join-Path $tb 'output/ranks.csv') -Algorithm SHA256).Hash.ToLower()
    $m.sha256.prior_predictive=(Get-FileHash (Join-Path $tb 'output/prior-predictive.csv') -Algorithm SHA256).Hash.ToLower()
    $m|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $mp
    "$(((Get-FileHash $mp -Algorithm SHA256).Hash.ToLower()))  wp1-toy/output/manifest.json"|Set-Content -Encoding ascii (Join-Path (Split-Path $tb -Parent) 'wp1-toy-root-anchor.sha256')
  }
  $integrationRoot=Join-Path ([IO.Path]::GetTempPath()) ("wp1-integration-"+[guid]::NewGuid());$integrationToy=Join-Path $integrationRoot 'wp1-toy'
  try{New-Item -ItemType Directory $integrationRoot|Out-Null;Copy-Item $toy $integrationToy -Recurse;& (Join-Path $integrationToy 'run-wp1-toy.ps1')|Out-Null;Validate-ToyPackage $integrationToy}
  finally{if(Test-Path $integrationRoot){Remove-Item $integrationRoot -Recurse -Force}}
  function New-RunnerFixture {
    $tr=Join-Path ([IO.Path]::GetTempPath()) ("wp1-runner-"+[guid]::NewGuid())
    $tt=Join-Path $tr 'wp1-toy'
    New-Item -ItemType Directory $tr|Out-Null
    Copy-Item $toy $tt -Recurse
    Copy-Item (Join-Path (Split-Path $toy -Parent) 'wp1-toy-root-anchor.sha256') $tr
    [pscustomobject]@{Root=$tr;Toy=$tt;Anchor=(Join-Path $tr 'wp1-toy-root-anchor.sha256')}
  }
  $fx=New-RunnerFixture
  try{
    $lock=Join-Path $fx.Root '.wp1-toy.lock'
    [IO.File]::WriteAllText($lock,'self-test lock',[Text.Encoding]::UTF8)
    $rejected=$false
    try{& (Join-Path $fx.Toy 'run-wp1-toy.ps1')|Out-Null}catch{$rejected=$_.Exception.Message -match 'exclusive lock held'}
    if(!$rejected-or!(Test-Path $lock)){throw 'runner lock conflict self-test failed'}
  }finally{if(Test-Path $fx.Root){Remove-Item $fx.Root -Recurse -Force}}
  foreach($fault in @('WorkerFailure','PublishAfterOutputSwap')){
    $fx=New-RunnerFixture
    try{
      $beforeOutput=(Get-FileHash (Join-Path $fx.Toy 'output/manifest.json') -Algorithm SHA256).Hash
      $beforeAnchor=(Get-FileHash $fx.Anchor -Algorithm SHA256).Hash
      $beforeStages=@(Get-ChildItem $fx.Toy -Directory -Filter '.stage-*').Count
      $raised=$false
      try{& (Join-Path $fx.Toy 'run-wp1-toy.ps1') -TestFault $fault|Out-Null}catch{$raised=$true}
      $afterOutput=(Get-FileHash (Join-Path $fx.Toy 'output/manifest.json') -Algorithm SHA256).Hash
      $afterAnchor=(Get-FileHash $fx.Anchor -Algorithm SHA256).Hash
      $fm=Join-Path $fx.Toy 'last-failure-manifest.json'
      if(!$raised-or$beforeOutput-ne$afterOutput-or$beforeAnchor-ne$afterAnchor-or!(Test-Path $fm)){throw "runner failure preservation self-test failed:$fault"}
      $failure=Get-Content -Raw $fm|ConvertFrom-Json
      $afterStages=@(Get-ChildItem $fx.Toy -Directory -Filter '.stage-*').Count
      if($failure.status-ne'Failed'-or(Test-Path (Join-Path $fx.Root '.wp1-toy.lock'))-or$afterStages-ne$beforeStages){throw "runner failure cleanup self-test failed:$fault"}
    }finally{if(Test-Path $fx.Root){Remove-Item $fx.Root -Recurse -Force}}
  }
  foreach($fault in @('RecoveryAfterJournal','RecoveryAfterOldMove','RecoveryAfterOutputMove','RecoveryAfterAnchorMove')){
    $fx=New-RunnerFixture
    try{
      $beforeOutput=(Get-FileHash (Join-Path $fx.Toy 'output/manifest.json') -Algorithm SHA256).Hash
      $beforeAnchor=(Get-FileHash $fx.Anchor -Algorithm SHA256).Hash
      & (Join-Path $fx.Toy 'run-wp1-toy.ps1') -TestFault $fault|Out-Null
      $journal=Join-Path $fx.Root '.wp1-toy-publish.json'
      if(!(Test-Path $journal)){throw "runner recovery journal missing:$fault"}
      & (Join-Path $fx.Toy 'run-wp1-toy.ps1') -RecoverOnly|Out-Null
      $afterOutput=(Get-FileHash (Join-Path $fx.Toy 'output/manifest.json') -Algorithm SHA256).Hash
      $afterAnchor=(Get-FileHash $fx.Anchor -Algorithm SHA256).Hash
      if($beforeOutput-ne$afterOutput-or$beforeAnchor-ne$afterAnchor-or(Test-Path $journal)-or(Test-Path (Join-Path $fx.Root '.wp1-toy.lock'))){throw "runner interrupted recovery self-test failed:$fault"}
      Validate-ToyPackage $fx.Toy
    }finally{if(Test-Path $fx.Root){Remove-Item $fx.Root -Recurse -Force}}
  }
  $fx=New-RunnerFixture
  try{
    $beforeOutput=(Get-FileHash (Join-Path $fx.Toy 'output/manifest.json') -Algorithm SHA256).Hash
    $beforeAnchor=(Get-FileHash $fx.Anchor -Algorithm SHA256).Hash
    & (Join-Path $fx.Toy 'run-wp1-toy.ps1') -TestFault RecoveryAfterOldMove|Out-Null
    $journal=Join-Path $fx.Root '.wp1-toy-publish.json'
    [IO.File]::WriteAllBytes($journal,[Text.Encoding]::UTF8.GetBytes('{"schema_version":1,"phase":'))
    & (Join-Path $fx.Toy 'run-wp1-toy.ps1') -RecoverOnly|Out-Null
    $afterOutput=(Get-FileHash (Join-Path $fx.Toy 'output/manifest.json') -Algorithm SHA256).Hash
    $afterAnchor=(Get-FileHash $fx.Anchor -Algorithm SHA256).Hash
    $residue=@((Join-Path $fx.Toy '.publish-old'),(Join-Path $fx.Root '.wp1-toy-anchor.publish-tmp'),(Join-Path $fx.Root '.wp1-toy-anchor.publish-backup'),$journal,(Join-Path $fx.Root '.wp1-toy.lock'))|Where-Object{Test-Path $_}
    if($beforeOutput-ne$afterOutput-or$beforeAnchor-ne$afterAnchor-or$residue.Count){throw 'runner torn-journal recovery self-test failed'}
    Validate-ToyPackage $fx.Toy
  }finally{if(Test-Path $fx.Root){Remove-Item $fx.Root -Recurse -Force}}
  $mutations=@(
    {param($tb)$p=Join-Path $tb 'output/results.json';$x=Get-Content -Raw $p|ConvertFrom-Json;$x.summaries[0].interval_estimate_90=.123;$x|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'output/results.json';$x=Get-Content -Raw $p|ConvertFrom-Json;$x.summaries[0].rank_chi_square=999;$x|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'output/results.json';$x=Get-Content -Raw $p|ConvertFrom-Json;$x.calibration_records[0].estimate=.123;$x|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'output/results.json';$x=Get-Content -Raw $p|ConvertFrom-Json;$x.calibration_records[0].split_id='shared_xi/main/m';$x|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'output/ranks.csv';$x=@(Import-Csv $p);$x[0..($x.Count-2)]|Export-Csv -NoTypeInformation -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'output/ranks.csv';$x=@(Import-Csv $p);$x[0].run_id='WRONG';$x|Export-Csv -NoTypeInformation -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'config.json';$x=Get-Content -Raw $p|ConvertFrom-Json;$x.shared_xi.a[0]=9.0;$x|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $p;Sync-Fixture $tb},
    {param($tb)$p=Join-Path $tb 'config.json';$x=Get-Content -Raw $p|ConvertFrom-Json;$x.corr_t.sigma=@(@(1.0,.999999999999),@(.999999999999,1.0));$x|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 $p;Sync-Fixture $tb}
  )
  $pkgCaught=0
  foreach($mut in $mutations){$tmpRoot=Join-Path ([IO.Path]::GetTempPath()) ("wp1-fixture-"+[guid]::NewGuid());$tb=Join-Path $tmpRoot 'wp1-toy'
    try{New-Item -ItemType Directory $tmpRoot|Out-Null;Copy-Item $toy $tb -Recurse;Copy-Item (Join-Path (Split-Path $toy -Parent) 'wp1-toy-root-anchor.sha256') $tmpRoot;&$mut $tb;try{Validate-ToyPackage $tb}catch{$pkgCaught++}}
    finally{if(Test-Path $tmpRoot){Remove-Item $tmpRoot -Recurse -Force}}
  }
  if($pkgCaught-ne$mutations.Count){throw "package self-test negatives not rejected:$pkgCaught/$($mutations.Count)"}
}
"PASS files=$($files.Count) dag_factors=8 calibration_types=5 toy_models=2 self_test=$([bool]$SelfTest)"
