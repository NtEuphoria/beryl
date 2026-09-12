# Own one hidden Workbench instance for this exact staged comparison addon.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $Token,
    [Parameter(Mandatory)][int] $ExpectedOperations
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owned = $null
$record = [ordered]@{schema_version=1;stage='engine_pid_comparison';status='failure';loaded_projects=$null;rpc=$null;session=$null;failure=$null}
try {
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue).Count) {
        throw 'Another Workbench session is running; it will not be reused or stopped.'
    }
    $start = & (Join-Path $ToolRoot 'scripts/Start-WorkbenchDaemon.ps1') -ProjectDir $ProjectDir
    if (-not $start.Ok -or $start.Reused) { throw 'No exclusively owned Workbench session was started' }
    $owned = Get-Process -Id $start.ProcessId
    $startedAt = $owned.StartTime
    $record.session = @{process_id=$owned.Id;start_time=$startedAt.ToUniversalTime().ToString('o');project=$ProjectDir;reused=$false}
    $rpcScript = Join-Path $ToolRoot 'scripts/Invoke-WorkbenchRpc.ps1'
    $projects = & $rpcScript -Function GetLoadedProjects -ClientId BerylPidVerifier
    $record.loaded_projects = $projects
    if (-not $projects.Ok) { throw 'Loaded project identity lookup failed' }
    if (@($projects.Response.'Loaded Projects') -notcontains 'BerylPidComparison') { throw 'The comparison project is not loaded' }
    $reply = & $rpcScript -Function BerylPidComparison -Parameters @{token=$Token} -ClientId BerylPidVerifier -TimeoutMs 60000
    $record.rpc = $reply
    if (-not $reply.Ok -or -not $reply.Response) { throw 'No engine comparison response' }
    if ($reply.Response.token -ne $Token) { throw 'Stale engine response: compiled token differs' }
    if ($reply.Response.ok -ne 1) { throw ('PID comparison failed: '+$reply.Response.detail) }
    if ($reply.Response.operations -ne $ExpectedOperations -or $ExpectedOperations -le 0) { throw 'Missing or partial PID operations' }
    if ($reply.Response.checks -ne (30 * $ExpectedOperations)) { throw 'Missing or partial PID field comparisons' }
    $record.status = 'success'
} catch {
    $record.failure = $_.Exception.Message
} finally {
    if ($owned) {
        $current = Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
        if ($current -and $current.StartTime -eq $startedAt) { Stop-Process -Id $owned.Id -Force }
    }
    $record | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResultPath -Encoding utf8
}
if ($record.status -ne 'success') { Write-Error $record.failure; exit 1 }
