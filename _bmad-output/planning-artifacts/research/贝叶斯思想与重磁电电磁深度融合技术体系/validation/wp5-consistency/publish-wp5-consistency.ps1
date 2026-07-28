[CmdletBinding()]param([ValidateSet('','SnapshotDrift','AfterStage','AfterVersion','AfterFlush','AfterReplace')][string]$InjectFailure='')
$ErrorActionPreference='Stop'
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
$root=Split-Path -Parent (Split-Path -Parent $here)
$lockPath=Join-Path $here '.publish.lock'
try{$lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}catch{throw 'WP5 publish lock busy'}
$active=Join-Path $here 'active-output.json';$backup=$active+'.bak'
if(-not(Test-Path $active)-and(Test-Path $backup)){Move-Item -LiteralPath $backup -Destination $active}
Get-ChildItem -LiteralPath $here -Directory -Filter '.stage-*'|Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $here -File -Filter 'active-output.json.tmp-*'|Remove-Item -Force
$contractPath=Join-Path $here 'consistency-contract.json'
$contract=Get-Content -Raw -LiteralPath $contractPath|ConvertFrom-Json
$validator=Join-Path $root 'validate-wp5.ps1'
$snapshot=[ordered]@{};foreach($p in $contract.documents.PSObject.Properties){$snapshot[$p.Name]=(Get-FileHash -Algorithm SHA256 (Join-Path $root $p.Name)).Hash.ToLowerInvariant()};foreach($p in $contract.supporting_files.PSObject.Properties){$snapshot[$p.Name]=(Get-FileHash -Algorithm SHA256 (Join-Path $root $p.Name)).Hash.ToLowerInvariant()}
& (Get-Process -Id $PID).Path -NoProfile -File $validator -SemanticOnly *> $null
$scanResult=[ordered]@{status=if($LASTEXITCODE-eq0){'Passed'}else{'Failed'};validator_exit_code=$LASTEXITCODE};if($scanResult.status-cne'Passed'){throw 'WP5 semantic scan failed'}
if($InjectFailure-ceq'SnapshotDrift'){$first=@($snapshot.Keys)[0];$snapshot[$first]='0'*64}
foreach($p in $snapshot.GetEnumerator()){if((Get-FileHash -Algorithm SHA256 (Join-Path $root $p.Key)).Hash.ToLowerInvariant()-cne$p.Value){throw 'WP5 snapshot drift'}}
$run=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N')
$stage=Join-Path $here ('.stage-'+[guid]::NewGuid().ToString('N'))
$tmp=$null
New-Item -ItemType Directory -Force $stage|Out-Null
try{
 $docs=[ordered]@{}
 foreach($p in $snapshot.GetEnumerator()){$docs[$p.Key]=$p.Value}
 $scan=[ordered]@{schema='wp5-consistency-scan-v1';run_instance_id=$run;status=$scanResult.status;evidence_id='EVD-WP5-GOVERNANCE';claim='Document consistency and evidence-boundary governance only';documents=$docs}
 $scan|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 (Join-Path $stage 'scan.json')
 $manifest=[ordered]@{schema='wp5-consistency-manifest-v1';run_instance_id=$run;status=$scanResult.status;evidence_class='Document-governance';files=[ordered]@{'scan.json'=(Get-FileHash -Algorithm SHA256 (Join-Path $stage 'scan.json')).Hash.ToLowerInvariant()};sources=[ordered]@{'consistency-contract.json'=(Get-FileHash -Algorithm SHA256 $contractPath).Hash.ToLowerInvariant();'claim-ledger.json'=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'claim-ledger.json')).Hash.ToLowerInvariant();'previous-claim-ledger.json'=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'previous-claim-ledger.json')).Hash.ToLowerInvariant();'scope-registry.json'=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'scope-registry.json')).Hash.ToLowerInvariant();'high-risk-classification.json'=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'high-risk-classification.json')).Hash.ToLowerInvariant();'publish-wp5-consistency.ps1'=(Get-FileHash -Algorithm SHA256 $MyInvocation.MyCommand.Path).Hash.ToLowerInvariant()}}
 $manifest|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 (Join-Path $stage 'manifest.json')
 if($InjectFailure-ceq'AfterStage'){throw 'WP5 injected failure AfterStage'}
 $versions=Join-Path $here 'versions';New-Item -ItemType Directory -Force $versions|Out-Null
 $dest=Join-Path $versions $run;Move-Item -LiteralPath $stage -Destination $dest
 if($InjectFailure-ceq'AfterVersion'){throw 'WP5 injected failure AfterVersion'}
 $mh=(Get-FileHash -Algorithm SHA256 (Join-Path $dest 'manifest.json')).Hash.ToLowerInvariant()
 $tmp=$active+'.tmp-'+[guid]::NewGuid().ToString('N')
 $json=[ordered]@{schema='wp5-active-output-v1';run_instance_id=$run;version_path=('versions/'+$run);manifest_sha256=$mh}|ConvertTo-Json
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($json+"`n");$fs=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$fs.Write($bytes,0,$bytes.Length);$fs.Flush($true)}finally{$fs.Dispose()}
 if($InjectFailure-ceq'AfterFlush'){throw 'WP5 injected failure AfterFlush'}
 if(Test-Path $active){[IO.File]::Replace($tmp,$active,$backup,$true)}else{Move-Item -LiteralPath $tmp -Destination $active}
 if($InjectFailure-ceq'AfterReplace'){if(Test-Path $backup){$failed=$active+'.failed';[IO.File]::Replace($backup,$active,$failed,$true);Remove-Item -Force $failed};throw 'WP5 injected failure AfterReplace'}
 if(Test-Path $backup){Remove-Item -Force $backup}
 "PASS version=$run"
}finally{if(Test-Path $stage){Remove-Item -Recurse -Force -LiteralPath $stage};if($tmp-and(Test-Path $tmp)){Remove-Item -Force -LiteralPath $tmp};if($null-ne$lock){$lock.Dispose()}}






