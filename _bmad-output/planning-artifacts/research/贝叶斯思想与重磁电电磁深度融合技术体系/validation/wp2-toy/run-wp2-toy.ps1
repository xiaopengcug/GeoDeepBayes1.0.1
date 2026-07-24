[CmdletBinding()]
param([switch]$InjectWorkerFailure,[switch]$InjectPublishInterruption)

$ErrorActionPreference='Stop'
$here=Split-Path -Parent $MyInvocation.MyCommand.Path;$worker=Join-Path $here 'wp2-toy-worker.ps1'
$output=Join-Path $here 'output';$versions=Join-Path $here 'versions';$active=Join-Path $here 'active-output.json';$attempts=Join-Path $here 'attempts';$journal=Join-Path $here '.publish-journal.json'
$lockPath=Join-Path $here '.run.lock';$lock=$null;$stage=Join-Path $here ('.stage-'+[guid]::NewGuid().ToString('N'));$old=''
try{
    $lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    if(Test-Path $journal){try{$null=Get-Content -Raw $journal|ConvertFrom-Json}catch{};Remove-Item -LiteralPath $journal}
    New-Item -ItemType Directory -Path $stage|Out-Null;$token=([guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N'));[IO.File]::WriteAllText((Join-Path $stage '.capability'),$token,[Text.UTF8Encoding]::new($false));$started=[DateTime]::UtcNow
    $psi=[Diagnostics.ProcessStartInfo]::new();$psi.FileName=(Get-Process -Id $PID).Path
    $psi.ArgumentList.Add('-NoProfile');$psi.ArgumentList.Add('-File');$psi.ArgumentList.Add($worker);$psi.ArgumentList.Add('-OutputStage');$psi.ArgumentList.Add($stage);$psi.ArgumentList.Add('-CapabilityToken');$psi.ArgumentList.Add($token)
    $psi.WorkingDirectory=$here;$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
    $p=[Diagnostics.Process]::new();$p.StartInfo=$psi;if(-not$p.Start()){throw 'failed to start WP2 worker'}
    $stdout=$p.StandardOutput.ReadToEnd();$stderr=$p.StandardError.ReadToEnd();$p.WaitForExit();$exit=$p.ExitCode;$p.Dispose()
    if($InjectWorkerFailure){$exit=97;$stderr+="injected worker failure`n"}
    [IO.File]::WriteAllText((Join-Path $stage 'stdout.log'),$stdout,[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText((Join-Path $stage 'stderr.log'),$stderr,[Text.UTF8Encoding]::new($false))
    if($exit-ne0){New-Item -ItemType Directory -Force $attempts|Out-Null;$attempt=Join-Path $attempts ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N'));Move-Item $stage $attempt;throw "WP2 worker failed exit=$exit; attempt=$attempt"}
    $mf=Join-Path $stage 'manifest.json';$m=Get-Content -Raw $mf|ConvertFrom-Json;$m.started_utc=$started.ToString('o');$m.ended_utc=[DateTime]::UtcNow.ToString('o');$m.exit_code=$exit
    $m.command.executable='pwsh';$m.command.script='run-wp2-toy.ps1';$m.command.arguments=@('-NoProfile','-File','wp2-toy-worker.ps1','-OutputStage','<stage>','-CapabilityToken','<redacted>')
    foreach($s in @('stdout','stderr')){$path=Join-Path $stage "$s.log";$m.$s.path="$s.log";$m.$s.sha256=(Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant();$m.$s.bytes=(Get-Item $path).Length}
    $m.sources=@(
      [pscustomobject]@{path='run-wp2-toy.ps1';sha256=(Get-FileHash -Algorithm SHA256 $MyInvocation.MyCommand.Path).Hash.ToLowerInvariant()},
      [pscustomobject]@{path='wp2-toy-worker.ps1';sha256=(Get-FileHash -Algorithm SHA256 $worker).Hash.ToLowerInvariant()},
      [pscustomobject]@{path='config.json';sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'config.json')).Hash.ToLowerInvariant()},
      [pscustomobject]@{path='diagnostic-contract.json';sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'diagnostic-contract.json')).Hash.ToLowerInvariant()},
      [pscustomobject]@{path='report-contract.json';sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $here 'report-contract.json')).Hash.ToLowerInvariant()})
    $m.files.PSObject.Properties.Remove('.capability');foreach($name in @('stdout.log','stderr.log')){$m.files.$name=(Get-FileHash -Algorithm SHA256 (Join-Path $stage $name)).Hash.ToLowerInvariant()};$m|ConvertTo-Json -Depth 8|Set-Content -Encoding utf8 $mf
    Remove-Item -LiteralPath (Join-Path $stage '.capability');New-Item -ItemType Directory -Force $versions|Out-Null
    $instance=([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N'));$version=Join-Path $versions $instance
    $oldPointer=if(Test-Path $active){Get-Content -Raw $active}else{''};$jt=([ordered]@{old_pointer=$oldPointer;new_instance=$instance}|ConvertTo-Json -Compress);$js=[IO.File]::Open($journal,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None);$jb=[Text.Encoding]::UTF8.GetBytes($jt);$js.Write($jb,0,$jb.Length);$js.Flush($true);$js.Dispose()
    Move-Item $stage $version;if($InjectPublishInterruption){throw 'injected publish interruption'}
    $pointer=[ordered]@{schema='wp2-active-output-v1';run_instance_id=$instance;version_path=("versions/$instance");manifest_sha256=(Get-FileHash -Algorithm SHA256 (Join-Path $version 'manifest.json')).Hash.ToLowerInvariant()};$ptmp="$active.tmp-"+[guid]::NewGuid().ToString('N');$pb=[Text.Encoding]::UTF8.GetBytes(($pointer|ConvertTo-Json -Compress));$ps=[IO.File]::Open($ptmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);$ps.Write($pb,0,$pb.Length);$ps.Flush($true);$ps.Dispose();[IO.File]::Move($ptmp,$active,$true)
    if(Test-Path $journal){Remove-Item $journal};Write-Output $stdout.TrimEnd()
}catch{
    if(Test-Path $stage){New-Item -ItemType Directory -Force $attempts|Out-Null;$attempt=Join-Path $attempts ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N'));Move-Item $stage $attempt}
    if(Test-Path $journal){Remove-Item $journal};throw
}finally{if($lock){$lock.Dispose()}}
