# Explicit owned world-opening experiment. No script opener, play, save or spawn.
# The existing installed RPC bridge is used unchanged. Its native calls are not
# hard-cancelled here; the caller also owns a bounded enclosing host process.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ProjectId,
    [Parameter(Mandatory)][string] $InputManifest,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $Token,
    [Parameter(Mandatory)][string] $ExpectedEnginePath,
    [Parameter(Mandatory)][string] $ExpectedEngineHash,
    [Parameter(Mandatory)][string] $ExpectedEngineVersion,
    [ValidateSet('startup-cli','netapi-resource','module-netapi-resource','module-netapi-registered')][string] $OpeningMechanism='startup-cli'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$record = [ordered]@{
    schema_version=1;stage='preflight';status='failure';opening_mechanism=$OpeningMechanism;mechanism=$null;token=$Token;
    function='BerylStartupReadiness';project_id=$ProjectId;scope='startup-world readiness observation only';
    engine_path=$null;engine_sha256=$null;engine_version=$null;tools=$null;adapter_sha256=$null;
    expected_world=$null;input_manifest=$null;staged_inputs=$null;engine_outputs=@();
    session=$null;arguments=@();startup=$null;health=$null;loaded_projects=$null;preliminary=$null;native_open=$null;completion=$null;
    rpcs=@();port_checks=@();port_query_errors=@();session_checks=@();raw_logs=@();log_directories=@();evidence_errors=@();
    cleanup=$null;failure=$null;elapsed_ms=0;callback_execution='not_run';
    play='not_run';spawn='not_run';save='not_run';policy_changes='not_run';
    limits=[ordered]@{stage_ms=30000;rpc_ms=8000;total_ms=180000;cleanup_ms=5000;max_polls=64;
        native_launch_and_bridge_calls_not_hard_cancelled=$true;raw_logs_aggregate_bytes=67108864}
}
$clock=[Diagnostics.Stopwatch]::StartNew()
$stageClock=$null
$ownedProcess=$null
$ownedPid=$null
$ownedStartTicks=$null
$ownedExecutable=$null
$mutex=$null
$acquired=$false
$paths=$null
$pluginPaths=@{}
$pluginHashes=@{}
$manifest=$null
$manifestHash=$null
$canonicalProject=$null
$canonicalWorld=$null
$priorLogDirectories=@()
$logsBaselineCaptured=$false
$resultFullPath=[IO.Path]::GetFullPath($ResultPath)
$adapterPath=$PSCommandPath
$adapterHash=$null
$resultCanWrite=$false

