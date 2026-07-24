$path = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'validate-wp5.ps1'
$text = [IO.File]::ReadAllText($path)
$prefix = '$script:currentUpstreamFixtureId=$selfTestStageFixtureIds[$script:upstreamFixtureIndex];$script:upstreamFixtureIndex++;if($selfTestSelectedIds.Count-gt0-and-not$selfTestSelectedIds.Contains($script:currentUpstreamFixtureId)){continue};'
$text = $text.Replace('$script:upstreamFixtureIndex=0;$script:currentUpstreamFixtureId=$null`r`n ', '$script:upstreamFixtureIndex=0;$script:currentUpstreamFixtureId=$null'+[Environment]::NewLine)
$text = [regex]::Replace($text, '(?m)^(\s*EnterSelfTestStage ''upstream-lineage''\r?\n)', ('$1'+' $script:upstreamFixtureIndex=0;$script:currentUpstreamFixtureId=$null'+[Environment]::NewLine), 1)
$text = [regex]::Replace($text, '(?m)^foreach\(\$tc in @\(''positive'',''duplicate'',''old_hash'',''document'',''span_start'',''span_end''\)\)\{', ('$0' + $prefix), 1)
$text = [regex]::Replace($text, '(?m)^ foreach\(\$rule in @\(''diagnostic'',''design_eig'',''realized_ig'',''lomo'',''pod'',''rjmcmc'',''calibration'',''depth'',''resource''\)\)\{', ('$0' + $prefix), 1)
$text = [regex]::Replace($text, '(?m)^ foreach\(\$un in @\(''wp2-active'',''wp3-active'',''wp4-active''\)\)\{foreach\(\$kind in @\(''pointer'',''manifest'',''status'',''run'',''member'',''source''\)\)\{', ('$0' + $prefix), 1)
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
