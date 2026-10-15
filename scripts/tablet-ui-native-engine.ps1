# Experimental bounded startup image readiness; no alternate process lookup or path fallback.
# Experimental pinned-file read lease window; original callbacks/caps remain unchanged.
# Distinct bounded native UI/frame/queued-method/destruction observer transport.
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
    [Parameter(Mandatory)][string] $ExpectedContractHash,
    [Parameter(Mandatory)][string] $ExpectedEnginePath,
    [Parameter(Mandatory)][string] $ExpectedEngineHash,
    [Parameter(Mandatory)][string] $ExpectedEngineVersion
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$suiteProfile='sparkos.tablet.ui-native.n1b-n3.source.v1'
$record=[ordered]@{
    schema_version=1;stage='preflight';status='failure';profile=$suiteProfile;mechanism='owned_tablet_ui_native_n1b_n3';
    token=$Token;source_sha256=$ExpectedSourceHash;source_contract_sha256=$ExpectedContractHash;project_id=$ProjectId;
    scope='native UI actions, delivered frames/queued methods and OnDelete milestones; no equipment, physical input, pixels or physical release claim';
    engine_path=$null;engine_bytes=$null;engine_sha256=$null;engine_version=$null;tools=$null;adapter_sha256=$null;
    input_manifest=$null;staged_inputs=$null;engine_outputs=@();arguments=@();startup=$null;session=$null;loaded_projects=$null;
    expected_world=$null;stages=@();natural_progress_windows=@();trace_checks=@();completion=$null;rpcs=@();session_checks=@();
    port_checks=@();port_query_errors=@();raw_logs=@();log_directories=@();evidence_errors=@();cleanup=$null;cleanup_errors=@();
    failure=$null;elapsed_ms=0;save='not_run';physical_ui_input='not_run';multiplayer='not_run';visual_review='not_run';policy_changes='not_run';
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
$script:lastLoadProgress=$null
$script:lastUIProgress=$null

# Windows read-sharing leases cover pinned file bytes during spawn/stop only.
# No native handles/pointers are serialized in the evidence record.
$script:nativeLeaseHandles=[Collections.Generic.List[object]]::new()
$script:nativeLeaseFast=$false
$script:nativeLeaseComplete=$false
$record.read_lease=[ordered]@{
    schema_version=1;policy='FileMode.Open/FileAccess.Read/FileShare.Read';status='not_requested';acquisition_status='not_requested';release_status='not_requested';
    expected_count=104;opened_count=0;released_count=0;entries=@();errors=@();
    open_started_ms=$null;open_completed_ms=$null;open_duration_ms=$null;
    close_started_ms=$null;close_completed_ms=$null;close_duration_ms=$null;
    fast_checks=@();fast_check_count=0;full_checks_with_handles=0;post_release_full_check=$false;
    byte_identity='hashed_while_held; fast_checks_length_and_readability_only';
    native_open_dispose_not_hard_cancelled=$true
}

function Beryl-BundleHash([byte[]] $Bytes) {
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
}
function Write-BerylReceiptBytes([string] $Path,[byte[]] $Bytes) {
    $tmp=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
    $stream=[IO.FileStream]::new($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true) } finally { $stream.Dispose() }
    $sha=Beryl-BundleHash $Bytes
    if ((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sha) {throw 'Temporary receipt bytes differ'}
    [IO.File]::Move($tmp,$Path,$false)
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sha) {throw 'Published receipt bytes differ'}
    return [pscustomobject]@{bytes=$Bytes.Length;sha256=$sha}
}
# Replacement capsule function only. All original public failure fields remain.
function Beryl-BundleFailure([Collections.IDictionary] $Record,[string] $Reason,[object] $FullBytes,[object] $FullSha,[string] $Detail) {
    $clip={param($value,[int]$length)if($null -eq $value){return $null};$s=[string]$value;if($s.Length -gt $length){return $s.Substring(0,$length)};return $s}
    $logs=@($Record['raw_logs']);$cleanupErrors=@($Record['cleanup_errors'])
    $retainedLogs=@();$retainedErrors=@()
    foreach($entry in @($logs|Select-Object -First 16)) {
        if($null -ne $entry) {
            $retainedLogs+=@{retained=(&$clip $entry.retained 2048);sha256=(&$clip $entry.sha256 64);bytes=$entry.bytes}
        }
    }
    foreach($entry in @($cleanupErrors|Select-Object -First 16)) {
        if($null -ne $entry) {$retainedErrors+=@{stage=(&$clip $entry.stage 256);message=(&$clip $entry.message 2048)}}
    }
    return [ordered]@{
        schema_version=1;profile=(&$clip $Record['profile'] 256);evidence_format='beryl.evidence.receipt-failure.v1';status='failure';stage='receipt_serialization';failure=$Reason;
        token=(&$clip $Record['token'] 64);source_sha256=(&$clip $Record['source_sha256'] 64);source_contract_sha256=(&$clip $Record['source_contract_sha256'] 64);
        cleanup=(&$clip $Record['cleanup'] 256);cleanup_errors=$retainedErrors;raw_logs=$retainedLogs;rpcs=@();stages=@();natural_progress_windows=@();completion=$null;
        receipt_serialization=[ordered]@{
            schema_version=1;format='compact_json_utf8';limit_bytes=2MB;manifest_limit_bytes=2MB;chunk_limit_bytes=1MB;max_chunks=16;aggregate_limit_bytes=16MB;
            full_serialized_bytes=$FullBytes;full_serialized_sha256=$FullSha;trace_complete=$false;
            prior_status=(&$clip $Record['status'] 256);prior_stage=(&$clip $Record['stage'] 256);prior_failure=(&$clip $Record['failure'] 65536);
            serialization_error=(&$clip $Detail 4096);details=(&$clip $Detail 4096);prior_metadata_may_be_clipped=$true;
            raw_log_reference_count=$logs.Count;raw_log_references_complete=($logs.Count -le 16);raw_log_reference_values_may_be_clipped=$true;
            cleanup_error_count=$cleanupErrors.Count;cleanup_error_references_complete=($cleanupErrors.Count -le 16);cleanup_error_reference_values_may_be_clipped=$true
        }
    }
}
function Write-BerylBundledReceipt([Collections.IDictionary] $Record,[string] $Path) {
    $full=$null;$fullSha=$null;$fullSize=$null
    try {
        $fullJson=$Record|ConvertTo-Json -Depth 32 -Compress -WarningAction Stop
        $full=[Text.UTF8Encoding]::new($false).GetBytes($fullJson)
        $fullSize=$full.Length;$fullSha=Beryl-BundleHash $full
    } catch {
        $capsule=Beryl-BundleFailure $Record 'Suite adapter receipt serialization failed' $null $null $_.Exception.Message
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($capsule|ConvertTo-Json -Depth 32 -Compress -WarningAction Stop))
        if($bytes.Length -gt 2MB){throw 'Serialization failure capsule exceeds manifest cap'}
        $written=Write-BerylReceiptBytes $Path $bytes
        return [pscustomobject]@{record=$capsule;mode='failure_capsule';bytes=$written.bytes;sha256=$written.sha256;full_bytes=$null;full_sha256=$null}
    }
    if($fullSize -le 2MB) {
        $written=Write-BerylReceiptBytes $Path $full
        return [pscustomobject]@{record=$Record;mode='direct_json';bytes=$written.bytes;sha256=$written.sha256;full_bytes=$fullSize;full_sha256=$fullSha}
    }
    if($fullSize -gt 16MB) {
        $capsule=Beryl-BundleFailure $Record 'Suite adapter receipt exceeds 16 MiB bundle budget' $fullSize $fullSha 'No complete bundle was published'
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($capsule|ConvertTo-Json -Depth 32 -Compress -WarningAction Stop))
        if($bytes.Length -gt 2MB){throw 'Oversize failure capsule exceeds manifest cap'}
        $written=Write-BerylReceiptBytes $Path $bytes
        return [pscustomobject]@{record=$capsule;mode='failure_capsule';bytes=$written.bytes;sha256=$written.sha256;full_bytes=$fullSize;full_sha256=$fullSha}
    }
    try {
        $parts=@();$partCount=[int][Math]::Ceiling($fullSize/[double](1MB))
        if($partCount -lt 1 -or $partCount -gt 16){throw 'Invalid receipt part count'}
        for($index=0;$index -lt $partCount;$index++) {
            $offset=$index*1MB;$length=[int][Math]::Min(1MB,$fullSize-$offset)
            $part=[byte[]]::new($length)
            [Buffer]::BlockCopy($full,$offset,$part,0,$length)
            $name=[IO.Path]::GetFileName($Path)+('.part-{0:D4}.bin' -f $index)
            $partPath=Join-Path ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Path))) $name
            # Parts are CreateNew and immutable after this write. No pooling.
            $stream=[IO.FileStream]::new($partPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
            try {$stream.Write($part,0,$length);$stream.Flush($true)}finally{$stream.Dispose()}
            $sha=Beryl-BundleHash $part
            if((Get-FileHash -LiteralPath $partPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sha){throw 'Receipt part readback differs'}
            $parts+=@{index=$index;name=$name;bytes=$length;sha256=$sha}
        }
        $header=[ordered]@{
            schema_version=1;profile='beryl.evidence.chunked-json.v1';status='unavailable';stage='receipt_bundle_requires_hydration';
            failure='Bundled receipt requires independent hydration and semantic validation';
            encoding='utf-8';format='json_compact';original_status=$Record['status'];original_stage=$Record['stage'];original_failure=$Record['failure'];
            limits=@{manifest_bytes=2MB;part_bytes=1MB;max_parts=16;aggregate_bytes=16MB};
            bundle=[ordered]@{count=$partCount;total_bytes=$fullSize;sha256=$fullSha;parts=$parts}
        }
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($header|ConvertTo-Json -Depth 32 -Compress -WarningAction Stop))
        if($bytes.Length -gt 2MB){throw 'Receipt bundle manifest exceeds 2 MiB'}
        $written=Write-BerylReceiptBytes $Path $bytes
        # Process outcome follows the original transport. Header alone is unavailable.
        return [pscustomobject]@{record=$Record;mode='chunked_json';bytes=$written.bytes;sha256=$written.sha256;full_bytes=$fullSize;full_sha256=$fullSha}
    } catch {
        $capsule=Beryl-BundleFailure $Record 'Suite adapter receipt bundle write failed' $fullSize $fullSha $_.Exception.Message
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($capsule|ConvertTo-Json -Depth 32 -Compress -WarningAction Stop))
        if($bytes.Length -gt 2MB){throw 'Bundle failure capsule exceeds manifest cap'}
        # Existing final output is never overwritten, including failed publishing.
        $written=Write-BerylReceiptBytes $Path $bytes
        return [pscustomobject]@{record=$capsule;mode='failure_capsule';bytes=$written.bytes;sha256=$written.sha256;full_bytes=$fullSize;full_sha256=$fullSha}
    }
}

