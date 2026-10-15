# Trusted experimental callback transport. The caller validates semantic traces.
# Uses the installed Workbench bridge; never enables NetAPI, changes policy,
# saves the world, or takes over a session owned by someone else.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ProjectId,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $Token,
    [Parameter(Mandatory)][string] $Function,
    [Parameter(Mandatory)][string] $ExpectedEngineHash,
    [Parameter(Mandatory)][string] $ExpectedEngineVersion,
    [ValidateSet('focus-dependent', 'force-update')][string] $EngineUpdates = 'focus-dependent',
    [ValidateSet('off', 'world-state-v1')][string] $FrameDiagnostics = 'off',
    [ValidateRange(10, 120)][int] $StageTimeoutSeconds = 30,
    [ValidateRange(1, 64)][int] $MaxPolls = 64,
    [ValidateRange(30, 300)][int] $TotalTimeoutSeconds = 180
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$record = [ordered]@{
    schema_version = 1; stage = 'preflight'; status = 'failure';
    scope = 'owned world transitions and engine callback probe transport; semantic verification is performed by the caller';
    token = $Token; function = $Function; project_id = $ProjectId;
    engine_sha256 = $null; engine_version = $null; engine_path = $null;
    tools = $null; expected_world = $null; session = $null; startup = $null;
    engine_updates = $EngineUpdates; engine_update_launch = $null;
    frame_diagnostics = $FrameDiagnostics; frame_state_rpcs = @();
    launch_checks = @(); port_checks = @(); port_query_errors = @();
    loaded_projects = $null; stages = @(); rpcs = @(); session_checks = @();
    wire_codec = 'strict JSON bool or integer 0/1; omitted caseIds only before execution; omitted rows only before execution with zero event count';
    path_contract = 'native addon/world/resource-name resolutions pinned independently with explicit module/API presence; raw current_project is informational';
    completion = $null; cleanup = $null; log_directories = @(); raw_logs = @();
    failure = $null; evidence_errors = @(); elapsed_ms = 0;
    semantic_comparison = 'not_performed'; policy_changes = 'not_run'; save = 'not_run'
}
$ownedProcess = $null
$ownedPid = $null
$ownedStartTicks = $null
$ownedExecutable = $null
$mutex = $null
$acquired = $false
$paths = $null
$pluginPaths = @{}
$pluginHashes = @{}
$priorLogDirectories = @()
$logsBaselineCaptured = $false
$clock = [Diagnostics.Stopwatch]::StartNew()
$totalLimitMs = $TotalTimeoutSeconds * 1000
$stageClock = $null
$stageLimitMs = $StageTimeoutSeconds * 1000
$canonicalProject = $null
$canonicalWorld = $null
$resultFullPath = [IO.Path]::GetFullPath($ResultPath)
$script:lastLoadProgress = $null

function Throw-Outcome([string] $Status, [string] $Message) {
    $record.status = $Status
    throw [InvalidOperationException]::new($Message)
}

function Content-Hash([string] $Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Normal-Path([string] $Path) {
    return $Path.Replace('/', '\').TrimEnd('\')
}

function Required-Field([object] $Value, [string] $Name) {
    if ($null -eq $Value) { Throw-Outcome 'failure' "Missing structured response while reading '$Name'" }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -eq $property) { Throw-Outcome 'failure' "Missing response field '$Name'" }
    # Keep empty arrays and single-element arrays as array values.
    return ,$property.Value
}

function Assert-Int([object] $Value, [int] $Minimum, [int] $Maximum, [string] $Name) {
    if (($Value -isnot [int] -and $Value -isnot [long]) -or $Value -lt $Minimum -or $Value -gt $Maximum) {
        Throw-Outcome 'failure' "Invalid scalar response field '$Name'"
    }
}

function Assert-Deadline {
    if ($clock.ElapsedMilliseconds -ge $totalLimitMs -or
        ($null -ne $stageClock -and $stageClock.ElapsedMilliseconds -ge $stageLimitMs)) {
        Throw-Outcome 'timeout' 'Monotonic callback-probe deadline expired'
    }
}

function Assert-Inputs {
    foreach ($name in $pluginPaths.Keys) {
        if ((Content-Hash $pluginPaths[$name]) -cne $pluginHashes[$name]) {
            Throw-Outcome 'stale_input' "Installed integration script changed: $name"
        }
    }
    if ((Content-Hash $record.engine_path) -cne $ExpectedEngineHash -or
        (Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion -cne $ExpectedEngineVersion) {
        Throw-Outcome 'stale_input' 'Engine executable identity changed'
    }
}

function Assert-OwnedSession([string] $Site) {
    Assert-Deadline
    $current = Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
    if ($null -eq $current) { Throw-Outcome 'unavailable' 'Owned Workbench process exited before the operation completed' }
    try {
        $startTicks = $current.StartTime.ToUniversalTime().Ticks
        $executable = Normal-Path $current.Path
    } catch { Throw-Outcome 'unavailable' 'Owned Workbench process identity could not be read' }
    if ($startTicks -ne $ownedStartTicks -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals($executable, $ownedExecutable)) {
        Throw-Outcome 'stale_input' 'Workbench process ID was reused or its executable path changed'
    }
    $others = @(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $ownedPid })
    if ($others.Count) { Throw-Outcome 'unavailable' 'An unrelated Workbench session appeared; it will not be reused or stopped' }
    $record.session_checks += [ordered]@{ site = $Site; process_id = $ownedPid; start_ticks = $startTicks;
        executable = $executable; elapsed_ms = $clock.ElapsedMilliseconds }
}

function Select-EngineUpdateProfile([string] $Policy, [string] $Project) {
    if ($Policy -ceq 'focus-dependent') { return $null }
    if ($Policy -cne 'force-update') { Throw-Outcome 'failure' 'Unknown engine update policy' }
    return ,@('-gproj', (Join-Path $Project 'addon.gproj'), '-noOpenLastResource', '-scriptAuthorizeAll', '-forceUpdate')
}

function Assert-LaunchIdentity([string] $Site) {
    # Separate startup evidence leaves the established callback check sequence intact.
    Assert-Deadline
    $current = Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
    if ($null -eq $current) { Throw-Outcome 'unavailable' 'Owned force-update process exited during startup' }
    if ($current.StartTime.ToUniversalTime().Ticks -ne $ownedStartTicks -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $current.Path), $ownedExecutable)) {
        Throw-Outcome 'stale_input' 'Owned force-update process identity changed'
    }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $ownedPid }).Count) {
        Throw-Outcome 'unavailable' 'An unrelated Workbench session appeared during force-update startup'
    }
    $record.launch_checks += [ordered]@{site=$Site;process_id=$ownedPid;start_ticks=$ownedStartTicks;
        executable=$ownedExecutable;elapsed_ms=$clock.ElapsedMilliseconds}
}

