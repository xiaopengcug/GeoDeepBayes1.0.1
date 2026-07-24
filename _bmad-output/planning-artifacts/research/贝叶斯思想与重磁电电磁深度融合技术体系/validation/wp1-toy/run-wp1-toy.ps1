param(
  [string]$Config = (Join-Path $PSScriptRoot 'config.json'),
  [ValidateSet('None','WorkerFailure','PublishAfterOutputSwap','RecoveryAfterJournal','RecoveryAfterOldMove','RecoveryAfterOutputMove','RecoveryAfterAnchorMove')]
  [string]$TestFault = 'None',
  [switch]$RecoverOnly
)
$ErrorActionPreference='Stop'
$start=(Get-Date).ToUniversalTime()
$cfgPath=(Resolve-Path $Config).Path
$cfg=Get-Content -Raw $cfgPath|ConvertFrom-Json
$worker=Join-Path $PSScriptRoot 'invoke-wp1-toy-worker.ps1'
$parent=Split-Path $PSScriptRoot -Parent
$lockPath=Join-Path $parent '.wp1-toy.lock'
$journalPath=Join-Path $parent '.wp1-toy-publish.json'
$fixedOld=Join-Path $PSScriptRoot '.publish-old'
$fixedAnchorTmp=Join-Path $parent '.wp1-toy-anchor.publish-tmp'
$fixedAnchorBackup=Join-Path $parent '.wp1-toy-anchor.publish-backup'
$stage=$null;$stdout=$null;$stderr=$null;$exit=1
function Write-PublishJournal($value){
  $tmp=$journalPath+'.tmp-'+[guid]::NewGuid().ToString('N')
  try{
    $bytes=[Text.Encoding]::UTF8.GetBytes(($value|ConvertTo-Json -Depth 5))
    $fs=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$fs.Write($bytes,0,$bytes.Length);$fs.Flush($true)}finally{$fs.Dispose()}
    [IO.File]::Move($tmp,$journalPath,$true)
  }finally{if(Test-Path $tmp){Remove-Item -LiteralPath $tmp -Force}}
}
try{$lockStream=[IO.File]::Open($lockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}catch{throw 'WP1 toy runner is already active (exclusive lock held)'}
try {
  $lockBytes=[Text.Encoding]::UTF8.GetBytes("$PID $($start.ToString('o'))");$lockStream.Write($lockBytes,0,$lockBytes.Length);$lockStream.Flush()
  # A write-ahead journal always rolls an interrupted publication back to the prior output+anchor pair.
  if(Test-Path $journalPath){
    try{$j=Get-Content -Raw $journalPath|ConvertFrom-Json -ErrorAction Stop}
    catch{
      # Fixed transaction artifacts permit deterministic rollback even when the journal itself is torn.
      $out=Join-Path $PSScriptRoot 'output';$anchor=Join-Path $parent 'wp1-toy-root-anchor.sha256'
      if(Test-Path $fixedOld){if(Test-Path $out){Remove-Item -LiteralPath $out -Recurse -Force};Move-Item -LiteralPath $fixedOld -Destination $out}
      if(Test-Path $fixedAnchorBackup){[IO.File]::Copy($fixedAnchorBackup,$anchor,$true)}
      foreach($p in @($fixedAnchorTmp,$fixedAnchorBackup)){if(Test-Path $p){Remove-Item -LiteralPath $p -Force}}
      Get-ChildItem -LiteralPath $PSScriptRoot -Directory -Filter '.stage-*' -ErrorAction SilentlyContinue|Remove-Item -Recurse -Force
      Get-ChildItem -LiteralPath $parent -File -Filter '.wp1-toy-publish.json.tmp-*' -ErrorAction SilentlyContinue|Remove-Item -Force
      Remove-Item -LiteralPath $journalPath -Force
      $j=$null
    }
    if($null-ne$j){
    if($j.had_output -and (Test-Path $j.old)){
      if(Test-Path $j.output){Remove-Item -LiteralPath $j.output -Recurse -Force}
      Move-Item -LiteralPath $j.old -Destination $j.output
    }
    if($j.had_anchor -and (Test-Path $j.anchor_backup)){[IO.File]::Copy($j.anchor_backup,$j.anchor,$true)}
    elseif(!$j.had_anchor -and (Test-Path $j.anchor)){Remove-Item -LiteralPath $j.anchor -Force}
    foreach($p in @($j.stage,$j.anchor_tmp,$j.old,$j.anchor_backup)){if($p-and(Test-Path $p)){Remove-Item -LiteralPath $p -Recurse -Force}}
    Remove-Item -LiteralPath $journalPath -Force
    }
  }
  if($RecoverOnly){return}
  # Lock holder may remove only abandoned stages older than one hour.
  Get-ChildItem -LiteralPath $PSScriptRoot -Directory -Filter '.stage-*' -ErrorAction SilentlyContinue|Where-Object{$_.LastWriteTimeUtc-lt[DateTime]::UtcNow.AddHours(-1)}|Remove-Item -Recurse -Force
  $stage=Join-Path $PSScriptRoot ('.stage-'+[guid]::NewGuid().ToString('N'))
  $stdout=Join-Path $stage 'stdout.txt';$stderr=Join-Path $stage 'stderr.txt'
  New-Item -ItemType Directory -Path $stage|Out-Null
  if($TestFault-eq'WorkerFailure'){throw 'injected worker failure'}
  & pwsh -NoProfile -File $worker -Config $cfgPath -Output $stage 1>$stdout 2>$stderr
  $exit=$LASTEXITCODE
  if($exit-ne 0){throw "worker exit $exit"}
  $rp=Join-Path $stage 'results.json';$cp=Join-Path $stage 'ranks.csv';$pp=Join-Path $stage 'prior-predictive.csv'
  foreach($p in @($rp,$cp,$pp)){if(!(Test-Path $p)){throw "worker omitted $p"}}
  $end=(Get-Date).ToUniversalTime()
  $manifest=[ordered]@{
    schema_version=2;run_id=$cfg.run_id;status='Synthetic-run'
    started_utc=$start.ToString('o');finished_utc=$end.ToString('o')
    command='pwsh -NoProfile -File invoke-wp1-toy-worker.ps1 -Config <resolved-config> -Output <stage>'
    exit_code=$exit;stdout=(Get-Content -Raw $stdout);stderr=(Get-Content -Raw $stderr)
    environment=[ordered]@{pwsh=$PSVersionTable.PSVersion.ToString();dotnet=[System.Environment]::Version.ToString();os=[System.Runtime.InteropServices.RuntimeInformation]::OSDescription}
    repetitions=[int]$cfg.repetitions;prior_predictive_n=[int]$cfg.prior_predictive_n;posterior_draws=[int]$cfg.posterior_draws
    config_snapshot=$cfg
    sha256=[ordered]@{
      config=(Get-FileHash $cfgPath -Algorithm SHA256).Hash.ToLower()
      wrapper=(Get-FileHash $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash.ToLower()
      worker=(Get-FileHash $worker -Algorithm SHA256).Hash.ToLower()
      results=(Get-FileHash $rp -Algorithm SHA256).Hash.ToLower()
      ranks=(Get-FileHash $cp -Algorithm SHA256).Hash.ToLower()
      prior_predictive=(Get-FileHash $pp -Algorithm SHA256).Hash.ToLower()
    }
  }
  $manifest|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 (Join-Path $stage 'manifest.json')
  Remove-Item $stdout,$stderr -Force
  $out=Join-Path $PSScriptRoot 'output';$old=$fixedOld
  $anchor=Join-Path $parent 'wp1-toy-root-anchor.sha256';$anchorTmp=$fixedAnchorTmp
  $anchorBackup=$fixedAnchorBackup
  foreach($p in @($old,$anchorTmp,$anchorBackup)){if(Test-Path $p){throw "publication residue without journal: $p"}}
  $manifestHash=(Get-FileHash (Join-Path $stage 'manifest.json') -Algorithm SHA256).Hash.ToLower()
  [IO.File]::WriteAllText($anchorTmp,"$manifestHash  wp1-toy/output/manifest.json`n",[Text.Encoding]::ASCII)
  $hadOutput=Test-Path $out;$hadAnchor=Test-Path $anchor
  if($hadAnchor){[IO.File]::Copy($anchor,$anchorBackup,$true)}
  $journal=[ordered]@{schema_version=1;phase='prepared';had_output=$hadOutput;had_anchor=$hadAnchor;output=$out;old=$old;stage=$stage;anchor=$anchor;anchor_tmp=$anchorTmp;anchor_backup=$anchorBackup}
  Write-PublishJournal $journal
  if($TestFault-eq'RecoveryAfterJournal'){return}
  if(Test-Path $out){Move-Item -LiteralPath $out -Destination $old}
  $journal.phase='old-moved';Write-PublishJournal $journal
  if($TestFault-eq'RecoveryAfterOldMove'){return}
  try{
    Move-Item -LiteralPath $stage -Destination $out
    $journal.phase='output-moved';Write-PublishJournal $journal
    if($TestFault-eq'RecoveryAfterOutputMove'){return}
    if($TestFault-eq'PublishAfterOutputSwap'){throw 'injected publish failure after output swap'}
    [IO.File]::Move($anchorTmp,$anchor,$true)
    $journal.phase='anchor-moved';Write-PublishJournal $journal
    if($TestFault-eq'RecoveryAfterAnchorMove'){return}
  }
  catch{
    if(Test-Path $out){Remove-Item $out -Recurse -Force}
    if(Test-Path $old){Move-Item $old $out}
    if($hadAnchor-and(Test-Path $anchorBackup)){[IO.File]::Copy($anchorBackup,$anchor,$true)}
    elseif(!$hadAnchor-and(Test-Path $anchor)){Remove-Item $anchor -Force}
    foreach($p in @($anchorTmp,$anchorBackup)){if(Test-Path $p){Remove-Item $p -Force}}
    if(Test-Path $journalPath){Remove-Item $journalPath -Force}
    throw
  }
  if(Test-Path $old){try{Remove-Item $old -Recurse -Force}catch{Set-Content -Encoding utf8 (Join-Path $out 'cleanup-warning.txt') $_.Exception.Message}}
  if(Test-Path $anchorBackup){Remove-Item $anchorBackup -Force}
  Remove-Item -LiteralPath $journalPath -Force
  $staleFailure=Join-Path $PSScriptRoot 'last-failure-manifest.json';if(Test-Path $staleFailure){Remove-Item -LiteralPath $staleFailure -Force}
  Get-Content -Raw (Join-Path $out 'results.json')
} catch {
  $end=(Get-Date).ToUniversalTime()
  $outText=if(Test-Path $stdout){Get-Content -Raw $stdout}else{''}
  $errText=if(Test-Path $stderr){Get-Content -Raw $stderr}else{''}
  $failure=[ordered]@{schema_version=2;run_id=$cfg.run_id;status='Failed';started_utc=$start.ToString('o');finished_utc=$end.ToString('o');exit_code=$exit;
    stdout=$outText;stderr=($errText+"`n$($_.Exception.Message)");
    environment=[ordered]@{pwsh=$PSVersionTable.PSVersion.ToString();dotnet=[System.Environment]::Version.ToString();os=[System.Runtime.InteropServices.RuntimeInformation]::OSDescription}}
  $failure|ConvertTo-Json -Depth 8|Set-Content -Encoding utf8 (Join-Path $PSScriptRoot 'last-failure-manifest.json')
  if($stage-and(Test-Path $stage)){Remove-Item $stage -Recurse -Force}
  throw
} finally {
  if($null-ne$lockStream){$lockStream.Dispose()}
  if(Test-Path $lockPath){Remove-Item -LiteralPath $lockPath -Force}
}
