[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$stageDir = Join-Path $vroot 'release-evidence-v1/stages'
$output = Join-Path $vroot 'release-evidence-v1/envelope.json'
$pointerPath = Join-Path $vroot 'active-output.json'
$fixturePath = Join-Path $vroot 'selftest-fixture-manifest.json'
$validatorPath = Join-Path (Split-Path -Parent (Split-Path -Parent $vroot)) 'validate-wp5.ps1'
$root = Split-Path -Parent (Split-Path -Parent $vroot)
$rootPath = Join-Path $root 'WP5-consistency-input-root.sha256'
$rootAnchorPath = Join-Path $vroot 'WP5-consistency-root-anchor.sha256'
$pointer = Get-Content -Raw -LiteralPath $pointerPath | ConvertFrom-Json -ErrorAction Stop
$fixtureManifest = Get-Content -Raw -LiteralPath $fixturePath | ConvertFrom-Json -ErrorAction Stop
$fixtureHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $fixturePath).Hash.ToLowerInvariant()
$validatorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $validatorPath).Hash.ToLowerInvariant()

function Get-RootBinding {
  $rootLines = @(Get-Content -LiteralPath $rootPath)
  if($rootLines.Count-ne31-or$rootLines[0]-cne'# WP5 consistency root v1'-or$rootLines[1]-cne''){throw 'release evidence root identity'}
  $rootMembers = @($rootLines[2..30])
  foreach($member in $rootMembers){
    if($member-cnotmatch'^([0-9a-f]{64})  (.+)$'){throw 'release evidence root member syntax'}
    $memberPath=[IO.Path]::GetFullPath((Join-Path $root $Matches[2]))
    $relative=[IO.Path]::GetRelativePath([IO.Path]::GetFullPath($root),$memberPath).Replace('\','/')
    if($relative-cne$Matches[2]-or(Get-FileHash -Algorithm SHA256 -LiteralPath $memberPath).Hash.ToLowerInvariant()-cne$Matches[1]){throw 'release evidence root member binding'}
  }
  $memberRootHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes(($rootMembers-join"`n")+"`n"))).ToLowerInvariant()
  $rootFileHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rootPath).Hash.ToLowerInvariant()
  $anchorBytes=[IO.File]::ReadAllBytes($rootAnchorPath);$anchorText=[Text.UTF8Encoding]::new($false,$true).GetString($anchorBytes)
  if($anchorBytes.Length-ne65-or$anchorText-cne($rootFileHash+"`n")){throw 'release evidence root anchor binding'}
  [pscustomobject]@{member_root_sha256=$memberRootHash;root_file_sha256=$rootFileHash;root_anchor_file_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $rootAnchorPath).Hash.ToLowerInvariant()}
}
$beforeRoots=Get-RootBinding
$memberRootHash=$beforeRoots.member_root_sha256
$rootFileHash=$beforeRoots.root_file_sha256
$rootAnchorFileHash=$beforeRoots.root_anchor_file_sha256
$expected = [ordered]@{
  'upstream-lineage' = 33
  'allowlist' = 9
  'registry' = 25
  'language-structure-boundary' = 31
  'publish' = 20
  'signoff' = 28
  'lineage-migration' = 154
}

