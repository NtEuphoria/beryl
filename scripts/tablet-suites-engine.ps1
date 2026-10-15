# Fixed existing MESH suites in an exclusively owned requested editor context.
# No world opening, play, spawn, save, promotion or physical UI input is requested.
# Native launch/bridge calls are bounded by observation, not hard-cancelled here.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ProjectId,
    [Parameter(Mandatory)][string] $InputManifest,
    [Parameter(Mandatory)][string] $InputManifestHash,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $Token,
    [Parameter(Mandatory)][string] $ExpectedSourceHash,
    [Parameter(Mandatory)][string] $ExpectedEnginePath,
    [Parameter(Mandatory)][string] $ExpectedEngineHash,
    [Parameter(Mandatory)][string] $ExpectedEngineVersion
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$suiteProfile='sparkos.tablet.existing-suites-runtime.v1'
$selections=@(
    [ordered]@{suite='ui';arg=''},
    [ordered]@{suite='screen';arg=''},
    [ordered]@{suite='actions';arg=''},
    [ordered]@{suite='clicks';arg=''},
    [ordered]@{suite='schema';arg='{B37EEB64E149CBAD}Prefabs/SPK_Tablet.et'}
)
$record=[ordered]@{
    schema_version=1;stage='preflight';status='failure';profile=$suiteProfile;mechanism='owned_empty_editor_existing_suites';
    token=$Token;source_sha256=$ExpectedSourceHash;project_id=$ProjectId;
    scope='existing MESH ui, screen, actions, clicks and schema suites only';
    requested_editor_context='WorldEditor startup requested; no resource load requested';
    engine_path=$null;engine_bytes=$null;engine_sha256=$null;engine_version=$null;tools=$null;adapter_sha256=$null;
    input_manifest=$null;staged_inputs=$null;engine_outputs=@();arguments=@();startup=$null;session=$null;loaded_projects=$null;
    suite_selections=$selections;suites=@();identity_observations=@();completion=$null;rpcs=@();session_checks=@();
    port_checks=@();port_query_errors=@();raw_logs=@();log_directories=@();evidence_errors=@();cleanup=$null;cleanup_errors=@();
    failure=$null;elapsed_ms=0;play='not_run';spawn='not_run';save='not_run';world_open='not_run';
    tablet_callback_delivery='not_run';physical_ui_input='not_run';multiplayer='not_run';visual_review='not_run';policy_changes='not_run';
    limits=[ordered]@{stage_ms=30000;rpc_ms=8000;total_ms=180000;cleanup_ms=5000;max_polls=64;
        native_launch_and_bridge_calls_not_hard_cancelled=$true;raw_logs_aggregate_bytes=67108864}
}
$clock=[Diagnostics.Stopwatch]::StartNew()
$stageClock=$null
$ownedProcess=$null;$ownedPid=$null;$ownedStartTicks=$null;$ownedExecutable=$null
$mutex=$null;$acquired=$false;$paths=$null
$pluginPaths=@{};$pluginHashes=@{};$manifest=$null;$manifestHash=$null;$canonicalProject=$null;$expectedDirectories=@()
$priorLogDirectories=@();$logsBaselineCaptured=$false
$resultFullPath=[IO.Path]::GetFullPath($ResultPath)
$adapterPath=$PSCommandPath;$adapterHash=$null;$resultCanWrite=$false

