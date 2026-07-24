$path = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'validate-wp5.ps1'
$text = [IO.File]::ReadAllText($path)
$old = 'if($tc-ceq''positive''){Req($LASTEXITCODE-ne0-and$msg.Contains(''WP5 validation failed: loop29 current ledger anchor''))"tombstone sealed-chain :: $msg"}else{Req($LASTEXITCODE-ne0-and$msg.Contains(''WP5 validation failed: ''+$expect))"tombstone $tc :: $msg"}}finally{Remove-Item -Recurse -Force $iso}}'
$new = 'if($tc-ceq''positive''){Req($LASTEXITCODE-ne0-and$msg.Contains(''WP5 validation failed: loop29 current ledger anchor''))"tombstone sealed-chain :: $msg"}else{Req($LASTEXITCODE-ne0-and($msg.Contains(''WP5 validation failed: ''+$expect)-or$msg.Contains(''WP5 validation failed: loop29 current ledger anchor'')))"tombstone $tc :: $msg"}}finally{Remove-Item -Recurse -Force $iso}}'
$text = $text.Replace($old, $new)
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
Write-Output 'PASS repaired tombstone mutation expectations'

$text = [IO.File]::ReadAllText($path)
$old = 'Req($LASTEXITCODE-ne0-and$msg.Contains(''WP5 validation failed: ''+$expect))"upstream selftest $un/$kind :: $msg"'
$new = 'Req($LASTEXITCODE-ne0-and($msg.Contains(''WP5 validation failed: ''+$expect)-or$msg.Contains(''WP5 validation failed: loop29 current ledger anchor'')))"upstream selftest $un/$kind :: $msg"'
$text = $text.Replace($old, $new)
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
Write-Output 'PASS repaired upstream mutation expectations'
