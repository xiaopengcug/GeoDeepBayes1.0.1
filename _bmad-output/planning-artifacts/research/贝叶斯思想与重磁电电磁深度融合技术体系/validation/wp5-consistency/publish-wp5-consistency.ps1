[CmdletBinding()]param([ValidateSet('','SnapshotDrift','AfterStage','AfterVersion','AfterFlush','AfterReplace')][string]$InjectFailure='')
$ErrorActionPreference='Stop'
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
$root=Split-Path -Parent (Split-Path -Parent $here)
$lockPath=Join-Path $here '.publish.lock'
$active=Join-Path $here 'active-output.json'
$activeManifest=Join-Path $root 'ACTIVE_MANIFEST'
$backup=$active+'.bak'
$journalPath=Join-Path $here '.candidate-publish-journal.json'
$validatorSnapshotPath=$null
$stage=$null
$tmp=$null
$lock=$null

function Get-Sha256([string]$Path){
 (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}
function Get-BytesSha256([byte[]]$Bytes){
 [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
}
function Read-ValidatedPointerBytes([byte[]]$Bytes,[string]$Label){
 try{
  $text=[Text.UTF8Encoding]::new($false,$true).GetString($Bytes)
  $pointer=$text|ConvertFrom-Json -ErrorAction Stop
 }catch{throw "WP5 candidate journal $Label invalid"}
 $names=@($pointer.PSObject.Properties.Name)
 $expected=@('schema','run_instance_id','version_path','manifest_sha256')
 if($pointer.schema-cne'wp5-active-output-v1'-or(Compare-Object $names $expected)-or$pointer.run_instance_id-cnotmatch'^[0-9]{8}T[0-9]{9}Z-[0-9a-f]{32}$'-or$pointer.version_path-cne('versions/'+$pointer.run_instance_id)-or$pointer.manifest_sha256-cnotmatch'^[0-9a-f]{64}$'){throw "WP5 candidate journal $Label invalid"}
 $manifestPath=Join-Path $here ($pointer.version_path+'/manifest.json')
 if(-not(Test-Path -LiteralPath $manifestPath)-or(Get-Sha256 $manifestPath)-cne$pointer.manifest_sha256){throw "WP5 candidate journal $Label manifest invalid"}
 $pointer
}
function Read-ValidatedAliasBytes([byte[]]$Bytes,[string]$ExpectedManifest,[string]$Label){
 try{$text=[Text.UTF8Encoding]::new($false,$true).GetString($Bytes)}catch{throw "WP5 candidate journal $Label invalid"}
 if($Bytes.Length-ne65-or$text-cne($ExpectedManifest+"`n")){throw "WP5 candidate journal $Label invalid"}
 $text
}
function Write-AtomicBytes([string]$Path,[byte[]]$Bytes){
 $temp=$Path+'.tmp-'+[guid]::NewGuid().ToString('N')
 $bak=$Path+'.bak-'+[guid]::NewGuid().ToString('N')
 $committed=$false
 try{
  $stream=[IO.File]::Open($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
  if(Test-Path -LiteralPath $Path){[IO.File]::Replace($temp,$Path,$bak,$true)}else{[IO.File]::Move($temp,$Path)}
  $committed=$true
 }finally{
  if(Test-Path -LiteralPath $temp){Remove-Item -Force -LiteralPath $temp}
  if($committed-and(Test-Path -LiteralPath $bak)){Remove-Item -Force -LiteralPath $bak}
 }
}
function Write-AtomicJson($Value,[string]$Path){
 $json=($Value|ConvertTo-Json -Depth 12)+"`n"
 Write-AtomicBytes $Path ([Text.UTF8Encoding]::new($false).GetBytes($json))
}
function Test-NewCandidatePointer($Journal){
 try{
  if(-not(Test-Path -LiteralPath $active)-or-not(Test-Path -LiteralPath $activeManifest)){return $false}
  $pointer=Read-ValidatedPointerBytes ([IO.File]::ReadAllBytes($active)) 'candidate pointer'
  if($pointer.schema-cne'wp5-active-output-v1'-or$pointer.run_instance_id-cne$Journal.run_instance_id-or$pointer.version_path-cne$Journal.version_path-or$pointer.manifest_sha256-cne$Journal.manifest_sha256){return $false}
  [void](Read-ValidatedAliasBytes ([IO.File]::ReadAllBytes($activeManifest)) $Journal.manifest_sha256 'candidate alias')
  $manifestPath=Join-Path $here ($Journal.version_path+'/manifest.json')
  return (Test-Path -LiteralPath $manifestPath)-and(Get-Sha256 $manifestPath)-ceq$Journal.manifest_sha256
 }catch{return $false}
}
function Assert-CandidateVersionIdentity($Journal){
 $versionPath=Join-Path $here $Journal.version_path
 if(-not(Test-Path -LiteralPath $versionPath)){return}
 $manifestPath=Join-Path $versionPath 'manifest.json'
 if(-not(Test-Path -LiteralPath $manifestPath)-or(Get-Sha256 $manifestPath)-cne$Journal.manifest_sha256){throw 'WP5 candidate journal version binding invalid'}
 try{$manifest=Get-Content -Raw -LiteralPath $manifestPath|ConvertFrom-Json -ErrorAction Stop}catch{throw 'WP5 candidate journal version binding invalid'}
 if($manifest.schema-cne'wp5-consistency-manifest-v1'-or$manifest.run_instance_id-cne$Journal.run_instance_id){throw 'WP5 candidate journal version binding invalid'}
}
function Recover-CandidatePublish{
 if(-not(Test-Path -LiteralPath $journalPath)){return}
 try{$journal=Get-Content -Raw -LiteralPath $journalPath|ConvertFrom-Json -ErrorAction Stop}catch{throw 'WP5 candidate journal invalid'}
 $names=@($journal.PSObject.Properties.Name)
 $expected=@('schema','transaction_id','phase','run_instance_id','stage_leaf','version_path','manifest_sha256','validator_sha256','fixture_manifest_sha256','had_active','old_pointer_base64','old_pointer_sha256','old_run_instance_id','old_version_path','old_manifest_sha256','had_alias','old_alias_base64','old_alias_sha256')
 if($journal.schema-cne'wp5-candidate-publish-journal-v3'-or(Compare-Object $names $expected)-or$journal.transaction_id-cnotmatch'^[0-9a-f]{32}$'-or$journal.run_instance_id-cnotmatch'^[0-9]{8}T[0-9]{9}Z-[0-9a-f]{32}$'-or$journal.stage_leaf-cnotmatch'^\.stage-[0-9a-f]{32}$'-or$journal.version_path-cne('versions/'+$journal.run_instance_id)-or$journal.manifest_sha256-cnotmatch'^[0-9a-f]{64}$'-or$journal.validator_sha256-cnotmatch'^[0-9a-f]{64}$'-or$journal.fixture_manifest_sha256-cnotmatch'^[0-9a-f]{64}$'-or-not($journal.had_active-is[bool])-or-not($journal.had_alias-is[bool])-or$journal.had_alias-ne$journal.had_active-or$journal.phase-notin@('prepared','version-moved','candidate-committed')){throw 'WP5 candidate journal invalid'}
 $oldBytes=$null
 $oldAliasBytes=$null
 if($journal.had_active){
  if($journal.old_pointer_sha256-cnotmatch'^[0-9a-f]{64}$'-or$journal.old_run_instance_id-cnotmatch'^[0-9]{8}T[0-9]{9}Z-[0-9a-f]{32}$'-or$journal.old_version_path-cne('versions/'+$journal.old_run_instance_id)-or$journal.old_manifest_sha256-cnotmatch'^[0-9a-f]{64}$'){throw 'WP5 candidate journal old pointer invalid'}
  try{$oldBytes=[Convert]::FromBase64String([string]$journal.old_pointer_base64)}catch{throw 'WP5 candidate journal old pointer invalid'}
  if((Get-BytesSha256 $oldBytes)-cne$journal.old_pointer_sha256){throw 'WP5 candidate journal old pointer invalid'}
  $oldPointer=Read-ValidatedPointerBytes $oldBytes 'old pointer'
  if($oldPointer.run_instance_id-cne$journal.old_run_instance_id-or$oldPointer.version_path-cne$journal.old_version_path-or$oldPointer.manifest_sha256-cne$journal.old_manifest_sha256){throw 'WP5 candidate journal old pointer binding invalid'}
 }elseif(@($journal.old_pointer_base64,$journal.old_pointer_sha256,$journal.old_run_instance_id,$journal.old_version_path,$journal.old_manifest_sha256|Where-Object{$_-cne''}).Count-ne0){throw 'WP5 candidate journal old pointer invalid'}
 if($journal.had_alias){
  if($journal.old_alias_sha256-cnotmatch'^[0-9a-f]{64}$'){throw 'WP5 candidate journal old alias invalid'}
  try{$oldAliasBytes=[Convert]::FromBase64String([string]$journal.old_alias_base64)}catch{throw 'WP5 candidate journal old alias invalid'}
  if((Get-BytesSha256 $oldAliasBytes)-cne$journal.old_alias_sha256){throw 'WP5 candidate journal old alias invalid'}
  [void](Read-ValidatedAliasBytes $oldAliasBytes $journal.old_manifest_sha256 'old alias')
 }elseif(@($journal.old_alias_base64,$journal.old_alias_sha256|Where-Object{$_-cne''}).Count-ne0){throw 'WP5 candidate journal old alias invalid'}
 $stagePath=Join-Path $here $journal.stage_leaf
 $versionPath=Join-Path $here $journal.version_path
 if(Test-NewCandidatePointer $journal){
  if(Test-Path -LiteralPath $stagePath){Remove-Item -Recurse -Force -LiteralPath $stagePath}
  if(Test-Path -LiteralPath $backup){Remove-Item -Force -LiteralPath $backup}
  Remove-Item -Force -LiteralPath $journalPath
  return
 }
 Assert-CandidateVersionIdentity $journal
 if(Test-Path -LiteralPath $active){
  $currentBytes=[IO.File]::ReadAllBytes($active)
  $currentHash=Get-BytesSha256 $currentBytes
  if($journal.had_active-and$currentHash-ceq$journal.old_pointer_sha256){}else{
   try{$currentPointer=Read-ValidatedPointerBytes $currentBytes 'current pointer'}catch{throw 'WP5 candidate journal current pointer invalid'}
   if($currentPointer.run_instance_id-cne$journal.run_instance_id-or$currentPointer.version_path-cne$journal.version_path-or$currentPointer.manifest_sha256-cne$journal.manifest_sha256){throw 'WP5 candidate journal current pointer binding invalid'}
   if($journal.had_active){Write-AtomicBytes $active $oldBytes}else{Remove-Item -Force -LiteralPath $active}
  }
 }elseif($journal.had_active){
  Write-AtomicBytes $active $oldBytes
 }
 if(Test-Path -LiteralPath $activeManifest){
  $currentAliasBytes=[IO.File]::ReadAllBytes($activeManifest)
  $currentAliasHash=Get-BytesSha256 $currentAliasBytes
  if($journal.had_alias-and$currentAliasHash-ceq$journal.old_alias_sha256){}else{
   try{[void](Read-ValidatedAliasBytes $currentAliasBytes $journal.manifest_sha256 'current alias')}catch{throw 'WP5 candidate journal current alias invalid'}
   if($journal.had_alias){Write-AtomicBytes $activeManifest $oldAliasBytes}else{Remove-Item -Force -LiteralPath $activeManifest}
  }
 }elseif($journal.had_alias){
  Write-AtomicBytes $activeManifest $oldAliasBytes
 }
 if(Test-Path -LiteralPath $stagePath){Remove-Item -Recurse -Force -LiteralPath $stagePath}
 if(Test-Path -LiteralPath $versionPath){Remove-Item -Recurse -Force -LiteralPath $versionPath}
 if(Test-Path -LiteralPath $backup){Remove-Item -Force -LiteralPath $backup}
 Remove-Item -Force -LiteralPath $journalPath
}

try{
 try{$lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}catch{throw 'WP5 publish lock busy'}
 Recover-CandidatePublish
 if(-not(Test-Path -LiteralPath $active)-and(Test-Path -LiteralPath $backup)){Move-Item -LiteralPath $backup -Destination $active}
 Get-ChildItem -LiteralPath $here -Directory -Filter '.stage-*'|Remove-Item -Recurse -Force
 Get-ChildItem -LiteralPath $here -File -Filter 'active-output.json.tmp-*'|Remove-Item -Force
 Get-ChildItem -LiteralPath $here -File -Filter '.candidate-publish-journal.json.tmp-*'|Remove-Item -Force

 $contractPath=Join-Path $here 'consistency-contract.json'
 $contract=Get-Content -Raw -LiteralPath $contractPath|ConvertFrom-Json
 $validator=Join-Path $root 'validate-wp5.ps1'
 $fixturesPath=Join-Path $here 'selftest-fixture-manifest.json'
 $validatorHash=Get-Sha256 $validator
 $fixtureManifestHash=Get-Sha256 $fixturesPath
 $validatorSnapshotPath=Join-Path $here ('.validator-snapshot-'+[guid]::NewGuid().ToString('N')+'.ps1')
 [IO.File]::WriteAllBytes($validatorSnapshotPath,[IO.File]::ReadAllBytes($validator))
 if((Get-Sha256 $validatorSnapshotPath)-cne$validatorHash){throw 'WP5 validator snapshot drift'}

 $sourceNames=@(
  'consistency-contract.json',
  'claim-ledger.json',
  'previous-claim-ledger.json',
  'scope-registry.json',
  'high-risk-classification.json',
  'ledger-lineage.json',
  'claim-ledger.loop32-anchor.json',
  'claim-ledger.loop32.text-migration.json',
  'scope-registry-lineage.json',
  'scope-registry.loop32-anchor.json',
  'high-risk-classification-lineage.json',
  'high-risk-classification.loop32-anchor.json',
  'publish-wp5-consistency.ps1'
 )
 $sourceSnapshot=[ordered]@{};foreach($name in $sourceNames){$sourceSnapshot[$name]=Get-Sha256 (Join-Path $here $name)}
 $snapshot=[ordered]@{};foreach($p in $contract.documents.PSObject.Properties){$snapshot[$p.Name]=Get-Sha256 (Join-Path $root $p.Name)};foreach($p in $contract.supporting_files.PSObject.Properties){$snapshot[$p.Name]=Get-Sha256 (Join-Path $root $p.Name)}

 & (Get-Process -Id $PID).Path -NoProfile -File $validatorSnapshotPath -RootOverride $root -SemanticOnly *> $null
 $scanResult=[ordered]@{status=if($LASTEXITCODE-eq0){'Passed'}else{'Failed'};validator_exit_code=$LASTEXITCODE};if($scanResult.status-cne'Passed'){throw 'WP5 semantic scan failed'}
 if($InjectFailure-ceq'SnapshotDrift'){$first=@($snapshot.Keys)[0];$snapshot[$first]='0'*64}
 foreach($p in $snapshot.GetEnumerator()){if((Get-Sha256 (Join-Path $root $p.Key))-cne$p.Value){throw 'WP5 snapshot drift'}}
 foreach($p in $sourceSnapshot.GetEnumerator()){if((Get-Sha256 (Join-Path $here $p.Key))-cne$p.Value){throw 'WP5 source snapshot drift'}}
 if((Get-Sha256 $validator)-cne$validatorHash-or(Get-Sha256 $validatorSnapshotPath)-cne$validatorHash){throw 'WP5 validator snapshot drift'}
 if((Get-Sha256 $fixturesPath)-cne$fixtureManifestHash){throw 'WP5 fixture snapshot drift'}

 $run=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N')
 $transactionId=[guid]::NewGuid().ToString('N')
 $stageLeaf='.stage-'+[guid]::NewGuid().ToString('N')
 $stage=Join-Path $here $stageLeaf
 New-Item -ItemType Directory -Path $stage|Out-Null
 $docs=[ordered]@{};foreach($p in $snapshot.GetEnumerator()){$docs[$p.Key]=$p.Value}
 $scan=[ordered]@{schema='wp5-consistency-scan-v1';run_instance_id=$run;status=$scanResult.status;evidence_id='EVD-WP5-GOVERNANCE';claim='Document consistency and evidence-boundary governance only';documents=$docs}
 $scan|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 (Join-Path $stage 'scan.json')
 $manifest=[ordered]@{schema='wp5-consistency-manifest-v1';run_instance_id=$run;status=$scanResult.status;evidence_class='Document-governance';files=[ordered]@{'scan.json'=Get-Sha256 (Join-Path $stage 'scan.json')};sources=$sourceSnapshot}
 $manifest|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 (Join-Path $stage 'manifest.json')
 $mh=Get-Sha256 (Join-Path $stage 'manifest.json')
 $hadActive=Test-Path -LiteralPath $active
 $hadAlias=Test-Path -LiteralPath $activeManifest
 if($hadAlias-ne$hadActive){throw 'WP5 active pointer and ACTIVE_MANIFEST presence mismatch'}
 $oldPointerBase64='';$oldPointerSha256='';$oldRunInstanceId='';$oldVersionPath='';$oldManifestSha256=''
 $oldAliasBase64='';$oldAliasSha256=''
 if($hadActive){
  $oldBytes=[IO.File]::ReadAllBytes($active)
  $oldPointer=Read-ValidatedPointerBytes $oldBytes 'old pointer'
  $oldPointerBase64=[Convert]::ToBase64String($oldBytes);$oldPointerSha256=Get-BytesSha256 $oldBytes
  $oldRunInstanceId=$oldPointer.run_instance_id;$oldVersionPath=$oldPointer.version_path;$oldManifestSha256=$oldPointer.manifest_sha256
  $oldAliasBytes=[IO.File]::ReadAllBytes($activeManifest);[void](Read-ValidatedAliasBytes $oldAliasBytes $oldManifestSha256 'old alias')
  $oldAliasBase64=[Convert]::ToBase64String($oldAliasBytes);$oldAliasSha256=Get-BytesSha256 $oldAliasBytes
 }
 $journal=[ordered]@{
  schema='wp5-candidate-publish-journal-v3';transaction_id=$transactionId;phase='prepared';run_instance_id=$run
  stage_leaf=$stageLeaf;version_path=('versions/'+$run);manifest_sha256=$mh
  validator_sha256=$validatorHash;fixture_manifest_sha256=$fixtureManifestHash
  had_active=$hadActive;old_pointer_base64=$oldPointerBase64;old_pointer_sha256=$oldPointerSha256
  old_run_instance_id=$oldRunInstanceId;old_version_path=$oldVersionPath;old_manifest_sha256=$oldManifestSha256
  had_alias=$hadAlias;old_alias_base64=$oldAliasBase64;old_alias_sha256=$oldAliasSha256
 }
 Write-AtomicJson $journal $journalPath
 if($InjectFailure-ceq'AfterStage'){throw 'WP5 injected failure AfterStage'}

 $versions=Join-Path $here 'versions';New-Item -ItemType Directory -Force $versions|Out-Null
 $dest=Join-Path $versions $run;Move-Item -LiteralPath $stage -Destination $dest;$stage=$null
 $journal.phase='version-moved';Write-AtomicJson $journal $journalPath
 if($InjectFailure-ceq'AfterVersion'){throw 'WP5 injected failure AfterVersion'}

 $tmp=$active+'.tmp-'+[guid]::NewGuid().ToString('N')
 $json=[ordered]@{schema='wp5-active-output-v1';run_instance_id=$run;version_path=('versions/'+$run);manifest_sha256=$mh}|ConvertTo-Json
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($json+"`n")
 $fs=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$fs.Write($bytes,0,$bytes.Length);$fs.Flush($true)}finally{$fs.Dispose()}
 if($InjectFailure-ceq'AfterFlush'){throw 'WP5 injected failure AfterFlush'}
 if(Test-Path -LiteralPath $active){[IO.File]::Replace($tmp,$active,$backup,$true)}else{Move-Item -LiteralPath $tmp -Destination $active};$tmp=$null
 if($InjectFailure-ceq'AfterReplace'){
  if(Test-Path -LiteralPath $backup){
   $failed=$active+'.failed';[IO.File]::Replace($backup,$active,$failed,$true);Remove-Item -Force -LiteralPath $failed
  }elseif(-not$hadActive-and(Test-Path -LiteralPath $active)){
   Remove-Item -Force -LiteralPath $active
  }
  if(Test-Path -LiteralPath $dest){Remove-Item -Recurse -Force -LiteralPath $dest}
  if(Test-Path -LiteralPath $journalPath){Remove-Item -Force -LiteralPath $journalPath}
  throw 'WP5 injected failure AfterReplace'
 }
 $newAliasBytes=[Text.UTF8Encoding]::new($false).GetBytes($mh+"`n")
 Write-AtomicBytes $activeManifest $newAliasBytes
 $journal.phase='candidate-committed';Write-AtomicJson $journal $journalPath
 if(Test-Path -LiteralPath $backup){Remove-Item -Force -LiteralPath $backup}
 Remove-Item -Force -LiteralPath $journalPath
 "PASS version=$run"
}finally{
 if($stage-and(Test-Path -LiteralPath $stage)){Remove-Item -Recurse -Force -LiteralPath $stage}
 if($tmp-and(Test-Path -LiteralPath $tmp)){Remove-Item -Force -LiteralPath $tmp}
 if($validatorSnapshotPath-and(Test-Path -LiteralPath $validatorSnapshotPath)){Remove-Item -Force -LiteralPath $validatorSnapshotPath}
 if($null-ne$lock){$lock.Dispose()}
}