function Assert-Parameters([string] $Function,[hashtable] $Parameters) {
    if ($Function -ceq 'GetLoadedProjects') {
        if ($Parameters.Count -ne 0) { Throw-Outcome 'failure' 'Unexpected builtin inventory parameters' }
        return
    }
    if ($Function -ceq 'BerylTabletSuiteIdentity') {
        if ($Parameters.Count -ne 1 -or 'token' -cnotin $Parameters.Keys -or $Parameters.token -isnot [string] -or
            $Parameters.token -cne $Token) { Throw-Outcome 'stale_input' 'Compiled identity parameters differ' }
        return
    }
    if ($Function -ceq 'SPK_MeshSelfTest') {
        if ($Parameters.Count -ne 2 -or @($Parameters.Keys | Where-Object {$_ -cnotin @('suite','arg')}).Count -or
            $Parameters.suite -isnot [string] -or $Parameters.arg -isnot [string] -or
            @($selections | Where-Object {$_.suite -ceq $Parameters.suite -and $_.arg -ceq $Parameters.arg}).Count -ne 1) {
            Throw-Outcome 'failure' 'Only the five fixed suite requests are permitted'
        }
        return
    }
    Throw-Outcome 'failure' 'Unregistered RPC; no opener, play, spawn, save or fallback'
}
function Assert-LoadedProjects([object] $Response) {
    Assert-Names $Response @('Loaded Projects')
    $projects=Required-Field $Response 'Loaded Projects'
    if ($projects -isnot [Array] -or $projects.Count -gt 8 -or $ProjectId -cnotin $projects -or
        @($projects | Select-Object -Unique).Count -ne $projects.Count) { Throw-Outcome 'stale_input' 'Loaded addon identity differs' }
    foreach ($project in $projects) {
        Assert-Text $project 'Loaded Projects'
        if ($project -cnotin @($ProjectId,'ArmaReforger','core')) { Throw-Outcome 'stale_input' 'Unrelated addon is loaded' }
    }
}
function Check-Identity([object] $Response) {
    Assert-Names $Response @('token','profile','source_sha256')
    foreach ($name in @('token','profile','source_sha256')) { Assert-Text (Required-Field $Response $name) $name }
    if ($Response.token -cne $Token -or $Response.profile -cne $suiteProfile -or $Response.source_sha256 -cne $ExpectedSourceHash) {
        Throw-Outcome 'stale_input' 'Compiled literal token, profile or source stamp differs'
    }
    return [pscustomobject][ordered]@{token=$Response.token;profile=$Response.profile;source_sha256=$Response.source_sha256}
}
function Check-Suite([object] $Response) {
    Assert-Names $Response @('ok','detail')
    $ok=Required-Field $Response 'ok';$detail=Required-Field $Response 'detail'
    Assert-Int $ok 'ok'
    if ($detail -isnot [string] -or $detail.Length -gt 65536 -or $detail.Contains([char]0)) {
        Throw-Outcome 'failure' 'Suite response must contain one signed i32 and bounded text'
    }
    return [pscustomobject][ordered]@{ok=$ok;detail=$detail}
}
function Assert-Int([object] $Value,[string] $Name) {
    if (($Value -isnot [int] -and $Value -isnot [long]) -or $Value -lt -2147483648L -or $Value -gt 2147483647L) {
        Throw-Outcome 'failure' ('Invalid signed i32 response '+$Name)
    }
}
function Assert-RawResponse([object] $Reply) {
    try { $raw=$Reply.Raw | ConvertFrom-Json }
    catch { Throw-Outcome 'failure' 'Raw RPC JSON could not be decoded' }
    if ($null -eq $raw -or $null -eq $Reply.Response) {
        Throw-Outcome 'failure' 'Raw RPC JSON and decoded response must be structured values'
    }
    $rawNames=@($raw.PSObject.Properties | ForEach-Object {$_.Name} | Sort-Object -CaseSensitive)
    $responseNames=@($Reply.Response.PSObject.Properties | ForEach-Object {$_.Name} | Sort-Object -CaseSensitive)
    if (($rawNames -join "`n") -cne ($responseNames -join "`n") -or
        ($raw | ConvertTo-Json -Depth 24 -Compress) -cne ($Reply.Response | ConvertTo-Json -Depth 24 -Compress)) {
        Throw-Outcome 'failure' 'Raw RPC JSON and untouched decoded response differ'
    }
}
function Invoke-Call([string] $Function,[hashtable] $Parameters) {
    Assert-Parameters $Function $Parameters
    Assert-Inputs
    Assert-OwnedSession ('before.'+$Function)
    $remaining=[Math]::Min(180000-$clock.ElapsedMilliseconds,30000-$stageClock.ElapsedMilliseconds)
    if ($remaining -le 0) { Throw-Outcome 'timeout' 'No remaining RPC response budget' }
    $limit=[int][Math]::Min(8000,$remaining)
    $entry=[ordered]@{stage=$record.stage;function=$Function;params=$Parameters.Clone();elapsed_ms=$clock.ElapsedMilliseconds;
        timeout_ms=$limit;result=$null;normalized_response=$null;failure=$null;failure_kind=$null;duration_ms=0}
    $record.rpcs+=$entry
    $callClock=[Diagnostics.Stopwatch]::StartNew()
    try {
        try { $reply=& $pluginPaths['Invoke-WorkbenchRpc.ps1'] -Function $Function -Parameters $Parameters -ClientId BerylTabletSuitesVerifier -TimeoutMs $limit }
        catch {
            $entry.failure=$_.Exception.Message
            Assert-OwnedSession ('after.'+$Function)
            if ($callClock.ElapsedMilliseconds -ge $limit) { Throw-Outcome 'timeout' 'Suite RPC exceeded its response deadline' }
            if ($_.Exception.Message -match '^No response from Workbench') {
                $entry.failure_kind='accepted_transport_no_response';Throw-Outcome 'timeout' $entry.failure
            }
            $entry.failure_kind='transport_failure_unclassified';Throw-Outcome 'unavailable' $entry.failure
        }
        $entry.result=$reply
        Assert-OwnedSession ('after.'+$Function)
        if ($callClock.ElapsedMilliseconds -ge $limit) { Throw-Outcome 'timeout' 'Late suite RPC response rejected' }
        Assert-Inputs
        Assert-Transport $reply $Function
        Assert-RawResponse $reply
        if ($Function -ceq 'BerylTabletSuiteIdentity') { $entry.normalized_response=Check-Identity $reply.Response }
        elseif ($Function -ceq 'SPK_MeshSelfTest') { $entry.normalized_response=Check-Suite $reply.Response }
        Assert-Deadline
        if ($callClock.ElapsedMilliseconds -ge $limit) { Throw-Outcome 'timeout' 'Whole suite RPC/evidence operation exceeded its admitted budget' }
        return ,$reply
    } catch {
        if ($null -eq $entry.failure) { $entry.failure=$_.Exception.Message }
        throw
    } finally { $entry.duration_ms=$callClock.ElapsedMilliseconds }
}
function Observe-Identity([string] $Site) {
    $reply=Invoke-Call 'BerylTabletSuiteIdentity' @{token=$Token}
    $record.identity_observations+= [ordered]@{site=$Site;rpc_index=$record.rpcs.Count-1;response=(Check-Identity $reply.Response)}
}