function Wait-ForceUpdateListener {
    if ($null -eq (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        Throw-Outcome 'unavailable' 'Native TCP listener inventory unavailable'
    }
    for ($poll=0; $poll -lt 64; $poll++) {
        Assert-Deadline
        $queryErrors=@()
        $listeners=@(Get-NetTCPConnection -LocalPort 5775 -State Listen -ErrorAction SilentlyContinue -ErrorVariable queryErrors)
        if ($listeners.Count -gt 32 -or $queryErrors.Count -gt 16 -or $record.port_query_errors.Count+$queryErrors.Count -gt 128) {
            Throw-Outcome 'unavailable' 'Native TCP listener query exceeded its bounded inventory'
        }
        $owners=@($listeners | ForEach-Object {$_.OwningProcess} | Select-Object -Unique)
        $owner=$(if($owners.Count -eq 1){[long]$owners[0]}else{$null})
        $record.port_checks += [ordered]@{elapsed_ms=$clock.ElapsedMilliseconds;listening=($listeners.Count -gt 0);owning_process=$owner}
        Assert-LaunchIdentity 'port.check'
        foreach ($queryError in $queryErrors) {
            $record.port_query_errors += [ordered]@{elapsed_ms=$clock.ElapsedMilliseconds;
                category=$queryError.CategoryInfo.Category.ToString();id=$queryError.FullyQualifiedErrorId;
                message=$queryError.Exception.Message.Substring(0,[Math]::Min(2048,$queryError.Exception.Message.Length))}
            if ($queryError.CategoryInfo.Category -ne [Management.Automation.ErrorCategory]::ObjectNotFound) {
                Throw-Outcome 'unavailable' 'Native TCP listener inventory failed'
            }
        }
        if ($listeners.Count) {
            if ($owners.Count -ne 1 -or $owner -ne $ownedPid) {
                Throw-Outcome 'unavailable' 'NetAPI listener is not exclusively owned by the force-update process'
            }
            return
        }
        if ($poll -eq 63) { Throw-Outcome 'timeout' 'Force-update listener exhausted 64 bounded polls' }
        Start-Sleep -Milliseconds 200
        Assert-Deadline
    }
}

function Assert-LoadProgress([object] $Response, [object] $Previous = $null) {
    $counters = @('load_requested','load_submitted','load_entered','load_resumed','load_returned')
    foreach ($name in $counters) { Assert-Int (Required-Field $Response $name) 0 1 $name }
    if ((Required-Field $Response 'load_accepted') -isnot [bool]) { Throw-Outcome 'failure' 'Invalid normalized native load acceptance' }
    if ($Response.load_submitted -gt $Response.load_requested -or $Response.load_entered -gt $Response.load_requested -or
        $Response.load_resumed -gt $Response.load_entered -or $Response.load_resumed -gt $Response.load_submitted -or
        $Response.load_returned -gt $Response.load_resumed -or ($Response.load_accepted -and $Response.load_returned -ne 1)) {
        Throw-Outcome 'failure' 'Impossible native load progress order'
    }
    if ($Response.status -cin @('ready','complete') -and
        ($Response.load_requested -ne 1 -or $Response.load_submitted -ne 1 -or $Response.load_entered -ne 1 -or
         $Response.load_resumed -ne 1 -or $Response.load_returned -ne 1 -or -not $Response.load_accepted)) {
        Throw-Outcome 'failure' 'Ready/completed response lacks accepted native load execution'
    }
    if ($null -ne $Previous) {
        Assert-LoadProgress $Previous
        if ($Response.token -isnot [string] -or $Response.token -cne $Previous.token) {
            Throw-Outcome 'stale_input' 'Native load progress belongs to another compiled token'
        }
        foreach ($name in $counters) {
            if ($Response.$name -lt $Previous.$name) { Throw-Outcome 'stale_input' 'Native load progress reset during the owned job' }
        }
        if ($Previous.load_accepted -and -not $Response.load_accepted) { Throw-Outcome 'stale_input' 'Native load acceptance reset during the owned job' }
    }
}

function Check-Response([object] $Response, [string] $Action) {
    $expected = @('token','action','status','failure','world_path','current_project','addon_world_path','addon_world_resolved',
                  'world_absolute_path','world_path_resolved','world_matches','edit_mode','game_mode',
                  'in_play_mode','world_present','resource_name','resource_path','resource_absolute_path','resource_name_resolved','module_present','api_present',
                  'module_open_requested','module_open_accepted',
                  'load_requested','load_submitted','load_entered','load_resumed','load_returned','load_accepted',
                  'phase','executed','checks','failures','event_count','checksum','caseIds','rows')
    if ($null -eq $Response) { Throw-Outcome 'failure' 'Missing structured callback response' }
    $names = @($Response.PSObject.Properties | ForEach-Object { $_.Name })
    $missing = @($expected | Where-Object { $_ -cnotin $names })
    if (@($names | Where-Object { $_ -cnotin $expected }).Count -or
        @($missing | Where-Object { $_ -cnotin @('caseIds','rows') }).Count) {
        Throw-Outcome 'failure' 'Callback response has unknown or missing fields'
    }
    # This is a new object. The caller retains the original RPC Response unchanged.
    $normalized = [ordered]@{}
    $codec = [ordered]@{schema_version=1;name='enfusion.jsonapistruct.bool01-emptyarrays.v1';numeric_boolean_fields=@();omitted_empty_arrays=@()}
    $replyToken = Required-Field $Response 'token'
    $replyAction = Required-Field $Response 'action'
    if ($replyToken -isnot [string] -or $replyAction -isnot [string] -or
        $replyToken -cne $Token -or $replyAction -cne $Action) {
        Throw-Outcome 'stale_input' 'Callback response token or requested action differs'
    }
    $status = Required-Field $Response 'status'
    if ($status -isnot [string] -or $status -cnotin @('pending','ready','complete','failure','unavailable')) {
        Throw-Outcome 'failure' 'Unknown callback response status'
    }
    $normalized.token = $replyToken
    $normalized.action = $replyAction
    $normalized.status = $status
    foreach ($name in @('addon_world_resolved','world_path_resolved','world_matches','edit_mode','game_mode','in_play_mode','world_present',
                       'resource_name_resolved','module_present','api_present','module_open_requested','module_open_accepted','load_accepted')) {
        $value = Required-Field $Response $name
        if ($value -is [bool]) {
            $normalized[$name] = $value
        } elseif (($value -is [int] -or $value -is [long]) -and ($value -eq 0 -or $value -eq 1)) {
            $normalized[$name] = ($value -eq 1)
            $codec.numeric_boolean_fields += $name
        } else { Throw-Outcome 'failure' "Invalid Boolean response field '$name'" }
    }
    foreach ($name in @('failure','world_path','current_project','addon_world_path','world_absolute_path','resource_name','resource_path','resource_absolute_path')) {
        $text = Required-Field $Response $name
        if ($text -isnot [string] -or $text.Length -gt 2048) { Throw-Outcome 'failure' "Invalid text response field '$name'" }
        $normalized[$name] = $text
    }
    Assert-Int (Required-Field $Response 'phase') 0 6 'phase'
    Assert-Int (Required-Field $Response 'executed') 0 1 'executed'
    Assert-Int (Required-Field $Response 'checks') 0 100000 'checks'
    Assert-Int (Required-Field $Response 'failures') 0 100000 'failures'
    Assert-Int (Required-Field $Response 'event_count') 0 4096 'event_count'
    Assert-Int (Required-Field $Response 'checksum') 0 1000002 'checksum'
    foreach ($name in @('phase','executed','checks','failures','event_count','checksum')) {
        $normalized[$name] = Required-Field $Response $name
    }
    foreach ($name in @('load_requested','load_submitted','load_entered','load_resumed','load_returned')) {
        Assert-Int (Required-Field $Response $name) 0 1 $name
        $normalized[$name] = Required-Field $Response $name
    }
    $caseIds = @()
    if ('caseIds' -cin $names) { $caseIds = Required-Field $Response 'caseIds' }
    elseif ($normalized.executed -eq 0) { $codec.omitted_empty_arrays += 'caseIds' }
    else { Throw-Outcome 'failure' 'Completed callback response omitted case identities' }
    $rows = @()
    if ('rows' -cin $names) { $rows = Required-Field $Response 'rows' }
    elseif ($normalized.executed -eq 0 -and $normalized.event_count -eq 0) { $codec.omitted_empty_arrays += 'rows' }
    else { Throw-Outcome 'failure' 'Nonempty or completed callback response omitted trace rows' }
    if ($caseIds -isnot [Array] -or $caseIds.Count -gt 16 -or $rows -isnot [Array] -or $rows.Count -gt 4096) {
        Throw-Outcome 'failure' 'Callback trace exceeds its structural bounds'
    }
    foreach ($case in $caseIds) {
        if ($case -isnot [string] -or $case -cnotmatch '^[A-Za-z0-9._-]{1,80}$') {
            Throw-Outcome 'failure' 'Invalid callback case identity'
        }
    }
    foreach ($row in $rows) {
        if ($row -isnot [string] -or $row.Length -gt 512) { Throw-Outcome 'failure' 'Invalid callback trace row' }
    }
    if ($rows.Count -ne $normalized.event_count) { Throw-Outcome 'failure' 'Callback event count differs from actual wire rows' }
    $normalized.caseIds = @($caseIds)
    $normalized.rows = @($rows)
    Assert-LoadProgress ([pscustomobject]$normalized)
    return [pscustomobject]@{ response=[pscustomobject]$normalized; codec=[pscustomobject]$codec }
}

function Invoke-Probe([string] $Action) {
    if ($Action -cnotin @('load','status','play','spawn','delete','stop')) {
        Throw-Outcome 'failure' 'Unregistered callback probe action'
    }
    Assert-OwnedSession ('before.' + $Action)
    Assert-Deadline
    $remaining = [Math]::Min($totalLimitMs - $clock.ElapsedMilliseconds, $stageLimitMs - $stageClock.ElapsedMilliseconds)
    $rpcLimit = [int][Math]::Max(1, [Math]::Min(8000, $remaining))
    $entry = [ordered]@{ stage = $record.stage; action = $Action; elapsed_ms = $clock.ElapsedMilliseconds;
                        timeout_ms = $rpcLimit; result = $null; normalized_response = $null; codec = $null; failure = $null }
    $record.rpcs += $entry
    try {
        $reply = & ($pluginPaths['Invoke-WorkbenchRpc.ps1']) -Function $Function -Parameters @{ token = $Token; action = $Action } `
                    -ClientId BerylCallbackVerifier -TimeoutMs $rpcLimit
        $entry.result = $reply
        # A response arriving beyond the terminal deadline is not success.
        Assert-Deadline
        Assert-OwnedSession ('after.' + $Action)
        if ($null -eq $reply -or $reply.Ok -isnot [bool] -or -not $reply.Ok -or
            $reply.Function -cne $Function -or $reply.Raw -isnot [string] -or $reply.Raw.Length -gt 1024 * 1024) {
            Throw-Outcome 'failure' 'Missing, failed, unrelated or oversized callback RPC result'
        }
        $checked = Check-Response $reply.Response $Action
        $entry.normalized_response = $checked.response
        $entry.codec = $checked.codec
        Assert-LoadProgress $checked.response $script:lastLoadProgress
        $script:lastLoadProgress = $checked.response
        if ($checked.response.status -ceq 'unavailable') { Throw-Outcome 'unavailable' ('Engine probe unavailable: ' + $checked.response.failure) }
        if ($checked.response.status -ceq 'failure') { Throw-Outcome 'failure' ('Engine probe reported failure: ' + $checked.response.failure) }
        return ,$checked.response
    } catch {
        $entry.failure = $_.Exception.Message
        if ($record.status -eq 'failure' -and $null -eq $entry.result) {
            if ($clock.ElapsedMilliseconds -ge $totalLimitMs -or $stageClock.ElapsedMilliseconds -ge $stageLimitMs -or
                $_.Exception.Message -match '^No response from Workbench.*within.*ms') {
                $record.status = 'timeout'
            } else { $record.status = 'unavailable' }
        }
        throw
    }
}

function Assert-FrameIdentity([object] $Entry, [string] $Site) {
    # These checks are separate from the unchanged callback identity sequence.
    Assert-Deadline
    Assert-Inputs
    $current = Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
    if ($null -eq $current) { Throw-Outcome 'unavailable' 'Owned process unavailable for frame observation' }
    if ($current.StartTime.ToUniversalTime().Ticks -ne $ownedStartTicks -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $current.Path), $ownedExecutable)) {
        Throw-Outcome 'stale_input' 'Frame observation process identity differs'
    }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $ownedPid }).Count) {
        Throw-Outcome 'unavailable' 'Unrelated Workbench appeared before frame observation'
    }
    $Entry.identity_checks += [ordered]@{site=$Site;process_id=$ownedPid;start_ticks=$ownedStartTicks;
        executable=$ownedExecutable;elapsed_ms=$clock.ElapsedMilliseconds}
}

function Observe-FrameState([object] $Response) {
    if ($FrameDiagnostics -ceq 'off' -or $record.stage -cne 'spawn' -or
        $Response.phase -notin @(2,3) -or $record.frame_state_rpcs.Count -ge 2) { return }
    # Instrumentation consumes the original deadlines; it cannot advance a case.
    $primaryStatus = $record.status
    $entry = [ordered]@{function='BerylComponentFrameState';params=@{token=$Token};stage='spawn';phase=$Response.phase;
        elapsed_ms=$clock.ElapsedMilliseconds;timeout_ms=1;result=$null;failure=$null;identity_checks=@()}
    $record.frame_state_rpcs += $entry
    try {
        Assert-FrameIdentity $entry 'before'
        $entry.elapsed_ms = $clock.ElapsedMilliseconds
        $remaining = [Math]::Min($totalLimitMs-$clock.ElapsedMilliseconds,$stageLimitMs-$stageClock.ElapsedMilliseconds)
        if ($remaining -le 0) { Throw-Outcome 'timeout' 'No original deadline budget remains for frame observation' }
        $entry.timeout_ms = [int][Math]::Min(8000,$remaining)
        $reply = & ($pluginPaths['Invoke-WorkbenchRpc.ps1']) -Function 'BerylComponentFrameState' -Parameters @{token=$Token} `
            -ClientId BerylCallbackVerifier -TimeoutMs $entry.timeout_ms
        $entry.result = $reply
        Assert-FrameIdentity $entry 'after'
        if ($clock.ElapsedMilliseconds - $entry.elapsed_ms -gt $entry.timeout_ms) {
            Throw-Outcome 'timeout' 'Frame observation returned beyond its bounded RPC budget'
        }
        if ($null -eq $reply -or $reply.Ok -isnot [bool] -or -not $reply.Ok -or
            $reply.Function -cne 'BerylComponentFrameState' -or $reply.Raw -isnot [string] -or $reply.Raw.Length -gt 1024*1024) {
            Throw-Outcome 'failure' 'Missing, failed, unrelated or oversized frame observation'
        }
    } catch {
        $entry.failure = $_.Exception.Message.Substring(0,[Math]::Min(4096,$_.Exception.Message.Length))
    } finally {
        # An auxiliary observation must not replace the callback's primary outcome.
        $record.status = $primaryStatus
    }
}

function Assert-PinnedWorld([object] $Response) {
    if (-not $Response.addon_world_resolved -or -not $Response.world_path_resolved -or -not $Response.world_matches -or
        -not $Response.resource_name_resolved -or -not $Response.module_present -or -not $Response.api_present -or
        -not $Response.module_open_requested -or -not $Response.module_open_accepted -or
        $Response.load_requested -ne 1 -or $Response.load_submitted -ne 1 -or $Response.load_entered -ne 1 -or
        $Response.load_resumed -ne 1 -or $Response.load_returned -ne 1 -or -not $Response.load_accepted -or
        $Response.resource_name -cne '{BCCBA11B20261008}worlds/BerylCallbackProbe.ent' -or
        $Response.resource_path -isnot [string] -or $Response.resource_path.Length -eq 0 -or $Response.resource_path.Length -gt 2048 -or
        $Response.addon_world_path -cnotmatch '^[A-Za-z]:[\\/]' -or $Response.world_absolute_path -cnotmatch '^[A-Za-z]:[\\/]' -or
        $Response.resource_absolute_path -cnotmatch '^[A-Za-z]:[\\/]' -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.addon_world_path), (Normal-Path $canonicalWorld)) -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.world_absolute_path), (Normal-Path $canonicalWorld)) -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.resource_absolute_path), (Normal-Path $canonicalWorld))) {
        Throw-Outcome 'stale_input' 'Ready callback native resource resolutions are not the pinned owned world'
    }
}

