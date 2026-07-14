[CmdletBinding()]
param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

$previousCi = $env:CI
$previousConfig = $env:VEIN_CONFIG
$previousPython = $env:PYTHON_BIN

function Invoke-ValidationStep {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host "[VALIDATE] $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

try {
    $env:CI = "true"
    $env:VEIN_CONFIG = Join-Path $root "Config\config.example.yaml"
    $env:PYTHON_BIN = $PythonExe

    New-Item -ItemType Directory -Force -Path `
        (Join-Path $root "Server"), `
        (Join-Path $root "Server\Vein\Saved\SaveGames"), `
        (Join-Path $root "Server\Vein\Saved\Logs") | Out-Null

    Invoke-ValidationStep "Documentation and version consistency" {
        & $PythonExe "Controller\Tools\documentation_check.py"
    }
    Invoke-ValidationStep "Source hygiene" {
        & $PythonExe "Controller\Tools\source_hygiene_check.py"
    }
    Invoke-ValidationStep "Architecture and subsystem registry" {
        & $PythonExe "Controller\Tools\architecture_check.py"
    }
    Invoke-ValidationStep "Unit tests" {
        & $PythonExe -m unittest discover -s Tests
    }
    Invoke-ValidationStep "Health check" {
        & $PythonExe "Controller\health_check.py"
    }
    Invoke-ValidationStep "Diagnostic suite" {
        & "Scripts\TestSuite.bat" __RUN__
    }
    Invoke-ValidationStep "Coverage" {
        & "Scripts\RunCoverage.bat"
    }
    Invoke-ValidationStep "Working-tree whitespace" {
        & git diff --check
    }
    Invoke-ValidationStep "Staged whitespace" {
        & git diff --cached --check
    }

    Write-Host ""
    Write-Host "[PASS] Repository validation completed successfully." -ForegroundColor Green
}
finally {
    $env:CI = $previousCi
    $env:VEIN_CONFIG = $previousConfig
    $env:PYTHON_BIN = $previousPython
    Pop-Location
}