# Shared proven ownership/input/log primitives are copied below into this new
# adapter so the frozen earlier experiments remain untouched.
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
        Throw-Outcome 'timeout' 'Monotonic existing-suite deadline expired'
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
function Fixed-Arguments([string] $OwnedProject) {
    return @('-gproj',(Join-Path $OwnedProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-wbmodule=WorldEditor','-run')
}
function Assert-Transport([object] $Reply,[string] $Function) {
    Assert-Names $Reply @('Ok','Function','ErrorCode','Response','Raw')
    if ($null -eq $Reply -or $Reply.Ok -isnot [bool] -or -not $Reply.Ok -or $Reply.Function -cne $Function -or
        $Reply.ErrorCode -cne 'Ok' -or $Reply.Raw -isnot [string] -or $Reply.Raw.Length -gt 1MB) {
        Throw-Outcome 'failure' 'Invalid owned suite RPC transport envelope'
    }
}
function Record-CleanupError([string] $Stage,[string] $Message) {
    $detail=[ordered]@{stage=$Stage;message=$Message}
    $record.cleanup_errors+= $detail
    $record.evidence_errors+= $detail
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
        ($tree.directories -join "`n") -cne (@($expectedDirectories) -join "`n")) {
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
try {
    if ($PSVersionTable.PSVersion.Major -lt 7 -or $null -eq ([Diagnostics.ProcessStartInfo]::new()).ArgumentList) {
        Throw-Outcome 'unavailable' 'This fixed launcher requires PowerShell 7 and .NET ProcessStartInfo.ArgumentList'
    }
    if ($Token -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedEngineHash -cnotmatch '^[0-9a-f]{64}$' -or
        $ExpectedSourceHash -cnotmatch '^[0-9a-f]{64}$' -or $InputManifestHash -cnotmatch '^[0-9a-f]{64}$' -or
        $ProjectId -cnotmatch '^[A-Za-z_][A-Za-z0-9_]{0,127}$') { Throw-Outcome 'failure' 'Invalid pinned suite identity' }
    if (-not [IO.Path]::IsPathFullyQualified($ExpectedEnginePath)) { Throw-Outcome 'failure' 'Expected engine path must be absolute' }
    $canonicalProject=(Resolve-Path -LiteralPath $ProjectDir).ProviderPath
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
    if ($manifestHash -cne $InputManifestHash) { Throw-Outcome 'stale_input' 'Input manifest differs from caller-pinned identity' }
    $manifest=[IO.File]::ReadAllText($InputManifest) | ConvertFrom-Json -AsHashtable
    if ($manifest -isnot [Collections.IDictionary] -or $manifest.Count -ne 3 -or
        @('schema_version','profile','files' | Where-Object {-not $manifest.Contains($_)}).Count -or
        ($manifest.schema_version -isnot [int] -and $manifest.schema_version -isnot [long]) -or $manifest.schema_version -ne 1 -or
        $manifest.profile -isnot [string] -or $manifest.profile -cne $suiteProfile -or
        $manifest.files -isnot [Collections.IDictionary] -or $manifest.files.Count -ne 87) {
        Throw-Outcome 'failure' 'Only the typed frozen 87-input existing-suite profile is permitted'
    }
    foreach ($required in @('addon.gproj','scripts/WorkbenchGameCommon/BerylTabletSuiteIdentity.c',
                            'scripts/WorkbenchGameCommon/SPK_MeshSelfTest.c','scripts/WorkbenchGameCommon/ValidatePrefab.c',
                            'scripts/Game/SparkOSMesh/UI/SPK_TabletComponent.c','Prefabs/SPK_Tablet.et')) {
        if (-not $manifest.files.Contains($required)) { Throw-Outcome 'failure' 'Required candidate source/resource is absent' }
    }
    $directorySet=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($name in $manifest.files.Keys) {
        if ($name -isnot [string] -or $name.Length -gt 2048 -or $name.Contains('\') -or
            $name -cmatch '(^/|(^|/)\.\.?(/|$)|[:\x00])' -or $name.Length -eq 0 -or $name -ceq 'resourceDatabase.rdb') {
            Throw-Outcome 'failure' 'Invalid relative immutable input path'
        }
        $parent=$name
        while ($parent.Contains('/')) {
            $parent=$parent.Substring(0,$parent.LastIndexOf('/'))
            $null=$directorySet.Add($parent)
        }
    }
    foreach ($hash in $manifest.files.Values) { if ($hash -isnot [string] -or $hash -cnotmatch '^[0-9a-f]{64}$') { Throw-Outcome 'failure' 'Invalid manifest source hash' } }
    $expectedDirectories=@($directorySet | Sort-Object -CaseSensitive)
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
    $record.engine_bytes=(Get-Item -LiteralPath $record.engine_path).Length
    $record.engine_version=(Get-Item -LiteralPath $record.engine_path).VersionInfo.FileVersion
    Assert-Inputs
    if (Test-Path -LiteralPath $paths.LogsDir) { $priorLogDirectories=@(Get-ChildItem -LiteralPath $paths.LogsDir -Directory | ForEach-Object {$_.FullName}) }
    $logsBaselineCaptured=$true
    $record.stage='startup'
    $stageClock=[Diagnostics.Stopwatch]::StartNew()
    $argv=@(Fixed-Arguments $canonicalProject)
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
    $record.loaded_projects=Invoke-Call 'GetLoadedProjects' @{}
    Assert-LoadedProjects $record.loaded_projects.Response
    $record.stage='identity.initial';$stageClock=[Diagnostics.Stopwatch]::StartNew()
    Observe-Identity 'initial'
    foreach ($selection in $selections) {
        $record.stage='suite.'+$selection.suite
        $stageClock=[Diagnostics.Stopwatch]::StartNew()
        Observe-Identity ('before.'+$selection.suite)
        $reply=Invoke-Call 'SPK_MeshSelfTest' @{suite=$selection.suite;arg=$selection.arg}
        $answer=Check-Suite $reply.Response
        $suite=[ordered]@{suite=$selection.suite;arg=$selection.arg;rpc_index=$record.rpcs.Count-1;response=$answer;
            status=$(if($answer.ok -eq 1){'success'}else{'failure'})}
        $record.suites+= $suite
        Observe-Identity ('after.'+$selection.suite)
        if ($answer.ok -ne 1) { Throw-Outcome 'failure' ('Existing suite rejected: '+$selection.suite+'; '+$answer.detail) }
        Assert-Deadline
    }
    $record.stage='identity.final';$stageClock=[Diagnostics.Stopwatch]::StartNew()
    Observe-Identity 'final'
    Assert-Deadline;Assert-Inputs
    $record.completion=[ordered]@{suite_count=$record.suites.Count;identity_count=$record.identity_observations.Count;
        suite_ids=@($record.suites | ForEach-Object {$_.suite});requests_executed=$record.suites.Count}
    if ($record.suites.Count -ne 5 -or $record.identity_observations.Count -ne 12 -or $record.rpcs.Count -ne 18) {
        Throw-Outcome 'failure' 'Incomplete fixed suite/identity call ledger'
    }
    $record.status='success';$record.stage='suites_complete'
} catch {
    $record.failure=$_.Exception.Message
    if ($_.Exception -is [Management.Automation.PipelineStoppedException]) { $record.status='cancelled' }
} finally {
    try {
        if ($null -eq $ownedProcess) { $record.cleanup='no_owned_process' }
        elseif ($ownedProcess.WaitForExit(0)) { $record.cleanup='owned_process_already_exited' }
        elseif ($null -eq $ownedPid -or $null -eq $ownedStartTicks -or $null -eq $ownedExecutable) {
            $record.cleanup='owned_process_identity_unavailable_not_stopped'
            Record-CleanupError 'owned_cleanup' 'Started process retained but complete identity unavailable; no stop attempted'
        } else {
            $current=Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
            if ($null -eq $current -or $current.StartTime.ToUniversalTime().Ticks -ne $ownedStartTicks -or
                -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $current.Path),$ownedExecutable)) {
                $record.cleanup='identity_changed_not_stopped'
                Record-CleanupError 'owned_cleanup' 'Owned process identity changed; no stop attempted'
            } else {
                $ownedProcess.Kill()
                if ($ownedProcess.WaitForExit(5000)) { $record.cleanup='owned_process_stopped' }
                else {
                    $record.cleanup='owned_process_exit_not_confirmed'
                    Record-CleanupError 'owned_cleanup' 'No confirmed exit within five seconds; no stronger stop attempted'
                }
            }
        }
    } catch {
        $record.cleanup='owned_process_exit_not_confirmed'
        Record-CleanupError 'owned_cleanup' $_.Exception.Message
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
                    $retainedDir=Join-Path ([IO.Path]::GetDirectoryName($resultFullPath)) ('tablet-suite-logs/'+$directory.Name)
                    $null=[IO.Directory]::CreateDirectory($retainedDir)
                    $retained=Join-Path $retainedDir $log.Name
                    [IO.File]::Copy($log.FullName,$retained,$false)
                    if ((Content-Hash $retained) -cne $before -or (Content-Hash $log.FullName) -cne $before) { throw 'Raw log changed during capture' }
                    $record.raw_logs+= [ordered]@{original=$log.FullName;retained=$retained;sha256=$before;bytes=$log.Length}
                }
            }
        }
        if ($record.stage -ceq 'suites_complete' -and -not $record.raw_logs.Count) { throw 'Owned session raw logs unavailable' }
    } catch { $record.evidence_errors+= [ordered]@{stage='raw_session_logs';message=$_.Exception.Message} }
    $beforeFinalStatus=$record.status
    try { if ($null -ne $manifest -and $null -ne $record.engine_path) { Assert-Inputs } }
    catch {
        $record.evidence_errors+= [ordered]@{stage='final_input_identity';message=$_.Exception.Message}
        if ($null -eq $record.failure) {$record.failure=$_.Exception.Message}
        if ($beforeFinalStatus -eq 'success' -or ($beforeFinalStatus -eq 'unavailable' -and $record.stage -ceq 'suites_complete')) {$record.status='stale_input'}
        else {$record.status=$beforeFinalStatus}
    }
    try { if ($acquired) {$mutex.ReleaseMutex()};if ($null -ne $mutex) {$mutex.Dispose()} }
    catch { Record-CleanupError 'session_gate_cleanup' $_.Exception.Message }
    if ($record.status -eq 'success' -and $record.evidence_errors.Count) { $record.status='unavailable';$record.failure='Cleanup or raw evidence incomplete' }
    if (($record.status -eq 'success' -or ($record.status -eq 'unavailable' -and $record.stage -ceq 'suites_complete')) -and $clock.ElapsedMilliseconds -ge 180000) {
        $record.status='timeout';$record.failure='Overall deadline expired during evidence capture'
    }
    $record.elapsed_ms=$clock.ElapsedMilliseconds
    $record.raw_log_observation=$(if($record.cleanup -cin @('owned_process_stopped','owned_process_already_exited')){'snapshot_after_confirmed_owned_exit'}else{'point_in_time_exit_unconfirmed'})
    if ($resultCanWrite) {
        $json=$record | ConvertTo-Json -Depth 32
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes($json)
        if ($bytes.Length -gt 2MB) { throw 'Suite adapter receipt exceeds 2 MiB' }
        $output=[IO.FileStream]::new($resultFullPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $output.Write($bytes,0,$bytes.Length);$output.Flush($true) } finally {$output.Dispose()}
        if ([IO.File]::ReadAllText($resultFullPath) -cne $json) { throw 'Incomplete suite adapter receipt write' }
    }
}
if ($record.status -ne 'success') { Write-Error $record.failure;exit 1 }
