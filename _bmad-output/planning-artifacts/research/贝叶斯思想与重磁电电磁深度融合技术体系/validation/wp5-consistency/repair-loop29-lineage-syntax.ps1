[CmdletBinding()]
param([string]$ValidatorPath = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'validate-wp5.ps1'))

$ErrorActionPreference = 'Stop'
$text = [IO.File]::ReadAllText($ValidatorPath)
$text = $text.Replace('|? id -ceq $t.id', '|?{ $_.id -ceq $t.id }')
$text = $text.Replace('|? id -ceq $entry.id', '|?{ $_.id -ceq $entry.id }')
$text = $text.Replace("|? disposition -ceq'replacement'", "|?{ `$_.disposition -ceq'replacement' }")
$text = $text.Replace("|? disposition -ceq'tombstone'", "|?{ `$_.disposition -ceq'tombstone' }")
$text = $text.Replace('Req($prior.Count-eq1-and$prior[0].text_sha256 -eq $null -or $true)"$label tombstone predecessor"', 'Req($prior.Count-eq1)"$label tombstone predecessor"')
$text = $text.Replace("@('loop27','loop28','loop29'))-and-not(Compare-Object @(`$lineage.migrations", "@('loop27','loop28','loop29-reanchor','loop29'))-and-not(Compare-Object @(`$lineage.migrations")
$text = $text.Replace("@('loop27','loop28','loop29')){`$a=", "@('loop27','loop28','loop29-reanchor','loop29')){`$a=")
$text = $text.Replace('$loop27=ReadLedgerAnchor ''loop27'';$loop28=ReadLedgerAnchor ''loop28'';Req((Get-FileHash', '$loop27=ReadLedgerAnchor ''loop27'';$loop28=ReadLedgerAnchor ''loop28'';$loop29Reanchor=ReadLedgerAnchor ''loop29-reanchor'';Req((Get-FileHash')
$text = $text.Replace('$ledger.previous_ledger_sha256-ceq$lineage.anchors.loop28.sha256-and$loop28.previous_ledger_sha256-ceq$lineage.anchors.loop27.sha256', '$ledger.previous_ledger_sha256-ceq$lineage.anchors.''loop29-reanchor''.sha256-and$loop29Reanchor.previous_ledger_sha256-ceq$lineage.anchors.loop28.sha256-and$loop28.previous_ledger_sha256-ceq$lineage.anchors.loop27.sha256')
$text = $text.Replace("AssertTombstoneContinuity `$loop27 `$loop28 'loop28';AssertTombstoneContinuity `$loop28 `$ledger 'loop29'", "AssertTombstoneContinuity `$loop27 `$loop28 'loop28';AssertTombstoneContinuity `$loop28 `$loop29Reanchor 'loop29-reanchor';AssertTombstoneContinuity `$loop29Reanchor `$ledger 'loop29'")
$text = $text.Replace("AssertMigration 'loop28' `$loop27 `$loop28;AssertMigration 'loop29' `$loop28 `$ledger", "AssertMigration 'loop28' `$loop27 `$loop28;AssertMigration 'loop29' `$loop29Reanchor `$ledger")
$text = $text.Replace("`$m.from-ceq('loop'+([int]`$name.Substring(4)-1))-and`$m.to-ceq`$name", "((`$name-ceq'loop28'-and`$m.from-ceq'loop27')-or(`$name-ceq'loop29'-and`$m.from-ceq'loop29-reanchor'))-and`$m.to-ceq`$name")
[IO.File]::WriteAllText($ValidatorPath, $text, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($ValidatorPath, $text, [Text.UTF8Encoding]::new($false))
Write-Output "PASS repaired $ValidatorPath"
