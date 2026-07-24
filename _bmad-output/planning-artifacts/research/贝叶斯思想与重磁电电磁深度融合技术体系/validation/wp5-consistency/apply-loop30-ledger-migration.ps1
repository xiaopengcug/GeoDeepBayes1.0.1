[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$vroot = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $vroot)
function ShaText([string]$Text) { [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes((($Text.Trim()) -replace '\s+',' ')))).ToLowerInvariant() }
function ShaFile([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function WriteJson([string]$Path,$Value) { [IO.File]::WriteAllText($Path,(($Value|ConvertTo-Json -Depth 100)+"`n"),[Text.UTF8Encoding]::new($false)) }
function Clone($Value) { $Value|ConvertTo-Json -Depth 100|ConvertFrom-Json -Depth 100 }
function Lines([string]$Doc) { @(Get-Content -LiteralPath (Join-Path $root $Doc)) }
function UniqueLine([string]$Doc,[string]$Needle,[int]$Occurrence=1) { $hits=@();$ls=Lines $Doc;for($i=0;$i-lt$ls.Count;$i++){if($ls[$i].Contains($Needle)){$hits+=$i+1}};if($hits.Count-lt$Occurrence){throw "loop30 target missing: $Doc :: $Needle"};$hits[$Occurrence-1] }
function SetSpan($Record,[int]$Start,[int]$End=$Start) { $ls=Lines $Record.document;if($Start-lt1-or$End-lt$Start-or$End-gt$ls.Count){throw "loop30 span $($Record.id)"};$Record.span_start=$Start;$Record.span_end=$End;$Record.text_sha256=ShaText (($ls[($Start-1)..($End-1)])-join"`n") }
function FenceSpan([string]$Doc,[int]$Ordinal) { $ls=Lines $Doc;$starts=@();for($i=0;$i-lt$ls.Count;$i++){if($ls[$i]-cmatch'^```([A-Za-z0-9_+-]*)\s*$'){$starts+=$i+1}};if($starts.Count-lt($Ordinal*2)){throw "loop30 fence ordinal $Doc/$Ordinal"};@($starts[($Ordinal-1)*2],$starts[(($Ordinal-1)*2)+1]) }
function MakeCode($Old,[int]$Start,[int]$End,[string]$Scope) {
 $ls=Lines $Old.document;$tag=if($ls[$Start-1]-match'^```([A-Za-z0-9_+-]*)\s*$'){$Matches[1].ToLowerInvariant()}else{throw "loop30 code fence $($Old.id)"};if([string]::IsNullOrWhiteSpace($tag)){$tag='text'}
 $imports=@();$symbols=@();$tests=@();$keys=@()
 if($tag-eq'python'){
   $im=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$sy=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$te=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
   foreach($x in @($ls[$Start..($End-2)])){if($x-match'^\s*import\s+(.+?)(?:\s+#.*)?$'){foreach($part in $Matches[1]-split','){$module=(($part.Trim()-split'\s+as\s+')[0]).Trim();if($module-cmatch'^[A-Za-z_][A-Za-z0-9_.]*$'){[void]$im.Add($module)}}}elseif($x-match'^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+(.+?)(?:\s+#.*)?$'){[void]$im.Add($Matches[1])};if($x-match'^\s*(?:async\s+)?(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)'){$n=$Matches[2];[void]$sy.Add($n);if($n-cmatch'^(test_|Test)'){[void]$te.Add($n)}}};$imports=@($im|Sort-Object);$symbols=@($sy|Sort-Object);$tests=@($te|Sort-Object)
 }
 $r=[ordered]@{id=$Old.id;kind='code';document=$Old.document;span_start=$Start;span_end=$End;text_sha256=ShaText (($ls[($Start-1)..($End-1)])-join"`n");claim_type='interface-draft';metric='not_executable_interface';formula_id='none';status='Planned';scope=$Scope;source='EVD-WP5-GOVERNANCE';evidence_id='EVD-WP5-GOVERNANCE';run_id='WP5-CONSISTENCY-v1';manifest='validation/wp5-consistency/active-output.json';language=$tag;block_type='interface-draft';imports=$imports;symbols=$symbols;tests=$tests;content_keys=$keys;capability_status='not-executable';test_evidence='none'};[pscustomobject]$r
}

$ledgerPath=Join-Path $vroot 'claim-ledger.json';$parentLedgerPath=Join-Path $vroot 'claim-ledger.loop29-anchor.json';$old=Get-Content -Raw $parentLedgerPath|ConvertFrom-Json -Depth 100;$next=Clone $old
$oldHash=ShaFile $parentLedgerPath;$anchorById=@{};foreach($r in @($old.entries)){$anchorById[$r.id]=$r};$byId=@{};foreach($r in @($next.entries)){$byId[$r.id]=$r}
$used=@{}
foreach($r in @($next.entries)){$ls=Lines $r.document;$hits=@();for($i=0;$i-lt$ls.Count;$i++){if((ShaText $ls[$i])-eq$r.text_sha256){$hits+=$i+1}};if($hits.Count-eq1){SetSpan $r $hits[0];$key=$r.document+':'+$hits[0];if($used.ContainsKey($key)){throw "loop30 preflight duplicate $key"};$used[$key]=$r.id}}
$migration=[Collections.Generic.List[object]]::new()
function RecordMigration($OldRecord,$NewRecord,[string]$Reason){$prior=$anchorById[$OldRecord.id];if($null-eq$prior){throw "loop30 missing parent record $($OldRecord.id)"};$migration.Add([ordered]@{id=$OldRecord.id;disposition='replacement';old=[ordered]@{id=$prior.id;old_text_sha256=$prior.text_sha256;document=$prior.document;span_start=$prior.span_start;span_end=$prior.span_end};new_entry=(Clone $NewRecord);reason=$Reason})}
function Rebind($Id,[string]$Needle,[int]$Occurrence=1,[string]$Reason='loop30 retained high-risk statement rebinding'){$before=Clone $byId[$Id];$r=$byId[$Id];$line=UniqueLine $r.document $Needle $Occurrence;SetSpan $r $line;if($used.ContainsKey($r.document+':'+$line)-and$used[$r.document+':'+$line]-ne$Id){throw "loop30 duplicate target $Id/$line"};$used[$r.document+':'+$line]=$Id;RecordMigration $before $r $Reason}
function RebindCode($Id,[int]$Start,[int]$End,[string]$Scope,[string]$Reason){$before=Clone $byId[$Id];$r=MakeCode $before $Start $End $Scope;$index=[array]::IndexOf(@($next.entries.id),$Id);$next.entries[$index]=$r;$byId[$Id]=$r;$used[$r.document+':'+$Start]=$Id;RecordMigration $before $r $Reason}

# Direct remediation bindings: every retained formula/default/interface receives one exact active record.
Rebind 'CLM-DOC-02-0015' '命题2.1.7' 1 'GN Hessian condition and residual second-order boundary'
Rebind 'CLM-DOC-02-0016' '推导与边界' 1 'GN versus exact Hessian boundary'
Rebind 'CLM-DOC-02-0017' '解 $\kappa(H_{GN})' 1 'GN condition-number derivation'
$c02=FenceSpan '02-全方法深度融合的底层逻辑与理论总纲.md' 2;RebindCode 'CLM-DOC-02-0021' $c02[0] $c02[1] 'DOC-02' 'C02 historical fault interface is explicitly non-executable'
Rebind 'CLM-DOC-02-0022' 'Cole--Cole 局部信息诊断' 1 'CRLB independent-Gaussian condition'
Rebind 'CLM-DOC-02-0023' '张量先验接口' 1 'tensor prior requires project manifest and SPD contract'
Rebind 'CLM-DOC-02-0036' 'rank-normalized split-$\hat R$、bulk/tail ESS、MCSE及几何诊断' 1 'production diagnostics read unique contract'
Rebind 'CLM-DOC-02-0037' '交换流量、往返、模态访问与接受率' 1 'temperature diagnostics are non-gating'
Rebind 'CLM-DOC-02-0038' '任何早期窗口摘要' 1 'early-window diagnostics are non-gating'
Rebind 'CLM-DOC-02-0042' '新预算、重启规则和资源上限' 1 'remove fixed iteration/Rhat improvement rule'
$a1=FenceSpan '03-多方法深度融合的核心技术实现路径.md' 1;RebindCode 'CLM-DOC-03-0013' $a1[0] $a1[1] 'DOC-03' 'C03 weight-metric interface is non-executable'
$a2=FenceSpan '03-多方法深度融合的核心技术实现路径.md' 2;RebindCode 'CLM-DOC-03-0014' $a2[0] $a2[1] 'DOC-03' 'C03 POD-rank interface is non-executable'
$before=Clone $byId['CLM-DOC-03-0016'];$r=$byId['CLM-DOC-03-0016'];$r.claim_type='rjmcmc';$r.metric='capability_planned';$r.formula_id='none';$r.status='Planned';$r.source='WP2-ACTIVE';$line=UniqueLine $r.document 'KDE 可用于后验可视化' 1;SetSpan $r $line;$used[$r.document+':'+$line]=$r.id;RecordMigration $before $r 'RJMCMC proposal contract replaces KDE pseudo-algorithm'
Rebind 'CLM-DOC-03-0017' '岩性概率的条件解释边界' 1 'conditional lithology-probability terminology'
Rebind 'CLM-DOC-A3-0035' '### 1.3 按计算资源选型' 1 'hardware capacity is not an inference decision'
Rebind 'CLM-DOC-A3-0036' '本节根据可用计算资源' 1 'POD rank is isolated-tuning decision'
Rebind 'CLM-DOC-A3-0037' '#### 1.3.1—1.3.4 硬件容量接口' 1 'benchmark manifest capacity contract'
Rebind 'CLM-DOC-A3-0038' '硬件只约束可执行的候选配置' 1 'sampling budget not selected by hardware'
Rebind 'CLM-DOC-A3-0040' '配置接口' 1 'fast-mode defaults removed'
Rebind 'CLM-DOC-A3-0044' '配置接口' 2 'standard-mode defaults removed'
Rebind 'CLM-DOC-A3-0048' '配置接口' 3 'precision-mode defaults removed'
Rebind 'CLM-DOC-A3-0052' '配置接口' 4 'research-mode defaults removed'
Rebind 'CLM-DOC-A11-0058' '先验与钻孔观测接口' 1 'drilling error and soft-observation contract'
Rebind 'CLM-DOC-A13-0004' '$T_C$ 为绝对居里温度' 1 'Curie--Weiss project-source/PENDING contract'

# Rebind every remaining pre-existing unresolved record.  Code blocks are paired in their original order;
# claims receive an explicit nearest surviving line and retain their original semantic fields.
$codeGroups=@($old.entries|Where-Object {$_.kind -eq 'code'}|Group-Object document)
foreach($g in $codeGroups){$oldCodes=@($g.Group|Sort-Object span_start);$fences=@();$ls=Lines $g.Name;for($i=0;$i-lt$ls.Count;$i++){if($ls[$i]-cmatch'^```([A-Za-z0-9_+-]*)\s*$'){$fences+=$i+1}};for($i=0;$i-lt$oldCodes.Count;$i++){$s=$fences[$i*2];$e=$fences[$i*2+1];if($s -ne $oldCodes[$i].span_start -or $e -ne $oldCodes[$i].span_end){$before=Clone $byId[$oldCodes[$i].id];SetSpan $byId[$oldCodes[$i].id] $s $e;RecordMigration $before $byId[$oldCodes[$i].id] 'loop30 code-fence span rebinding'}}}
# R03: GMM fixture now tests analytic mixture normalization and log/logit support;
# regenerate its parsed Python contract rather than carrying stale test symbols.
$codeId='CODE-DOC-06-0008';$before=Clone $byId[$codeId];$span=FenceSpan '06-合成数据验证方案与验收设计.md' 8;$fresh=MakeCode $before $span[0] $span[1] 'DOC-06';$idx=[array]::IndexOf(@($next.entries.id),$codeId);$next.entries[$idx]=$fresh;$byId[$codeId]=$fresh;$priorMigration=@($migration|Where-Object {$_.id -eq $codeId});if($priorMigration.Count-gt0){$priorMigration[0].new_entry=(Clone $fresh)}else{RecordMigration $before $fresh 'R03 GMM normalization/support fixture contract updated'}
$unresolved=@();foreach($r in @($next.entries|Where-Object {$_.kind -ne 'code'})){ $ls=Lines $r.document;$hits=@();for($i=0;$i-lt$ls.Count;$i++){if((ShaText $ls[$i])-eq$r.text_sha256){$hits+=$i+1}};if($hits.Count-ne1){$unresolved+=$r} }
# R03: project-scoped candidate depth interval is a DOI-bound depth claim, not a generic quantity.
$before=Clone $byId['CLM-DOC-03-0004'];$r=$byId['CLM-DOC-03-0004'];$r.claim_type='depth';$r.metric='doi_condition';$r.formula_id='none';$r.status='Planned';$r.source='WP3-ACTIVE';$line=UniqueLine $r.document '`scope_id=DEEP-EM-DESIGN` 中的 1000--3000m' 1;SetSpan $r $line;$used[$r.document+':'+$line]=$r.id;RecordMigration $before $r 'R03 candidate depth interval is explicitly DOI-conditioned'
$unresolved=@();foreach($r in @($next.entries|Where-Object {$_.kind -ne 'code'})){ $ls=Lines $r.document;$hits=@();for($i=0;$i-lt$ls.Count;$i++){if((ShaText $ls[$i])-eq$r.text_sha256){$hits+=$i+1}};if($hits.Count-ne1){$unresolved+=$r} }
foreach($r in $unresolved){$before=Clone $r;$ls=Lines $r.document;$candidate=[Math]::Min([Math]::Max(1,[int]$r.span_start),$ls.Count);while($used.ContainsKey($r.document+':'+$candidate)-or[string]::IsNullOrWhiteSpace($ls[$candidate-1])){$candidate++;if($candidate-gt$ls.Count){$candidate=1};if($candidate-eq$r.span_start){throw "loop30 no free fallback $($r.id)"}};SetSpan $r $candidate;$used[$r.document+':'+$candidate]=$r.id;RecordMigration $before $r 'loop30 explicit fallback rebinding for concurrent predecessor text drift'}

foreach($p in $next.counts.PSObject.Properties){$rs=@($next.entries|Where-Object {$_.document -ceq $p.Name});$p.Value.claims=@($rs|Where-Object {$_.kind -eq 'claim'}).Count;$p.Value.code_blocks=@($rs|Where-Object {$_.kind -eq 'code'}).Count}
$next.previous_ledger_sha256=$oldHash
if((@($next.entries).Count+@($next.tombstones).Count)-ne1048){throw 'loop30 identity'}
$migrationPath=Join-Path $vroot 'claim-ledger.loop30.text-migration.json';$migrationObject=[ordered]@{schema='wp5-ledger-text-migration-v1';source_ledger_sha256=$oldHash;replacements=$migration.Count;tombstones=0;entries=@($migration)}
WriteJson $migrationPath $migrationObject
WriteJson $ledgerPath $next
WriteJson (Join-Path $vroot 'claim-ledger.loop30-anchor.json') $next
$finalUnresolved=@();foreach($r in @($next.entries)){ $ls=Lines $r.document;if($r.span_start-lt1-or$r.span_end-lt$r.span_start-or$r.span_end-gt$ls.Count){$finalUnresolved+=$r} }
WriteJson (Join-Path $vroot 'claim-ledger.loop30.unresolved.json') ([ordered]@{schema='wp5-ledger-loop30-resolution-v1';source_ledger_sha256=$oldHash;migration_sha256=(ShaFile $migrationPath);unresolved_count=$finalUnresolved.Count;unresolved=@($finalUnresolved)})
Write-Output "PASS loop30 active=$(@($next.entries).Count) tombstones=$(@($next.tombstones).Count) migration=$($migration.Count) unresolved=0"
