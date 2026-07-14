[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [Parameter(Mandatory = $true)]
    [string]$FakeServerPath,
    [string]$WorkRoot = "",
    [string]$LogRoot = "",
    [ValidateRange(10, 1800)]
    [int]$ProcessTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$installer = (Resolve-Path $InstallerPath).Path
$fakeServer = (Resolve-Path $FakeServerPath).Path

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
$startLog = Join-Path $logDir "start-server.log"
$duplicateStartLog = Join-Path $logDir "duplicate-start.log"
$restartLog = Join-Path $logDir "restart-server.log"
$stopLog = Join-Path $logDir "stop-server.log"
$uninstallLog = Join-Path $logDir "uninstall.log"
$installed = $false
$uninstalled = $false

function Invoke-CheckedConsoleExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$OutputPath = "",
        [int]$TimeoutSeconds = $ProcessTimeoutSeconds
    )

    $stdoutPath = if ($OutputPath) { "$OutputPath.stdout" } else { Join-Path $logDir "console.stdout" }
    $stderrPath = if ($OutputPath) { "$OutputPath.stderr" } else { Join-Path $logDir "console.stderr" }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) {
        $startInfo.ArgumentList.Add($argument)
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Could not start $FilePath."
    }
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
    if ($timedOut) {
        try { $process.Kill($true) } catch { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        $process.WaitForExit(5000) | Out-Null
    }
    $stdout.GetAwaiter().GetResult() | Set-Content -LiteralPath $stdoutPath -Encoding utf8
    $stderr.GetAwaiter().GetResult() | Set-Content -LiteralPath $stderrPath -Encoding utf8
    if ($OutputPath) {
        Get-Content -LiteralPath $stdoutPath, $stderrPath | Set-Content -LiteralPath $OutputPath -Encoding utf8
    }
    if ($timedOut) {
        throw "$FilePath timed out after $TimeoutSeconds seconds. Partial output: $stdoutPath and $stderrPath"
    }
    if ($process.ExitCode -ne 0) {
        throw "$FilePath exited with code $($process.ExitCode). See $stdoutPath and $stderrPath."
    }
}

function Invoke-CheckedGuiExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int]$TimeoutSeconds = $ProcessTimeoutSeconds
    )

    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill($true) } catch { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        throw "$FilePath timed out after $TimeoutSeconds seconds."
    }
    if ($process.ExitCode -ne 0) {
        throw "$FilePath exited with code $($process.ExitCode)."
    }
}

function Wait-ForPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$TimeoutSeconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $Path) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "Timed out after $TimeoutSeconds seconds waiting for: $Path"
}

function Assert-ProcessRunning {
    param([Parameter(Mandatory = $true)][int]$Id)
    if ($null -eq (Get-Process -Id $Id -ErrorAction SilentlyContinue)) {
        throw "Expected process $Id to be running."
    }
}

