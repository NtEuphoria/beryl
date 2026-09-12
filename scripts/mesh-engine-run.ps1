# Reuse the installed NetAPI transport; own only the session started here.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $Token
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$owned = $null
$record = [ordered]@{schema_version=1;stage='mesh_workbench_tests';status='failure';loaded_projects=$null;identity=$null;tests=@();session=$null;failure=$null}
try {
    if (@(Get-Process -Name 'ArmaReforgerWorkbench*' -ErrorAction SilentlyContinue).Count) { throw 'An unrelated Workbench session is running' }
    $start = & (Join-Path $ToolRoot 'scripts/Start-WorkbenchDaemon.ps1') -ProjectDir $ProjectDir
    if (-not $start.Ok -or $start.Reused) { throw 'No exclusively owned Workbench session' }
    $owned = Get-Process -Id $start.ProcessId
    $startedAt = $owned.StartTime
    $record.session = @{process_id=$owned.Id;start_time=$startedAt.ToUniversalTime().ToString('o');project=$ProjectDir}
    $rpc = Join-Path $ToolRoot 'scripts/Invoke-WorkbenchRpc.ps1'
    $projects = & $rpc -Function GetLoadedProjects -ClientId BerylMeshVerifier
    $record.loaded_projects = $projects
    if (-not $projects.Ok -or @($projects.Response.'Loaded Projects') -notcontains 'SparkOSMesh') { throw 'MESH project identity lookup failed' }
    $identity = & $rpc -Function BerylMeshIdentity -Parameters @{token=$Token} -ClientId BerylMeshVerifier
    $record.identity = $identity
    if (-not $identity.Ok -or $identity.Response.token -ne $Token -or $identity.Response.ok -ne 1) { throw 'Stale or incorrect MESH candidate token' }
    $suites = @('pid','flightspec','rotor','mixer','manual','guidance','task','loiter','datalink')
    foreach ($suite in $suites) {
        $reply = & $rpc -Function SPK_MeshSelfTest -Parameters @{suite=$suite;arg=''} -ClientId BerylMeshVerifier -TimeoutMs 60000
        $record.tests += @{suite=$suite;result=$reply}
        if (-not $reply.Ok -or -not $reply.Response -or $reply.Response.ok -ne 1) { throw ('MESH suite failed: '+$suite) }
    }
    if ($record.tests.Count -ne $suites.Count -or $suites.Count -eq 0) { throw 'Incomplete MESH suite results' }
    $record.status = 'success'
} catch {
    $record.failure = $_.Exception.Message
} finally {
    if ($owned) {
        $current = Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
        if ($current -and $current.StartTime -eq $startedAt) { Stop-Process -Id $owned.Id -Force }
    }
    $record | ConvertTo-Json -Depth 24 | Set-Content -LiteralPath $ResultPath -Encoding utf8
}
if ($record.status -ne 'success') { Write-Error $record.failure; exit 1 }
