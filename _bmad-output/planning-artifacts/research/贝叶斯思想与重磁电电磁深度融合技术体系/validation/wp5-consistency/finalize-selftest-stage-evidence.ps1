[CmdletBinding()]
param(
  [ValidateSet('upstream-lineage','allowlist','registry','language-structure-boundary','publish','signoff','lineage-migration')]
  [string]$Stage
)

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$resultDir = Join-Path $vroot 'release-evidence-v1/stages'
$pointer = Get-Content -Raw -LiteralPath (Join-Path $vroot 'active-output.json') | ConvertFrom-Json -ErrorAction Stop
$fixturesPath = Join-Path $vroot 'selftest-fixture-manifest.json'
$fixtures = Get-Content -Raw -LiteralPath $fixturesPath | ConvertFrom-Json -ErrorAction Stop
$validator = Join-Path (Split-Path -Parent (Split-Path -Parent $vroot)) 'validate-wp5.ps1'
$root = Split-Path -Parent (Split-Path -Parent $vroot)
$rootPath = Join-Path $root 'WP5-consistency-input-root.sha256'
$rootAnchorPath = Join-Path $vroot 'WP5-consistency-root-anchor.sha256'
$ids = @($fixtures.fixtures | Where-Object { $_.stage -ceq $Stage } | ForEach-Object { [string]$_.id })
$fixtureManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $fixturesPath).Hash.ToLowerInvariant()
$validatorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $validator).Hash.ToLowerInvariant()

function Get-RootBinding {
  $rootLines = @(Get-Content -LiteralPath $rootPath)
  if($rootLines.Count-ne31-or$rootLines[0]-cne'# WP5 consistency root v1'-or$rootLines[1]-cne''){throw 'stage finalizer root identity'}
  $rootMembers = @($rootLines[2..30])
  foreach($member in $rootMembers){
    if($member-cnotmatch'^([0-9a-f]{64})  (.+)$'){throw 'stage finalizer root member syntax'}
    $memberPath=[IO.Path]::GetFullPath((Join-Path $root $Matches[2]))
    $relative=[IO.Path]::GetRelativePath([IO.Path]::GetFullPath($root),$memberPath).Replace('\','/')
    if($relative-cne$Matches[2]-or(Get-FileHash -Algorithm SHA256 -LiteralPath $memberPath).Hash.ToLowerInvariant()-cne$Matches[1]){throw 'stage finalizer root member binding'}
  }
  $memberRootHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes(($rootMembers-join"`n")+"`n"))).ToLowerInvariant()
  $rootFileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rootPath).Hash.ToLowerInvariant()
  $anchorBytes=[IO.File]::ReadAllBytes($rootAnchorPath);$anchorText=[Text.UTF8Encoding]::new($false,$true).GetString($anchorBytes)
  if($anchorBytes.Length-ne65-or$anchorText-cne($rootFileHash+"`n")){throw 'stage finalizer root anchor binding'}
  [pscustomobject]@{member_root_sha256=$memberRootHash;root_file_sha256=$rootFileHash;root_anchor_file_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $rootAnchorPath).Hash.ToLowerInvariant()}
}
$beforeRoots=Get-RootBinding
$memberRootHash=$beforeRoots.member_root_sha256
$rootFileHash=$beforeRoots.root_file_sha256
$rootAnchorFileHash=$beforeRoots.root_anchor_file_sha256

