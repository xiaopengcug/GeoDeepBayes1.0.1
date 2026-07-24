[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$vroot=$PSScriptRoot
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function WriteJson([string]$p,$o){[IO.File]::WriteAllText($p,(($o|ConvertTo-Json -Depth 100)+"`n"),[Text.UTF8Encoding]::new($false))}
$base=Get-Content -Raw (Join-Path $vroot 'claim-ledger.loop29-intermediate-anchor.json')|ConvertFrom-Json -Depth 100
$migration=Get-Content -Raw (Join-Path $vroot 'claim-ledger.loop29.final-migration.json')|ConvertFrom-Json -Depth 100
if($migration.source_ledger_sha256-cne(Sha (Join-Path $vroot 'claim-ledger.loop29-intermediate-anchor.json'))){throw 'loop29 restore source'}
foreach($m in @($migration.entries)){ $current=@($base.entries|Where-Object {$_.id-ceq$m.id});if($current.Count-ne1){throw "loop29 restore id $($m.id)"};if($m.disposition-ceq'replacement'){$i=[array]::IndexOf(@($base.entries),$current[0]);$base.entries[$i]=$m.new_entry}else{$base.entries=@($base.entries|Where-Object {$_.id-cne$m.id});$base.tombstones=@($base.tombstones)+@([pscustomobject][ordered]@{id=$m.old.id;old_text_sha256=$m.old.old_text_sha256;document=$m.old.document;span_start=$m.old.span_start;span_end=$m.old.span_end})}}
foreach($p in $base.counts.PSObject.Properties){$rs=@($base.entries|Where-Object {$_.document-ceq$p.Name});$p.Value.claims=@($rs|Where-Object {$_.kind-ceq'claim'}).Count;$p.Value.code_blocks=@($rs|Where-Object {$_.kind-ceq'code'}).Count}
$base.previous_ledger_sha256=Sha (Join-Path $vroot 'claim-ledger.loop29-intermediate-anchor.json')
if(@($base.entries).Count-ne350-or@($base.tombstones).Count-ne698){throw 'loop29 restore counts'}
WriteJson (Join-Path $vroot 'claim-ledger.loop29-anchor.json') $base
Copy-Item -LiteralPath (Join-Path $vroot 'high-risk-classification.loop29-intermediate-anchor.json') -Destination (Join-Path $vroot 'high-risk-classification.loop29-anchor.json') -Force
Copy-Item -LiteralPath (Join-Path $vroot 'scope-registry.loop29-intermediate-anchor.json') -Destination (Join-Path $vroot 'scope-registry.loop29-anchor.json') -Force
& (Join-Path $vroot 'materialize-loop29-scope-registry.ps1') -RegistryPath (Join-Path $vroot 'scope-registry.loop29-anchor.json') -LedgerPath (Join-Path $vroot 'claim-ledger.loop29-anchor.json') | Out-Null
Write-Output "PASS loop29 ledger=$(Sha (Join-Path $vroot 'claim-ledger.loop29-anchor.json')) scope=$(Sha (Join-Path $vroot 'scope-registry.loop29-anchor.json')) risk=$(Sha (Join-Path $vroot 'high-risk-classification.loop29-anchor.json'))"