function Assert-Parameters([string] $Function,[hashtable] $Parameters) {
    if ($Function -ceq 'GetLoadedProjects') {
        if ($Parameters.Count -ne 0) { Throw-Outcome 'failure' 'Unexpected builtin inventory parameters' }
        return
    }
    if ($Function -ceq 'BerylTabletUINative') {
        if ($Parameters.Count -ne 2 -or @($Parameters.Keys | Where-Object {$_ -cnotin @('token','action')}).Count -or
            $Parameters.token -isnot [string] -or $Parameters.token -cne $Token -or
            $Parameters.action -isnot [string] -or $Parameters.action -cnotin @('load','status','play','spawn','run0','run1','run2','run3','run4','run5','run6','stop')) {
            Throw-Outcome 'failure' 'Only fixed native UI probe requests are permitted'
        }
        return
    }
    Throw-Outcome 'failure' 'Unregistered RPC; no direct deletion, input, save or fallback'
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
function Assert-Int([object] $Value,[string] $Name) {
    if (($Value -isnot [int] -and $Value -isnot [long]) -or $Value -lt -2147483648L -or $Value -gt 2147483647L) {
        Throw-Outcome 'failure' ('Invalid signed i32 response '+$Name)
    }
}
function Check-Native([object] $Response,[string] $Action) {
    $texts=@('token','action','status','failure','profile','source_contract_sha256','source_sha256','world_path','current_project',
        'addon_world_path','world_absolute_path','resource_name','resource_path','resource_absolute_path')
    $booleans=@('addon_world_resolved','world_path_resolved','resource_name_resolved','module_present','api_present',
        'module_open_requested','module_open_accepted','load_accepted','world_matches','edit_mode','game_mode','in_play_mode',
        'world_present','game_world_present','actions_ready','stop_requested','outside_domain',
        'first_progress_ready','reopen_progress_ready','final_focused')
    $ints=@('schema_version','load_requested','load_submitted','load_entered','load_resumed','load_returned',
        'phase','executed','failures','owner_count','row_count','checksum','raw_bytes',
        'action_count','frame_count','queue_count','init_count','delete_count','presuper_count','after_super_count')
    $arrays=@('caseIds','rows')
    $expected=@($texts+$booleans+$ints+$arrays)
    if ($null -eq $Response) { Throw-Outcome 'failure' 'Missing native UI response' }
    $names=@($Response.PSObject.Properties | ForEach-Object {$_.Name})
    $missing=@($expected | Where-Object {$_ -cnotin $names})
    if (@($names | Where-Object {$_ -cnotin $expected}).Count -or @($missing | Where-Object {$_ -cnotin $arrays}).Count) {
        Throw-Outcome 'failure' 'Unknown or missing native UI response fields'
    }
    $n=[ordered]@{};$codec=[ordered]@{schema_version=1;numeric_boolean_fields=@();omitted_empty_arrays=@()}
    foreach ($name in $texts) { $value=Required-Field $Response $name;Assert-Text $value $name;$n[$name]=$value }
    foreach ($name in $booleans) { $n[$name]=Normalize-Bool (Required-Field $Response $name) $name $codec }
    foreach ($name in $ints) { $value=Required-Field $Response $name;Assert-Int $value $name;$n[$name]=$value }
    if ($n.token -cne $Token -or $n.action -cne $Action -or $n.profile -cne $suiteProfile -or
        $n.source_sha256 -cne $ExpectedSourceHash -or $n.source_contract_sha256 -cne $ExpectedContractHash) {
        Throw-Outcome 'stale_input' 'Compiled native UI identity differs'
    }
    if ($n.schema_version -ne 1 -or $n.status -cnotin @('pending','ready','complete','failure','unavailable') -or
        $n.phase -notin @(0,2,3,4) -or $n.executed -lt 0 -or $n.executed -gt 7 -or
        $n.action_count -ne $n.executed -or $n.failures -notin @(0,1) -or
        $n.owner_count -lt 0 -or $n.owner_count -gt 2 -or $n.row_count -lt 0 -or $n.row_count -gt 12288 -or
        $n.init_count -lt 0 -or $n.init_count -gt 4 -or $n.raw_bytes -lt 0 -or $n.raw_bytes -gt 8388608 -or
        $n.frame_count -lt 0 -or $n.frame_count -gt 2048 -or $n.queue_count -lt 0 -or $n.queue_count -gt 64 -or
        $n.delete_count -lt 0 -or $n.delete_count -gt 2 -or $n.presuper_count -lt 0 -or $n.presuper_count -gt 2 -or
        $n.after_super_count -lt 0 -or $n.after_super_count -gt 2 -or $n.checksum -lt 0 -or $n.checksum -gt 1000002) {
        Throw-Outcome 'failure' 'Invalid native UI response domain'
    }
    $successful=$n.status -cin @('pending','ready','complete')
    if ($successful -and ($n.failure -cne '' -or $n.failures -ne 0 -or $n.outside_domain)) {
        Throw-Outcome 'failure' 'Successful native UI progress contains failure or outside-domain evidence'
    }
    if ($n.outside_domain -and ($n.status -cne 'unavailable' -or $n.failure -ceq '' -or $n.failures -ne 1 -or $n.actions_ready)) {
        Throw-Outcome 'failure' 'Outside-domain evidence must retain an unavailable partial outcome'
    }
    foreach ($name in $arrays) {
        if ($name -cin $names) { $value=Required-Field $Response $name }
        elseif (($name -ceq 'rows' -and $n.row_count -eq 0) -or ($name -ceq 'caseIds' -and $n.action_count -eq 0)) {
            $value=@();$codec.omitted_empty_arrays+=$name
        } else { Throw-Outcome 'failure' 'Omitted nonempty native UI trace field' }
        if ($value -isnot [Array]) { Throw-Outcome 'failure' 'Native UI arrays must be literal array values' }
        $n[$name]=@($value)
    }
    if ($n.rows.Count -ne $n.row_count -or $n.caseIds.Count -ne $n.action_count) {
        Throw-Outcome 'failure' 'Native UI trace collection counts differ'
    }
    $caseIds=@('n1b.held','n1b.focus','n1b.focus.repeated','n1b.unfocus','n1b.reopen','n1b.stow','n3.focused.before-teardown')
    for ($index=0;$index -lt $n.caseIds.Count;$index++) {
        if ($n.caseIds[$index] -isnot [string] -or $n.caseIds[$index] -cne $caseIds[$index]) {
            Throw-Outcome 'failure' 'Native UI case prefix is unknown, duplicated or out of order'
        }
    }
    $actualChecksum=0L;$actualBytes=0L
    $counts=@{init=0;frame=0;queue=0;action=0;delete=0;presuper=0;after_super=0}
    for ($index=0;$index -lt $n.rows.Count;$index++) {
        $row=$n.rows[$index]
        if ($row -isnot [string] -or $row.Length -eq 0 -or $row.Length -gt 1024 -or $row -cmatch '[^\x20-\x7e]') {
            Throw-Outcome 'failure' 'Invalid native UI printable ASCII trace row'
        }
        $columns=@($row -split '\|')
        if ($columns.Count -lt 2 -or $columns[0] -cne ([string]($index+1))) {
            Throw-Outcome 'failure' 'Native UI sequence is not a canonical contiguous prefix'
        }
        switch -CaseSensitive ($columns[1]) {
            'queue' { if ($columns.Count -ne 10) { Throw-Outcome 'failure' 'Wrong queue column count' };$counts.queue++ }
            'after-super' { if ($columns.Count -ne 4) { Throw-Outcome 'failure' 'Wrong after-super column count' };$counts.after_super++ }
            'init' { if ($columns.Count -ne 23) { Throw-Outcome 'failure' 'Wrong init column count' };$counts.init++ }
            'frame' { if ($columns.Count -ne 23 -or $columns[5] -cnotin @('before','after')) { Throw-Outcome 'failure' 'Wrong frame columns/phase' };if ($columns[5] -ceq 'before') {$counts.frame++} }
            'action' { if ($columns.Count -ne 23 -or $columns[5] -cnotin @('before','after')) { Throw-Outcome 'failure' 'Wrong action columns/phase' };if ($columns[5] -ceq 'after') {$counts.action++} }
            'delete' { if ($columns.Count -ne 23 -or $columns[5] -cne 'entry') { Throw-Outcome 'failure' 'Wrong delete columns/phase' };$counts.delete++ }
            'service' { if ($columns.Count -ne 23) { Throw-Outcome 'failure' 'Wrong service column count' };if ($columns[4] -ceq '19' -and $columns[5] -ceq 'pre-super') {$counts.presuper++} }
            default { Throw-Outcome 'failure' 'Unknown native UI row kind' }
        }
        foreach ($character in $row.ToCharArray()) { $actualChecksum=($actualChecksum*31L+[int][char]$character)%1000003L }
        $actualChecksum=($actualChecksum*31L+10L)%1000003L
        $actualBytes+=$row.Length+1L
    }
    if ($actualChecksum -ne $n.checksum -or $actualBytes -ne $n.raw_bytes -or
        $counts.init -ne $n.init_count -or $counts.frame -ne $n.frame_count -or $counts.queue -ne $n.queue_count -or
        $counts.action -ne $n.action_count -or $counts.delete -ne $n.delete_count -or
        $counts.presuper -ne $n.presuper_count -or $counts.after_super -ne $n.after_super_count) {
        Throw-Outcome 'failure' 'Native UI raw checksum, byte count or observed counters differ'
    }
    foreach ($name in @('load_requested','load_submitted','load_entered','load_resumed','load_returned')) {
        if ($n[$name] -notin @(0,1)) { Throw-Outcome 'failure' 'Invalid native load counter' }
    }
    if ($n.load_submitted -gt $n.load_requested -or $n.load_entered -gt $n.load_requested -or
        $n.load_resumed -gt $n.load_entered -or $n.load_resumed -gt $n.load_submitted -or
        $n.load_returned -gt $n.load_resumed -or ($n.load_accepted -and $n.load_returned -ne 1)) {
        Throw-Outcome 'failure' 'Impossible native load progress'
    }
    if ($null -ne $script:lastLoadProgress) {
        foreach ($name in @('load_requested','load_submitted','load_entered','load_resumed','load_returned')) {
            if ($n[$name] -lt $script:lastLoadProgress.$name) { Throw-Outcome 'stale_input' 'Deferred load progress reset' }
        }
        if ($script:lastLoadProgress.load_accepted -and -not $n.load_accepted) { Throw-Outcome 'stale_input' 'Deferred load acceptance reset' }
    }
    if ($n.status -cin @('ready','complete') -or ($successful -and $n.phase -ge 2)) {
        if ($n.load_requested -ne 1 -or $n.load_submitted -ne 1 -or $n.load_entered -ne 1 -or $n.load_resumed -ne 1 -or
            $n.load_returned -ne 1 -or -not $n.load_accepted) { Throw-Outcome 'failure' 'Accepted native load execution missing' }
    }
    if ($successful -and $n.phase -ge 2 -and ($n.owner_count -ne 2 -or $n.init_count -ne 4 -or $n.row_count -lt 4)) {
        Throw-Outcome 'failure' 'Native UI live/captured owner and initialization witnesses incomplete'
    }
    if ($successful -and $n.actions_ready -ne ($n.action_count -eq 7 -and $n.first_progress_ready -and $n.reopen_progress_ready)) {
        Throw-Outcome 'failure' 'Native UI ready flag differs from completed actions and natural windows'
    }
    if ($n.status -ceq 'complete' -and ($n.executed -ne 7 -or $n.phase -ne 4 -or -not $n.stop_requested -or
        $n.owner_count -ne 2 -or $n.init_count -ne 4 -or $n.delete_count -ne 2 -or $n.presuper_count -ne 2 -or $n.after_super_count -ne 2 -or
        -not $n.actions_ready -or -not $n.first_progress_ready -or -not $n.reopen_progress_ready -or -not $n.final_focused -or
        -not $n.edit_mode -or $n.game_mode -or $n.in_play_mode)) {
        Throw-Outcome 'failure' 'Native UI completion lacks fresh stop and actual callback milestones'
    }
    if ($null -ne $script:lastUIProgress) {
        $previous=$script:lastUIProgress
        if ($n.rows.Count -lt $previous.rows.Count -or $n.phase -lt $previous.phase) { Throw-Outcome 'stale_input' 'Native UI scalar prefix or phase reset' }
        for ($index=0;$index -lt $previous.rows.Count;$index++) {
            if ($n.rows[$index] -cne $previous.rows[$index]) { Throw-Outcome 'stale_input' 'Native UI prior scalar row changed' }
        }
        foreach ($name in @('owner_count','init_count','action_count','frame_count','queue_count','delete_count','presuper_count','after_super_count')) {
            if ($n[$name] -lt $previous.$name) { Throw-Outcome 'stale_input' 'Native UI observed counter reset' }
        }
        foreach ($name in @('first_progress_ready','reopen_progress_ready','final_focused','stop_requested')) {
            if ($previous.$name -and -not $n[$name]) { Throw-Outcome 'stale_input' 'Native UI progress flag reset' }
        }
        if ($previous.phase -eq 4 -and ($n.row_count -ne $previous.row_count -or $n.checksum -ne $previous.checksum -or $n.raw_bytes -ne $previous.raw_bytes)) {
            Throw-Outcome 'stale_input' 'Native UI sealed completion appended or changed'
        }
    }
    $normalized=[pscustomobject]$n
    $script:lastUIProgress=$normalized
    $record.trace_checks+=[ordered]@{elapsed_ms=$clock.ElapsedMilliseconds;action=$Action;phase=$n.phase;status=$n.status;
        row_count=$n.row_count;checksum=$n.checksum;raw_bytes=$n.raw_bytes;action_count=$n.action_count;frame_count=$n.frame_count;
        queue_count=$n.queue_count;delete_count=$n.delete_count;presuper_count=$n.presuper_count;after_super_count=$n.after_super_count;
        prefix='retained_exact';semantic_oracle='not_run';numeric_equality='not_claimed'}
    return [pscustomobject]@{response=$normalized;codec=[pscustomobject]$codec}
}
function Assert-World([object] $Response) {
    if (-not $Response.module_present -or -not $Response.api_present -or -not $Response.addon_world_resolved -or
        -not $Response.world_path_resolved -or -not $Response.resource_name_resolved -or -not $Response.world_matches -or
        -not $Response.world_present -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.addon_world_path),(Normal-Path $record.expected_world)) -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.world_absolute_path),(Normal-Path $record.expected_world)) -or
        -not [StringComparer]::OrdinalIgnoreCase.Equals((Normal-Path $Response.resource_absolute_path),(Normal-Path $record.expected_world)) -or
        $Response.resource_name -cne '{BE71572A20261010}worlds/BerylTabletUINative.ent' -or
        $Response.resource_path -cne 'worlds/BerylTabletUINative.ent') { Throw-Outcome 'stale_input' 'Native owned world identity differs' }
}
function Stage-Ready([object] $Response,[string] $Action) {
    switch -CaseSensitive ($Action) {
        'load' { if ($Response.status -cne 'ready' -or -not $Response.edit_mode -or $Response.game_mode -or $Response.in_play_mode -or $Response.phase -ne 0) {return $false};Assert-World $Response;return $true }
        'play' { if ($Response.status -cne 'ready' -or $Response.edit_mode -or -not $Response.game_mode -or -not $Response.in_play_mode -or -not $Response.game_world_present -or $Response.phase -ne 0) {return $false};Assert-World $Response;return $true }
        'spawn' { if ($Response.phase -ne 2 -or $Response.status -cne 'pending' -or $Response.owner_count -ne 2 -or $Response.init_count -ne 4 -or $Response.executed -ne 0) {return $false};Assert-World $Response;if ($Response.edit_mode -or -not $Response.game_mode -or -not $Response.in_play_mode -or -not $Response.game_world_present) {Throw-Outcome 'failure' 'Native spawn observed outside play'};return $true }
        'stop' { if ($Response.status -cne 'complete' -or $Response.phase -ne 4) {return $false};Assert-World $Response;return $true }
        default {
            if ($Action -cnotmatch '^run[0-6]$') { Throw-Outcome 'failure' 'Unregistered native UI stage' }
            $expectedCount=[int]::Parse($Action.Substring(3))+1
            if ($Response.phase -ne 2 -or $Response.status -cne 'pending' -or $Response.action_count -ne $expectedCount -or $Response.executed -ne $expectedCount) {return $false}
            Assert-World $Response
            if ($Response.edit_mode -or -not $Response.game_mode -or -not $Response.in_play_mode -or -not $Response.game_world_present) {Throw-Outcome 'failure' 'Native UI action observed outside play'}
            if ($Action -ceq 'run6' -and (-not $Response.actions_ready -or -not $Response.final_focused)) { Throw-Outcome 'failure' 'Final native UI action did not retain focused readiness' }
            return $true
        }
    }
}
function Run-Stage([string] $Action) {
    $record.stage=$Action;$script:stageClock=[Diagnostics.Stopwatch]::StartNew()
    $item=[ordered]@{action=$Action;status='pending';polls=0;response=$null;elapsed_ms=0;mutation_requests=1};$record.stages+=$item
    try {
        # Exactly one request may mutate this stage. Every follow-up is status.
        $response=Invoke-Probe $Action;$item.response=$response
        while (-not (Stage-Ready $response $Action)) {
            if ($item.polls -ge 64) { Throw-Outcome 'timeout' 'Native UI stage exhausted its poll count' }
            Assert-Deadline
            $delay=$(if ($Action -cin @('spawn','stop') -or $Action -cmatch '^run[0-6]$'){1}else{100})
            Start-Sleep -Milliseconds $delay
            Assert-Deadline;$item.polls++
            $response=Invoke-Probe 'status';$item.response=$response
        }
        Assert-Deadline;$item.status='completed';$item.elapsed_ms=$stageClock.ElapsedMilliseconds
        return ,$response
    } catch { $item.status=$record.status;$item.elapsed_ms=$stageClock.ElapsedMilliseconds;throw }
}
function Wait-NaturalProgress([string] $Window) {
    if ($Window -cnotin @('first','reopen')) { Throw-Outcome 'failure' 'Unknown native UI natural-progress window' }
    $expectedCount=$(if ($Window -ceq 'first'){2}else{5})
    $readyField=$(if ($Window -ceq 'first'){'first_progress_ready'}else{'reopen_progress_ready'})
    if ($null -eq $script:lastUIProgress -or $script:lastUIProgress.action_count -ne $expectedCount -or
        $script:lastUIProgress.phase -ne 2 -or $script:lastUIProgress.status -cne 'pending') {
        Throw-Outcome 'failure' 'Natural progress wait did not start after its completed native action'
    }
    $record.stage='natural.'+$Window;$script:stageClock=[Diagnostics.Stopwatch]::StartNew()
    $waitBeginMs=$clock.ElapsedMilliseconds
    $waitClock=[Diagnostics.Stopwatch]::StartNew()
    $item=[ordered]@{window=$Window;after_action=($expectedCount-1);required_minimum_wall_ms=600;status='pending';
        begin_total_ms=$waitBeginMs;end_wait_total_ms=$null;wait_elapsed_ms=$null;
        clock_source='Stopwatch';stopwatch_frequency=[Diagnostics.Stopwatch]::Frequency;wait_begin_ticks=0L;wait_end_ticks=$null;
        ready_total_ms=$null;elapsed_ms=0;polls=0;response=$null;mutation_requests=0}
    $record.natural_progress_windows+=$item
    try {
        # Observe naturally delivered callbacks; never call, tick or advance them.
        while ($waitClock.ElapsedMilliseconds -lt 600) {
            Assert-Deadline
            $remaining=600L-$waitClock.ElapsedMilliseconds
            Start-Sleep -Milliseconds ([int][Math]::Max(1,[Math]::Min(20,$remaining)))
            Assert-Deadline
        }
        $item.end_wait_total_ms=$clock.ElapsedMilliseconds
        $item.wait_elapsed_ms=$waitClock.ElapsedMilliseconds
        $item.wait_end_ticks=$waitClock.ElapsedTicks
        if ($item.wait_elapsed_ms -lt 600 -or $item.end_wait_total_ms-$item.begin_total_ms -lt 600) { Throw-Outcome 'failure' 'Natural progress wall wait was incomplete' }
        while ($true) {
            if ($item.polls -ge 64) { Throw-Outcome 'timeout' 'Native UI natural progress exhausted its poll count' }
            Assert-Deadline;$item.polls++
            $response=Invoke-Probe 'status';$item.response=$response
            Assert-World $response
            if ($response.phase -ne 2 -or $response.status -cne 'pending' -or $response.action_count -ne $expectedCount -or
                $response.edit_mode -or -not $response.game_mode -or -not $response.in_play_mode -or -not $response.game_world_present) {
                Throw-Outcome 'failure' 'Native UI natural progress lost its owned focused window'
            }
            if ($response.$readyField) { break }
            Start-Sleep -Milliseconds 100
            Assert-Deadline
        }
        $item.ready_total_ms=$clock.ElapsedMilliseconds;$item.elapsed_ms=$stageClock.ElapsedMilliseconds;$item.status='completed'
        return ,$response
    } catch {
        if ($null -eq $item.end_wait_total_ms) {$item.end_wait_total_ms=$clock.ElapsedMilliseconds;$item.wait_elapsed_ms=$waitClock.ElapsedMilliseconds}
        if ($null -eq $item.wait_end_ticks) {$item.wait_end_ticks=$waitClock.ElapsedTicks}
        $item.elapsed_ms=$stageClock.ElapsedMilliseconds;$item.status=$record.status;throw
    }
}
function Invoke-Probe([string] $Action) {
    $reply=Invoke-Call 'BerylTabletUINative' @{token=$Token;action=$Action}
    $normalized=$record.rpcs[$record.rpcs.Count-1].normalized_response
    $script:lastLoadProgress=$normalized
    if ($normalized.status -ceq 'failure') { Throw-Outcome 'failure' ('Engine native fixture failed: '+$normalized.failure) }
    if ($normalized.status -ceq 'unavailable') { Throw-Outcome 'unavailable' ('Engine native fixture unavailable: '+$normalized.failure) }
    return ,$normalized
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
        try { $reply=& $pluginPaths['Invoke-WorkbenchRpc.ps1'] -Function $Function -Parameters $Parameters -ClientId BerylTabletUINativeVerifier -TimeoutMs $limit }
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
        if ($Function -ceq 'BerylTabletUINative') { $checked=Check-Native $reply.Response $Parameters.action;$entry.normalized_response=$checked.response;$entry['codec']=$checked.codec }
        Assert-Deadline
        if ($callClock.ElapsedMilliseconds -ge $limit) { Throw-Outcome 'timeout' 'Whole suite RPC/evidence operation exceeded its admitted budget' }
        return ,$reply
    } catch {
        if ($null -eq $entry.failure) { $entry.failure=$_.Exception.Message }
        throw
    } finally { $entry.duration_ms=$callClock.ElapsedMilliseconds }
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
        Throw-Outcome 'timeout' 'Monotonic native-tablet deadline expired'
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
    return @('-gproj',(Join-Path $OwnedProject 'addon.gproj'),'-noOpenLastResource','-scriptAuthorizeAll','-forceUpdate')
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

