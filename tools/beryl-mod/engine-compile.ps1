# Typed adapter to the existing Workbench build tool. No project-provided code.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $ToolRoot,
    [Parameter(Mandatory)][string] $ProjectDir,
    [Parameter(Mandatory)][string] $ResultPath,
    [Parameter(Mandatory)][string] $ExpectedVersion,
    [int] $TimeoutSeconds = 240
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$mutex = $null
$acquired = $false
$record = [ordered]@{schema_version=1;stage='workbench_compile';status='failure';engine_version=$null;engine_sha256=$null;tools=$null;result=$null;failure=$null}
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
        throw 'A Workbench session is already running. This compile job does not own it.'
    }
    $paths = & (Join-Path $ToolRoot 'scripts/Find-Workbench.ps1')
    if (-not $paths.WorkbenchExe) { $record.status = 'unavailable'; throw 'Workbench executable unavailable' }
    $record.engine_version = (Get-Item -LiteralPath $paths.WorkbenchExe).VersionInfo.FileVersion
    if ($record.engine_version -ne $ExpectedVersion) { $record.status = 'stale_input'; throw 'Binding version differs from installed Workbench' }
    $record.engine_sha256 = Get-ContentHash $paths.WorkbenchExe
    $toolHashes = [ordered]@{}
    foreach ($file in @('Find-Workbench.ps1','Invoke-ReforgerBuild.ps1','Invoke-Workbench.ps1','Get-WorkbenchErrors.ps1')) {
        $toolHashes[$file] = Get-ContentHash (Join-Path $ToolRoot ('scripts/'+$file))
    }
    $record.tools = $toolHashes
    $result = & (Join-Path $ToolRoot 'scripts/Invoke-ReforgerBuild.ps1') -ProjectDir $ProjectDir -TimeoutSeconds $TimeoutSeconds -IncludeWarnings
    $record.result = $result
    if ($result.Stage -eq 'Timeout') { $record.status = 'timeout'; throw $result.Summary }
    if ($result.Stage -eq 'DidNotStart') { $record.status = 'unavailable'; throw 'Workbench returned without an associated log directory; engine startup and compilation outcome are unverified. Inspect the retained plugin result and host logs.' }
    if (-not $result.Ok) { throw $result.Summary }
    if ((Get-ContentHash $paths.WorkbenchExe) -ne $record.engine_sha256) { $record.status = 'stale_input'; throw 'Engine changed during compilation' }
    foreach ($file in $toolHashes.Keys) {
        if ((Get-ContentHash (Join-Path $ToolRoot ('scripts/'+$file))) -ne $toolHashes[$file]) {
            $record.status = 'stale_input'; throw 'Integration tools changed during compilation'
        }
    }
    $record.status = 'success'
} catch {
    $record.failure = $_.Exception.Message
} finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
    $record | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $ResultPath -Encoding utf8
}
if ($record.status -ne 'success') { Write-Error $record.failure; exit 1 }
