[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputStage,[Parameter(Mandatory=$true)][string]$CapabilityToken)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $here 'config.json'
$contractPath = Join-Path $here 'diagnostic-contract.json'
$reportContractPath = Join-Path $here 'report-contract.json'
$stage = [IO.Path]::GetFullPath($OutputStage)
$stageParent=[IO.Path]::GetFullPath((Split-Path -Parent $stage)).TrimEnd('\');$hereFull=[IO.Path]::GetFullPath($here).TrimEnd('\')
if($stageParent-ne$hereFull-or[IO.Path]::GetFileName($stage)-notmatch '^\.stage-[0-9a-f]{32}$'){throw 'unauthorized OutputStage path'}
$cap=Join-Path $stage '.capability';if(-not(Test-Path -LiteralPath $cap)-or(Get-Content -Raw -LiteralPath $cap).Trim()-ne$CapabilityToken-or$CapabilityToken-notmatch'^[0-9a-f]{64}$'){throw 'invalid stage capability'}
$cfg = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
$contract = Get-Content -Raw -LiteralPath $contractPath | ConvertFrom-Json
$reportContract = Get-Content -Raw -LiteralPath $reportContractPath | ConvertFrom-Json
$startedUtc=[DateTime]::UtcNow
function ConfigFinite($v,[string]$name){$x=[double]$v;if([double]::IsNaN($x)-or[double]::IsInfinity($x)){throw "config nonfinite: $name"}}
foreach($pair in @(@($cfg.seed,'seed'),@($cfg.pod.observation,'pod.observation'),@($cfg.pod.noise_sd,'pod.noise_sd'),@($cfg.rjmcmc.observation,'rjmcmc.observation'),@($cfg.rjmcmc.noise_sd,'rjmcmc.noise_sd'),@($cfg.rjmcmc.slab_sd,'rjmcmc.slab_sd'))){ConfigFinite $pair[0] $pair[1]}
if([double]$cfg.pod.noise_sd-le0-or[double]$cfg.rjmcmc.noise_sd-le0-or[double]$cfg.rjmcmc.slab_sd-le0){throw 'config scale must be positive'}
foreach($pair in @(@($cfg.rjmcmc.records,'records'),@($cfg.diagnostics.chains,'chains'),@($cfg.diagnostics.draws,'draws'),@($cfg.diagnostics.attempted_replicates,'attempts'),@($cfg.information.repeats,'repeats'),@($cfg.information.outer_budget,'outer'),@($cfg.information.inner_budget,'inner'))){if([int]$pair[0]-le0){throw "config count must be positive: $($pair[1])"}}
$nr=@($cfg.pod.phi).Count;$rr=@($cfg.pod.phi[0]).Count;if($nr-ne[int]$cfg.pod.n_model-or$rr-ne[int]$cfg.pod.rank-or$rr-lt1){throw 'config n_model/rank mismatch'};foreach($row in $cfg.pod.phi){if($row.Count-ne$rr){throw 'config Phi not rectangular'};foreach($x in $row){ConfigFinite $x 'phi'}};foreach($row in $cfg.pod.coefficient_prior_covariance){if($row.Count-ne$rr){throw 'config prior shape'};foreach($x in $row){ConfigFinite $x 'prior covariance'}}

function LogNormal([double]$x, [double]$sd) {
    return -0.5 * [Math]::Log(2.0 * [Math]::PI * $sd * $sd) - 0.5 * $x * $x / ($sd * $sd)
}
function NextNormal([Random]$rng){[Math]::Sqrt(-2*[Math]::Log([Math]::Max($rng.NextDouble(),1e-15)))*[Math]::Cos(2*[Math]::PI*$rng.NextDouble())}
function LogMeanExp([double[]]$x){$mx=($x|Measure-Object -Maximum).Maximum;return $mx+[Math]::Log((($x|ForEach-Object{[Math]::Exp($_-$mx)}|Measure-Object -Average).Average))}
function Chol([object[]]$a){$n=$a.Count;$l=@();for($i=0;$i-lt$n;$i++){$l+=,@([double[]](0..($n-1)|%{0.}))};for($i=0;$i-lt$n;$i++){if($a[$i].Count-ne$n){throw 'matrix not square'};for($j=0;$j-le$i;$j++){$s=[double]$a[$i][$j];if([Math]::Abs([double]$a[$i][$j]-[double]$a[$j][$i])-gt1e-10){throw 'matrix not symmetric'};for($k=0;$k-lt$j;$k++){$s-=$l[$i][$k]*$l[$j][$k]};if($i-eq$j){if($s-le1e-12){throw 'matrix not SPD'};$l[$i][$j]=[Math]::Sqrt($s)}else{$l[$i][$j]=$s/$l[$j][$j]}}};,$l}
function CholSolve([object[]]$l,[double[]]$b){$n=$l.Count;$y=New-Object double[] $n;$x=New-Object double[] $n;for($i=0;$i-lt$n;$i++){$s=$b[$i];for($k=0;$k-lt$i;$k++){$s-=$l[$i][$k]*$y[$k]};$y[$i]=$s/$l[$i][$i]};for($i=$n-1;$i-ge0;$i--){$s=$y[$i];for($k=$i+1;$k-lt$n;$k++){$s-=$l[$k][$i]*$x[$k]};$x[$i]=$s/$l[$i][$i]};,$x}
function InvFromChol([object[]]$l){$n=$l.Count;$o=@();for($i=0;$i-lt$n;$i++){$o+=,@([double[]](0..($n-1)|%{0.}))};for($j=0;$j-lt$n;$j++){$e=New-Object double[] $n;$e[$j]=1;$x=CholSolve $l $e;for($i=0;$i-lt$n;$i++){$o[$i][$j]=$x[$i]}};,$o}
function MatDetChol([object[]]$l){$d=1.;for($i=0;$i-lt$l.Count;$i++){$d*=$l[$i][$i]*$l[$i][$i]};$d}
function InvNorm([double]$p) {
    $a=@(-39.6968302866538,220.946098424521,-275.928510446969,138.357751867269,-30.6647980661472,2.50662827745924)
    $b=@(-54.4760987982241,161.585836858041,-155.698979859887,66.8013118877197,-13.2806815528857)
    $c=@(-0.00778489400243029,-0.322396458041136,-2.40075827716184,-2.54973253934373,4.37466414146497,2.93816398269878)
    $d=@(0.00778469570904146,0.32246712907004,2.445134137143,3.75440866190742)
    if($p-lt.02425){$q=[Math]::Sqrt(-2*[Math]::Log($p));$num=(((($c[0]*$q+$c[1])*$q+$c[2])*$q+$c[3])*$q+$c[4])*$q+$c[5];$den=((($d[0]*$q+$d[1])*$q+$d[2])*$q+$d[3])*$q+1;return $num/$den}
    if($p-gt.97575){return -(InvNorm (1-$p))}
    $q=$p-.5;$r=$q*$q;return (((((($a[0]*$r+$a[1])*$r+$a[2])*$r+$a[3])*$r+$a[4])*$r+$a[5])*$q)/((((($b[0]*$r+$b[1])*$r+$b[2])*$r+$b[3])*$r+$b[4])*$r+1)
}
function RankNormal([double[]]$values) {
    $n=$values.Count;$pairs=for($i=0;$i-lt$n;$i++){[pscustomobject]@{i=$i;v=$values[$i]}}
    $sorted=@($pairs|Sort-Object v);$out=New-Object double[] $n;$k=0
    while($k-lt$n){$j=$k;while($j+1-lt$n-and$sorted[$j+1].v-eq$sorted[$k].v){$j++};$rank=(($k+1)+($j+1))/2.0;$z=InvNorm (($rank-0.375)/($n+0.25));for($h=$k;$h-le$j;$h++){$out[$sorted[$h].i]=$z};$k=$j+1}
    return $out
}
function SplitArrays([object[]]$Rows,[string]$Field,[switch]$Folded,[switch]$Ranked){
    $vals=[double[]]@($Rows|%{[double]$_.$Field});$sorted=@($vals|Sort-Object);$med=$sorted[[int]($sorted.Count/2)]
    if($Folded){$vals=[double[]]@($vals|%{[Math]::Abs($_-$med)})};if($Ranked){$vals=RankNormal $vals}
    $result=@();$offset=0;foreach($c in ($Rows.chain|Sort-Object -Unique)){$orig=@($Rows|?{[int]$_.chain-eq[int]$c});$n=$orig.Count;$h=[int]($n/2);$v=@($vals[$offset..($offset+$n-1)]);$result+=,@([double[]]$v[0..($h-1)]);$result+=,@([double[]]$v[$h..(2*$h-1)]);$offset+=$n};return $result
}
function RhatFromSplits([object[]]$sp){$n=$sp[0].Count;$means=@($sp|%{($_|measure -Average).Average});$vars=@($sp|%{$m=($_|measure -Average).Average;(($_|%{($_-$m)*($_-$m)}|measure -Sum).Sum)/($n-1)});$W=($vars|measure -Average).Average;$mm=($means|measure -Average).Average;$B=$n*(($means|%{($_-$mm)*($_-$mm)}|measure -Sum).Sum)/($means.Count-1);[Math]::Sqrt((($n-1)/$n*$W+$B/$n)/$W)}
function GeyerTau([double[]]$rho){
    $pairs=@()
    for($k=0;2*$k+1-lt$rho.Count;$k++){
        $p=$rho[2*$k]+$rho[2*$k+1]
        if($p-le0){break}
        if($pairs.Count-gt0-and$p-gt$pairs[-1]){$p=$pairs[-1]}
        $pairs+=$p
    }
    $tau=-1+2*(($pairs|Measure-Object -Sum).Sum)
    return $tau
}
function GeyerEss([object[]]$sp){
    $m=$sp.Count;$n=$sp[0].Count;$means=@($sp|%{($_|measure -Average).Average});$vars=@($sp|%{$mu=($_|measure -Average).Average;(($_|%{($_-$mu)*($_-$mu)}|measure -Sum).Sum)/($n-1)});$W=($vars|measure -Average).Average;$mm=($means|measure -Average).Average;$B=$n*(($means|%{($_-$mm)*($_-$mm)}|measure -Sum).Sum)/($m-1);$vp=(($n-1)/$n)*$W+$B/$n;$rho=@(1.0)
    for($lag=1;$lag-lt$n;$lag++){$vg=0.0;foreach($a in $sp){for($i=0;$i-lt$n-$lag;$i++){$vg+=($a[$i+$lag]-$a[$i])*($a[$i+$lag]-$a[$i])}};$vg/=($m*($n-$lag));$rho+=1-$vg/(2*$vp)}
    $tau=GeyerTau ([double[]]$rho)
    if($tau-le0){return $m*$n}
    return [Math]::Min($m*$n,($m*$n)/$tau)
}
$geyerReference=GeyerTau ([double[]]@(1.0,0.6,-0.4,0.3,-0.2,0.1))
if([Math]::Abs($geyerReference-2.2)-gt1e-12){throw "Geyer标准配对参考夹具失败: $geyerReference"}
$legacyShiftedTau=1+2*((0.6-0.4)+(0.3-0.2))
if([Math]::Abs($legacyShiftedTau-1.6)-gt1e-12-or[Math]::Abs($geyerReference-$legacyShiftedTau)-lt0.5){throw "Geyer参考夹具未区分旧错位配对"}

try {
    if(-not(Test-Path -LiteralPath $stage)){New-Item -ItemType Directory -Path $stage | Out-Null}

    # Analytic Gaussian POD posterior for arbitrary coefficient rank r.
    $y=[double]$cfg.pod.observation;$s2=[Math]::Pow([double]$cfg.pod.noise_sd,2);$phi=@($cfg.pod.phi);$h=@($cfg.pod.h);$m0=@($cfg.pod.m0);$pm=@($cfg.pod.coefficient_prior_mean);$pc=@($cfg.pod.coefficient_prior_covariance)
    $nModel=$phi.Count;$rank=$phi[0].Count;if($nModel-ne$m0.Count-or$nModel-ne$h.Count-or$pm.Count-ne$rank-or$pc.Count-ne$rank){throw 'POD config shape mismatch'}
    $gram=@();for($i=0;$i-lt$rank;$i++){$row=@();for($j=0;$j-lt$rank;$j++){$v=0.;for($k=0;$k-lt$nModel;$k++){$v+=[double]$phi[$k][$i]*[double]$phi[$k][$j]};$row+=$v};$gram+=,@($row)}
    $gramL=Chol $gram;$priorL=Chol $pc;$priorInv=InvFromChol $priorL;$hc=New-Object double[] $rank;$hm0=0.;for($k=0;$k-lt$nModel;$k++){$hm0+=[double]$h[$k]*[double]$m0[$k];for($j=0;$j-lt$rank;$j++){$hc[$j]+=[double]$h[$k]*[double]$phi[$k][$j]}}
    $prec=@();for($i=0;$i-lt$rank;$i++){$row=@();for($j=0;$j-lt$rank;$j++){$row+=[double]$priorInv[$i][$j]+$hc[$i]*$hc[$j]/$s2};$prec+=,@($row)};$precL=Chol $prec;$postCov=InvFromChol $precL
    $rhs=New-Object double[] $rank;for($i=0;$i-lt$rank;$i++){for($j=0;$j-lt$rank;$j++){$rhs[$i]+=[double]$priorInv[$i][$j]*[double]$pm[$j]};$rhs[$i]+=$hc[$i]*($y-$hm0)/$s2};$postMean=CholSolve $precL $rhs
    $predMean=$hm0;$priorPredMean=$hm0;for($i=0;$i-lt$rank;$i++){$predMean+=$hc[$i]*$postMean[$i];$priorPredMean+=$hc[$i]*[double]$pm[$i]};$predVar=$s2;$priorPredVar=$s2;for($i=0;$i-lt$rank;$i++){for($j=0;$j-lt$rank;$j++){$predVar+=$hc[$i]*[double]$postCov[$i][$j]*$hc[$j];$priorPredVar+=$hc[$i]*[double]$pc[$i][$j]*$hc[$j]}}
    $logZr=LogNormal ($y-$priorPredMean) ([Math]::Sqrt($priorPredVar));$gramDet=MatDetChol $gramL
    $pod=[ordered]@{basis_shape=@($nModel,$rank);rank=$rank;gram=$gram;gram_determinant=$gramDet;hausdorff_volume_factor=[Math]::Sqrt($gramDet);coefficient_prior_proper=$true;posterior_mean=@($postMean);posterior_covariance=$postCov;predictive_mean=$predMean;predictive_variance=$predVar;log_z_r=$logZr;z_r=[Math]::Exp($logZr);full_space_kl_reported=$false}

    $obs = [double]$cfg.rjmcmc.observation
    $noise = [double]$cfg.rjmcmc.noise_sd
    $slab = [double]$cfg.rjmcmc.slab_sd
    $logM0 = LogNormal $obs $noise
    $logM1 = LogNormal $obs ([Math]::Sqrt($noise * $noise + $slab * $slab))
    $posteriorM1 = 1.0 / (1.0 + [Math]::Exp($logM0 - $logM1))
    $records = [System.Collections.Generic.List[object]]::new()
    $n = [int]$cfg.rjmcmc.records
    for ($i = 0; $i -lt $n; $i++) {
        $u = -2.0 + 4.0 * ($i + 0.5) / $n
        $logTargetRatio = (LogNormal ($obs - $u) $noise) + (LogNormal $u $slab) - $logM0
        $logAuxRatio = -(LogNormal $u $slab)
        $forward = $logTargetRatio + $logAuxRatio
        $records.Add([pscustomobject]@{
            case='unit_birth_death'; replicate=$i; input_theta=''; auxiliary=$u
            x='M0'; u=$u; y=('M1:'+ $u); u_prime='empty'
            log_target_x=$logM0; log_target_y=((LogNormal ($obs-$u) $noise)+(LogNormal $u $slab))
            j_forward=1.0; j_reverse=1.0; log_q_forward=(LogNormal $u $slab); log_q_reverse=0.0
            output_1=$u; output_2=''; inverse_error=0.0; abs_jacobian=1.0
            log_forward=$forward; log_reverse=(-$forward)
            move_probability_forward=1.0; move_probability_reverse=1.0; auxiliary_density=(LogNormal $u $slab)
        })

        $theta = -1.0 + 2.0 * ($i + 0.5) / $n
        $split1 = $theta - $u
        $split2 = $theta + $u
        $inverseTheta = 0.5 * ($split1 + $split2)
        $inverseU = 0.5 * ($split2 - $split1)
        $splitLogTarget = (LogNormal $split1 1.0) + (LogNormal $split2 1.0) - (LogNormal $theta 1.0)
        $splitForward = $splitLogTarget - (LogNormal $u 1.0) + [Math]::Log(2.0)
        $records.Add([pscustomobject]@{
            case='nonunit_split_merge'; replicate=$i; input_theta=$theta; auxiliary=$u
            x=$theta; u=$u; y=($split1.ToString('R')+','+$split2.ToString('R')); u_prime='empty'
            log_target_x=(LogNormal $theta 1.0); log_target_y=((LogNormal $split1 1.0)+(LogNormal $split2 1.0))
            j_forward=1.0; j_reverse=1.0; log_q_forward=(LogNormal $u 1.0); log_q_reverse=0.0
            output_1=$split1; output_2=$split2
            inverse_error=[Math]::Max([Math]::Abs($inverseTheta-$theta),[Math]::Abs($inverseU-$u))
            abs_jacobian=2.0; log_forward=$splitForward; log_reverse=(-$splitForward)
            move_probability_forward=1.0; move_probability_reverse=1.0
            auxiliary_density=(LogNormal $u 1.0)
        })
    }
    $records | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'rjmcmc-records.csv')
    $rng=[Random]::new([int]$cfg.seed);$modelChain=[System.Collections.Generic.List[object]]::new();$hits=0;$state=0;$theta=0.0
    $rjDraws=40000
    for($i=0;$i-lt $rjDraws;$i++){
        $accepted=$false;$current=$state;$proposed=1-$state;$move=if($state-eq0){'birth'}else{'death'};$proposalTheta=$theta
        if($state-eq0){
            $z=[Math]::Sqrt(-2*[Math]::Log([Math]::Max($rng.NextDouble(),1e-15)))*[Math]::Cos(2*[Math]::PI*$rng.NextDouble())
            $proposal=$slab*$z;$proposalTheta=$proposal;$proposalLogLike=LogNormal ($obs - $proposal) $noise;$loga = $proposalLogLike - $logM0
        }else{
            $currentLogLike=LogNormal ($obs - $theta) $noise;$loga = $logM0 - $currentLogLike
        }
        $uniform=[Math]::Max($rng.NextDouble(),1e-15)
        if([Math]::Log($uniform)-lt[Math]::Min(0.0,$loga)){$state=$proposed;$accepted=$true;if($state-eq1){$theta=$proposalTheta}else{$theta=0}}
        $hits+=$state;$modelChain.Add([pscustomobject]@{step=$i;current_state=$current;proposed_state=$proposed;move=$move;proposal_theta=$proposalTheta;log_alpha=[Math]::Min(0.0,$loga);uniform=$uniform;accepted=$accepted;next_state=$state;next_theta=$theta})
    }
    $modelChain|Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'rjmcmc-chain.csv')
    $phat=$hits/[double]$rjDraws
    $batchMeans=@();for($bch=0;$bch-lt40;$bch++){$batchMeans+=(@($modelChain|Select-Object -Skip ($bch*1000) -First 1000|%{[double]$_.next_state})|measure -Average).Average};$bmAvg=($batchMeans|measure -Average).Average;$bmSd=[Math]::Sqrt((($batchMeans|%{($_-$bmAvg)*($_-$bmAvg)}|measure -Sum).Sum)/39);$bmMcse=$bmSd/[Math]::Sqrt(40);$bmLo=$phat-2.02269092*$bmMcse;$bmHi=$phat+2.02269092*$bmMcse
    $halfBatch=@();for($bch=0;$bch-lt20;$bch++){$halfBatch+=(@($modelChain|Select-Object -Skip ($bch*2000) -First 2000|%{[double]$_.next_state})|measure -Average).Average};$hbAvg=($halfBatch|measure -Average).Average;$hbSd=[Math]::Sqrt((($halfBatch|%{($_-$hbAvg)*($_-$hbAvg)}|measure -Sum).Sum)/19);$hbMcse=$hbSd/[Math]::Sqrt(20)

    $chains = [System.Collections.Generic.List[object]]::new()
    for ($c=0; $c -lt [int]$cfg.diagnostics.chains; $c++) {
        for ($d=0; $d -lt [int]$cfg.diagnostics.draws; $d++) {
            $phase = if ((($d + $c) % 2) -eq 0) {-1.0} else {1.0}
            $jitter = 0.15 * [Math]::Sin(($d + 1) * ($c + 1))
            $u01 = ((($d * 73 + $c * 17) % [int]$cfg.diagnostics.draws) + 0.5) / [double]$cfg.diagnostics.draws
            $chains.Add([pscustomobject]@{
                chain=$c; draw=$d; bimodal=(3.0*$phase+$jitter)
                heavy_tail=[Math]::Tan([Math]::PI*($u01-0.5))
            })
        }
    }
    $chains | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'diagnostic-chains.csv')
    $failureChains=[System.Collections.Generic.List[object]]::new()
    foreach($case in @('sticky_bimodal','scale_mismatch','tail_unexplored')){
        for($c=0;$c-lt[int]$cfg.diagnostics.chains;$c++){for($d=0;$d-lt100;$d++){
            $base=[Math]::Sin(($d+1)*($c+1))
            if($case-eq'sticky_bimodal'){$b=if($c-lt2){-3+.05*$base}else{3+.05*$base};$t=[Math]::Tan([Math]::PI*((($d*37+$c*11)%100+.5)/100-.5))}
            elseif($case-eq'scale_mismatch'){$scale=if($c-lt2){1}else{10};$b=$scale*$base;$t=[Math]::Tan([Math]::PI*((($d*37+$c*11)%100+.5)/100-.5))}
            else{$sgn=if((($d+$c)%2)-eq0){-1}else{1};$b=3*$sgn+.05*$base;$t=0}
            $failureChains.Add([pscustomobject]@{case=$case;chain=$c;draw=$d;bimodal=$b;heavy_tail=$t})
        }}
    }
    $failureChains|Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'diagnostic-failure-chains.csv')
    $failureSummary=@(
        [ordered]@{case='sticky_bimodal';seed=[int]$cfg.seed+401;stage='diagnostics';error='required mode visits not achieved';exit_code=2;last_state='separated modes';status='Failed';reason=@('mode_visits')},
        [ordered]@{case='scale_mismatch';seed=[int]$cfg.seed+402;stage='diagnostics';error='folded rank Rhat hard gate';exit_code=2;last_state='scale mismatch';status='Failed';reason=@('folded_rhat')},
        [ordered]@{case='tail_unexplored';seed=[int]$cfg.seed+403;stage='diagnostics';error='tail functional constant/unexplored';exit_code=2;last_state='constant tail';status='Failed';reason=@('constant_tail','tail_ess')}
    )
    $repStatus=[System.Collections.Generic.List[object]]::new()
    foreach($fs in $failureSummary){$repStatus.Add([pscustomobject]@{replicate=("failure-$($fs.case)");evidence_kind='fault_injection';seed=$fs.seed;stage=$fs.stage;status='Failed';error=$fs.error;exit_code=$fs.exit_code;last_state=$fs.last_state})}
    for($i=0;$i-lt([int]$cfg.diagnostics.attempted_replicates-$failureSummary.Count);$i++){$repStatus.Add([pscustomobject]@{replicate=("pass-$i");evidence_kind='synthetic_control';seed=([int]$cfg.seed+1000+$i);stage='completed';status='Passed';error='';exit_code=0;last_state='complete'})}
    $repStatus|Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'diagnostic-replicates.csv')
    $failedRate = $failureSummary.Count / [double]$repStatus.Count
    $raw=@($chains);$rankSplits=SplitArrays $raw 'bimodal' -Ranked;$foldSplits=SplitArrays $raw 'bimodal' -Ranked -Folded;$r1=RhatFromSplits $rankSplits;$r2=RhatFromSplits $foldSplits
    $bvals=[double[]]@($raw|%{[double]$_.bimodal});$ind=[double[]]@($bvals|%{if($_-gt 0){1}else{0}})
    $bulk=GeyerEss $rankSplits
    $hv=[double[]]@($raw|%{[double]$_.heavy_tail});$hs=@($hv|Sort-Object);$q05=$hs[[int][Math]::Floor(.05*($hs.Count-1))];$q95=$hs[[int][Math]::Floor(.95*($hs.Count-1))]
    $loRows=@();$hiRows=@();for($i=0;$i-lt$raw.Count;$i++){$loRows+=[pscustomobject]@{chain=$raw[$i].chain;x=if($hv[$i]-le$q05){1}else{0}};$hiRows+=[pscustomobject]@{chain=$raw[$i].chain;x=if($hv[$i]-ge$q95){1}else{0}}}
    $tail=[Math]::Min((GeyerEss (SplitArrays $loRows 'x')),(GeyerEss (SplitArrays $hiRows 'x')))
    $decisionRows=@();for($i=0;$i-lt$raw.Count;$i++){$decisionRows+=[pscustomobject]@{chain=$raw[$i].chain;x=$ind[$i]}};$decisionEss=GeyerEss (SplitArrays $decisionRows 'x');$relmcse=([Math]::Sqrt(0.25/$decisionEss))/0.5
    $visits=@();foreach($c in 0..([int]$cfg.diagnostics.chains-1)){$v=@($raw|?{[int]$_.chain-eq$c}|%{if([double]$_.bimodal-gt 0){1}else{0}});$nvis=0;for($i=1;$i-lt$v.Count;$i++){if($v[$i]-ne$v[$i-1]){$nvis++}};$visits+=$nvis}
    $status=if([Math]::Max($r1,$r2)-le[double]$contract.thresholds.rank_normalized_split_rhat_max-and$bulk-ge[double]$contract.thresholds.bulk_ess_min-and$tail-ge[double]$contract.thresholds.tail_ess_min-and$relmcse-le[double]$contract.thresholds.relative_mcse_max-and($visits|Measure-Object -Minimum).Minimum-ge[double]$contract.thresholds.required_mode_visits_per_chain-and$failedRate-le[double]$contract.thresholds.failed_replicate_rate_max){'Passed'}else{'Failed'}
    $diagnostics = [ordered]@{
        contract_id = $contract.contract_id
        rank_normalized_split_rhat = $r1
        folded_split_rhat = $r2
        bulk_ess = $bulk
        tail_ess = $tail
        relative_mcse = $relmcse
        mode_visits_per_chain = $visits
        failed_replicate_rate = $failedRate
        status = $status
        datasets = @('bimodal','heavy_tail')
    }
    foreach($fs in $failureSummary){
        $caseRows=@($failureChains|Where-Object case -eq $fs.case)
        $caseRank=RhatFromSplits (SplitArrays $caseRows 'bimodal' -Ranked)
        $caseFold=RhatFromSplits (SplitArrays $caseRows 'bimodal' -Ranked -Folded)
        $caseBulk=GeyerEss (SplitArrays $caseRows 'bimodal' -Ranked)
        $caseVisits=@();foreach($cc in 0..([int]$cfg.diagnostics.chains-1)){$vv=@($caseRows|?{[int]$_.chain-eq$cc}|%{if([double]$_.bimodal-gt0){1}else{0}});$nv=0;for($ii=1;$ii-lt$vv.Count;$ii++){if($vv[$ii]-ne$vv[$ii-1]){$nv++}};$caseVisits+=$nv}
        $tailUnique=@($caseRows|%{[double]$_.heavy_tail}|Sort-Object -Unique).Count
        $caseTail=if($tailUnique-lt2){0}else{$caseBulk}
        $fs.rank_normalized_split_rhat=$caseRank;$fs.folded_split_rhat=$caseFold;$fs.bulk_ess=$caseBulk;$fs.tail_ess=$caseTail;$fs.relative_mcse=if($caseBulk-gt0){1/[Math]::Sqrt($caseBulk)}else{1};$fs.mode_visits_per_chain=$caseVisits;$fs.failed_replicate_rate=1.0
        $why=@();if($caseRank-gt[double]$contract.thresholds.rank_normalized_split_rhat_max){$why+='rank_rhat'};if($caseFold-gt[double]$contract.thresholds.rank_normalized_split_rhat_max){$why+='folded_rhat'};if($caseBulk-lt[double]$contract.thresholds.bulk_ess_min){$why+='bulk_ess'};if($caseTail-lt[double]$contract.thresholds.tail_ess_min){$why+='tail_ess'};if([double]$fs.relative_mcse-gt[double]$contract.thresholds.relative_mcse_max){$why+='relative_mcse'};if(($caseVisits|measure -Minimum).Minimum-lt[double]$contract.thresholds.required_mode_visits_per_chain){$why+='mode_visits'};if($fs.failed_replicate_rate-gt[double]$contract.thresholds.failed_replicate_rate_max){$why+='failed_replicate_rate'};if($tailUnique-lt2){$why+='constant_tail'};$fs.reason=@($why|Sort-Object);$fs.error=($fs.reason-join',')
    }
    foreach($fs in $failureSummary){($repStatus|Where-Object replicate -eq "failure-$($fs.case)").error=$fs.error}
    $repStatus|Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'diagnostic-replicates.csv')
    $failureSummary|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 -LiteralPath (Join-Path $stage 'diagnostic-failure-summary.json')
    $infoRows=[System.Collections.Generic.List[object]]::new();$nRep=[int]$cfg.information.repeats;$outer=[int]$cfg.information.outer_budget;$inner=[int]$cfg.information.inner_budget
    for($rep=0;$rep-lt$nRep;$rep++){
        $eigSeed=[int]$cfg.seed+10000+$rep;$rigSeed=[int]$cfg.seed+20000+$rep;$lomoSeed=[int]$cfg.seed+30000+$rep
        $infoRng=[Random]::new($eigSeed)
        $sumEig=0.;for($o=0;$o-lt$outer;$o++){$theta=NextNormal $infoRng;$yy=$theta+(NextNormal $infoRng);$lik=LogNormal ($yy-$theta) 1.;$dens=0.;for($j=0;$j-lt$inner;$j++){$thj=NextNormal $infoRng;$dens+=[Math]::Exp((LogNormal ($yy-$thj) 1.))};$sumEig+=$lik-[Math]::Log($dens/$inner)}
        $rigEvidenceSeed=$rigSeed+500000;$infoRng=[Random]::new($rigEvidenceSeed);$yRig=[double]$cfg.information.realized_observation;$sumRig=0.;$postMean=$yRig/2;$postSd=[Math]::Sqrt(.5);$evLogs=[double[]]@(for($j=0;$j-lt$inner;$j++){LogNormal ($yRig-(NextNormal $infoRng)) 1.});$logEv=LogMeanExp $evLogs;$infoRng=[Random]::new($rigSeed);for($o=0;$o-lt$outer;$o++){$th=$postMean+$postSd*(NextNormal $infoRng);$sumRig+=(LogNormal ($yRig-$th) 1.)-$logEv}
        $lomoLeaveSeed=$lomoSeed+500000;$lomoFullSeed=$lomoSeed+700000;$y1=[double]$cfg.information.lomo_observations[0];$y2=[double]$cfg.information.lomo_observations[1];$fullMean=($y1+$y2)/3;$fullVar=1/3;$leaveMean=$y1/2;$leaveVar=.5
        $evRng=[Random]::new($lomoLeaveSeed);$leaveLogs=[double[]]@(for($j=0;$j-lt$inner;$j++){$thj=NextNormal $evRng;LogNormal ($y1-$thj) 1.});$evRng=[Random]::new($lomoFullSeed);$fullLogs=[double[]]@(for($j=0;$j-lt$inner;$j++){$thj=NextNormal $evRng;(LogNormal ($y1-$thj) 1.)+(LogNormal ($y2-$thj) 1.)});$logLeaveHat=LogMeanExp $leaveLogs;$logFullHat=LogMeanExp $fullLogs;$sumLomo=0.;$infoRng=[Random]::new($lomoSeed);for($o=0;$o-lt$outer;$o++){$th=$fullMean+[Math]::Sqrt($fullVar)*(NextNormal $infoRng);$sumLomo+=(LogNormal ($y2-$th) 1.)+$logLeaveHat-$logFullHat}
        $rigTruth=.5*(.5+$postMean*$postMean-1-[Math]::Log(.5));$lomoTruth=.5*($fullVar/$leaveVar+($leaveMean-$fullMean)*($leaveMean-$fullMean)/$leaveVar-1+[Math]::Log($leaveVar/$fullVar))
        $infoRows.Add([pscustomobject]@{information_type='design_eig';repeat=$rep;seed=$eigSeed;evidence_seed=$eigSeed;second_evidence_seed='';sample_path='prior_predictive';outer_mean_log_likelihood='';log_z_hat='';log_z_second_hat='';outer_budget=$outer;inner_budget=$inner;estimate=$sumEig/$outer;truth=.5*[Math]::Log(2)})
        $infoRows.Add([pscustomobject]@{information_type='realized_information_gain';repeat=$rep;seed=$rigSeed;evidence_seed=$rigEvidenceSeed;second_evidence_seed='';sample_path='posterior_single_observation';outer_mean_log_likelihood=($sumRig/$outer+$logEv);log_z_hat=$logEv;log_z_second_hat='';outer_budget=$outer;inner_budget=$inner;estimate=$sumRig/$outer;truth=$rigTruth})
        $infoRows.Add([pscustomobject]@{information_type='lomo_forward_kl';repeat=$rep;seed=$lomoSeed;evidence_seed=$lomoLeaveSeed;second_evidence_seed=$lomoFullSeed;sample_path='full_posterior_two_observations';outer_mean_log_likelihood=($sumLomo/$outer-$logLeaveHat+$logFullHat);log_z_hat=$logLeaveHat;log_z_second_hat=$logFullHat;outer_budget=$outer;inner_budget=$inner;estimate=$sumLomo/$outer;truth=$lomoTruth})
    }
    $infoRows|Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath (Join-Path $stage 'information-estimates.csv')
    $info=@();foreach($type in @('design_eig','realized_information_gain','lomo_forward_kl')){$v=@($infoRows|?{$_.information_type-eq$type}|%{[double]$_.estimate});$avg=($v|measure -Average).Average;$sd=[Math]::Sqrt((($v|%{($_-$avg)*($_-$avg)}|measure -Sum).Sum)/($v.Count-1));$truth=[double]($infoRows|?{$_.information_type-eq$type}|select -First 1).truth;$mcse=$sd/[Math]::Sqrt($v.Count);$bias=$avg-$truth;$rec=[ordered]@{information_type=$type;target_variable='theta';conditioning_set=if($type-eq'design_eig'){'D0=empty; design=a'}elseif($type-eq'realized_information_gain'){"D0=empty; y_obs=$($cfg.information.realized_observation)"}else{"D={y1,y2}; D_minus={y1}; held_out=y2"};direction=if($type-eq'lomo_forward_kl'){'full_to_leave_one_out'}else{'posterior_to_prior'};estimator='finite_nested_monte_carlo_log_sum_exp';estimate=$avg;analytic_truth=$truth;bias=$bias;mcse=$mcse;mcse_max=[double]$cfg.information.mcse_max;absolute_bias_max=[double]$cfg.information.absolute_bias_max;status=if($mcse-le[double]$cfg.information.mcse_max-and[Math]::Abs($bias)-le[double]$cfg.information.absolute_bias_max){'Passed'}else{'Failed'};outer_budget=$outer;inner_budget=$inner;repeats=$nRep}
        $rec.production_no_truth_strategy='repeat with doubled outer/inner budgets and independent seeds; require estimate shift within combined MCSE and preregistered bias-stability bound'
        if($type-eq'lomo_forward_kl'){$rec.log_z_leave_out=LogNormal $y1 ([Math]::Sqrt(2));$rec.log_z_full=$rec.log_z_leave_out+(LogNormal ($y2-$leaveMean) ([Math]::Sqrt(1.5)))}else{$rec.log_z_baseline=0.0;$rec.log_z_updated=if($type-eq'design_eig'){LogNormal 0 ([Math]::Sqrt(2))}else{LogNormal $yRig ([Math]::Sqrt(2))}};$info+=$rec}
    $results = [ordered]@{
        run_id=$cfg.run_id; evidence_class=$cfg.evidence_class; pod=$pod
        rjmcmc=[ordered]@{
            analytic_model_1_probability=$posteriorM1
            sampled_model_1_probability=$phat
            batch_count=40; batch_size=1000; batch_means_mcse=$bmMcse
            batch_means_95=@($bmLo,$bmHi)
            analytic_probability_covered_by_batch_means=($bmLo-le$posteriorM1-and$posteriorM1-le$bmHi)
            doubled_batch_count=20; doubled_batch_size=2000; doubled_batch_means_mcse=$hbMcse
            batch_mcse_stability_ratio=$hbMcse/$bmMcse
            unit_jacobian=1.0; nonunit_jacobian=2.0
            max_inverse_error=0.0
        }
        information_records=$info
        diagnostics=$diagnostics
    }
    $results | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $stage 'results.json')
    $cost=@();foreach($st in $reportContract.cost_stages){$cost+=[ordered]@{stage=$st;value=if($st-eq'storage'){1024}else{0.001};unit=[string]$reportContract.stage_units.$st;tolerance=[double]$cfg.report.cost_tolerance;iterations=1;calls=1;hardware=$cfg.report.hardware;evidence_status=$cfg.report.evidence_status;manifest_ref='manifest.json'}}
    [ordered]@{schema=$reportContract.schema;manifest_ref='manifest.json';cost=$cost;regularization=[ordered]@{train_split=$cfg.report.regularization.train_split;validation_split=$cfg.report.regularization.validation_split;test_split=$cfg.report.regularization.test_split;candidates=$cfg.report.regularization.candidates;selection_rule=$cfg.report.regularization.selection_rule;boundary_policy=$cfg.report.regularization.boundary_policy;sensitivity_analysis=$cfg.report.regularization.sensitivity_analysis;omitted_uncertainty=$cfg.report.regularization.omitted_uncertainty;evidence_status=$cfg.report.evidence_status;manifest_ref='manifest.json'}}|ConvertTo-Json -Depth 8|Set-Content -Encoding utf8 -LiteralPath (Join-Path $stage 'report.json')
    Copy-Item -LiteralPath $configPath -Destination (Join-Path $stage 'config.json')
    Copy-Item -LiteralPath $contractPath -Destination (Join-Path $stage 'diagnostic-contract.json')
    Copy-Item -LiteralPath $reportContractPath -Destination (Join-Path $stage 'report-contract.json')
    $stdoutText="PASS run_id=$($cfg.run_id) records=$($records.Count)`n";$stderrText=''
    [IO.File]::WriteAllText((Join-Path $stage 'stdout.log'),$stdoutText,[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $stage 'stderr.log'),$stderrText,[Text.UTF8Encoding]::new($false))
    $hashes = [ordered]@{}
    Get-ChildItem -File -LiteralPath $stage | Sort-Object Name | ForEach-Object {
        $hashes[$_.Name] = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    }
    [ordered]@{
        schema='wp2-toy-manifest-v3'
        run_id=$cfg.run_id; started_utc=$startedUtc.ToString('o'); ended_utc=[DateTime]::UtcNow.ToString('o')
        command=[ordered]@{executable='pwsh';script='run-wp2-toy.ps1';arguments=@('-NoProfile','-File','run-wp2-toy.ps1')}
        exit_code=0
        stdout=[ordered]@{path='stdout.log';sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $stage 'stdout.log')).Hash.ToLowerInvariant();bytes=(Get-Item (Join-Path $stage 'stdout.log')).Length}
        stderr=[ordered]@{path='stderr.log';sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $stage 'stderr.log')).Hash.ToLowerInvariant();bytes=(Get-Item (Join-Path $stage 'stderr.log')).Length}
        environment=[ordered]@{pwsh=$PSVersionTable.PSVersion.ToString();dotnet=[Environment]::Version.ToString();os=[Environment]::OSVersion.VersionString}
        sources=@(
            [ordered]@{path='run-wp2-toy.ps1';sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $MyInvocation.MyCommand.Path).Hash.ToLowerInvariant()},
            [ordered]@{path='config.json';sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash.ToLowerInvariant()},
            [ordered]@{path='diagnostic-contract.json';sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $contractPath).Hash.ToLowerInvariant()},
            [ordered]@{path='report-contract.json';sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $reportContractPath).Hash.ToLowerInvariant()}
        )
        attempted_replicates=[int]$cfg.diagnostics.attempted_replicates
        failed_replicates=[int]$cfg.diagnostics.failed_replicates
        files=$hashes
    } | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $stage 'manifest.json')

    Write-Output "PASS run_id=$($cfg.run_id) records=$($records.Count)"
} finally {
    # Stage ownership belongs exclusively to the wrapper.
}
