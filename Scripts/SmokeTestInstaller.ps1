[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [string]$WorkRoot = "",
    [string]$LogRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$installer = (Resolve-Path $InstallerPath).Path

if ([string]::IsNullOrWhiteSpace($WorkRoot)) {
    $base = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { Join-Path $repoRoot "dist" }
    $WorkRoot = Join-Path $base ("VeinServerManagement-installer-smoke-" + [Guid]::NewGuid().ToString("N"))
}
if ([string]::IsNullOrWhiteSpace($LogRoot)) {
    $LogRoot = Join-Path $repoRoot "dist\installer-smoke"
}

$installDir = [System.IO.Path]::GetFullPath($WorkRoot)
$logDir = [System.IO.Path]::GetFullPath($LogRoot)
if ($installDir.Length -lt 12 -or $installDir -eq [System.IO.Path]::GetPathRoot($installDir)) {
    throw "Refusing unsafe installer smoke-test directory: $installDir"
}
if ((Test-Path -LiteralPath $installDir) -and
    (Get-ChildItem -LiteralPath $installDir -Force | Select-Object -First 1)) {
    throw "Installer smoke-test directory must be new or empty: $installDir"
}

New-Item -ItemType Directory -Force -Path $installDir, $logDir | Out-Null
$setupLog = Join-Path $logDir "setup.log"
$cliLog = Join-Path $logDir "cli-help.log"
$healthLog = Join-Path $logDir "health-check.log"
$uninstallLog = Join-Path $logDir "uninstall.log"
$installed = $false
$uninstalled = $false

function Invoke-CheckedConsoleExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$OutputPath = ""
    )

    if ($OutputPath) {
        & $FilePath @Arguments *> $OutputPath
    }
    else {
        & $FilePath @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath exited with code $LASTEXITCODE."
    }
}

function Invoke-CheckedGuiExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "$FilePath exited with code $($process.ExitCode)."
    }
}

try {
    Write-Host "[SMOKE] Installing management app only into $installDir"
    Invoke-CheckedGuiExecutable -FilePath $installer -Arguments @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/MANAGEMENTAPPONLY=1",
        "/DIR=`"$installDir`"",
        "/LOG=`"$setupLog`""
    )
    $installed = $true

    $manager = Join-Path $installDir "VeinManager.exe"
    $tools = Join-Path $installDir "VeinTools.exe"
    $config = Join-Path $installDir "Config\config.yaml"
    $version = Join-Path $installDir "version.txt"
    $uninstallerRecord = Join-Path $installDir "Runtime\uninstaller_path.txt"
    foreach ($required in @($manager, $tools, $config, $version, $uninstallerRecord)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Installed package is missing required file: $required"
        }
    }

    if (Test-Path -LiteralPath (Join-Path $installDir "SteamCMD\steamcmd.exe")) {
        throw "Management-app-only smoke install unexpectedly configured SteamCMD."
    }
    if (Test-Path -LiteralPath (Join-Path $installDir "Server\Vein\Binaries\Win64\VeinServer-Win64-Test.exe")) {
        throw "Management-app-only smoke install unexpectedly installed a game server."
    }

    Write-Host "[SMOKE] Running packaged CLI help and health checks"
    Invoke-CheckedConsoleExecutable -FilePath $tools -Arguments @("--help") -OutputPath $cliLog
    Invoke-CheckedConsoleExecutable -FilePath $tools -Arguments @(
        "--config", $config, "health-check"
    ) -OutputPath $healthLog

    $uninstaller = (Get-Content -LiteralPath $uninstallerRecord -Raw).Trim()
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw "Recorded uninstaller does not exist: $uninstaller"
    }
    $resolvedUninstaller = (Resolve-Path $uninstaller).Path
    $installPrefix = $installDir.TrimEnd('\') + '\'
    if (-not $resolvedUninstaller.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Recorded uninstaller escapes the smoke install directory: $resolvedUninstaller"
    }

    Write-Host "[SMOKE] Uninstalling the packaged management app"
    Invoke-CheckedGuiExecutable -FilePath $resolvedUninstaller -Arguments @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/LOG=`"$uninstallLog`""
    )
    $uninstalled = $true

    foreach ($removed in @($manager, $tools, $version)) {
        if (Test-Path -LiteralPath $removed) {
            throw "Uninstaller left packaged application file behind: $removed"
        }
    }
    if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
        throw "Uninstaller did not preserve local configuration as expected: $config"
    }
    Write-Host "[PASS] Packaged install, CLI, health check, and uninstall smoke test passed."
}
finally {
    if ($installed -and -not $uninstalled) {
        $record = Join-Path $installDir "Runtime\uninstaller_path.txt"
        if (Test-Path -LiteralPath $record -PathType Leaf) {
            $fallbackUninstaller = (Get-Content -LiteralPath $record -Raw).Trim()
            if (Test-Path -LiteralPath $fallbackUninstaller -PathType Leaf) {
                $resolvedFallback = (Resolve-Path $fallbackUninstaller).Path
                $installPrefix = $installDir.TrimEnd('\') + '\'
                if ($resolvedFallback.StartsWith($installPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                    Start-Process -FilePath $resolvedFallback -ArgumentList @(
                        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
                    ) -Wait | Out-Null
                }
            }
        }
    }
    if (Test-Path -LiteralPath $installDir) {
        Remove-Item -LiteralPath $installDir -Recurse -Force
    }
}