function Get-TextSha256([string]$Text) {
  [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes($Text))).ToLowerInvariant()
}
function Assert-ExactNames($Object, [string[]]$Names, [string]$Label) {
  $actual = @($Object.PSObject.Properties.Name)
  if ($actual.Count -ne $Names.Count -or (Compare-Object -CaseSensitive $actual $Names)) { throw "$Label exact schema" }
}
function Assert-OrdinalExact([string[]]$Actual, [string[]]$Expected, [string]$Label) {
  if ($Actual.Count -ne $Expected.Count) { throw $Label }
  for ($i = 0; $i -lt $Expected.Count; $i++) { if ($Actual[$i] -cne $Expected[$i]) { throw $Label } }
}
function Assert-OrdinalUnique([string[]]$Values, [string]$Label) {
  $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  foreach ($value in @($Values)) { if ([string]::IsNullOrWhiteSpace($value) -or -not $seen.Add($value)) { throw $Label } }
}
function Assert-ResultAgainstOracle($Result,[string]$ExpectedStage,[string]$Label) {
  $fixtureId=[string]$Result.fixture_id
  if(-not$fixtureOracle.ContainsKey($fixtureId)){throw "$Label oracle"}
  $oracle=$fixtureOracle[$fixtureId]
  $actualExpected=@($Result.expected_rejections|ForEach-Object{[string]$_})
  $oracleExpected=@($oracle.expected_rejections|ForEach-Object{[string]$_})
  $expectedCriterion=if([int]$oracle.expected_exit-eq0){'child accepts this positive fixture'}else{'child rejects this fixture with one predeclared business assertion'}
  $validOutcome=if([int]$oracle.expected_exit-eq0){
    [int]$Result.actual_exit-eq0-and[string]::IsNullOrEmpty([string]$Result.actual_rejection)
  }else{
    [int]$Result.actual_exit-ne0-and$oracleExpected.Count-eq1-and[string]$Result.actual_rejection-ceq[string]$oracleExpected[0]
  }
  if($oracle.stage-cne$ExpectedStage-or[int]$Result.expected_exit-ne[int]$oracle.expected_exit-or
    $actualExpected.Count-ne$oracleExpected.Count-or($actualExpected-join"`0")-cne($oracleExpected-join"`0")-or
    -not$validOutcome-or-not[bool]$Result.matched-or[string]$Result.success_criterion-cne$expectedCriterion-or
    -not($Result.case-is[string])-or$Result.case-cne$oracle.canonical_case-or[int64]$Result.duration_ms-lt0){throw "$Label oracle"}
}
function Get-ResultStableRecord($Result) {
  [ordered]@{
    fixture_id=[string]$Result.fixture_id;case=[string]$Result.case
    expected_exit=[int]$Result.expected_exit;actual_exit=[int]$Result.actual_exit
    expected_rejections=@($Result.expected_rejections|ForEach-Object{[string]$_})
    actual_rejection=[string]$Result.actual_rejection
    success_criterion=[string]$Result.success_criterion;matched=[bool]$Result.matched
  }
}
function Get-PartialStableHash($Item) {
  $stable=[ordered]@{
    source_run_instance_id=[string]$Item.source_run_instance_id
    source_version_path=[string]$Item.source_version_path
    source_manifest_sha256=[string]$Item.source_manifest_sha256
    validator_sha256=[string]$Item.validator_sha256
    fixture_manifest_sha256=[string]$Item.fixture_manifest_sha256
    member_root_sha256=[string]$Item.member_root_sha256
    root_file_sha256=[string]$Item.root_file_sha256
    root_anchor_file_sha256=[string]$Item.root_anchor_file_sha256
    stage=[string]$Item.stage
    fixture_id_set=@($Item.fixture_id_set|ForEach-Object{[string]$_})
    batch_role=[string]$Item.batch_role
    fixture_results=@($Item.fixture_results|ForEach-Object{Get-ResultStableRecord $_})
    status=[string]$Item.status
    validator_exit=[int]$Item.validator_exit
    pass_marker_count=[int]$Item.pass_marker_count
  }
  Get-TextSha256 ($stable|ConvertTo-Json -Depth 20 -Compress)
}
function Write-NewAtomicFile([string]$Path,[byte[]]$Bytes) {
  if(Test-Path -LiteralPath $Path){throw 'Refusing to overwrite final evidence.'}
  $temp=Join-Path (Split-Path -Parent $Path) ('.tmp-'+[IO.Path]::GetFileName($Path)+'-'+[guid]::NewGuid().ToString('N'))
  try{
    $stream=[IO.File]::Open($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
    [IO.File]::Move($temp,$Path)
  }finally{
    if(Test-Path -LiteralPath $temp){Remove-Item -Force -LiteralPath $temp}
  }
}

$fixtureFields=@('id','stage','canonical_case','expected_exit','expected_rejections')
$fixtureOracle=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
if($fixtures.schema-cne'wp5-selftest-fixture-manifest-v3'-or@($fixtures.fixtures).Count-ne300){throw 'Fixture oracle manifest identity invalid.'}
foreach($fixture in @($fixtures.fixtures)){
  Assert-ExactNames $fixture $fixtureFields 'Fixture oracle manifest record'
  $expectedRejections=@($fixture.expected_rejections)
  $validOracle=if([int]$fixture.expected_exit-eq0){$expectedRejections.Count-eq0}elseif([int]$fixture.expected_exit-eq1){$expectedRejections.Count-eq1-and-not[string]::IsNullOrWhiteSpace([string]$expectedRejections[0])}else{$false}
  if($fixture.stage-cnotin @('upstream-lineage','allowlist','registry','language-structure-boundary','publish','signoff','lineage-migration')-or
    -not($fixture.canonical_case-is[string])-or$fixture.canonical_case-cne$fixture.id-or
    -not$validOracle-or-not$fixtureOracle.TryAdd([string]$fixture.id,$fixture)){throw "Fixture oracle manifest record invalid: $($fixture.id)"}
}
Assert-OrdinalUnique $ids 'stage fixture identity violation'

$partialNames = @('schema','evidence_class','source_run_instance_id','source_version_path','source_manifest_sha256','validator_sha256','fixture_manifest_sha256','member_root_sha256','root_file_sha256','root_anchor_file_sha256','stage','fixture_count','fixture_id_set','batch_role','fixture_results','status','completed_at_utc','output_sha256','validator_exit','pass_marker_count')
$resultNames = @('fixture_id','case','expected_exit','actual_exit','expected_rejections','actual_rejection','success_criterion','matched','duration_ms')
$selectedByBatch = [ordered]@{}
foreach ($file in @(Get-ChildItem -LiteralPath $resultDir -File -Filter 'partial-selftest-*.json' | Sort-Object Name)) {
  $item = Get-Content -Raw -LiteralPath $file.FullName | ConvertFrom-Json -ErrorAction Stop
  if ($item.source_run_instance_id -cne $pointer.run_instance_id -or $item.source_version_path -cne $pointer.version_path -or $item.source_manifest_sha256 -cne $pointer.manifest_sha256 -or $item.fixture_manifest_sha256 -cne $fixtureManifestHash -or $item.validator_sha256 -cne $validatorHash -or $item.member_root_sha256 -cne $memberRootHash -or $item.root_file_sha256 -cne $rootFileHash -or $item.root_anchor_file_sha256 -cne $rootAnchorFileHash) { continue }
  if ($item.stage -cne $Stage) { continue }
  Assert-ExactNames $item $partialNames ('partial '+$file.Name)
  if ($item.schema -cne 'wp5-selftest-partial-evidence-v1' -or $item.batch_role -cne 'stage' -or $item.stage -cne $Stage -or $item.status -cne 'Passed' -or [int]$item.validator_exit -ne 0 -or [int]$item.pass_marker_count -ne 1 -or $item.output_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw "partial binding $($file.Name)" }
  $partialIds = @($item.fixture_id_set | ForEach-Object { [string]$_ })
  $resultIds = @($item.fixture_results | ForEach-Object { [string]$_.fixture_id })
  if ([int]$item.fixture_count -ne $partialIds.Count) { throw "partial fixture_count $($file.Name)" }
  Assert-OrdinalUnique $partialIds "partial fixture_id_set $($file.Name)"
  Assert-OrdinalExact $resultIds $partialIds "partial result id order $($file.Name)"
  foreach ($result in @($item.fixture_results)) {
    Assert-ExactNames $result $resultNames ('partial result '+$file.Name)
    Assert-ResultAgainstOracle $result $Stage "partial result $($result.fixture_id)"
  }
  $batchKey=$partialIds-join"`0"
  $stableHash=Get-PartialStableHash $item
  if($selectedByBatch.Contains($batchKey)){
    if($selectedByBatch[$batchKey].stable_hash-cne$stableHash){throw "Partial evidence conflicting retry $($file.Name)"}
    continue
  }
  $selectedByBatch[$batchKey]=[pscustomobject]@{path=$file.Name;sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant();stable_hash=$stableHash;data=$item}
}

$partials=@($selectedByBatch.Values)
$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$resultById=[ordered]@{}
foreach($partial in $partials){
  foreach($result in @($partial.data.fixture_results)){
    if(-not$seen.Add([string]$result.fixture_id)){throw "Partial evidence overlapping fixture $($result.fixture_id)"}
    $resultById[[string]$result.fixture_id]=$result
  }
}
Assert-OrdinalUnique $ids 'stage fixture identity violation'
if($seen.Count-ne$ids.Count){throw 'Partial evidence does not exactly cover the stage fixture set.'}
foreach($id in $ids){if(-not$seen.Contains($id)){throw 'Partial evidence does not exactly cover the stage fixture set.'}}

$ordered=@($ids|ForEach-Object{
  $result=$resultById[$_]
  [ordered]@{
    fixture_id=[string]$result.fixture_id;case=[string]$result.case
    expected_exit=[int]$result.expected_exit;actual_exit=[int]$result.actual_exit
    expected_rejections=@($result.expected_rejections|ForEach-Object{[string]$_})
    actual_rejection=[string]$result.actual_rejection
    success_criterion=[string]$result.success_criterion;matched=[bool]$result.matched
    duration_ms=[int64]$result.duration_ms
  }
})
$partialEvidence=@($partials|ForEach-Object{[ordered]@{path=$_.path;sha256=$_.sha256}})
$partialRootText=(@($partialEvidence|ForEach-Object{"$($_.sha256)  $($_.path)"})-join"`n")+"`n"
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$file='selftest-{0}-{1}-{2}.json' -f $pointer.run_instance_id,$Stage,$stamp
$path=Join-Path $resultDir $file
$payload=[ordered]@{
  schema='wp5-selftest-finalized-evidence-v1'
  evidence_class='Finalized from exact, non-overlapping partial evidence; not an input to its referenced manifest'
  source_run_instance_id=$pointer.run_instance_id;source_version_path=$pointer.version_path;source_manifest_sha256=$pointer.manifest_sha256
  validator_sha256=$validatorHash;fixture_manifest_sha256=$fixtureManifestHash
  member_root_sha256=$memberRootHash;root_file_sha256=$rootFileHash;root_anchor_file_sha256=$rootAnchorFileHash
  stage=$Stage;fixture_count=$ids.Count
  fixture_id_set=$ids;batch_role='stage';partial_evidence=$partialEvidence;fixture_results=$ordered
  status='Passed';completed_at_utc=[DateTime]::UtcNow.ToString('o');output_sha256=Get-TextSha256 $partialRootText
  validator_exit=0;pass_marker_count=1
}
$bytes=[Text.UTF8Encoding]::new($false).GetBytes((($payload|ConvertTo-Json -Depth 20)+"`n"))
$afterRoots=Get-RootBinding
if($afterRoots.member_root_sha256-cne$memberRootHash-or$afterRoots.root_file_sha256-cne$rootFileHash-or$afterRoots.root_anchor_file_sha256-cne$rootAnchorFileHash){throw 'stage finalizer root binding drift'}
Write-NewAtomicFile $path $bytes
Write-Output "PASS evidence=$file sha256=$((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()) stage=$Stage fixtures=$($ids.Count) source_manifest=$($pointer.manifest_sha256)"