function Throw-Outcome([string] $Status,[string] $Message) {
    $record.status=$Status
    throw [InvalidOperationException]::new($Message)
}
function Normal-Path([string] $Path) { return $Path.Replace('/','\').TrimEnd('\') }
function Content-Hash([string] $Path) {
    $item=Get-Item -LiteralPath $Path
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Throw-Outcome 'stale_input' 'A pinned file is not a direct regular file'
    }
    $stream=[IO.File]::OpenRead($Path)
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$sha.Dispose() }
}
function Required-Field([object] $Value,[string] $Name) {
    if ($null -eq $Value -or $null -eq $Value.PSObject.Properties[$Name]) {
        Throw-Outcome 'failure' ('Missing response field '+$Name)
    }
    return ,$Value.PSObject.Properties[$Name].Value
}
function Assert-Deadline {
    if ($clock.ElapsedMilliseconds -ge 180000 -or
        ($null -ne $stageClock -and $stageClock.ElapsedMilliseconds -ge 30000)) {
        Throw-Outcome 'timeout' 'Monotonic startup-readiness deadline expired'
    }
}
function Assert-Text([object] $Value,[string] $Name) {
    if ($Value -isnot [string] -or $Value.Length -gt 2048 -or $Value.Contains([char]0)) {
        Throw-Outcome 'failure' ('Invalid response text '+$Name)
    }
}
function Normalize-Bool([object] $Value,[string] $Name,[object] $Codec) {
    if ($Value -is [bool]) { return $Value }
    if (($Value -is [int] -or $Value -is [long]) -and ($Value -eq 0 -or $Value -eq 1)) {
        $Codec.numeric_boolean_fields+= $Name
        return ($Value -eq 1)
    }
    Throw-Outcome 'failure' ('Invalid Boolean response '+$Name)
}
function Assert-Names([object] $Value,[string[]] $Expected) {
    if ($null -eq $Value) { Throw-Outcome 'failure' 'Missing structured response' }
    $names=@($Value.PSObject.Properties | ForEach-Object {$_.Name})
    if ($names.Count -ne $Expected.Count -or @($names | Where-Object {$_ -cnotin $Expected}).Count -or
        @($Expected | Where-Object {$_ -cnotin $names}).Count) {
        Throw-Outcome 'failure' 'Unknown or missing response fields'
    }
}
function Select-OpeningProfile([string] $Name,[string] $OwnedProject) {
    $arguments=@('-gproj',(Join-Path $OwnedProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll')
    if ($Name -ceq 'startup-cli') {
        return [pscustomobject]@{mechanism='startup_cli';scope='startup-world readiness observation only';
            arguments=@($arguments)+@('-wbmodule=WorldEditor','-run','-load','worlds/BerylCallbackProbe.ent')}
    }
    if ($Name -ceq 'netapi-resource') {
        return [pscustomobject]@{mechanism='native_netapi';scope='native NetAPI resource request and owned-world readiness observation only';arguments=@($arguments)}
    }
    if ($Name -ceq 'module-netapi-resource') {
        return [pscustomobject]@{mechanism='module_native_netapi';scope='native NetAPI resource request and owned-world readiness observation only';
            arguments=@($arguments)+@('-wbmodule=WorldEditor','-run')}
    }
    if ($Name -ceq 'module-netapi-registered') {
        return [pscustomobject]@{mechanism='module_registered_netapi';scope='native NetAPI resource request and owned-world readiness observation only';
            arguments=@($arguments)+@('-wbmodule=WorldEditor','-run')}
    }
    Throw-Outcome 'failure' 'Unregistered opening profile; no automatic fallback'
}
function Assert-Transport([object] $Reply,[string] $Function) {
    Assert-Names $Reply @('Ok','Function','ErrorCode','Response','Raw')
    if ($null -eq $Reply -or $Reply.Ok -isnot [bool] -or -not $Reply.Ok -or $Reply.Function -cne $Function -or
        $Reply.ErrorCode -cne 'Ok' -or $Reply.Raw -isnot [string] -or $Reply.Raw.Length -gt 1MB) {
        Throw-Outcome 'failure' 'Invalid owned startup RPC transport envelope'
    }
}
function Assert-Parameters([string] $Function,[hashtable] $Parameters) {
    if ($Function -cin @('IsWorkbenchRunning','GetLoadedProjects')) {
        if ($Parameters.Count -ne 0) { Throw-Outcome 'failure' 'Unexpected builtin inventory parameters' }
        return
    }
    if ($Function -ceq 'BerylStartupReadiness') {
        if ($Parameters.Count -ne 2 -or @($Parameters.Keys | Where-Object {$_ -cnotin @('token','action')}).Count -or
            $Parameters.token -cne $Token -or $Parameters.action -cne 'observe') {
            Throw-Outcome 'stale_input' 'Read-only observer parameters differ'
        }
        return
    }
    if ($Function -ceq 'OpenResource') {
        if ($record.mechanism -cnotin @('native_netapi','module_native_netapi','module_registered_netapi')) { Throw-Outcome 'failure' 'Native opener is unavailable in the selected profile' }
        $expectedResource=$canonicalWorld
        if ($record.mechanism -ceq 'module_registered_netapi') { $expectedResource='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent' }
        if ($Parameters.Count -ne 1 -or @($Parameters.Keys | Where-Object {$_ -cne 'ResourceName'}).Count -or
            $Parameters.ResourceName -isnot [string] -or $Parameters.ResourceName -cne $expectedResource) {
            Throw-Outcome 'stale_input' 'Native opener resource differs from the exact selected owned-world spelling'
        }
        return
    }
    Throw-Outcome 'failure' 'Unregistered startup RPC function'
}
function Check-NativeOpen([object] $Response) {
    Assert-Names $Response @('Opened')
    $codec=[ordered]@{schema_version=1;name='enfusion.jsonapistruct.bool01.v1';numeric_boolean_fields=@()}
    $opened=Normalize-Bool (Required-Field $Response 'Opened') 'Opened' $codec
    return [pscustomobject]@{response=[pscustomobject]@{Opened=$opened};codec=[pscustomobject]$codec}
}
function Assert-NativeOpened([object] $Response) {
    Assert-Names $Response @('Opened')
    if ($Response.Opened -isnot [bool]) { Throw-Outcome 'failure' 'Native opening confirmation is not a normalized Boolean' }
    if (-not $Response.Opened) { Throw-Outcome 'unavailable' 'The single native OpenResource request was refused; no retry or fallback' }
}
function Assert-LoadedProjects([object] $Response) {
    Assert-Names $Response @('Loaded Projects')
    $projects=Required-Field $Response 'Loaded Projects'
    if ($projects -isnot [Array] -or $projects.Count -gt 256 -or $ProjectId -cnotin $projects) {
        Throw-Outcome 'stale_input' 'Loaded addon identity differs'
    }
    foreach ($project in $projects) { Assert-Text $project 'Loaded Projects' }
}
function Check-Response([object] $Response) {
    $strings=@('token','action','status','failure','mechanism','current_project','addon_world_path',
               'resource_name','resource_path','resource_absolute_path','world_path','world_absolute_path')
    $booleans=@('addon_world_resolved','resource_name_resolved','module_present','api_present','world_path_resolved',
                'world_matches','edit_mode','game_mode','in_play_mode','world_present')
    Assert-Names $Response ($strings+$booleans)
    $normalized=[ordered]@{}
    $codec=[ordered]@{schema_version=1;name='enfusion.jsonapistruct.bool01.v1';numeric_boolean_fields=@()}
    foreach ($name in $strings) {
        $text=Required-Field $Response $name
        Assert-Text $text $name
        $normalized[$name]=$text
    }
    if ($normalized.token -cne $Token -or $normalized.action -cne 'observe' -or $normalized.mechanism -cne $record.mechanism) {
        Throw-Outcome 'stale_input' 'Observer token, action or selected opening mechanism differs'
    }
    if ($normalized.status -cnotin @('pending','ready','failure','unavailable')) {
        Throw-Outcome 'failure' 'Unknown startup observer status'
    }
    foreach ($name in $booleans) { $normalized[$name]=Normalize-Bool (Required-Field $Response $name) $name $codec }
    return [pscustomobject]@{response=[pscustomobject]$normalized;codec=[pscustomobject]$codec}
}
function Stage-Ready([object] $Response) {
    if ($Response.status -ceq 'unavailable') { Throw-Outcome 'unavailable' ('Native observation unavailable: '+$Response.failure) }
    if ($Response.status -ceq 'failure') { Throw-Outcome 'failure' ('Native observation failed: '+$Response.failure) }
    if ($Response.failure.Length -ne 0) { Throw-Outcome 'failure' 'Pending or ready observation contains failure evidence' }
    if (-not $Response.addon_world_resolved -or -not $Response.resource_name_resolved -or
        $Response.resource_path.Length -eq 0) {
        Throw-Outcome 'stale_input' 'Pending or ready observation lacks the pinned addon/resource roundtrip'
    }
    if ($Response.addon_world_resolved -and
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.addon_world_path),(Normal-Path $canonicalWorld))) {
        Throw-Outcome 'stale_input' 'Native addon resolution selected a foreign world'
    }
    if ($Response.resource_name_resolved -and
        ($Response.resource_name -cne '{BCCBA11B20261008}worlds/BerylCallbackProbe.ent' -or
         -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.resource_absolute_path),(Normal-Path $canonicalWorld)))) {
        Throw-Outcome 'stale_input' 'Native registered resource selected a foreign world'
    }
    if ($Response.world_path.Length -gt 0 -and (-not $Response.world_path_resolved -or -not $Response.world_matches -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.world_absolute_path),(Normal-Path $canonicalWorld)))) {
        Throw-Outcome 'unavailable' 'A nonempty observed world is foreign or unresolved'
    }
    if ($Response.game_mode -or $Response.in_play_mode) { Throw-Outcome 'unavailable' 'Unexpected active play in a readiness-only job' }
    if ($Response.status -ceq 'pending') { return $false }
    foreach ($name in @('addon_world_path','resource_absolute_path','world_absolute_path')) {
        if ($Response.$name -cnotmatch '^[A-Za-z]:[\\/]' -or
            -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.$name),(Normal-Path $canonicalWorld))) {
            Throw-Outcome 'stale_input' 'Ready world resolutions differ from the pinned owned world'
        }
    }
    if (-not $Response.addon_world_resolved -or -not $Response.resource_name_resolved -or
        -not $Response.module_present -or -not $Response.api_present -or -not $Response.world_path_resolved -or
        -not $Response.world_matches -or -not $Response.world_present -or -not $Response.edit_mode -or
        $Response.game_mode -or $Response.in_play_mode -or $Response.world_path.Length -eq 0 -or
        $Response.resource_path.Length -eq 0 -or $Response.resource_name -cne '{BCCBA11B20261008}worlds/BerylCallbackProbe.ent') {
        Throw-Outcome 'stale_input' 'Ready response lacks the exact resource, world or edit-mode contract'
    }
    return $true
}
function Relative-Name([string] $Path) {
    $name=[IO.Path]::GetRelativePath($canonicalProject,$Path).Replace('\','/')
    if ($name -ceq '.' -or $name -ceq '..' -or $name.StartsWith('../') -or [IO.Path]::IsPathRooted($name)) {
        Throw-Outcome 'stale_input' 'Input escaped the pinned addon'
    }
    return $name
}
function Tree-Snapshot {
    $files=@{}
    $directories=@()
    $outputs=@()
    $queue=[Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($canonicalProject)
    $total=0L
    while ($queue.Count) {
        $directory=$queue.Dequeue()
        $item=Get-Item -LiteralPath $directory
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Throw-Outcome 'stale_input' 'Linked addon directory' }
        foreach ($entry in @(Get-ChildItem -LiteralPath $directory -Force)) {
            $name=Relative-Name $entry.FullName
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { Throw-Outcome 'stale_input' 'Linked staged input' }
            if ($entry.PSIsContainer) {
                $directories+= $name
                if ($directories.Count -gt 256) { Throw-Outcome 'failure' 'Staged directory bound exceeded' }
                $queue.Enqueue($entry.FullName)
            } else {
                if ($name -ceq 'resourceDatabase.rdb' -and -not $manifest.files.Contains($name)) {
                    if ($entry.Length -gt 8MB) { Throw-Outcome 'stale_input' 'Derived root resource database exceeded 8 MiB' }
                    $outputs+= [ordered]@{path=$entry.FullName;relative=$name;sha256=(Content-Hash $entry.FullName);bytes=$entry.Length}
                    continue
                }
                if ($entry.Length -gt 64MB) { Throw-Outcome 'failure' 'Staged file bound exceeded' }
                $total+= $entry.Length
                if ($total -gt 256MB -or $files.Count -ge 256) { Throw-Outcome 'failure' 'Staged aggregate bound exceeded' }
                $files[$name]=Content-Hash $entry.FullName
            }
        }
    }
    return [pscustomobject]@{files=$files;directories=@($directories | Sort-Object -CaseSensitive);outputs=$outputs}
}
function Assert-Inputs {
    if ((Content-Hash $adapterPath) -cne $adapterHash -or (Content-Hash $InputManifest) -cne $manifestHash) {
        Throw-Outcome 'stale_input' 'Adapter or pinned input manifest changed'
    }
    foreach ($name in $pluginPaths.Keys) {
        if ((Content-Hash $pluginPaths[$name]) -cne $pluginHashes[$name]) { Throw-Outcome 'stale_input' ('Installed integration changed: '+$name) }
    }
    if ((Content-Hash $record.engine_path) -cne $ExpectedEngineHash -or
        (Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion -cne $ExpectedEngineVersion) {
        Throw-Outcome 'stale_input' 'Engine executable identity changed'
    }
    $tree=Tree-Snapshot
    if ($tree.files.Count -ne $manifest.files.Count -or
        @($tree.files.Keys | Where-Object {-not $manifest.files.Contains($_)}).Count -or
        @($manifest.files.Keys | Where-Object {-not $tree.files.ContainsKey($_) -or $tree.files[$_] -cne $manifest.files[$_]}).Count -or
        ($tree.directories -join "`n") -cne (@($manifest.directories) -join "`n")) {
        Throw-Outcome 'stale_input' 'Staged addon file, directory or content identity changed'
    }
    $record.engine_outputs=@($tree.outputs)
}
function Assert-OwnedSession([string] $Site) {
    Assert-Deadline
    if ($null -eq $ownedPid -or $null -eq $ownedStartTicks -or $null -eq $ownedExecutable) {
        Throw-Outcome 'unavailable' 'Complete owned process identity unavailable'
    }
    $current=Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
    if ($null -eq $current) { Throw-Outcome 'unavailable' 'Owned Workbench process exited' }
    if ($current.StartTime.ToUniversalTime().Ticks -ne $ownedStartTicks -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $current.Path),$ownedExecutable)) {
        Throw-Outcome 'stale_input' 'Owned process PID/start/executable changed'
    }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue | Where-Object {$_.Id -ne $ownedPid}).Count) {
        Throw-Outcome 'unavailable' 'Unrelated Workbench session appeared'
    }
    $record.session_checks+= [ordered]@{site=$Site;process_id=$ownedPid;start_ticks=$ownedStartTicks;
        executable=$ownedExecutable;elapsed_ms=$clock.ElapsedMilliseconds}
}
function Invoke-Call([string] $Function,[hashtable] $Parameters) {
    Assert-Parameters $Function $Parameters
    Assert-Inputs
    Assert-OwnedSession ('before.'+$Function)
    $remaining=[Math]::Min(180000-$clock.ElapsedMilliseconds,30000-$stageClock.ElapsedMilliseconds)
    $limit=[int][Math]::Max(1,[Math]::Min(8000,$remaining))
    $entry=[ordered]@{stage=$record.stage;function=$Function;action=$(if($Function -ceq 'BerylStartupReadiness'){'observe'}else{$null});
        params=$Parameters.Clone();elapsed_ms=$clock.ElapsedMilliseconds;timeout_ms=$limit;result=$null;normalized_response=$null;codec=$null;failure=$null;failure_kind=$null;duration_ms=0}
    $record.rpcs+= $entry
    $callClock=[Diagnostics.Stopwatch]::StartNew()
    try {
        try { $reply=& $pluginPaths['Invoke-WorkbenchRpc.ps1'] -Function $Function -Parameters $Parameters -ClientId BerylStartupVerifier -TimeoutMs $limit }
        catch {
            $entry.failure=$_.Exception.Message
            Assert-OwnedSession ('after.'+$Function)
            if ($callClock.ElapsedMilliseconds -ge $limit) { Throw-Outcome 'timeout' 'Startup RPC exceeded its admitted response deadline' }
            if ($_.Exception.Message -match '^No response from Workbench') {
                $entry.failure_kind='accepted_transport_no_response'
                Throw-Outcome 'timeout' $entry.failure
            }
            # The installed bridge formats connection errors as a new string;
            # native SocketError identity is unavailable and never inferred.
            $entry.failure_kind='transport_failure_unclassified'
            Throw-Outcome 'unavailable' $entry.failure
        }
        $entry.result=$reply
        Assert-OwnedSession ('after.'+$Function)
        if ($callClock.ElapsedMilliseconds -ge $limit) { Throw-Outcome 'timeout' 'Late startup RPC response rejected' }
        Assert-Transport $reply $Function
        if ($Function -ceq 'BerylStartupReadiness') {
            $checked=Check-Response $reply.Response
            $entry.normalized_response=$checked.response
            $entry.codec=$checked.codec
            return ,$checked.response
        }
        if ($Function -ceq 'OpenResource') {
            $record.native_open=$reply
            $checked=Check-NativeOpen $reply.Response
            $entry.normalized_response=$checked.response
            $entry.codec=$checked.codec
            return ,$checked.response
        }
        return ,$reply
    } catch {
        if ($null -eq $entry.failure) { $entry.failure=$_.Exception.Message }
        throw
    } finally { $entry.duration_ms=$callClock.ElapsedMilliseconds }
}
function Wait-Listener {
    if ($null -eq (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        Throw-Outcome 'unavailable' 'Native TCP listener inventory unavailable'
    }
    for ($poll=0;$poll -lt 64;$poll++) {
        $record.startup.polls=$poll
        $queryErrors=@()
        $listeners=@(Get-NetTCPConnection -LocalPort 5775 -State Listen -ErrorAction SilentlyContinue -ErrorVariable queryErrors)
        if ($queryErrors.Count -gt 16 -or $record.port_query_errors.Count+$queryErrors.Count -gt 128) {
            Throw-Outcome 'unavailable' 'Native listener query diagnostic bound exceeded'
        }
        $owners=@($listeners | ForEach-Object {$_.OwningProcess} | Select-Object -Unique)
        $owner=$(if($owners.Count -eq 1){[long]$owners[0]}else{$null})
        $record.port_checks+= [ordered]@{elapsed_ms=$clock.ElapsedMilliseconds;listening=($listeners.Count -gt 0);owning_process=$owner}
        Assert-OwnedSession 'port.check'
        foreach ($queryError in $queryErrors) {
            $record.port_query_errors+= [ordered]@{elapsed_ms=$clock.ElapsedMilliseconds;
                category=$queryError.CategoryInfo.Category.ToString();id=$queryError.FullyQualifiedErrorId;
                message=$queryError.Exception.Message.Substring(0,[Math]::Min(2048,$queryError.Exception.Message.Length))}
            if ($queryError.CategoryInfo.Category -ne [Management.Automation.ErrorCategory]::ObjectNotFound) {
                Throw-Outcome 'unavailable' 'Native TCP listener inventory failed'
            }
        }
        if ($listeners.Count -gt 32) { Throw-Outcome 'unavailable' 'Native TCP listener count exceeded the bounded query contract' }
        if ($listeners.Count) {
            if ($owners.Count -ne 1 -or $owner -ne $ownedPid) { Throw-Outcome 'unavailable' 'NetAPI listener is not exclusively owned by this Workbench process' }
            return
        }
        if ($poll -eq 63) { Throw-Outcome 'timeout' 'Native listener inventory exhausted 64 polls' }
        Assert-Deadline
        Start-Sleep -Milliseconds 200
        Assert-Deadline
    }
}
function Check-Health {
    # Listening metadata proves transport ownership only. Exactly one builtin
    # health request must independently observe both runtime readiness fields.
    $reply=Invoke-Call 'IsWorkbenchRunning' @{}
    Assert-Names $reply.Response @('IsRunning','ScriptsCompiled')
    $codec=[ordered]@{schema_version=1;name='enfusion.jsonapistruct.bool01.v1';numeric_boolean_fields=@()}
    $running=Normalize-Bool (Required-Field $reply.Response 'IsRunning') 'IsRunning' $codec
    $compiled=Normalize-Bool (Required-Field $reply.Response 'ScriptsCompiled') 'ScriptsCompiled' $codec
    $record.health=$reply
    if (-not $running -or -not $compiled) { Throw-Outcome 'unavailable' 'The single builtin health observation was not ready' }
}
function Wait-Ready {
    for ($poll=0;$poll -lt 64;$poll++) {
        $response=Invoke-Call 'BerylStartupReadiness' @{token=$Token;action='observe'}
        $record.completion=$response
        if (Stage-Ready $response) { return }
        if ($poll -eq 63) { Throw-Outcome 'timeout' 'Startup readiness exhausted 64 polls' }
        Assert-Deadline
        Start-Sleep -Milliseconds 200
        Assert-Deadline
    }
}

try {
    if ($PSVersionTable.PSVersion.Major -lt 7 -or $null -eq ([Diagnostics.ProcessStartInfo]::new()).ArgumentList) {
        Throw-Outcome 'unavailable' 'This fixed launcher requires PowerShell 7 and .NET ProcessStartInfo.ArgumentList'
    }
    if ($Token -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedEngineHash -cnotmatch '^[0-9a-f]{64}$' -or
        $ProjectId -cnotmatch '^[A-Za-z_][A-Za-z0-9_]{0,127}$') { Throw-Outcome 'failure' 'Invalid pinned startup identity' }
    if (-not [IO.Path]::IsPathFullyQualified($ExpectedEnginePath)) { Throw-Outcome 'failure' 'Expected engine path must be absolute' }
    $canonicalProject=(Resolve-Path -LiteralPath $ProjectDir).ProviderPath
    $profile=Select-OpeningProfile $OpeningMechanism $canonicalProject
    $record.mechanism=$profile.mechanism
    $record.scope=$profile.scope
    $canonicalWorld=[IO.Path]::GetFullPath((Join-Path $canonicalProject 'worlds/BerylCallbackProbe.ent'))
    $record.expected_world=$canonicalWorld
    foreach ($path in @($resultFullPath,[IO.Path]::GetFullPath($InputManifest))) {
        if ((Normal-Path $path).StartsWith((Normal-Path $canonicalProject)+'\',[StringComparison]::OrdinalIgnoreCase)) {
            Throw-Outcome 'failure' 'Receipt and manifest must be outside the immutable addon'
        }
    }
    if (Test-Path -LiteralPath $resultFullPath) { Throw-Outcome 'failure' 'Adapter receipt already exists' }
    $resultParent=Get-Item -LiteralPath ([IO.Path]::GetDirectoryName($resultFullPath))
    if (-not $resultParent.PSIsContainer -or ($resultParent.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Throw-Outcome 'failure' 'Adapter receipt parent must be an existing direct directory'
    }
    $resultCanWrite=$true
    if ((Get-Item -LiteralPath $InputManifest).Length -gt 1MB) { Throw-Outcome 'failure' 'Input manifest exceeds 1 MiB' }
    $manifestHash=Content-Hash $InputManifest
    $manifest=[IO.File]::ReadAllText($InputManifest) | ConvertFrom-Json -AsHashtable
    if ($manifest -isnot [Collections.IDictionary] -or $manifest.Count -ne 3 -or
        @('schema_version','files','directories' | Where-Object {-not $manifest.Contains($_)}).Count -or
        ($manifest.schema_version -isnot [int] -and $manifest.schema_version -isnot [long]) -or $manifest.schema_version -ne 1 -or
        $manifest.files -isnot [Collections.IDictionary] -or $manifest.files.Count -lt 1 -or $manifest.files.Count -gt 256 -or
        $manifest.directories -isnot [Array] -or $manifest.directories.Count -gt 256) {
        Throw-Outcome 'failure' 'Invalid typed input manifest'
    }
    foreach ($name in @($manifest.files.Keys)+@($manifest.directories)) {
        if ($name -isnot [string] -or $name.Length -gt 2048 -or $name.Contains('\') -or
            $name -cmatch '(^/|(^|/)\.\.?(/|$)|[:\x00])' -or $name.Length -eq 0) { Throw-Outcome 'failure' 'Invalid relative input manifest path' }
    }
    foreach ($hash in $manifest.files.Values) { if ($hash -isnot [string] -or $hash -cnotmatch '^[0-9a-f]{64}$') { Throw-Outcome 'failure' 'Invalid manifest source hash' } }
    if ((@($manifest.directories | Sort-Object -CaseSensitive) -join "`n") -cne (@($manifest.directories) -join "`n") -or
        @($manifest.directories | Select-Object -Unique).Count -ne $manifest.directories.Count) { Throw-Outcome 'failure' 'Manifest directories must be exact sorted unique paths' }
    $record.input_manifest=[ordered]@{path=[IO.Path]::GetFullPath($InputManifest);sha256=$manifestHash}
    $record.staged_inputs=$manifest
    $adapterHash=Content-Hash $adapterPath
    $record.adapter_sha256=$adapterHash
    foreach ($name in @('Find-Workbench.ps1','Invoke-WorkbenchRpc.ps1')) {
        $path=[IO.Path]::GetFullPath((Join-Path $ToolRoot ('scripts/'+$name)))
        $pluginPaths[$name]=$path
        $pluginHashes[$name]=Content-Hash $path
    }
    $record.tools=$pluginHashes
    $mutex=[Threading.Mutex]::new($false,'Local\BerylOwnedWorkbenchSessionV1')
    try { $acquired=$mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $acquired=$true }
    if (-not $acquired) { Throw-Outcome 'unavailable' 'Another Beryl job owns the session gate' }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue).Count) { Throw-Outcome 'unavailable' 'Existing Workbench session will not be reused or stopped' }
    $paths=& $pluginPaths['Find-Workbench.ps1']
    if (-not $paths.WorkbenchExe -or -not $paths.GameRoot -or -not (Test-Path -LiteralPath $paths.GameRoot -PathType Container)) {
        Throw-Outcome 'unavailable' 'Installed engine or game working directory unavailable'
    }
    $record.engine_path=[IO.Path]::GetFullPath($paths.WorkbenchExe)
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $record.engine_path),(Normal-Path ([IO.Path]::GetFullPath($ExpectedEnginePath))))) {
        Throw-Outcome 'stale_input' 'Discovery selected another engine executable'
    }
    $record.engine_sha256=Content-Hash $record.engine_path
    $record.engine_version=(Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion
    Assert-Inputs
    if (Test-Path -LiteralPath $paths.LogsDir) { $priorLogDirectories=@(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | ForEach-Object {$_.FullName}) }
    $logsBaselineCaptured=$true
    $record.stage='startup'
    $stageClock=[Diagnostics.Stopwatch]::StartNew()
    $argv=@($profile.arguments)
    $record.arguments=@($argv)
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=$record.engine_path
    $info.WorkingDirectory=$paths.GameRoot
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
    foreach ($argument in $argv) { $info.ArgumentList.Add($argument) }
    $record.startup=[ordered]@{mechanism=$record.mechanism;argv=@($argv);working_directory=$paths.GameRoot;
        use_shell_execute=$false;create_no_window=$true;window_style='Hidden';launch_returned=$false;polls=0}
    $ownedProcess=[Diagnostics.Process]::new()
    $ownedProcess.StartInfo=$info
    if (-not $ownedProcess.Start()) { $ownedProcess=$null;Throw-Outcome 'unavailable' 'Owned engine launch did not return a process' }
    # Retain the actual Process instance and PID before any other query or wait.
    $ownedPid=$ownedProcess.Id
    $record.startup.launch_returned=$true
    $record.startup.process_id=$ownedPid
    $ownedStartTicks=$ownedProcess.StartTime.ToUniversalTime().Ticks
    $ownedExecutable=Normal-Path $ownedProcess.Path
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($ownedExecutable,(Normal-Path $record.engine_path))) { Throw-Outcome 'stale_input' 'Started engine path differs' }
    $record.session=[ordered]@{process_id=$ownedPid;start_ticks=$ownedStartTicks;executable=$ownedExecutable;
        project=$canonicalProject;reused=$false;start_time=$ownedProcess.StartTime.ToUniversalTime().ToString('o')}
    Assert-OwnedSession 'startup.identity'
    Wait-Listener
    Check-Health
    $record.loaded_projects=Invoke-Call 'GetLoadedProjects' @{}
    Assert-LoadedProjects $record.loaded_projects.Response
    if ($OpeningMechanism -cin @('netapi-resource','module-netapi-resource','module-netapi-registered')) {
        $record.stage='preliminary'
        $stageClock=[Diagnostics.Stopwatch]::StartNew()
        $record.preliminary=Invoke-Call 'BerylStartupReadiness' @{token=$Token;action='observe'}
        # This read-only proof may be pending. It must still resolve the exact
        # addon/resource and reject any foreign world or active gameplay.
        $null=Stage-Ready $record.preliminary
        $record.stage='native_resource_open'
        $stageClock=[Diagnostics.Stopwatch]::StartNew()
        $requestedResource=$canonicalWorld
        if ($OpeningMechanism -ceq 'module-netapi-registered') {
            # The preceding actual native observation has already verified this
            # exact registration and roundtrip to the frozen owned world.
            $requestedResource='{BCCBA11B20261008}worlds/BerylCallbackProbe.ent'
        }
        $opened=Invoke-Call 'OpenResource' @{ResourceName=$requestedResource}
        Assert-NativeOpened $opened
    }
    $record.stage='readiness'
    $stageClock=[Diagnostics.Stopwatch]::StartNew()
    Wait-Ready
    Assert-Deadline
    Assert-Inputs
    $record.status='success'
    $record.stage='startup_readiness_complete'
} catch {
    $record.failure=$_.Exception.Message
    if ($_.Exception -is [Management.Automation.PipelineStoppedException]) { $record.status='cancelled' }
    elseif ($record.status -eq 'failure' -and $record.stage -eq 'startup') {
        if ($clock.ElapsedMilliseconds -ge 180000 -or ($null -ne $stageClock -and $stageClock.ElapsedMilliseconds -ge 30000)) { $record.status='timeout' }
        else { $record.status='unavailable' }
    }
} finally {
    try {
        if ($null -eq $ownedProcess) { $record.cleanup='no_owned_process' }
        elseif ($ownedProcess.WaitForExit(0)) { $record.cleanup='owned_process_already_exited' }
        elseif ($null -eq $ownedPid -or $null -eq $ownedStartTicks -or $null -eq $ownedExecutable) {
            $record.cleanup='owned_process_identity_unavailable_not_stopped'
            $record.evidence_errors+= [ordered]@{stage='owned_cleanup';message='Started process retained but complete identity unavailable; no stop attempted'}
        } else {
            $current=Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
            if ($null -eq $current -or $current.StartTime.ToUniversalTime().Ticks -ne $ownedStartTicks -or
                -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $current.Path),$ownedExecutable)) {
                $record.cleanup='identity_changed_not_stopped'
                $record.evidence_errors+= [ordered]@{stage='owned_cleanup';message='Owned process identity changed; no stop attempted'}
            } else {
                $ownedProcess.Kill()
                if ($ownedProcess.WaitForExit(5000)) { $record.cleanup='owned_process_stopped' }
                else {
                    $record.cleanup='owned_process_exit_not_confirmed'
                    $record.evidence_errors+= [ordered]@{stage='owned_cleanup';message='No confirmed exit within five seconds; no stronger stop attempted'}
                }
            }
        }
    } catch {
        $record.cleanup='owned_process_exit_not_confirmed'
        $record.evidence_errors+= [ordered]@{stage='owned_cleanup';message=$_.Exception.Message}
    }
    try {
        $totalBytes=0L
        if ($logsBaselineCaptured -and (Test-Path -LiteralPath $paths.LogsDir)) {
            $newLogs=@(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | Where-Object {$_.FullName -notin $priorLogDirectories})
            if ($newLogs.Count -gt 16) { throw 'Session log directory bound exceeded' }
            foreach ($directory in $newLogs) {
                if ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked log directory' }
                $record.log_directories+= $directory.FullName
                $logs=@(Get-ChildItem -LiteralPath $directory.FullName -File -Filter '*.log')
                if ($logs.Count -gt 256) { throw 'Session log file bound exceeded' }
                foreach ($log in $logs) {
                    $totalBytes+= $log.Length
                    if ($totalBytes -gt 64MB -or $log.Length -gt 64MB -or ($log.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Session log byte bound or link violation' }
                    $before=Content-Hash $log.FullName
                    $retainedDir=Join-Path ([IO.Path]::GetDirectoryName($resultFullPath)) ('startup-logs/'+$directory.Name)
                    $null=[IO.Directory]::CreateDirectory($retainedDir)
                    $retained=Join-Path $retainedDir $log.Name
                    [IO.File]::Copy($log.FullName,$retained,$false)
                    if ((Content-Hash $retained) -cne $before -or (Content-Hash $log.FullName) -cne $before) { throw 'Raw log changed during capture' }
                    $record.raw_logs+= [ordered]@{original=$log.FullName;retained=$retained;sha256=$before;bytes=$log.Length}
                }
            }
        }
        if ($record.status -eq 'success' -and -not $record.raw_logs.Count) { throw 'Owned session raw logs unavailable' }
    } catch { $record.evidence_errors+= [ordered]@{stage='raw_session_logs';message=$_.Exception.Message} }
    try { if ($null -ne $manifest -and $null -ne $record.engine_path) { Assert-Inputs } }
    catch {
        $record.evidence_errors+= [ordered]@{stage='final_input_identity';message=$_.Exception.Message}
        if ($null -eq $record.failure) {$record.failure=$_.Exception.Message}
        if ($record.status -eq 'success') {$record.status='stale_input'}
    }
    try { if ($acquired) {$mutex.ReleaseMutex()};if ($null -ne $mutex) {$mutex.Dispose()} }
    catch { $record.evidence_errors+= [ordered]@{stage='session_gate_cleanup';message=$_.Exception.Message} }
    if ($record.status -eq 'success' -and $record.evidence_errors.Count) { $record.status='unavailable';$record.failure='Cleanup or raw evidence incomplete' }
    if ($record.status -eq 'success' -and $clock.ElapsedMilliseconds -ge 180000) { $record.status='timeout';$record.failure='Overall deadline expired during evidence capture' }
    $record.elapsed_ms=$clock.ElapsedMilliseconds
    $record.raw_log_observation=$(if($record.cleanup -cin @('owned_process_stopped','owned_process_already_exited')){'snapshot_after_confirmed_owned_exit'}else{'point_in_time_exit_unconfirmed'})
    if ($resultCanWrite) {
        $json=$record | ConvertTo-Json -Depth 32
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes($json)
        if ($bytes.Length -gt 2MB) { throw 'Startup adapter receipt exceeds 2 MiB' }
        $output=[IO.FileStream]::new($resultFullPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $output.Write($bytes,0,$bytes.Length);$output.Flush($true) } finally {$output.Dispose()}
        if ([IO.File]::ReadAllText($resultFullPath) -cne $json) { throw 'Incomplete startup adapter receipt write' }
    }
}
if ($record.status -ne 'success') { Write-Error $record.failure;exit 1 }
