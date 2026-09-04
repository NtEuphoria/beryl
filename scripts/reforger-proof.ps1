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
    Leave the throwaway addon in place afterwards for inspection.
#>
[CmdletBinding()]
param(
    [string] $Source = 'examples/proof.be',
    [string] $Prefix = 'BEP',
    [switch] $Keep,
    [int]    $TimeoutSeconds = 240
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $beryl = Join-Path $repo 'build\beryl.exe'
    if (-not (Test-Path -LiteralPath $beryl)) {
        throw "build\beryl.exe is missing; run scripts/build.sh first"
    }

    $addons  = Join-Path $env:USERPROFILE 'Documents\My Games\ArmaReforgerWorkbench\addons'
    $proj    = Join-Path $addons '_BerylProof'
    $scripts = Join-Path $proj 'scripts\Game\BerylProof'

    if (Test-Path -LiteralPath $proj) { Remove-Item -LiteralPath $proj -Recurse -Force }
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
    [System.IO.File]::WriteAllText((Join-Path $proj 'addon.gproj'), $gproj,
        (New-Object System.Text.UTF8Encoding($false)))

    Write-Host "generating EnforceScript from $Source ..."
    & $beryl build -t enfusion --prefix $Prefix --out-dir $scripts $Source
    if ($LASTEXITCODE -ne 0) { throw "beryl failed to generate ($LASTEXITCODE)" }

    $builder = Join-Path $env:USERPROFILE 'Desktop\reforger-workbench-plugin\scripts\Invoke-ReforgerBuild.ps1'
    if (-not (Test-Path -LiteralPath $builder)) {
        Write-Warning "Workbench build script not found at $builder - skipping the real build."
        return
    }

    Write-Host "compiling in Workbench ..."
    $r = & $builder -ProjectDir $proj -TimeoutSeconds $TimeoutSeconds

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

    if (-not $Keep) { Remove-Item -LiteralPath $proj -Recurse -Force }
    exit $exit
}
finally {
    Pop-Location
}