function Lease-HandleHash([object] $Stream,[object] $ExpectedBytes) {
    if (($ExpectedBytes -isnot [int] -and $ExpectedBytes -isnot [long]) -or $ExpectedBytes -lt 0 -or $ExpectedBytes -gt 128MB -or
        $Stream -isnot [IO.Stream] -or -not $Stream.CanRead -or -not $Stream.CanSeek -or $Stream.Length -ne $ExpectedBytes) {
        Throw-Outcome 'stale_input' 'Lease stream or exact length is unavailable'
    }
    $Stream.Position=0
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        $value=[BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','').ToLowerInvariant()
        if (-not $Stream.CanRead -or $Stream.Length -ne $ExpectedBytes -or $Stream.Position -ne $ExpectedBytes) {
            Throw-Outcome 'stale_input' 'Lease byte observation was incomplete or changed'
        }
        $Stream.Position=0
        return $value
    } finally { $sha.Dispose() }
}
function Read-LeaseBasis {
    $basis=[Collections.Generic.List[object]]::new()
    foreach ($name in $manifest.files.Keys) {
        $path=[IO.Path]::GetFullPath((Join-Path $canonicalProject $name))
        $basis.Add([pscustomobject]@{path=$path;sha256=$manifest.files[$name];kind='addon'})
    }
    $basis.Add([pscustomobject]@{path=[IO.Path]::GetFullPath($adapterPath);sha256=$adapterHash;kind='adapter'})
    $basis.Add([pscustomobject]@{path=[IO.Path]::GetFullPath($InputManifest);sha256=$manifestHash;kind='manifest'})
    foreach ($name in $pluginPaths.Keys) {
        $basis.Add([pscustomobject]@{path=[IO.Path]::GetFullPath($pluginPaths[$name]);sha256=$pluginHashes[$name];kind='plugin'})
    }
    $basis.Add([pscustomobject]@{path=[IO.Path]::GetFullPath($record.engine_path);sha256=$ExpectedEngineHash;kind='engine'})
    if ($manifest.files.Count -ne 99 -or $pluginPaths.Count -ne 2 -or $basis.Count -ne 104) {
        Throw-Outcome 'failure' 'Exact 104-file lease basis unavailable'
    }
    return ,@($basis.ToArray() | Sort-Object -Property path -CaseSensitive)
}
function Open-ReadLease([object] $Basis) {
    if ($script:nativeLeaseHandles.Count -ne 0 -or $script:nativeLeaseComplete -or $script:nativeLeaseFast -or
        $Basis -isnot [Array] -or $Basis.Count -ne 104) { Throw-Outcome 'failure' 'Lease requires exactly one fresh 104-file acquisition' }
    $record.read_lease.status='opening';$record.read_lease.acquisition_status='attempted';$record.read_lease.open_started_ms=$clock.ElapsedMilliseconds
    $timer=[Diagnostics.Stopwatch]::StartNew()
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    try {
    # Validate the whole basis before opening its first file.
    foreach ($item in $Basis) {
        Assert-Names $item @('path','sha256','kind')
        if ($null -eq $item -or $item.path -isnot [string] -or -not [IO.Path]::IsPathFullyQualified($item.path) -or
            $item.sha256 -isnot [string] -or $item.sha256 -cnotmatch '^[0-9a-f]{64}$' -or
            $item.kind -isnot [string] -or $item.kind -cnotin @('addon','adapter','manifest','plugin','engine') -or
            -not $seen.Add([IO.Path]::GetFullPath($item.path))) {
            Throw-Outcome 'failure' 'Invalid or duplicate canonical lease basis path'
        }
    }
        if (@($Basis | Where-Object {$_.kind -ceq 'addon'}).Count -ne 99 -or
            @($Basis | Where-Object {$_.kind -ceq 'adapter'}).Count -ne 1 -or
            @($Basis | Where-Object {$_.kind -ceq 'manifest'}).Count -ne 1 -or
            @($Basis | Where-Object {$_.kind -ceq 'plugin'}).Count -ne 2 -or
            @($Basis | Where-Object {$_.kind -ceq 'engine'}).Count -ne 1) {
            Throw-Outcome 'failure' 'Lease categories must cover all 104 pinned inputs'
        }
        foreach ($item in $Basis) {
            Assert-Deadline
            $path=[IO.Path]::GetFullPath($item.path)
            $attributes=[IO.File]::GetAttributes($path)
            if (($attributes -band [IO.FileAttributes]::Directory) -or ($attributes -band [IO.FileAttributes]::ReparsePoint)) {
                Throw-Outcome 'stale_input' 'Lease input must be a direct regular file'
            }
            $stream=$null
            try { $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read) }
            catch { Throw-Outcome 'unavailable' ('Read lease unavailable: '+$path+': '+$_.Exception.Message) }
            # Retain every returned handle before any query/hash can fail.
            $entry=[ordered]@{path=$path;kind=$item.kind;expected_sha256=$item.sha256;sha256=$null;bytes=$null;status='opened';release_status='pending'}
            $owned=[pscustomobject]@{stream=$stream;entry=$entry;released=$false;release_attempted=$false}
            $script:nativeLeaseHandles.Add($owned)
            $record.read_lease.entries+= $entry
            $record.read_lease.opened_count=$script:nativeLeaseHandles.Count
            $length=$stream.Length
            $byteLimit=$(if ($item.kind -ceq 'engine') {128MB} else {64MB})
            if ($length -lt 0 -or $length -gt $byteLimit) { Throw-Outcome 'stale_input' 'Leased file exceeds bounded hash domain' }
            $entry.bytes=$length
            $observed=Lease-HandleHash $stream $length
            $entry.sha256=$observed
            if ($observed -cne $item.sha256) { Throw-Outcome 'stale_input' 'Held lease bytes differ from frozen source identity' }
            $after=[IO.File]::GetAttributes($path)
            if (($after -band [IO.FileAttributes]::Directory) -or ($after -band [IO.FileAttributes]::ReparsePoint)) {
                Throw-Outcome 'stale_input' 'Leased source path became nonregular'
            }
            $entry.status='verified_held'
        }
        $script:nativeLeaseComplete=$true
        $record.read_lease.status='held';$record.read_lease.acquisition_status='complete';$record.read_lease.open_completed_ms=$clock.ElapsedMilliseconds
        $record.read_lease.open_duration_ms=$timer.ElapsedMilliseconds
        Assert-HeldReadLease
    } catch {
        $record.read_lease.status='acquisition_failed';$record.read_lease.acquisition_status='failed';$record.read_lease.open_duration_ms=$timer.ElapsedMilliseconds
        throw
    }
}
function Assert-HeldReadLease {
    if (-not $script:nativeLeaseComplete -or $script:nativeLeaseHandles.Count -ne 104 -or $record.read_lease.opened_count -ne 104) {
        Throw-Outcome 'unavailable' 'Complete read lease is not held; no fallback is permitted'
    }
    foreach ($owned in $script:nativeLeaseHandles) {
        if ($owned.released -or $owned.entry.status -cne 'verified_held' -or $owned.entry.sha256 -cne $owned.entry.expected_sha256 -or
            -not $owned.stream.CanRead -or $owned.stream.Length -ne $owned.entry.bytes) {
            Throw-Outcome 'stale_input' 'Held lease readability/length/verified identity changed'
        }
    }
}
function Fast-NamespaceSnapshot {
    $attributes=[IO.File]::GetAttributes($canonicalProject)
    if (-not ($attributes -band [IO.FileAttributes]::Directory) -or ($attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Throw-Outcome 'stale_input' 'Leased addon root must remain a direct directory'
    }
    $queue=[Collections.Generic.Queue[string]]::new();$queue.Enqueue($canonicalProject)
    $files=@{};$directories=[Collections.Generic.List[string]]::new();$outputs=@();$total=0L
    while ($queue.Count) {
        $directory=$queue.Dequeue()
        foreach ($full in [IO.Directory]::EnumerateFileSystemEntries($directory)) {
            $attributes=[IO.File]::GetAttributes($full)
            if ($attributes -band [IO.FileAttributes]::ReparsePoint) { Throw-Outcome 'stale_input' 'Linked namespace entry during lease window' }
            $name=Relative-Name $full
            if ($attributes -band [IO.FileAttributes]::Directory) {
                if ($directories.Count -ge 256) { Throw-Outcome 'failure' 'Leased directory bound exceeded' }
                $directories.Add($name);$queue.Enqueue($full)
            } else {
                $length=([IO.FileInfo]::new($full)).Length
                if ($name -ceq 'resourceDatabase.rdb' -and -not $manifest.files.Contains($name)) {
                    if ($length -gt 8MB) { Throw-Outcome 'stale_input' 'Derived root resource database exceeded 8 MiB' }
                    $outputs+= [ordered]@{path=$full;relative=$name;bytes=$length;sha256=$null;observation='namespace_size_only; final full guard supplies hash'}
                    continue
                }
                if ($files.Count -ge 256 -or $length -gt 64MB) { Throw-Outcome 'failure' 'Leased namespace file bound exceeded' }
                $total+=$length
                if ($total -gt 256MB -or $files.ContainsKey($name)) { Throw-Outcome 'failure' 'Leased namespace aggregate or duplicate identity exceeded' }
                $files[$name]=$length
            }
        }
    }
    return [pscustomobject]@{files=$files;directories=@($directories.ToArray() | Sort-Object -CaseSensitive);outputs=$outputs}
}
function Assert-FastInputs {
    Assert-Deadline
    $timer=[Diagnostics.Stopwatch]::StartNew()
    Assert-HeldReadLease
    $tree=Fast-NamespaceSnapshot
    if ($tree.files.Count -ne 99 -or @($tree.files.Keys | Where-Object {-not $manifest.files.Contains($_)}).Count -or
        @($manifest.files.Keys | Where-Object {-not $tree.files.ContainsKey($_)}).Count -or
        ($tree.directories -join "`n") -cne (@($expectedDirectories) -join "`n")) {
        Throw-Outcome 'stale_input' 'Leased addon namespace differs from all pinned inputs/directories'
    }
    foreach ($owned in $script:nativeLeaseHandles) {
        if ($owned.entry.kind -ceq 'addon') {
            $name=Relative-Name $owned.entry.path
            if (-not $tree.files.ContainsKey($name) -or $tree.files[$name] -ne $owned.entry.bytes) {
                Throw-Outcome 'stale_input' 'Leased pathname length differs from its held addon stream'
            }
        }
    }
    if ($record.read_lease.fast_check_count -ge 512) { Throw-Outcome 'failure' 'Lease evidence check bound exhausted' }
    $record.engine_outputs=@($tree.outputs)
    $record.read_lease.fast_checks+= [ordered]@{elapsed_ms=$clock.ElapsedMilliseconds;duration_ms=$timer.ElapsedMilliseconds;
        held_count=104;file_count=$tree.files.Count;directory_count=$tree.directories.Count;bytehash='not_reexecuted; read-sharing leases held'}
    $record.read_lease.fast_check_count=$record.read_lease.fast_checks.Count
}
function Close-ReadLease {
    $script:nativeLeaseFast=$false
    if ($script:nativeLeaseHandles.Count -eq 0) { return $true }
    if (@($script:nativeLeaseHandles | Where-Object {-not $_.released}).Count -eq 0) { return $true }
    $record.read_lease.close_started_ms=$clock.ElapsedMilliseconds
    $record.read_lease.release_status='attempted'
    $timer=[Diagnostics.Stopwatch]::StartNew();$complete=$true
    foreach ($owned in $script:nativeLeaseHandles) {
        if ($owned.released) { continue }
        if ($owned.release_attempted) { $complete=$false;continue }
        try {
            $owned.release_attempted=$true
            $owned.stream.Dispose()
            if ($owned.stream.CanRead) { throw 'Disposed lease remained readable' }
            $owned.released=$true;$owned.entry.release_status='released'
            $record.read_lease.released_count++
        } catch {
            $complete=$false;$owned.entry.release_status='failure'
            $record.read_lease.errors+= [ordered]@{stage='release';path=$owned.entry.path;message=$_.Exception.Message}
        }
    }
    $script:nativeLeaseComplete=$false
    $record.read_lease.close_duration_ms=$timer.ElapsedMilliseconds
    if ($complete) {
        $record.read_lease.close_completed_ms=$clock.ElapsedMilliseconds
        $record.read_lease.status='released';$record.read_lease.release_status='complete'
    } else { $record.read_lease.status='release_failed';$record.read_lease.release_status='failed' }
    return $complete
}

function Assert-Inputs {
    if ($script:nativeLeaseFast) { Assert-FastInputs;return }
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
function Read-StartupIdentity([object] $Process,[int] $Attempt) {
    Assert-Deadline
    $row=[ordered]@{attempt=$Attempt;elapsed_ms=$clock.ElapsedMilliseconds;process_id=$null;start_ticks=$null;start_ticks_unit='dotnet_datetime_0001_utc_100ns';
        module_present=$false;raw_path=$null;normalized_path=$null;status='querying';query_error=$null}
    $record.startup.identity_checks+= $row
    try {
        $null=$Process.Refresh()
        # Invoke native getters directly so PowerShell's extended property
        # adapter cannot suppress a getter exception into a null observation.
        $id=$Process.get_Id()
        $row.process_id=$id
        if (($id -isnot [int] -and $id -isnot [long]) -or $id -le 0) { throw 'Process identity query did not expose a positive PID' }
        $start=$Process.get_StartTime()
        if ($start -isnot [DateTime]) { throw 'Process start time query did not expose DateTime' }
        $ticks=$start.ToUniversalTime().Ticks
        $row.start_ticks=$ticks
        # Retain actual queried start identity before evaluating the image path.
        if ($null -eq $script:ownedStartTicks) {
            $script:ownedStartTicks=$ticks
            $record.startup.identity_start_ticks=$ticks
            $record.startup.identity_start_ticks_unit='dotnet_datetime_0001_utc_100ns'
            $record.startup.identity_start_time=$start.ToUniversalTime().ToString('o')
        }
        $exited=$Process.WaitForExit(0)
        if ($exited -isnot [bool]) { throw 'Process exit query did not expose Boolean' }
        if ($exited) {
            $row.status='exited';$record.startup.identity_status='unavailable'
            Throw-Outcome 'unavailable' 'Owned process exit confirmed before startup image identity'
        }
        $module=$Process.get_MainModule()
        $row.module_present=($null -ne $module)
        $raw=$null
        if ($null -ne $module) { $raw=$module.get_FileName() }
        $row.raw_path=$raw
        if ($null -ne $raw -and $raw -isnot [string]) { throw 'Process image query did not expose a string or null' }
        if ($null -ne $raw -and $raw.Length -gt 32768) { throw 'Process image query exceeded its bounded path domain' }
        if ($null -ne $raw -and $raw.Length -gt 0) { $row.normalized_path=Normal-Path $raw }
    } catch {
        if ($_.Exception -is [InvalidOperationException] -and $row.status -ceq 'exited') { throw }
        $queryError=$_.Exception
        $row.status='query_error';$row.query_error=[ordered]@{type=$queryError.GetType().FullName;hresult=$queryError.HResult;
            message=$queryError.Message.Substring(0,[Math]::Min(2048,$queryError.Message.Length))}
        $record.startup.identity_status='unavailable'
        Throw-Outcome 'unavailable' ('Owned startup identity query failed: '+$row.query_error.type+': '+$row.query_error.message)
    }
    # Each actual observation is retained before its identity comparison.
    if ($row.process_id -ne $ownedPid -or $row.start_ticks -ne $ownedStartTicks) {
        $row.status='identity_changed';$record.startup.identity_status='stale_input'
        Throw-Outcome 'stale_input' 'Owned startup process PID/start identity changed'
    }
    if ($null -eq $row.raw_path -or $row.raw_path.Length -eq 0) {
        $row.status='pending';$record.startup.identity_status='pending'
        return ,$row
    }
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($row.normalized_path,(Normal-Path $record.engine_path))) {
        $row.status='foreign_image';$record.startup.identity_status='stale_input'
        Throw-Outcome 'stale_input' 'Started engine path differs from the pinned executable'
    }
    $row.status='verified';$record.startup.identity_status='verified'
    return ,$row
}
function Wait-StartupIdentity([object] $Process) {
    $record.startup.identity_status='pending';$record.startup.identity_polls=0
    $record.startup.identity_started_ms=$clock.ElapsedMilliseconds
    for ($attempt=0;$attempt -lt 64;$attempt++) {
        Assert-Deadline
        $record.startup.identity_polls=$attempt
        $row=Read-StartupIdentity $Process $attempt
        Assert-Deadline
        if ($row.status -ceq 'verified') {
            $record.startup.identity_completed_ms=$clock.ElapsedMilliseconds
            $record.startup.identity_duration_ms=$record.startup.identity_completed_ms-$record.startup.identity_started_ms
            return ,$row
        }
        if ($attempt -eq 63) {
            $record.startup.identity_status='timeout'
            Throw-Outcome 'timeout' 'Owned startup image identity exhausted64 observations'
        }
        Start-Sleep -Milliseconds 20
        Assert-Deadline
    }
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
        $ProjectId -cne 'BerylTabletUINativeN1bPrototype' -or $ExpectedContractHash -cnotmatch '^[0-9a-f]{64}$') { Throw-Outcome 'failure' 'Invalid pinned suite identity' }
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
        $manifest.files -isnot [Collections.IDictionary] -or $manifest.files.Count -ne 99) {
        Throw-Outcome 'failure' 'Only the typed frozen 99-input native-tablet profile is permitted'
    }
    foreach ($required in @('addon.gproj','scripts/WorkbenchGameCommon/BerylTabletUINative.c','scripts/Game/BerylTabletUINativeObserver.c','worlds/BerylTabletUINative.ent','worlds/BerylTabletUINative_Layers/default.layer','Prefabs/BerylTabletUINative.et',
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
    $record.expected_world=[IO.Path]::GetFullPath((Join-Path $canonicalProject 'worlds/BerylTabletUINative.ent'))
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
        use_shell_execute=$false;create_no_window=$true;window_style='Hidden';launch_returned=$false;polls=0;
        identity_checks=@();identity_status='not_requested';identity_polls=0;identity_start_ticks=$null;identity_start_ticks_unit='dotnet_datetime_0001_utc_100ns';identity_start_time=$null;
        identity_started_ms=$null;identity_completed_ms=$null;identity_duration_ms=$null}
    $ownedProcess=[Diagnostics.Process]::new()
    $ownedProcess.StartInfo=$info
    if (-not $ownedProcess.Start()) { $ownedProcess=$null;Throw-Outcome 'unavailable' 'Owned engine launch did not return a process' }
    # Retain the actual Process instance and PID before any other query or wait.
    $ownedPid=$ownedProcess.Id
    $record.startup.launch_returned=$true
    $record.startup.process_id=$ownedPid
    $startupIdentity=Wait-StartupIdentity $ownedProcess
    $ownedExecutable=$startupIdentity.normalized_path
    $record.session=[ordered]@{process_id=$ownedPid;start_ticks=$ownedStartTicks;executable=$ownedExecutable;
        project=$canonicalProject;reused=$false;start_time=$record.startup.identity_start_time}
    Assert-OwnedSession 'startup.identity'
    Wait-Listener

    $record.loaded_projects=Invoke-Call 'GetLoadedProjects' @{}
    Assert-LoadedProjects $record.loaded_projects.Response
    $null=Run-Stage 'load'
    $null=Run-Stage 'play'
    Open-ReadLease (Read-LeaseBasis)
    # The full original byte/tree/engine guard runs once with all 104 handles held.
    Assert-Inputs;Assert-HeldReadLease
    $record.read_lease.full_checks_with_handles++
    $script:nativeLeaseFast=$true
    $null=Run-Stage 'spawn'
    $null=Run-Stage 'run0'
    $null=Run-Stage 'run1'
    $null=Wait-NaturalProgress 'first'
    $null=Run-Stage 'run2'
    $null=Run-Stage 'run3'
    $null=Run-Stage 'run4'
    $null=Wait-NaturalProgress 'reopen'
    $null=Run-Stage 'run5'
    $finalLive=Run-Stage 'run6'
    if ($finalLive.action_count -ne 7 -or -not $finalLive.actions_ready -or -not $finalLive.first_progress_ready -or
        -not $finalLive.reopen_progress_ready -or -not $finalLive.final_focused -or $finalLive.delete_count -ne 0 -or
        $finalLive.presuper_count -ne 0 -or $finalLive.after_super_count -ne 0) {
        Throw-Outcome 'failure' 'Native UI stop cannot begin without complete natural windows and the actual focused pre-deletion receipt'
    }
    $record.completion=Run-Stage 'stop'
    $script:nativeLeaseFast=$false
    if (-not (Close-ReadLease)) { Throw-Outcome 'unavailable' 'Leased sources could not all be released; result cannot succeed' }
    Assert-Deadline;Assert-Inputs
    $record.read_lease.post_release_full_check=$true
    $record.status='success';$record.stage='native_ui_transport_complete'
} catch {
    $record.failure=$_.Exception.Message
    if ($_.Exception -is [Management.Automation.PipelineStoppedException]) { $record.status='cancelled' }
} finally {
    # Release every acquired source handle before owned-process cleanup, retaining
    # the original primary failure independently of secondary release evidence.
    try {
        if (-not (Close-ReadLease)) { Record-CleanupError 'read_lease_release' 'Not all acquired read leases were released' }
    } catch { Record-CleanupError 'read_lease_release' $_.Exception.Message }
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
                    $retainedDir=Join-Path ([IO.Path]::GetDirectoryName($resultFullPath)) ('tablet-native-logs/'+$directory.Name)
                    $null=[IO.Directory]::CreateDirectory($retainedDir)
                    $retained=Join-Path $retainedDir $log.Name
                    [IO.File]::Copy($log.FullName,$retained,$false)
                    if ((Content-Hash $retained) -cne $before -or (Content-Hash $log.FullName) -cne $before) { throw 'Raw log changed during capture' }
                    $record.raw_logs+= [ordered]@{original=$log.FullName;retained=$retained;sha256=$before;bytes=$log.Length}
                }
            }
        }
        if ($record.stage -ceq 'native_ui_transport_complete' -and -not $record.raw_logs.Count) { throw 'Owned session raw logs unavailable' }
    } catch { $record.evidence_errors+= [ordered]@{stage='raw_session_logs';message=$_.Exception.Message} }
    $beforeFinalStatus=$record.status
    try { if ($null -ne $manifest -and $null -ne $record.engine_path) { Assert-Inputs } }
    catch {
        $record.evidence_errors+= [ordered]@{stage='final_input_identity';message=$_.Exception.Message}
        if ($null -eq $record.failure) {$record.failure=$_.Exception.Message}
        if ($beforeFinalStatus -eq 'success' -or ($beforeFinalStatus -eq 'unavailable' -and $record.stage -ceq 'native_ui_transport_complete')) {$record.status='stale_input'}
        else {$record.status=$beforeFinalStatus}
    }
    try { if ($acquired) {$mutex.ReleaseMutex()};if ($null -ne $mutex) {$mutex.Dispose()} }
    catch { Record-CleanupError 'session_gate_cleanup' $_.Exception.Message }
    if ($record.status -eq 'success' -and $record.evidence_errors.Count) { $record.status='unavailable';$record.failure='Cleanup or raw evidence incomplete' }
    if (($record.status -eq 'success' -or ($record.status -eq 'unavailable' -and $record.stage -ceq 'native_ui_transport_complete')) -and $clock.ElapsedMilliseconds -ge 180000) {
        $record.status='timeout';$record.failure='Overall deadline expired during evidence capture'
    }
    $record.elapsed_ms=$clock.ElapsedMilliseconds
    $record.raw_log_observation=$(if($record.cleanup -cin @('owned_process_stopped','owned_process_already_exited')){'snapshot_after_confirmed_owned_exit'}else{'point_in_time_exit_unconfirmed'})
    if ($resultCanWrite) {
        $written=Write-BerylBundledReceipt $record $resultFullPath
        $record=$written.record
    }
}
if ($record.status -ne 'success') { Write-Error $record.failure;exit 1 }