function Get-TextSha256([string]$Text) {
  [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes($Text))).ToLowerInvariant()
}
function Assert-ExactNames($Object,[string[]]$Names,[string]$Label) {
  $actual=@($Object.PSObject.Properties.Name)
  if($actual.Count-ne$Names.Count-or(Compare-Object -CaseSensitive $actual $Names)){throw "$Label exact schema"}
}
function Assert-OrdinalExact([string[]]$Actual,[string[]]$Expected,[string]$Label) {
  if($Actual.Count-ne$Expected.Count){throw $Label}
  for($i=0;$i-lt$Expected.Count;$i++){if($Actual[$i]-cne$Expected[$i]){throw $Label}}
}
function Assert-Result($Result,[string]$Stage,[string]$Label) {
  Assert-ExactNames $Result @('fixture_id','case','expected_exit','actual_exit','expected_rejections','actual_rejection','success_criterion','matched','duration_ms') $Label
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
  if($oracle.stage-cne$Stage-or[int]$Result.expected_exit-ne[int]$oracle.expected_exit-or
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
function Get-FullResultRecord($Result) {
  [ordered]@{
    fixture_id=[string]$Result.fixture_id;case=[string]$Result.case
    expected_exit=[int]$Result.expected_exit;actual_exit=[int]$Result.actual_exit
    expected_rejections=@($Result.expected_rejections|ForEach-Object{[string]$_})
    actual_rejection=[string]$Result.actual_rejection
    success_criterion=[string]$Result.success_criterion;matched=[bool]$Result.matched
    duration_ms=[int64]$Result.duration_ms
  }
}
function Assert-PartialProvenance($Evidence,[string[]]$ExpectedIds,[string]$Stage,[string]$Label) {
  $refNames=@('path','sha256')
  $partialNames=@('schema','evidence_class','source_run_instance_id','source_version_path','source_manifest_sha256','validator_sha256','fixture_manifest_sha256','member_root_sha256','root_file_sha256','root_anchor_file_sha256','stage','fixture_count','fixture_id_set','batch_role','fixture_results','status','completed_at_utc','output_sha256','validator_exit','pass_marker_count')
  $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  $partialResultById=[ordered]@{}
  $seenPaths=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  foreach($ref in @($Evidence.partial_evidence)){
    Assert-ExactNames $ref $refNames "$Label partial reference"
    if($ref.path-cnotmatch('^partial-selftest-'+[regex]::Escape($pointer.run_instance_id)+'-'+[regex]::Escape($Stage)+'-\d{8}T\d{9}Z\.json$')-or$ref.sha256-cnotmatch'^[0-9a-f]{64}$'-or-not$seenPaths.Add([string]$ref.path)){throw "$Label partial reference"}
    $partialPath=Join-Path $stageDir ([string]$ref.path)
    if(-not(Test-Path -LiteralPath $partialPath)-or(Get-FileHash -Algorithm SHA256 -LiteralPath $partialPath).Hash.ToLowerInvariant()-cne$ref.sha256){throw "$Label partial hash"}
    $partial=Get-Content -Raw -LiteralPath $partialPath|ConvertFrom-Json -ErrorAction Stop
    Assert-ExactNames $partial $partialNames "$Label partial"
    if($partial.schema-cne'wp5-selftest-partial-evidence-v1'-or$partial.source_run_instance_id-cne$pointer.run_instance_id-or$partial.source_version_path-cne$pointer.version_path-or$partial.source_manifest_sha256-cne$pointer.manifest_sha256-or$partial.validator_sha256-cne$validatorHash-or$partial.fixture_manifest_sha256-cne$fixtureHash-or$partial.member_root_sha256-cne$memberRootHash-or$partial.root_file_sha256-cne$rootFileHash-or$partial.root_anchor_file_sha256-cne$rootAnchorFileHash-or$partial.stage-cne$Stage-or$partial.batch_role-cne'stage'-or$partial.status-cne'Passed'-or[int]$partial.validator_exit-ne0-or[int]$partial.pass_marker_count-ne1-or$partial.output_sha256-cnotmatch'^[0-9a-f]{64}$'){throw "$Label partial binding"}
    $partialIds=@($partial.fixture_id_set|ForEach-Object{[string]$_})
    $partialResultIds=@($partial.fixture_results|ForEach-Object{[string]$_.fixture_id})
    if([int]$partial.fixture_count-ne$partialIds.Count){throw "$Label partial count"}
    Assert-OrdinalExact $partialResultIds $partialIds "$Label partial result order"
    foreach($result in @($partial.fixture_results)){
      Assert-Result $result $Stage "$Label partial result"
      if(-not$seen.Add([string]$result.fixture_id)){throw "$Label partial overlap"}
      $partialResultById[[string]$result.fixture_id]=$result
    }
  }
  if($seen.Count-ne$ExpectedIds.Count){throw "$Label partial coverage"}
  foreach($id in $ExpectedIds){if(-not$seen.Contains($id)){throw "$Label partial coverage"}}
  foreach($result in @($Evidence.fixture_results)){
    $partialResult=$partialResultById[[string]$result.fixture_id]
    if($null-eq$partialResult-or((Get-FullResultRecord $partialResult|ConvertTo-Json -Depth 12 -Compress)-cne(Get-FullResultRecord $result|ConvertTo-Json -Depth 12 -Compress))){throw "$Label partial result binding"}
  }
  $rootText=(@($Evidence.partial_evidence|ForEach-Object{"$($_.sha256)  $($_.path)"})-join"`n")+"`n"
  if($Evidence.output_sha256-cne(Get-TextSha256 $rootText)){throw "$Label partial root"}
}
function Get-EvidenceStableHash($Evidence) {
  $stable=[ordered]@{
    schema=[string]$Evidence.schema
    source_run_instance_id=[string]$Evidence.source_run_instance_id
    source_version_path=[string]$Evidence.source_version_path
    source_manifest_sha256=[string]$Evidence.source_manifest_sha256
    validator_sha256=[string]$Evidence.validator_sha256
    fixture_manifest_sha256=[string]$Evidence.fixture_manifest_sha256
    member_root_sha256=[string]$Evidence.member_root_sha256
    root_file_sha256=[string]$Evidence.root_file_sha256
    root_anchor_file_sha256=[string]$Evidence.root_anchor_file_sha256
    stage=[string]$Evidence.stage
    fixture_id_set=@($Evidence.fixture_id_set|ForEach-Object{[string]$_})
    batch_role=[string]$Evidence.batch_role
    partial_evidence=if($Evidence.schema-ceq'wp5-selftest-finalized-evidence-v1'){@($Evidence.partial_evidence|ForEach-Object{[ordered]@{path=[string]$_.path;sha256=[string]$_.sha256}})}else{@()}
    fixture_results=@($Evidence.fixture_results|ForEach-Object{Get-ResultStableRecord $_})
    status=[string]$Evidence.status
    validator_exit=[int]$Evidence.validator_exit
    pass_marker_count=[int]$Evidence.pass_marker_count
  }
  Get-TextSha256 ($stable|ConvertTo-Json -Depth 20 -Compress)
}
function Validate-FormalEvidence($File,[string]$Stage,[string[]]$ExpectedIds) {
  $evidence=Get-Content -Raw -LiteralPath $File.FullName|ConvertFrom-Json -ErrorAction Stop
  $directNames=@('schema','evidence_class','source_run_instance_id','source_version_path','source_manifest_sha256','validator_sha256','fixture_manifest_sha256','member_root_sha256','root_file_sha256','root_anchor_file_sha256','stage','fixture_count','fixture_id_set','batch_role','fixture_results','status','completed_at_utc','output_sha256','validator_exit','pass_marker_count')
  $finalizedNames=@('schema','evidence_class','source_run_instance_id','source_version_path','source_manifest_sha256','validator_sha256','fixture_manifest_sha256','member_root_sha256','root_file_sha256','root_anchor_file_sha256','stage','fixture_count','fixture_id_set','batch_role','partial_evidence','fixture_results','status','completed_at_utc','output_sha256','validator_exit','pass_marker_count')
  if($evidence.schema-ceq'wp5-selftest-evidence-v1'){Assert-ExactNames $evidence $directNames "release evidence stage $Stage"}
  elseif($evidence.schema-ceq'wp5-selftest-finalized-evidence-v1'){Assert-ExactNames $evidence $finalizedNames "release evidence stage $Stage"}
  else{throw "release evidence stage $Stage schema"}
  if($evidence.source_run_instance_id-cne$pointer.run_instance_id-or$evidence.source_version_path-cne$pointer.version_path-or$evidence.source_manifest_sha256-cne$pointer.manifest_sha256-or$evidence.validator_sha256-cne$validatorHash-or$evidence.fixture_manifest_sha256-cne$fixtureHash-or$evidence.member_root_sha256-cne$memberRootHash-or$evidence.root_file_sha256-cne$rootFileHash-or$evidence.root_anchor_file_sha256-cne$rootAnchorFileHash-or$evidence.stage-cne$Stage-or[int]$evidence.fixture_count-ne$ExpectedIds.Count-or$evidence.batch_role-cne'stage'-or$evidence.status-cne'Passed'-or[int]$evidence.validator_exit-ne0-or[int]$evidence.pass_marker_count-ne1-or$evidence.output_sha256-cnotmatch'^[0-9a-f]{64}$'){throw "release evidence stage $Stage binding"}
  $actualIds=@($evidence.fixture_id_set|ForEach-Object{[string]$_})
  $resultIds=@($evidence.fixture_results|ForEach-Object{[string]$_.fixture_id})
  Assert-OrdinalExact $actualIds $ExpectedIds "release evidence stage $Stage fixture identity"
  Assert-OrdinalExact $resultIds $ExpectedIds "release evidence stage $Stage fixture identity"
  foreach($result in @($evidence.fixture_results)){Assert-Result $result $Stage "release evidence stage $Stage result"}
  if($evidence.schema-ceq'wp5-selftest-finalized-evidence-v1'){Assert-PartialProvenance $evidence $ExpectedIds $Stage "release evidence stage $Stage"}
  [pscustomobject]@{file=$File;evidence=$evidence;stable_hash=Get-EvidenceStableHash $evidence}
}

$fixtureFields=@('id','stage','canonical_case','expected_exit','expected_rejections')
$fixtureOracle=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
if($fixtureManifest.schema-cne'wp5-selftest-fixture-manifest-v3'-or@($fixtureManifest.fixtures).Count-ne300){throw 'release evidence fixture oracle manifest identity'}
foreach($fixture in @($fixtureManifest.fixtures)){
  Assert-ExactNames $fixture $fixtureFields 'release evidence fixture oracle record'
  $expectedRejections=@($fixture.expected_rejections)
  $validOracle=if([int]$fixture.expected_exit-eq0){$expectedRejections.Count-eq0}elseif([int]$fixture.expected_exit-eq1){$expectedRejections.Count-eq1-and-not[string]::IsNullOrWhiteSpace([string]$expectedRejections[0])}else{$false}
  if($fixture.stage-cnotin @($expected.Keys)-or-not($fixture.canonical_case-is[string])-or$fixture.canonical_case-cne$fixture.id-or-not$validOracle-or-not$fixtureOracle.TryAdd([string]$fixture.id,$fixture)){throw "release evidence fixture oracle record $($fixture.id)"}
}

$records=[Collections.Generic.List[object]]::new()
foreach($stage in $expected.Keys){
  $expectedIds=@($fixtureManifest.fixtures|Where-Object{$_.stage-ceq$stage}|ForEach-Object{[string]$_.id})
  if($expectedIds.Count-ne[int]$expected[$stage]){throw "release evidence fixture manifest stage $stage"}
  $bound=@(
    foreach($file in @(Get-ChildItem -LiteralPath $stageDir -File -Filter "selftest-$($pointer.run_instance_id)-$stage-*.json"|Sort-Object Name)){
      $candidateEvidence=Get-Content -Raw -LiteralPath $file.FullName|ConvertFrom-Json -ErrorAction Stop
      if($candidateEvidence.source_run_instance_id-ceq$pointer.run_instance_id-and$candidateEvidence.source_version_path-ceq$pointer.version_path-and$candidateEvidence.source_manifest_sha256-ceq$pointer.manifest_sha256-and$candidateEvidence.validator_sha256-ceq$validatorHash-and$candidateEvidence.fixture_manifest_sha256-ceq$fixtureHash-and$candidateEvidence.member_root_sha256-ceq$memberRootHash-and$candidateEvidence.root_file_sha256-ceq$rootFileHash-and$candidateEvidence.root_anchor_file_sha256-ceq$rootAnchorFileHash){
        Validate-FormalEvidence $file $stage $expectedIds
      }
    }
  )
  if($bound.Count-eq0){throw "release evidence stage $stage bound_count=0"}
  $stableHashes=@($bound.stable_hash|Sort-Object -Unique)
  if($stableHashes.Count-ne1){throw "release evidence stage $stage conflicting retries=$($bound.Count)"}
  $selected=@($bound|Sort-Object {$_.file.Name})[0]
  $records.Add([ordered]@{
    stage=$stage
    fixture_count=[int]$expected[$stage]
    path='stages/'+$selected.file.Name
    sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $selected.file.FullName).Hash.ToLowerInvariant()
  })
}
$payload=[ordered]@{
  schema='wp5-release-evidence-envelope-v1'
  evidence_class='Post-publication self-test evidence; document-governance only'
  candidate=[ordered]@{run_instance_id=$pointer.run_instance_id;version_path=$pointer.version_path;manifest_sha256=$pointer.manifest_sha256;member_root_sha256=$memberRootHash;root_file_sha256=$rootFileHash;root_anchor_file_sha256=$rootAnchorFileHash}
  validator_sha256=$validatorHash
  fixture_manifest_sha256=$fixtureHash
  total_fixture_count=[int](($expected.Values|Measure-Object -Sum).Sum)
  stages=@($records)
}
$directory=Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $directory|Out-Null
$afterRoots=Get-RootBinding
if($afterRoots.member_root_sha256-cne$memberRootHash-or$afterRoots.root_file_sha256-cne$rootFileHash-or$afterRoots.root_anchor_file_sha256-cne$rootAnchorFileHash){throw 'release evidence root binding drift'}
[IO.File]::WriteAllText($output,(($payload|ConvertTo-Json -Depth 12)+"`n"),[Text.UTF8Encoding]::new($false))
Write-Output "PASS release_envelope=$output sha256=$((Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash.ToLowerInvariant()) fixtures=$($payload.total_fixture_count)"
