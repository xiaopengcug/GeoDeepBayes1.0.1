param([Parameter(Mandatory)][string]$Config,[Parameter(Mandatory)][string]$Output)
$ErrorActionPreference='Stop'
$cfg=Get-Content -Raw $Config|ConvertFrom-Json
$NRep=[int]$cfg.repetitions;$DrawCount=[int]$cfg.posterior_draws;$BinCount=[int]$cfg.rank_bins;$N=[int]$cfg.prior_predictive_n
if($NRep-ne400-or$DrawCount-ne1000-or$N-ne10000-or$BinCount-ne20){throw 'frozen budget mismatch'}
if(-not('Wp1FastRandom' -as [type])){Add-Type @'
using System;
public static class Wp1FastRandom {
  public static double[] Normals(Random r, int n) {
    var x=new double[n]; for(int i=0;i<n;i++){double u1=Math.Max(r.NextDouble(),1e-15),u2=r.NextDouble();x[i]=Math.Sqrt(-2*Math.Log(u1))*Math.Cos(2*Math.PI*u2);} return x;
  }
  public static double[] GridDraws(Random r,double d1,double d2,double rho,double nu,double g0,double g1,int ng,int draws) {
    double det=1-rho*rho;if(det<=1e-10)throw new Exception("non-SPD inference Sigma");
    double step=(g1-g0)/(ng-1),sum=0;var cdf=new double[ng];
    for(int i=0;i<ng;i++){double m=g0+i*step,x=d1-m,y=d2-m,q=(x*x-2*rho*x*y+y*y)/det;double v=Math.Exp(-.5*m*m)*Math.Pow(1+q/nu,-(nu+2)/2);cdf[i]=v;sum+=v;}
    if(!(sum>0)||double.IsNaN(sum))throw new Exception("grid normalization failed");
    if((cdf[0]+cdf[ng-1])/sum>1e-6)throw new Exception("grid boundary mass gate failed");
    double z=0;for(int i=0;i<ng;i++){z+=cdf[i]/sum;cdf[i]=z;}cdf[ng-1]=1;
    var ans=new double[draws];for(int j=0;j<draws;j++){double u=r.NextDouble();int lo=0,hi=ng-1;while(lo<hi){int mid=(lo+hi)/2;if(cdf[mid]<u)lo=mid+1;else hi=mid;}ans[j]=g0+lo*step;}return ans;
  }
}
'@}
function Fin([double]$x){if([double]::IsNaN($x)-or[double]::IsInfinity($x)){throw 'non-finite value'};$x}
function Normal([Random]$rng){$u1=[math]::Max($rng.NextDouble(),1e-15);$u2=$rng.NextDouble();Fin ([math]::Sqrt(-2*[math]::Log($u1))*[math]::Cos(2*[math]::PI*$u2))}
function Gamma([Random]$rng,[double]$shape){
  if($shape-le 0){throw 'invalid gamma shape'};if($shape-lt1){return (Gamma $rng ($shape+1))*[math]::Pow($rng.NextDouble(),1/$shape)}
  $gd=$shape-1/3;$c=1/[math]::Sqrt(9*$gd)
  while($true){$x=Normal $rng;$v=1+$c*$x;if($v-le0){continue};$v=$v*$v*$v;$u=$rng.NextDouble();if($u-lt1-.0331*$x*$x*$x*$x-or[math]::Log($u)-lt.5*$x*$x+$gd*(1-$v+[math]::Log($v))){return $gd*$v}}
}
function Sorted([double[]]$x){$s=[double[]]$x.Clone();[array]::Sort($s);$s}
function QuantSorted([double[]]$s,[double]$p){$s[[int][math]::Floor($p*($s.Count-1))]}
function Wilson([int]$k,[int]$n){if($n-le0){return @($null,$null)};$z=1.95996398454;$p=$k/$n;$den=1+$z*$z/$n;$ctr=($p+$z*$z/(2*$n))/$den;$half=$z*[math]::Sqrt($p*(1-$p)/$n+$z*$z/(4*$n*$n))/$den;@(($ctr-$half),($ctr+$half))}
function Pred([double[]]$x){$s=Sorted $x;[ordered]@{n=$x.Count;mean=($x|Measure-Object -Average).Average;q01=QuantSorted $s .01;q05=QuantSorted $s .05;q50=QuantSorted $s .5;q95=QuantSorted $s .95;q99=QuantSorted $s .99}}
function Metrics([double[]]$draw,[double]$truth){$s=Sorted $draw;$rank=0;while($rank-lt$s.Count-and$s[$rank]-lt$truth){$rank++};@($rank,[int]($truth-ge(QuantSorted $s .05)-and$truth-le(QuantSorted $s .95)),[int]($truth-ge(QuantSorted $s .025)-and$truth-le(QuantSorted $s .975)))}
function GridDraws([Random]$rng,[double]$d1,[double]$d2,[double]$rho){
  $nu=[double]$cfg.corr_t.nu;$g0=[double]$cfg.corr_t.grid_min;$g1=[double]$cfg.corr_t.grid_max;$ng=[int]$cfg.corr_t.grid_count
  [Wp1FastRandom]::GridDraws($rng,$d1,$d2,$rho,$nu,$g0,$g1,$ng,$DrawCount)
}
function AddRow($list,[string]$toy,[string]$variant,[string]$parameter,[int]$rep,[int]$seed,[string]$status,$truth,$obs1,$obs2,$rank,$h90,$h95){
  $list.Add([pscustomobject][ordered]@{run_id=$cfg.run_id;toy=$toy;variant=$variant;parameter=$parameter;rep=$rep;seed=$seed;status=$status;truth=$truth;obs1=$obs1;obs2=$obs2;rank=$rank;hit_90=$h90;hit_95=$h95})
}
$rows=[Collections.Generic.List[object]]::new()
# Toy A: each repetition has its own root+r stream; failed repetitions are recorded and never redrawn.
$sig=$cfg.corr_t.sigma;$s00=[double]$sig[0][0];$s01=[double]$sig[0][1];$s10=[double]$sig[1][0];$s11=[double]$sig[1][1]
if([math]::Abs($s01-$s10)-gt1e-12-or$s00-le0-or$s00*$s11-$s01*$s01-le1e-10){throw 'corr_t Sigma must be finite SPD'}
$cL11=[math]::Sqrt($s00);$cL21=$s01/$cL11;$cL22=[math]::Sqrt($s11-$cL21*$cL21);$rho=$s01/[math]::Sqrt($s00*$s11)
for($rep=0;$rep-lt$NRep;$rep++){$seed=[int]$cfg.corr_t.seed+$rep;try{$rng=[Random]::new($seed);$m=Normal $rng;$lam=(Gamma $rng ([double]$cfg.corr_t.nu/2))/([double]$cfg.corr_t.nu/2);$z1=Normal $rng;$z2=Normal $rng;$d1=$m+$cL11*$z1/[math]::Sqrt($lam);$d2=$m+($cL21*$z1+$cL22*$z2)/[math]::Sqrt($lam)
  foreach($v in @(@('main',$rho),@('adversarial',0.0))){$dr=GridDraws $rng $d1 $d2 ([double]$v[1]);$met=Metrics $dr $m;AddRow $rows 'corr_t' $v[0] 'm' $rep $seed 'ok' $m $d1 $d2 $met[0] $met[1] $met[2]}
}catch{if($rep-eq0){throw "corr_t rep0: $($_.Exception.Message)"};foreach($v in @('main','adversarial')){AddRow $rows 'corr_t' $v 'm' $rep $seed 'failed' '' '' '' '' '' '' ''}}}
# Toy B, all coefficients from config; independent posterior draws for randomized integer ranks.
$a=@([double]$cfg.shared_xi.a[0],[double]$cfg.shared_xi.a[1]);$coefB=@([double]$cfg.shared_xi.b[0],[double]$cfg.shared_xi.b[1]);$sd=@([double]$cfg.shared_xi.noise_sd[0],[double]$cfg.shared_xi.noise_sd[1]);$xsd=[double]$cfg.shared_xi.xi_sd
if($sd[0]-le0-or$sd[1]-le0-or$xsd-le0){throw 'shared_xi scales must be positive'}
$p11=1.0;$p22=1/($xsd*$xsd);$p12=0.0;for($k=0;$k-lt2;$k++){$v=$sd[$k]*$sd[$k];$p11+=$a[$k]*$a[$k]/$v;$p22+=$coefB[$k]*$coefB[$k]/$v;$p12+=$a[$k]*$coefB[$k]/$v}
$det=$p11*$p22-$p12*$p12;if($det-le1e-12){throw 'ill-conditioned posterior'};$V11=$p22/$det;$V22=$p11/$det;$V12=-$p12/$det;$L11=[math]::Sqrt($V11);$L21=$V12/$L11;$L22=[math]::Sqrt($V22-$L21*$L21)
$pb=1+$a[0]*$a[0]/($sd[0]*$sd[0])+$a[1]*$a[1]/($sd[1]*$sd[1]);$Vb=1/$pb
for($rep=0;$rep-lt$NRep;$rep++){$seed=[int]$cfg.shared_xi.seed+$rep;try{$rng=[Random]::new($seed);[double]$m=Normal $rng;[double]$nx=Normal $rng;[double]$xi=([double]$xsd)*$nx;[double]$e0=Normal $rng;[double]$e1=Normal $rng
  [double]$obs0=([double]$a[0])*$m+([double]$coefB[0])*$xi+([double]$sd[0])*$e0;[double]$obs1=([double]$a[1])*$m+([double]$coefB[1])*$xi+([double]$sd[1])*$e1;[double[]]$obs=@($obs0,$obs1)
  $q1=$a[0]*$obs[0]/($sd[0]*$sd[0])+$a[1]*$obs[1]/($sd[1]*$sd[1]);$q2=$coefB[0]*$obs[0]/($sd[0]*$sd[0])+$coefB[1]*$obs[1]/($sd[1]*$sd[1]);$mm=$V11*$q1+$V12*$q2;$mx=$V12*$q1+$V22*$q2;$mb=$Vb*$q1
  $uu=[Wp1FastRandom]::Normals($rng,$DrawCount);$vv=[Wp1FastRandom]::Normals($rng,$DrawCount);$ww=[Wp1FastRandom]::Normals($rng,$DrawCount);$dm=New-Object double[] $DrawCount;$dx=New-Object double[] $DrawCount;$db=New-Object double[] $DrawCount;for($j=0;$j-lt$DrawCount;$j++){$dm[$j]=$mm+$L11*$uu[$j];$dx[$j]=$mx+$L21*$uu[$j]+$L22*$vv[$j];$db[$j]=$mb+[math]::Sqrt($Vb)*$ww[$j]}
  foreach($x in @(@('main','m',$m,$dm),@('main','xi',$xi,$dx),@('adversarial','m',$m,$db))){$dr=[double[]]$x[3];$truth=[double]$x[2];$met=Metrics $dr $truth;AddRow $rows 'shared_xi' $x[0] $x[1] $rep $seed 'ok' $truth $obs0 $obs1 $met[0] $met[1] $met[2]}
}catch{if($rep-eq0){throw};foreach($x in @(@('main','m'),@('main','xi'),@('adversarial','m'))){AddRow $rows 'shared_xi' $x[0] $x[1] $rep $seed 'failed' '' '' '' '' '' '' ''}}}
# Independent prior predictive streams, exactly N each.
$priorRows=[Collections.Generic.List[object]]::new();$pa1=[Collections.Generic.List[double]]::new();$pa2=[Collections.Generic.List[double]]::new();$rng=[Random]::new(([int]$cfg.corr_t.seed)-1)
for($i=0;$i-lt$N;$i++){$m=Normal $rng;$lam=(Gamma $rng ([double]$cfg.corr_t.nu/2))/([double]$cfg.corr_t.nu/2);$z1=Normal $rng;$z2=Normal $rng;$u=$m+$cL11*$z1/[math]::Sqrt($lam);$v=$m+($cL21*$z1+$cL22*$z2)/[math]::Sqrt($lam);$pa1.Add($u);$pa2.Add($v);$priorRows.Add([pscustomobject]@{run_id=$cfg.run_id;toy='corr_t';sample=$i;seed=([int]$cfg.corr_t.seed-1);channel1=$u;channel2=$v})}
$pb1=[Collections.Generic.List[double]]::new();$pb2=[Collections.Generic.List[double]]::new();$rng=[Random]::new(([int]$cfg.shared_xi.seed)-1)
for($i=0;$i-lt$N;$i++){$m=Normal $rng;$xi=$xsd*(Normal $rng);$u=$a[0]*$m+$coefB[0]*$xi+$sd[0]*(Normal $rng);$v=$a[1]*$m+$coefB[1]*$xi+$sd[1]*(Normal $rng);$pb1.Add($u);$pb2.Add($v);$priorRows.Add([pscustomobject]@{run_id=$cfg.run_id;toy='shared_xi';sample=$i;seed=([int]$cfg.shared_xi.seed-1);channel1=$u;channel2=$v})}
function Summary([string]$toy,[string]$variant,[string]$parameter){
  $x=@($rows|Where-Object{$_.toy-eq$toy-and$_.variant-eq$variant-and$_.parameter-eq$parameter});$ok=@($x|Where-Object status -eq 'ok');$bins=New-Object int[] $BinCount
  foreach($q in $ok){$bin=[math]::Min($BinCount-1,[int][math]::Floor(([int]$q.rank)*$BinCount/($DrawCount+1)));$bins[$bin]++};$k90=(@($ok|Where-Object hit_90 -eq '1')).Count;$k95=(@($ok|Where-Object hit_95 -eq '1')).Count
  $expected=$ok.Count/$BinCount;$chi=0.0;foreach($n in $bins){$chi+=($n-$expected)*($n-$expected)/$expected}
  [ordered]@{model="$toy/$variant/$parameter";attempted=$x.Count;succeeded=$ok.Count;failed=$x.Count-$ok.Count;rank_bins=$bins;rank_chi_square=$chi;interval_estimate_90=$k90/$ok.Count;interval_wilson95_90=(Wilson $k90 $ok.Count);interval_estimate_95=$k95/$ok.Count;interval_wilson95_95=(Wilson $k95 $ok.Count)}
}
$summaries=@(Summary 'corr_t' 'main' 'm';Summary 'corr_t' 'adversarial' 'm';Summary 'shared_xi' 'main' 'm';Summary 'shared_xi' 'main' 'xi';Summary 'shared_xi' 'adversarial' 'm')
$priorSummary=[ordered]@{corr_t=[ordered]@{channel1=Pred $pa1.ToArray();channel2=Pred $pa2.ToArray()};shared_xi=[ordered]@{channel1=Pred $pb1.ToArray();channel2=Pred $pb2.ToArray()}}
$records=[Collections.Generic.List[object]]::new()
foreach($s in $summaries){foreach($lev in @(90,95)){$records.Add([ordered]@{calibration_type='parameter_interval_coverage';nominal_level=$lev/100;sampling_unit='SBC repetition';split_id=$s.model;statistic='interval_hit_rate';estimate=$s."interval_estimate_$lev";uncertainty_interval=$s."interval_wilson95_$lev";sharpness=$null;status='Synthetic-run';evidence_id='WP1-TOY';run_id=$cfg.run_id})};$records.Add([ordered]@{calibration_type='sbc_rank';nominal_level=$null;sampling_unit='SBC repetition';split_id=$s.model;statistic='rank_chi_square';estimate=$s.rank_chi_square;uncertainty_interval=$null;sharpness=$null;status='Synthetic-run';evidence_id='WP1-TOY';run_id=$cfg.run_id})}
$totalAttempt=0;$totalOK=0;$totalFail=0;foreach($s in $summaries){$totalAttempt+=[int]$s.attempted;$totalOK+=[int]$s.succeeded;$totalFail+=[int]$s.failed}
$results=[ordered]@{schema_version=2;run_id=$cfg.run_id;status='Synthetic-run';repetitions=$NRep;prior_predictive_n=$N;posterior_draws=$DrawCount;rank_bins=$BinCount;attempted=$totalAttempt;succeeded=$totalOK;failed=$totalFail;config_snapshot=$cfg;
 prior_predictive=$priorSummary;summaries=$summaries;calibration_records=$records}
New-Item -ItemType Directory -Force $Output|Out-Null
$rows|Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $Output 'ranks.csv')
$priorRows|Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $Output 'prior-predictive.csv')
$results|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 (Join-Path $Output 'results.json')
Write-Output "OK run_id=$($cfg.run_id) rows=$($rows.Count)"