function Stage-Ready([object] $Response, [string] $Action) {
    if ($Response.status -ceq 'pending') { return $false }
    Assert-PinnedWorld $Response
    switch -CaseSensitive ($Action) {
        'load' { return ($Response.status -ceq 'ready' -and $Response.edit_mode -and -not $Response.game_mode -and -not $Response.in_play_mode) }
        'play' { return ($Response.status -ceq 'ready' -and $Response.game_mode -and $Response.in_play_mode -and $Response.world_present) }
        'spawn' { return ($Response.status -ceq 'ready' -and $Response.phase -eq 3 -and $Response.game_mode -and $Response.in_play_mode -and $Response.world_present) }
        'delete' { return ($Response.status -ceq 'complete' -and $Response.phase -eq 4 -and $Response.executed -eq 1 -and $Response.failures -eq 0) }
        'stop' { return (($Response.status -ceq 'ready' -or $Response.status -ceq 'complete') -and $Response.edit_mode -and -not $Response.game_mode -and -not $Response.in_play_mode) }
        default { Throw-Outcome 'failure' 'Unregistered callback stage' }
    }
}

function Run-Stage([string] $Action) {
    $record.stage = $Action
    $script:stageClock = [Diagnostics.Stopwatch]::StartNew()
    $item = [ordered]@{ action = $Action; status = 'pending'; polls = 0; response = $null; elapsed_ms = 0 }
    $record.stages += $item
    try {
        Assert-Inputs
        $response = Invoke-Probe $Action
        $item.response = $response
        if ($Action -ceq 'spawn' -and $FrameDiagnostics -ceq 'world-state-v1') { Observe-FrameState $response }
        while (-not (Stage-Ready $response $Action)) {
            if ($item.polls -ge $MaxPolls) { Throw-Outcome 'timeout' 'Callback stage exhausted its bounded poll count' }
            Assert-Deadline
            Start-Sleep -Milliseconds 200
            Assert-Deadline
            $item.polls++
            $response = Invoke-Probe 'status'
            $item.response = $response
            if ($Action -ceq 'spawn' -and $FrameDiagnostics -ceq 'world-state-v1' -and $item.polls -eq $MaxPolls) {
                Observe-FrameState $response
            }
        }
        Assert-Deadline
        Assert-Inputs
        $item.status = 'completed'
        $item.elapsed_ms = $stageClock.ElapsedMilliseconds
        return ,$response
    } catch {
        $item.status = $record.status
        $item.elapsed_ms = $stageClock.ElapsedMilliseconds
        throw
    }
}

