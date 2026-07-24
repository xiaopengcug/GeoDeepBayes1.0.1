[CmdletBinding()]param([Parameter(Mandatory)][string]$ConfigPath,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop'
$c=Get-Content -Raw -LiteralPath $ConfigPath|ConvertFrom-Json
function C([double]$re,[double]$im){[Numerics.Complex]::new($re,$im)}
function AdaptiveComplex([scriptblock]$f,[double]$a,[double]$b,[double]$tol,[int]$depth=18){
 $m=($a+$b)/2;$fa=&$f $a;$fm=&$f $m;$fb=&$f $b;$whole=($b-$a)/6*($fa+4*$fm+$fb)
 function Refine([double]$l,[double]$r,$fl,$fc,$fr,$s,[double]$eps,[int]$d){
  $m=($l+$r)/2;$lm=($l+$m)/2;$rm=($m+$r)/2;$flm=&$f $lm;$frm=&$f $rm
  $sl=($m-$l)/6*($fl+4*$flm+$fc);$sr=($r-$m)/6*($fc+4*$frm+$fr);$delta=$sl+$sr-$s
  if($d-le0-or$delta.Magnitude-le15*$eps){return $sl+$sr+$delta/15}
  (Refine $l $m $fl $flm $fc $sl ($eps/2) ($d-1))+(Refine $m $r $fc $frm $fr $sr ($eps/2) ($d-1))
 }
 Refine $a $b $fa $fm $fb $whole $tol $depth
}
$pi=[Math]::PI;$mu=[double]$c.medium.mu_h_m;$sigma=[double]$c.medium.sigma_s_m
$dc=[double]$c.dc.rho_ohm_m/(2*$pi)*(1/[double]$c.dc.am_m-1/[double]$c.dc.an_m-1/[double]$c.dc.bm_m+1/[double]$c.dc.bn_m)
$mt=[Numerics.Complex]::Sqrt($(C 0 (2*$pi*[double]$c.mt.frequency_hz*$mu*[double]$c.mt.rho_ohm_m)))
$moment=[double]$c.tem.transmitter_turns*[double]$c.tem.transmitter_area_m2*[double]$c.tem.current_a
$pickup=[double]$c.tem.receiver_turns*[double]$c.tem.receiver_area_m2
$coef=$moment*$pickup*($mu*$mu)*[Math]::Sqrt($mu)*$sigma*[Math]::Sqrt($sigma)/(20*$pi*[Math]::Sqrt($pi))
$tem=@();foreach($tv in $c.tem.times_s){$t=[double]$tv;$r=[double]$c.tem.ramp_s;$step=-$coef/[Math]::Sqrt($t*$t*$t*$t*$t);$ramp=-2*$coef/(3*$r)*(1/[Math]::Sqrt(($t-$r)*($t-$r)*($t-$r))-1/[Math]::Sqrt($t*$t*$t));$tem+=,[ordered]@{time_s=$t;step_v=$step;ramp_v=$ramp}}
$omega=2*$pi*[double]$c.csamt.frequency_hz;$gamma=[Numerics.Complex]::Sqrt($(C 0 ($omega*$mu*$sigma)));$h0=[double]$c.csamt.source_depth_m;$L=[double]$c.csamt.b_m-[double]$c.csamt.a_m;$cs=@()
foreach($xv in $c.csamt.receiver_x_m){
 $x=[double]$xv
 $fe={param($s)$q=$x-$s;$rr=[Math]::Sqrt($q*$q+$h0*$h0);$q/$rr*[Numerics.Complex]::Exp(-$gamma*$rr)/(2*$pi*$sigma)*($gamma/$rr+1/($rr*$rr))}
 $fh={param($s)$q=$x-$s;$rr=[Math]::Sqrt($q*$q+$h0*$h0);$h0*[Numerics.Complex]::Exp(-$gamma*$rr)/(4*$pi*$rr*$rr*$rr)*(1+$gamma*$rr)}
 $e=-[double]$c.csamt.current_a/$L*(AdaptiveComplex $fe ([double]$c.csamt.a_m) ([double]$c.csamt.b_m) 1e-14)
 $hy=[double]$c.csamt.current_a/$L*(AdaptiveComplex $fh ([double]$c.csamt.a_m) ([double]$c.csamt.b_m) 1e-14)
 $cs+=,[ordered]@{x_m=$x;ex_re=$e.Real;ex_im=$e.Imaginary;hy_re=$hy.Real;hy_im=$hy.Imaginary;rho_a=[Math]::Pow($e.Magnitude/$hy.Magnitude,2)/($omega*$mu);phase_rad=($e/$hy).Phase}
}
$wfomega=2*$pi*[double]$c.wfem.frequency_hz;$kg=[Numerics.Complex]::Sqrt($(C 0 ($wfomega*$mu*$sigma)))
function Endpoint([double]$receiver,[double]$electrode,$k0){$rr=[Math]::Abs($receiver-$electrode);[Numerics.Complex]::Exp(-$k0*$rr)/(2*[Math]::PI*$sigma*$rr)}
$wf=(Endpoint ([double]$c.wfem.m_m) ([double]$c.wfem.a_m) $kg)-(Endpoint ([double]$c.wfem.m_m) ([double]$c.wfem.b_m) $kg)-(Endpoint ([double]$c.wfem.n_m) ([double]$c.wfem.a_m) $kg)+(Endpoint ([double]$c.wfem.n_m) ([double]$c.wfem.b_m) $kg)
$wf0=(Endpoint ([double]$c.wfem.m_m) ([double]$c.wfem.a_m) (C 0 0))-(Endpoint ([double]$c.wfem.m_m) ([double]$c.wfem.b_m) (C 0 0))-(Endpoint ([double]$c.wfem.n_m) ([double]$c.wfem.a_m) (C 0 0))+(Endpoint ([double]$c.wfem.n_m) ([double]$c.wfem.b_m) (C 0 0))
$den=1/[Math]::Abs([double]$c.wfem.m_m-[double]$c.wfem.a_m)-1/[Math]::Abs([double]$c.wfem.n_m-[double]$c.wfem.a_m)-1/[Math]::Abs([double]$c.wfem.m_m-[double]$c.wfem.b_m)+1/[Math]::Abs([double]$c.wfem.n_m-[double]$c.wfem.b_m);$kSigned=2*$pi/$den;$app=$kSigned*$wf
[ordered]@{schema='wp3-oracle-v3';algorithm='adaptive Simpson direct finite-source E/H; analytic TEM finite-ramp; independent signed ABMN endpoints';dc_ohm=$dc;mt=@{re=$mt.Real;im=$mt.Imaginary};tem=$tem;csamt=$cs;wfem=@{re=$wf.Real;im=$wf.Imaginary;dc_re=$wf0.Real;dc_im=$wf0.Imaginary;geometric_factor_m=$kSigned;app_re=$app.Real;app_im=$app.Imaginary;rho_a_ohm_m=$app.Magnitude;phase_rad=$app.Phase}}|ConvertTo-Json -Depth 8|Set-Content -Encoding utf8 -LiteralPath $OutputPath
"PASS oracle"
