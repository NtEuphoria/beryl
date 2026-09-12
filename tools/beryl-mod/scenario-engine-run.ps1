# Trusted scenario transport; owns its session and preserves raw engine output.
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
    [ValidateRange(60000, 240000)][int] $RpcTimeoutMs = 60000
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owned = $null
$mutex = $null
$acquired = $false
$record = [ordered]@{schema_version=1;stage='scenario_engine_execution';status='failure';loaded_projects=$null;rpc=$null;session=$null;engine_sha256=$null;engine_version=$null;failure=$null}
function Get-ContentHash([string] $Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
try {
    $mutex = [Threading.Mutex]::new($false, 'Local\BerylOwnedWorkbenchSessionV1')
    try { $acquired = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $acquired = $true }
    if (-not $acquired) { $record.status = 'unavailable'; throw 'Another Beryl job owns the Workbench session gate.' }
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue).Count) {
        $record.status = 'unavailable'
        throw 'Another Workbench session is running; it will not be reused or stopped.'
    }
    $paths = & (Join-Path $ToolRoot 'scripts/Find-Workbench.ps1')
    if (-not $paths.WorkbenchExe) { throw 'Workbench executable unavailable' }
    $record.engine_sha256 = Get-ContentHash $paths.WorkbenchExe
    $record.engine_version = (Get-Item -LiteralPath $paths.WorkbenchExe).VersionInfo.FileVersion
    if ($record.engine_sha256 -ne $ExpectedEngineHash -or $record.engine_version -ne $ExpectedEngineVersion) {
        $record.status = 'stale_input'
        throw 'Engine changed between compilation and execution'
    }
    $start = & (Join-Path $ToolRoot 'scripts/Start-WorkbenchDaemon.ps1') -ProjectDir $ProjectDir
    if (-not $start.Ok -or $start.Reused) { throw 'No exclusively owned Workbench session was started' }
    $owned = Get-Process -Id $start.ProcessId
    $startedAt = $owned.StartTime
    $record.session = @{process_id=$owned.Id;start_time=$startedAt.ToUniversalTime().ToString('o');project=$ProjectDir;reused=$false}
    $rpcScript = Join-Path $ToolRoot 'scripts/Invoke-WorkbenchRpc.ps1'
    $projects = & $rpcScript -Function GetLoadedProjects -ClientId BerylScenarioVerifier
    $record.loaded_projects = $projects
    if (-not $projects.Ok -or @($projects.Response.'Loaded Projects') -notcontains $ProjectId) { throw 'Scenario project identity lookup failed' }
    $reply = & $rpcScript -Function $Function -Parameters @{token=$Token} -ClientId BerylScenarioVerifier -TimeoutMs $RpcTimeoutMs
    $record.rpc = $reply
    if (-not $reply.Ok -or -not $reply.Response) { throw 'No engine scenario response' }
    if ($reply.Response.token -ne $Token -or $reply.Response.executed -ne 1) { throw 'Stale or incomplete engine scenario response' }
    if ((Get-ContentHash $paths.WorkbenchExe) -ne $ExpectedEngineHash) { throw 'Engine changed during execution' }
    # Typed scenario semantics, complete selections and checksums are checked by
    # the Python consumer. Transport success alone is never a scenario receipt.
    $record.status = 'success'
} catch {
    $record.failure = $_.Exception.Message
} finally {
    if ($owned) {
        $current = Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
        if ($current -and $current.StartTime -eq $startedAt) { Stop-Process -Id $owned.Id -Force }
    }
    if ($acquired) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
    $record | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResultPath -Encoding utf8
}
if ($record.status -ne 'success') { Write-Error $record.failure; exit 1 }