try {
    if ($FrameDiagnostics -cnotin @('off','world-state-v1')) { Throw-Outcome 'failure' 'Unknown case-sensitive frame diagnostic profile' }
    if ($EngineUpdates -cnotin @('focus-dependent','force-update')) {
        Throw-Outcome 'failure' 'Unknown case-sensitive engine update policy'
    }
    if ($Token -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedEngineHash -cnotmatch '^[0-9a-f]{64}$' -or
        $Function -cnotmatch '^[A-Za-z_][A-Za-z0-9_]{0,127}$' -or $ProjectId -cnotmatch '^[A-Za-z_][A-Za-z0-9_]{0,127}$') {
        Throw-Outcome 'failure' 'Invalid pinned callback identity or executable hash'
    }
    $canonicalProject = (Resolve-Path -LiteralPath $ProjectDir).ProviderPath
    $canonicalWorld = [IO.Path]::GetFullPath((Join-Path $canonicalProject 'worlds/BerylCallbackProbe.ent'))
    $record.expected_world = $canonicalWorld
    if ((Normal-Path $resultFullPath).StartsWith((Normal-Path $canonicalProject) + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Throw-Outcome 'failure' 'Adapter receipt must be outside the immutable staged addon'
    }
    foreach ($path in @($canonicalProject, (Join-Path $canonicalProject 'worlds'), $canonicalWorld, (Join-Path $canonicalProject 'addon.gproj'))) {
        $item = Get-Item -LiteralPath $path
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Throw-Outcome 'stale_input' 'Linked project/world input is not admitted' }
    }
    foreach ($name in @('Find-Workbench.ps1','Start-WorkbenchDaemon.ps1','Invoke-WorkbenchRpc.ps1')) {
        $path = [IO.Path]::GetFullPath((Join-Path $ToolRoot ('scripts/' + $name)))
        if (-not [IO.File]::Exists($path)) { Throw-Outcome 'unavailable' "Installed integration script missing: $name" }
        $pluginPaths[$name] = $path
        $pluginHashes[$name] = Content-Hash $path
    }
    $record.tools = $pluginHashes
    $mutex = [Threading.Mutex]::new($false, 'Local\BerylOwnedWorkbenchSessionV1')
    try { $acquired = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $acquired = $true }
    if (-not $acquired) { Throw-Outcome 'unavailable' 'Another Beryl job owns the Workbench session gate' }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue).Count) {
        Throw-Outcome 'unavailable' 'An existing Workbench session will not be reused or stopped'
    }
    $paths = & ($pluginPaths['Find-Workbench.ps1'])
    if (-not $paths.WorkbenchExe) { Throw-Outcome 'unavailable' 'Installed Workbench executable was not located' }
    $record.engine_path = [IO.Path]::GetFullPath($paths.WorkbenchExe)
    $record.engine_sha256 = Content-Hash $record.engine_path
    $record.engine_version = (Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion
    Assert-Inputs
    if (Test-Path -LiteralPath $paths.LogsDir) {
        $priorLogDirectories = @(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | ForEach-Object { $_.FullName })
    }
    $logsBaselineCaptured = $true
    $record.stage = 'startup'
    $script:stageClock = [Diagnostics.Stopwatch]::StartNew()
    if ($EngineUpdates -ceq 'force-update') {
        if ($StageTimeoutSeconds -ne 30 -or $MaxPolls -ne 64 -or $TotalTimeoutSeconds -ne 180) {
            Throw-Outcome 'failure' 'Force-update launch requires the fixed 30/64/180 bounds'
        }
        if ($PSVersionTable.PSVersion.Major -lt 7 -or $null -eq ([Diagnostics.ProcessStartInfo]::new()).ArgumentList) {
            Throw-Outcome 'unavailable' 'Force-update launch requires PowerShell 7 and ProcessStartInfo.ArgumentList'
        }
        $argv=Select-EngineUpdateProfile $EngineUpdates $canonicalProject
        if ($paths.GameRoot -isnot [string] -or -not [IO.Directory]::Exists($paths.GameRoot) -or
            (Get-Item -LiteralPath $paths.GameRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Throw-Outcome 'unavailable' 'Selected engine working directory is missing or linked'
        }
        $info=[Diagnostics.ProcessStartInfo]::new()
        $info.FileName=$record.engine_path
        $info.WorkingDirectory=$paths.GameRoot
        $info.UseShellExecute=$false
        $info.CreateNoWindow=$true
        $info.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
        foreach ($argument in $argv) { $info.ArgumentList.Add($argument) }
        $record.engine_update_launch=[ordered]@{schema_version=1;mechanism='force_update_argument_list';arguments=@($argv);
            working_directory=$paths.GameRoot;use_shell_execute=$false;create_no_window=$true;window_style='Hidden';
            launch_returned=$false;process_id=$null;start_ticks=$null;executable=$null;
            limits=[ordered]@{startup_ms=30000;rpc_ms=8000;overall_ms=180000;cleanup_ms=5000;max_polls=64}}
        $ownedProcess=[Diagnostics.Process]::new()
        $ownedProcess.StartInfo=$info
        if (-not $ownedProcess.Start()) { $ownedProcess=$null;Throw-Outcome 'unavailable' 'Owned force-update launch did not return a process' }
        # Retain the actual process and PID before any query or wait.
        $ownedPid=$ownedProcess.Id
        $record.engine_update_launch.launch_returned=$true
        $record.engine_update_launch.process_id=$ownedPid
        $ownedStartTicks=$ownedProcess.StartTime.ToUniversalTime().Ticks
        $ownedExecutable=Normal-Path $ownedProcess.Path
        $record.engine_update_launch.start_ticks=$ownedStartTicks
        $record.engine_update_launch.executable=$ownedExecutable
        if (-not [StringComparer]::OrdinalIgnoreCase.Equals($ownedExecutable,(Normal-Path $record.engine_path))) {
            Throw-Outcome 'stale_input' 'Started force-update process differs from the pinned engine'
        }
        $record.session=[ordered]@{process_id=$ownedPid;start_time=$ownedProcess.StartTime.ToUniversalTime().ToString('o');
            start_ticks=$ownedStartTicks;executable=$ownedExecutable;project=$canonicalProject;reused=$false}
        Assert-LaunchIdentity 'launch.identity'
        Wait-ForceUpdateListener
        # Listener ownership proves transport availability only. Loaded-project
        # and every callback-stage check below still independently execute.
        $start=[pscustomobject]@{Ok=$true;Reused=$false;ProcessId=$ownedPid;Mechanism='force_update_argument_list'}
    } else {
        # Preserve the existing focus-dependent startup path without extra flags.
        $start = & ($pluginPaths['Start-WorkbenchDaemon.ps1']) -ProjectDir $canonicalProject -TimeoutSeconds $StageTimeoutSeconds
    }
    $record.startup = $start
    # The installed helper retains its own startup wait; reject a late return
    # using the monotonic deadline and the caller's outer owned-process budget.
    if ($null -eq $start -or $start.Ok -isnot [bool] -or -not $start.Ok -or $start.Reused -isnot [bool] -or $start.Reused) {
        Throw-Outcome 'unavailable' 'No exclusively owned Workbench session was started'
    }
    Assert-Int $start.ProcessId 1 ([int]::MaxValue) 'startup.ProcessId'
    if ($EngineUpdates -ceq 'focus-dependent') {
        $ownedProcess = Get-Process -Id $start.ProcessId
        $ownedPid = $ownedProcess.Id
        $ownedStartTicks = $ownedProcess.StartTime.ToUniversalTime().Ticks
        $ownedExecutable = Normal-Path $ownedProcess.Path
    }
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($ownedExecutable, (Normal-Path $record.engine_path))) {
        # Do not claim or stop a process whose path is not the selected engine.
        $ownedProcess = $null; $ownedPid = $null
        Throw-Outcome 'stale_input' 'Started process executable differs from the pinned engine'
    }
    $record.session = [ordered]@{process_id=$ownedPid;start_time=$ownedProcess.StartTime.ToUniversalTime().ToString('o');
        start_ticks=$ownedStartTicks;executable=$ownedExecutable;project=$canonicalProject;reused=$false}
    Assert-Deadline
    Assert-OwnedSession 'startup.complete'
    Assert-Inputs
    $loaded = & ($pluginPaths['Invoke-WorkbenchRpc.ps1']) -Function GetLoadedProjects -ClientId BerylCallbackVerifier -TimeoutMs 8000
    $record.loaded_projects = $loaded
    Assert-Deadline
    Assert-OwnedSession 'loaded-projects.complete'
    if ($null -eq $loaded -or $loaded.Ok -isnot [bool] -or -not $loaded.Ok -or
        $loaded.Function -cne 'GetLoadedProjects' -or $null -eq $loaded.Response -or
        $loaded.Response.'Loaded Projects' -isnot [Array] -or $ProjectId -cnotin $loaded.Response.'Loaded Projects') {
        Throw-Outcome 'stale_input' 'Loaded project receipt does not identify the exact owned addon'
    }
    $null = Run-Stage 'load'
    $null = Run-Stage 'play'
    $null = Run-Stage 'spawn'
    $record.completion = Run-Stage 'delete'
    $null = Run-Stage 'stop'
    Assert-Deadline
    Assert-Inputs
    $record.status = 'success'
    $record.stage = 'callback_transport_complete'
} catch {
    $record.failure = $_.Exception.Message
    if ($_.Exception -is [Management.Automation.PipelineStoppedException]) { $record.status = 'cancelled' }
    elseif ($record.stage -eq 'startup' -and $null -eq $record.session) {
        if ($_.Exception.Message -match 'within.*s' -or $clock.ElapsedMilliseconds -ge $totalLimitMs -or
            ($null -ne $stageClock -and $stageClock.ElapsedMilliseconds -ge $stageLimitMs)) { $record.status = 'timeout' }
        elseif ($record.status -eq 'failure') { $record.status = 'unavailable' }
    }
    elseif ($_.Exception -is [Management.Automation.PSSecurityException]) { $record.status = 'unavailable' }
} finally {
    # Cleanup is tied to all three identities, including executable path.
    try {
        if ($null -ne $ownedProcess) {
            $current = Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
            if ($null -eq $current) { $record.cleanup = 'owned_process_already_exited' }
            elseif ($null -eq $ownedStartTicks -or $null -eq $ownedExecutable) {
                $record.cleanup = 'owned_process_identity_unavailable_not_stopped'
                $record.evidence_errors += [ordered]@{stage='owned_cleanup';message='Launch returned a process but its full identity was unavailable; it was not stopped'}
                if ($record.status -eq 'success') { $record.status='unavailable';$record.failure='Owned process cleanup identity unavailable' }
            }
            elseif ($current.StartTime.ToUniversalTime().Ticks -eq $ownedStartTicks -and
                [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $current.Path), $ownedExecutable)) {
                Stop-Process -Id $ownedPid -Force
                $confirmedExit = $current.WaitForExit(5000)
                if ($confirmedExit) {
                    $record.cleanup = 'owned_process_stopped'
                } else {
                    $record.cleanup = 'owned_process_exit_not_confirmed'
                    $record.evidence_errors += [ordered]@{stage='owned_cleanup';message='Owned process did not confirm exit within the bounded cleanup wait'}
                    if ($record.status -eq 'success') {
                        $record.status = 'unavailable'
                        $record.failure = 'Owned process exit was not confirmed; no stronger stop was attempted'
                    }
                }
            } else {
                $record.cleanup = 'identity_changed_not_stopped'
                if ($record.status -eq 'success') { $record.status = 'stale_input'; $record.failure = 'Owned cleanup identity changed; no process was stopped' }
            }
        } else { $record.cleanup = 'no_owned_process_identity' }
    } catch {
        $record.evidence_errors += [ordered]@{stage='owned_cleanup';message=$_.Exception.Message}
        if ($record.status -eq 'success') { $record.status = 'failure'; $record.failure = $_.Exception.Message }
    }
    # Preserve newly created raw session logs on failure as well as success.
    try {
        if ($logsBaselineCaptured -and (Test-Path -LiteralPath $paths.LogsDir)) {
            $newLogs = @(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | Where-Object { $_.FullName -notin $priorLogDirectories })
            if ($newLogs.Count -gt 16) { throw 'Session log directory count exceeds fixture bound' }
            foreach ($directory in $newLogs) {
                if ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked session log directory' }
                $record.log_directories += $directory.FullName
                $logFiles = @(Get-ChildItem -LiteralPath $directory.FullName -File -Filter '*.log')
                if ($logFiles.Count -gt 256) { throw 'Session log file count exceeds fixture bound' }
                foreach ($log in $logFiles) {
                    if ($log.Length -gt 64MB -or ($log.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Linked or oversized session log' }
                    $before = Content-Hash $log.FullName
                    $destinationDirectory = Join-Path ([IO.Path]::GetDirectoryName($resultFullPath)) ('callback-logs/' + $directory.Name)
                    $null = [IO.Directory]::CreateDirectory($destinationDirectory)
                    $destination = Join-Path $destinationDirectory $log.Name
                    if ([IO.File]::Exists($destination)) { throw 'Raw session log destination already exists' }
                    [IO.File]::Copy($log.FullName, $destination, $false)
                    if ((Content-Hash $destination) -cne $before -or (Content-Hash $log.FullName) -cne $before) { throw 'Session log changed during capture' }
                    $record.raw_logs += [ordered]@{original=$log.FullName;retained=$destination;sha256=$before;bytes=$log.Length}
                }
            }
        }
        if ($record.status -eq 'success' -and -not $record.raw_logs.Count) { throw 'Raw owned-session logs unavailable' }
    } catch {
        $record.evidence_errors += [ordered]@{stage='raw_session_logs';message=$_.Exception.Message}
        if ($record.status -eq 'success') { $record.status = 'unavailable'; $record.failure = $_.Exception.Message }
    }
    try {
        if ($acquired) { $mutex.ReleaseMutex() }
        if ($null -ne $mutex) { $mutex.Dispose() }
    } catch {
        $record.evidence_errors += [ordered]@{stage='session_gate_cleanup';message=$_.Exception.Message}
        if ($record.status -eq 'success') { $record.status = 'failure'; $record.failure = $_.Exception.Message }
    }
    if ($record.status -eq 'success' -and $clock.ElapsedMilliseconds -ge $totalLimitMs) {
        $record.status = 'timeout'
        $record.failure = 'Monotonic callback-probe deadline expired during final cleanup/evidence capture'
    }
    $record.elapsed_ms = $clock.ElapsedMilliseconds
    $null = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($resultFullPath))
    $json = $record | ConvertTo-Json -Depth 32
    [IO.File]::WriteAllText($resultFullPath, $json, [Text.UTF8Encoding]::new($false))
    if ([IO.File]::ReadAllText($resultFullPath) -cne $json) { throw 'Incomplete callback adapter receipt write' }
}
if ($record.status -ne 'success') { Write-Error $record.failure; exit 1 }