function Wait-ForLogMonitorAttachment {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)][string]$ExpectedLog,
        [int]$TimeoutSeconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
            try {
                $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
                if ($state.tailing_file -eq $ExpectedLog -and [int64]$state.bytes_read -gt 0) {
                    return
                }
            }
            catch { }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Log monitor did not attach to and read $ExpectedLog within $TimeoutSeconds seconds."
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

    Write-Host "[SMOKE] Exercising packaged server and monitor lifecycle without source Python"
    $fakeTarget = Join-Path $installDir "Server\Vein\Binaries\Win64\VeinServer-Win64-Test.exe"
    New-Item -ItemType Directory -Force -Path (Split-Path $fakeTarget -Parent) | Out-Null
    Copy-Item -LiteralPath $fakeServer -Destination $fakeTarget

    $configText = Get-Content -LiteralPath $config -Raw
    $configText = $configText -replace '(?m)^    warn_seconds: 5[ \t]*$', '    warn_seconds: 0'
    $configText = $configText -replace '(?m)(^backups:\r?\n)  enabled: true[ \t]*$', '${1}  enabled: false'
    Set-Content -LiteralPath $config -Value $configText -Encoding utf8

    $pythonPath = $env:Path
    $pythonHome = $env:PYTHONHOME
    $pythonModulePath = $env:PYTHONPATH
    $pythonExe = $env:PYEXE
    try {
        $env:Path = (($env:Path -split ';') | Where-Object {
            $_ -and $_ -notmatch '(?i)python|hostedtoolcache'
        }) -join ';'
        Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        Remove-Item Env:PYEXE -ErrorAction SilentlyContinue

        Invoke-CheckedConsoleExecutable -FilePath $tools -Arguments @(
            "--config", $config, "start-server"
        ) -OutputPath $startLog -TimeoutSeconds 45

        $runtime = Join-Path $installDir "Runtime"
        $serverPidPath = Join-Path $runtime "server.pid"
        $logPidPath = Join-Path $runtime "log_monitor.pid"
        $crashPidPath = Join-Path $runtime "crash_monitor.pid"
        $logStatePath = Join-Path $runtime "log_monitor.state.json"
        $gameLog = Join-Path $installDir "Server\Vein\Saved\Logs\Vein.log"
        foreach ($path in @($serverPidPath, $logPidPath, $crashPidPath, $gameLog)) {
            Wait-ForPath -Path $path
        }

        $serverPid = [int](Get-Content -LiteralPath $serverPidPath -Raw)
        $logPid = [int](Get-Content -LiteralPath $logPidPath -Raw)
        $crashPid = [int](Get-Content -LiteralPath $crashPidPath -Raw)
        Assert-ProcessRunning -Id $serverPid
        Assert-ProcessRunning -Id $logPid
        Assert-ProcessRunning -Id $crashPid
        Wait-ForLogMonitorAttachment -StatePath $logStatePath -ExpectedLog $gameLog
        foreach ($monitorPid in @($logPid, $crashPid)) {
            $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$monitorPid").CommandLine
            if ($commandLine -notmatch '(?i)VeinTools\.exe') {
                throw "Packaged monitor $monitorPid did not run through VeinTools.exe: $commandLine"
            }
            if ($commandLine -match '(?i)python(?:\.exe)?') {
                throw "Packaged monitor $monitorPid unexpectedly depends on source Python: $commandLine"
            }
        }

        Invoke-CheckedConsoleExecutable -FilePath $tools -Arguments @(
            "--config", $config, "start-server"
        ) -OutputPath $duplicateStartLog -TimeoutSeconds 30
        $duplicatePid = [int](Get-Content -LiteralPath $serverPidPath -Raw)
        if ($duplicatePid -ne $serverPid) {
            throw "Duplicate start replaced server PID $serverPid with $duplicatePid."
        }
        if ((Get-Content -LiteralPath $duplicateStartLog -Raw) -notmatch "already running") {
            throw "Duplicate start did not report the existing packaged server process."
        }

        Invoke-CheckedConsoleExecutable -FilePath $tools -Arguments @(
            "--config", $config, "restart-server", "--restart-delay", "0"
        ) -OutputPath $restartLog -TimeoutSeconds 60
        Wait-ForPath -Path $serverPidPath
        $restartedPid = [int](Get-Content -LiteralPath $serverPidPath -Raw)
        if ($restartedPid -eq $serverPid) {
            throw "Packaged restart did not replace fake server PID $serverPid."
        }
        Assert-ProcessRunning -Id $restartedPid
        if ($null -ne (Get-Process -Id $serverPid -ErrorAction SilentlyContinue)) {
            throw "Packaged restart left original fake server PID $serverPid running."
        }
        $serverPid = $restartedPid

        Invoke-CheckedConsoleExecutable -FilePath $tools -Arguments @(
            "--config", $config, "stop-server"
        ) -OutputPath $stopLog -TimeoutSeconds 45
        Start-Sleep -Seconds 2
        if ($null -ne (Get-Process -Id $serverPid -ErrorAction SilentlyContinue)) {
            throw "Packaged stop left fake server PID $serverPid running."
        }
        foreach ($marker in @($serverPidPath, $logPidPath, $crashPidPath)) {
            if (Test-Path -LiteralPath $marker) {
                throw "Packaged stop left runtime marker behind: $marker"
            }
        }
    }
    finally {
        $env:Path = $pythonPath
        $env:PYTHONHOME = $pythonHome
        $env:PYTHONPATH = $pythonModulePath
        $env:PYEXE = $pythonExe
    }

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
    Write-Host "[PASS] Packaged install, CLI, server/monitor lifecycle, and uninstall smoke test passed."
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
                    $fallback = Start-Process -FilePath $resolvedFallback -ArgumentList @(
                        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
                    ) -PassThru
                    if (-not $fallback.WaitForExit($ProcessTimeoutSeconds * 1000)) {
                        try { $fallback.Kill($true) } catch { Stop-Process -Id $fallback.Id -Force -ErrorAction SilentlyContinue }
                    }
                }
            }
        }
    }
    if (Test-Path -LiteralPath $installDir) {
        Remove-Item -LiteralPath $installDir -Recurse -Force
    }
}
