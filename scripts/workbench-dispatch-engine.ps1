# Trusted harmless direct-thread adapter; existing plugin owns transport/startup.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $InputManifest,
    [Parameter(Mandatory)][string] $InputManifestHash,
    [Parameter(Mandatory)][string] $Token,
    [Parameter(Mandatory)][string] $ExpectedEngineHash,
    [Parameter(Mandatory)][string] $ExpectedEngineVersion
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$record = [ordered]@{schema_version=1;stage='preflight';status='failure';profile='workbench-game.harmless-direct-thread.v1';
    token=$Token;function='BerylWorkbenchDispatch';engine_path=$null;engine_sha256=$null;engine_version=$null;tools=$null;
    startup=$null;session=$null;loaded_projects=$null;rpcs=@();session_checks=@();completion=$null;cleanup=$null;
    failure=$null;evidence_errors=@();raw_logs=@();engine_derived_outputs=@();elapsed_ms=0;
    scope='harmless GameCommon direct-thread snapshots only; world/resource/module opening and callbacks not run'}
$clock=[Diagnostics.Stopwatch]::StartNew()
$stageClock=$null
$paths=$null
$pluginPaths=@{}
$pluginHashes=@{}
$ownedProcess=$null
$ownedPid=$null
$ownedStartTicks=$null
$ownedExecutable=$null
$mutex=$null
$acquired=$false
$logsBaselineCaptured=$false
$priorLogs=@()
$canonicalProject=$null
$expectedFiles=$null
$resultFullPath=[IO.Path]::GetFullPath($ResultPath)
function Fail([string]$Status,[string]$Message) { $record.status=$Status; throw [InvalidOperationException]::new($Message) }
function Hash([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$sha=[Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$sha.Dispose() }
}
function Normal([string]$Path) { $Path.Replace('/','\').TrimEnd('\') }
function Deadline {
    if ($clock.ElapsedMilliseconds -ge 180000 -or ($null -ne $stageClock -and $stageClock.ElapsedMilliseconds -ge 30000)) {
        Fail 'timeout' 'Monotonic dispatch deadline expired'
    }
}
function Inputs {
    if ((Hash $InputManifest) -cne $InputManifestHash) { Fail 'stale_input' 'Frozen input manifest changed' }
    foreach ($name in $pluginPaths.Keys) { if ((Hash $pluginPaths[$name]) -cne $pluginHashes[$name]) { Fail 'stale_input' "Plugin script changed: $name" } }
    if ((Hash $record.engine_path) -cne $ExpectedEngineHash -or (Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion -cne $ExpectedEngineVersion) {
        Fail 'stale_input' 'Engine executable changed'
    }
    $actual=@(Get-ChildItem -LiteralPath $canonicalProject -Recurse -Force)
    foreach ($item in $actual) { if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail 'stale_input' 'Linked staged input is not admitted' } }
    $files=@($actual | Where-Object { -not $_.PSIsContainer })
    $seen=@()
    foreach ($file in $files) {
        $name=$file.FullName.Substring($canonicalProject.Length+1).Replace('\','/')
        if ($name -ceq 'resourceDatabase.rdb') {
            if ($file.Length -gt 8MB) { Fail 'unavailable' 'Derived root resource cache exceeds bound' }
            $record.engine_derived_outputs=@([ordered]@{path=$file.FullName;sha256=(Hash $file.FullName);bytes=$file.Length})
        } elseif ($name -cin @('addon.gproj','scripts/WorkbenchGameCommon/BerylWorkbenchDispatch.c')) {
            if ((Hash $file.FullName) -cne $expectedFiles.PSObject.Properties[$name].Value) { Fail 'stale_input' "Staged bytes changed: $name" }
            $seen+= $name
        } else { Fail 'stale_input' "Unexpected staged file: $name" }
    }
    if ($seen.Count -ne 2) { Fail 'stale_input' 'Missing staged source or project' }
    $dirs=@($actual | Where-Object {$_.PSIsContainer} | ForEach-Object { $_.FullName.Substring($canonicalProject.Length+1).Replace('\','/') } | Sort-Object)
    if (($dirs -join '|') -cne 'scripts|scripts/WorkbenchGameCommon') { Fail 'stale_input' 'Staged directory set changed' }
}
function Owned([string]$Site) {
    Deadline
    $current=Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
    if ($null -eq $current) { Fail 'unavailable' 'Owned Workbench exited' }
    if ($current.StartTime.ToUniversalTime().Ticks -ne $ownedStartTicks -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal $current.Path),$ownedExecutable)) { Fail 'stale_input' 'Owned process identity changed' }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue | Where-Object {$_.Id -ne $ownedPid}).Count) {
        Fail 'unavailable' 'Unrelated editor appeared; it will not be stopped'
    }
    $record.session_checks+= [ordered]@{site=$Site;process_id=$ownedPid;start_ticks=$ownedStartTicks;executable=$ownedExecutable;elapsed_ms=$clock.ElapsedMilliseconds}
}
function Decode([object]$Response,[string]$Action) {
    $expected=@('token','action','status','failure','wb_module_present','game_module_present','phase','armed','submitted','entered','resumed','after_thread','sequence','arm_sequence','enter_sequence','after_sequence','resume_sequence')
    if ($null -eq $Response -or (@($Response.PSObject.Properties.Name | Sort-Object) -join '|') -cne (@($expected | Sort-Object) -join '|')) { Fail 'failure' 'Unknown or missing dispatch fields' }
    $value=[ordered]@{};$codec=[ordered]@{schema_version=1;name='enfusion.jsonapistruct.bool01.v1';numeric_boolean_fields=@()}
    foreach ($name in @('token','action','status','failure')) {
        $item=$Response.PSObject.Properties[$name].Value
        if ($item -isnot [string] -or $item.Length -gt 512) { Fail 'failure' "Invalid string: $name" }
        $value[$name]=$item
    }
    if ($value.token -cne $Token -or $value.action -cne $Action) { Fail 'stale_input' 'Wrong dispatch token/action' }
    if ($value.status -cnotin @('pending','complete','failure','unavailable')) { Fail 'failure' 'Unknown dispatch status' }
    foreach ($name in @('wb_module_present','game_module_present')) {
        $item=$Response.PSObject.Properties[$name].Value
        if ($item -is [bool]) { $value[$name]=$item }
        elseif (($item -is [int] -or $item -is [long]) -and ($item -eq 0 -or $item -eq 1)) { $value[$name]=($item -eq 1);$codec.numeric_boolean_fields+=$name }
        else { Fail 'failure' "Invalid Boolean wire value: $name" }
    }
    foreach ($name in @('phase','armed','submitted','entered','resumed','after_thread','sequence','arm_sequence','enter_sequence','after_sequence','resume_sequence')) {
        $item=$Response.PSObject.Properties[$name].Value
        if (($item -isnot [int] -and $item -isnot [long]) -or $item -lt 0 -or $item -gt 4) { Fail 'failure' "Invalid counter: $name" }
        $value[$name]=$item
    }
    return [pscustomobject]@{response=[pscustomobject]$value;codec=[pscustomobject]$codec}
}
function Rpc([string]$Action) {
    if ($Action -cnotin @('arm','status')) { Fail 'failure' 'Unregistered action' }
    Inputs;Owned ('before.'+$Action)
    $limit=[int][Math]::Max(1,[Math]::Min(8000,[Math]::Min(180000-$clock.ElapsedMilliseconds,30000-$stageClock.ElapsedMilliseconds)))
    $entry=[ordered]@{action=$Action;elapsed_ms=$clock.ElapsedMilliseconds;timeout_ms=$limit;result=$null;normalized_response=$null;codec=$null;failure=$null}
    $record.rpcs+=$entry
    try {
        $reply=& $pluginPaths['Invoke-WorkbenchRpc.ps1'] -Function BerylWorkbenchDispatch -Parameters @{token=$Token;action=$Action} -ClientId BerylDispatchVerifier -TimeoutMs $limit
        $entry.result=$reply
        Deadline;Owned ('after.'+$Action);Inputs
        if ($null -eq $reply -or $reply.Ok -isnot [bool] -or -not $reply.Ok -or $reply.Function -cne 'BerylWorkbenchDispatch' -or $reply.Raw -isnot [string] -or $reply.Raw.Length -gt 65536) { Fail 'failure' 'Incomplete or oversized RPC response' }
        $decoded=Decode $reply.Response $Action
        $entry.normalized_response=$decoded.response;$entry.codec=$decoded.codec
        if ($decoded.response.status -ceq 'unavailable') { Fail 'unavailable' $decoded.response.failure }
        if ($decoded.response.status -ceq 'failure') { Fail 'failure' $decoded.response.failure }
        return ,$decoded.response
    } catch {
        $entry.failure=$_.Exception.Message
        if ($null -eq $entry.result -and $record.status -eq 'failure') {
            if ($_.Exception.Message -match '^No response from Workbench.*within.*ms') { $record.status='timeout' } else { $record.status='unavailable' }
        }
        throw
    }
}
try {
    if ($Token -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedEngineHash -cnotmatch '^[0-9a-f]{64}$' -or $InputManifestHash -cnotmatch '^[0-9a-f]{64}$') { Fail 'failure' 'Invalid pinned hash/token' }
    $canonicalProject=(Resolve-Path -LiteralPath $ProjectDir).ProviderPath
    if ((Get-Item -LiteralPath $canonicalProject).Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail 'stale_input' 'Linked addon root' }
    if ((Normal $resultFullPath).StartsWith((Normal $canonicalProject)+'\',[StringComparison]::OrdinalIgnoreCase)) { Fail 'failure' 'Receipt must be outside addon' }
    if ((Hash $InputManifest) -cne $InputManifestHash) { Fail 'stale_input' 'Input manifest changed before startup' }
    $manifest=Get-Content -LiteralPath $InputManifest -Raw | ConvertFrom-Json
    if ($manifest.schema_version -isnot [long] -and $manifest.schema_version -isnot [int]) { Fail 'failure' 'Invalid manifest version' }
    if ($manifest.schema_version -ne 1 -or (@($manifest.files.PSObject.Properties.Name | Sort-Object) -join '|') -cne 'addon.gproj|scripts/WorkbenchGameCommon/BerylWorkbenchDispatch.c') { Fail 'failure' 'Unsupported exact staged manifest' }
    $expectedFiles=$manifest.files
    foreach ($name in @('Find-Workbench.ps1','Start-WorkbenchDaemon.ps1','Invoke-WorkbenchRpc.ps1')) {
        $path=[IO.Path]::GetFullPath((Join-Path $ToolRoot ('scripts/'+$name)))
        $pluginPaths[$name]=$path;$pluginHashes[$name]=Hash $path
    }
    $record.tools=$pluginHashes
    $mutex=[Threading.Mutex]::new($false,'Local\BerylOwnedWorkbenchSessionV1')
    try { $acquired=$mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $acquired=$true }
    if (-not $acquired) { Fail 'unavailable' 'Another Beryl job owns the session gate' }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue).Count) { Fail 'unavailable' 'Existing editor will not be reused or stopped' }
    $paths=& $pluginPaths['Find-Workbench.ps1']
    if (-not $paths.WorkbenchExe) { Fail 'unavailable' 'Workbench not located' }
    $record.engine_path=[IO.Path]::GetFullPath($paths.WorkbenchExe)
    $record.engine_sha256=Hash $record.engine_path;$record.engine_version=(Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion
    Inputs
    if (Test-Path -LiteralPath $paths.LogsDir) { $priorLogs=@(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | ForEach-Object {$_.FullName}) }
    $logsBaselineCaptured=$true;$record.stage='startup';$stageClock=[Diagnostics.Stopwatch]::StartNew()
    $start=& $pluginPaths['Start-WorkbenchDaemon.ps1'] -ProjectDir $canonicalProject -TimeoutSeconds 30
    $record.startup=$start
    if ($null -eq $start -or $start.Ok -isnot [bool] -or -not $start.Ok -or $start.Reused -isnot [bool] -or $start.Reused -or ($start.ProcessId -isnot [int] -and $start.ProcessId -isnot [long])) { Fail 'unavailable' 'No owned fresh editor started' }
    $ownedProcess=Get-Process -Id $start.ProcessId;$ownedPid=$ownedProcess.Id;$ownedStartTicks=$ownedProcess.StartTime.ToUniversalTime().Ticks;$ownedExecutable=Normal $ownedProcess.Path
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($ownedExecutable,(Normal $record.engine_path))) { $ownedProcess=$null;Fail 'stale_input' 'Started executable differs' }
    $record.session=[ordered]@{process_id=$ownedPid;start_ticks=$ownedStartTicks;start_time=$ownedProcess.StartTime.ToUniversalTime().ToString('o');executable=$ownedExecutable;project=$canonicalProject;reused=$false}
    Owned 'startup.complete';Inputs
    $loaded=& $pluginPaths['Invoke-WorkbenchRpc.ps1'] -Function GetLoadedProjects -ClientId BerylDispatchVerifier -TimeoutMs 8000
    $record.loaded_projects=$loaded
    Owned 'loaded.complete';Inputs
    if ($null -eq $loaded -or $loaded.Ok -isnot [bool] -or -not $loaded.Ok -or $loaded.Function -cne 'GetLoadedProjects' -or $loaded.Response.'Loaded Projects' -isnot [Array] -or 'BerylWorkbenchDispatchProbe' -cnotin $loaded.Response.'Loaded Projects') { Fail 'stale_input' 'Owned addon absent from loaded projects' }
    $record.stage='sentinel';$stageClock=[Diagnostics.Stopwatch]::StartNew()
    $arm=Rpc 'arm'
    if ($arm.status -cne 'pending' -or $arm.resumed -ne 0 -or $arm.armed -ne 1 -or $arm.submitted -ne 1 -or $arm.after_thread -ne 1) { Fail 'failure' 'Arm did not return its required before-completion snapshot' }
    $polls=0
    do {
        if ($polls -ge 64) { Fail 'timeout' 'Dispatch poll bound exhausted' }
        Deadline;Start-Sleep -Milliseconds 200;$polls++
        $reply=Rpc 'status'
    } while ($reply.status -cne 'complete')
    $record.completion=$reply
    if ($reply.phase -ne 3 -or $reply.armed -ne 1 -or $reply.submitted -ne 1 -or $reply.entered -ne 1 -or $reply.resumed -ne 1 -or $reply.after_thread -ne 1 -or $reply.sequence -ne 4 -or $reply.arm_sequence -ne 1 -or $reply.resume_sequence -ne 4 -or (@($reply.enter_sequence,$reply.after_sequence | Sort-Object) -join '|') -cne '2|3') { Fail 'failure' 'Incomplete native sentinel counters/order' }
    Deadline;Inputs;Owned 'sentinel.complete'
    $record.status='success';$record.stage='dispatch_transport_complete'
} catch {
    $record.failure=$_.Exception.Message
    if ($_.Exception -is [Management.Automation.PipelineStoppedException]) { $record.status='cancelled' }
    elseif ($_.Exception -is [Management.Automation.PSSecurityException]) { $record.status='unavailable' }
    elseif ($record.stage -eq 'startup' -and $null -eq $record.session) {
        if ($_.Exception.Message -match 'within.*s' -or $clock.ElapsedMilliseconds -ge 180000 -or $stageClock.ElapsedMilliseconds -ge 30000) { $record.status='timeout' }
        elseif ($record.status -eq 'failure') { $record.status='unavailable' }
    }
} finally {
    try {
        if ($null -ne $ownedProcess) {
            $current=Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
            if ($null -eq $current) { $record.cleanup='owned_process_already_exited' }
            elseif ($current.StartTime.ToUniversalTime().Ticks -eq $ownedStartTicks -and [StringComparer]::OrdinalIgnoreCase.Equals((Normal $current.Path),$ownedExecutable)) {
                Stop-Process -Id $ownedPid -Force
                if ($current.WaitForExit(5000)) { $record.cleanup='owned_process_stopped' }
                else { $record.cleanup='owned_process_exit_not_confirmed';$record.evidence_errors+=@{stage='cleanup';message='Exit not confirmed'};if($record.status -eq 'success'){$record.status='unavailable';$record.failure='Owned exit not confirmed'} }
            } else { $record.cleanup='identity_changed_not_stopped';if($record.status -eq 'success'){$record.status='stale_input';$record.failure='Cleanup identity changed'} }
        } else { $record.cleanup='no_owned_process_identity' }
    } catch { $record.evidence_errors+=@{stage='cleanup';message=$_.Exception.Message};if($record.status -eq 'success'){$record.status='failure';$record.failure=$_.Exception.Message} }
    try {
        if ($logsBaselineCaptured -and (Test-Path -LiteralPath $paths.LogsDir)) {
            $dirs=@(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | Where-Object {$_.FullName -notin $priorLogs})
            if($dirs.Count -gt 16){throw 'Too many raw log directories'}
            foreach($dir in $dirs){
                if($dir.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked log directory'}
                $logs=@(Get-ChildItem -LiteralPath $dir.FullName -File -Filter '*.log')
                if($logs.Count -gt 256){throw 'Too many raw logs'}
                foreach($log in $logs){
                    if($log.Length -gt 64MB -or ($log.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Linked or oversized raw log'}
                    $hash=Hash $log.FullName;$destDir=Join-Path ([IO.Path]::GetDirectoryName($resultFullPath)) ('dispatch-logs/'+$dir.Name)
                    $null=[IO.Directory]::CreateDirectory($destDir);$dest=Join-Path $destDir $log.Name
                    [IO.File]::Copy($log.FullName,$dest,$false)
                    if((Hash $dest) -cne $hash -or (Hash $log.FullName) -cne $hash){throw 'Log changed during capture'}
                    $record.raw_logs+=@{original=$log.FullName;retained=$dest;sha256=$hash;bytes=$log.Length}
                }
            }
        }
        if($record.status -eq 'success' -and -not $record.raw_logs.Count){throw 'No retained owned logs'}
    } catch { $record.evidence_errors+=@{stage='logs';message=$_.Exception.Message};if($record.status -eq 'success'){$record.status='unavailable';$record.failure=$_.Exception.Message} }
    try { if($acquired){$mutex.ReleaseMutex()};if($null -ne $mutex){$mutex.Dispose()} } catch { $record.evidence_errors+=@{stage='mutex';message=$_.Exception.Message};if($record.status -eq 'success'){$record.status='failure';$record.failure=$_.Exception.Message} }
    if($record.status -eq 'success' -and $clock.ElapsedMilliseconds -ge 180000){$record.status='timeout';$record.failure='Deadline expired during final evidence/cleanup'}
    $record.elapsed_ms=$clock.ElapsedMilliseconds
    $null=[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($resultFullPath));$json=$record | ConvertTo-Json -Depth 24
    [IO.File]::WriteAllText($resultFullPath,$json,[Text.UTF8Encoding]::new($false))
    if([IO.File]::ReadAllText($resultFullPath) -cne $json){throw 'Incomplete adapter receipt write'}
}
if($record.status -ne 'success'){Write-Error $record.failure;exit 1}
