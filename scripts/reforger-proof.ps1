<#
.SYNOPSIS
    Compiles Beryl-generated EnforceScript in the real Arma Reforger Workbench.

.DESCRIPTION
    A golden test proves the emitted text is what was expected. Only Workbench
    proves it compiles, and the difference is not academic: the two bugs this
    check found first - `out` being a reserved word, and `Clone` colliding with
    the engine base class - both produced text that looked entirely reasonable.

    Builds a throwaway addon containing nothing but generated script, so the
    real mod is never touched.

    NOTE: keep this file pure ASCII. Windows PowerShell 5.1 reads a BOM-less
    file as ANSI, so a stray em-dash becomes a parse error.

.PARAMETER Source
    The .be file to generate from. Defaults to examples/proof.be.

.PARAMETER Keep
    Retained for command compatibility. Artifacts are always kept under build/.
#>
[CmdletBinding()]
param(
    [string[]] $Source = @('examples/proof.be'),
    [string] $Prefix = 'BEP',
    [string] $Beryl = '',
    [string[]] $ExportClass = @(),
    [string[]] $ExportMethod = @(),
    [switch] $Keep,
    [int]    $TimeoutSeconds = 240
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $compilerPath = if ($Beryl) { $Beryl } else { Join-Path $repo 'build\beryl.exe' }
    if (-not (Test-Path -LiteralPath $compilerPath)) {
        throw "build\beryl.exe is missing; run scripts/build.sh first"
    }

    $builder = Join-Path $env:USERPROFILE 'Desktop\reforger-workbench-plugin\scripts\Invoke-ReforgerBuild.ps1'
    if (-not (Test-Path -LiteralPath $builder)) {
        throw "Workbench build script not found at $builder; real-engine validation did not run"
    }
    # Every invocation owns a new directory. Never delete a shared addon or
    # the user's existing _BerylProof project, even after a failed run.
    $proofId = [Guid]::NewGuid().ToString('N')
    $proj = Join-Path $repo ('build\enfusion-proof-' + $proofId)
    $scripts = Join-Path $proj 'scripts\Game\BerylProof'

    New-Item -ItemType Directory -Path $scripts -Force | Out-Null

    # A minimal addon that depends only on the base game data addon.
    $gproj = @'
GameProject {
 ID "BerylProof"
 GUID "BE41000000000001"
 TITLE "Beryl codegen proof"
 Dependencies {
  "58D0FB3206B6F859"
 }
}
'@
    $gproj = $gproj.Replace('BE41000000000001', $proofId.Substring(0, 16).ToUpperInvariant())
    [System.IO.File]::WriteAllText((Join-Path $proj 'addon.gproj'), $gproj,
        (New-Object System.Text.UTF8Encoding($false)))

    Write-Host "generating EnforceScript from $Source ..."
    $exportArguments = @()
    foreach ($mapping in $ExportClass) { $exportArguments += @('--export-class', $mapping) }
    foreach ($mapping in $ExportMethod) { $exportArguments += @('--export-method', $mapping) }
    & $compilerPath build -t enfusion --prefix $Prefix --out-dir $scripts @exportArguments @Source
    if ($LASTEXITCODE -ne 0) { throw "beryl failed to generate ($LASTEXITCODE)" }

    Write-Host "compiling in Workbench ..."
    $r = & $builder -ProjectDir $proj -TimeoutSeconds $TimeoutSeconds
    $r | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $proj 'result.json') -Encoding UTF8
    Write-Host "proof artifacts: $proj"

    $exit = 0
    if ($r.Ok) {
        Write-Host "ok  Workbench compiled the generated script cleanly" -ForegroundColor Green
    } else {
        Write-Host "FAIL  $($r.Summary)" -ForegroundColor Red
        foreach ($diag in $r.Diagnostics) {
            if ($diag.InProject) {
                Write-Host ("    " + $diag.File + ":" + $diag.Line + "  " + $diag.Message)
            }
        }
        $exit = 1
    }

    exit $exit
}
finally {
    Pop-Location
}
