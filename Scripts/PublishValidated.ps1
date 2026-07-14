[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CommitMessage,
    [string]$PythonExe = "python",
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [int]$RunDiscoveryTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root

function Assert-LastExitCode {
    param([string]$Message)
    if ($LASTEXITCODE -ne 0) {
        throw "$Message (exit code $LASTEXITCODE)."
    }
}

try {
    $currentBranch = (& git branch --show-current).Trim()
    Assert-LastExitCode "Could not determine the current branch"
    if ($currentBranch -ne $Branch) {
        throw "Validated owner publishing requires branch '$Branch'; current branch is '$currentBranch'. Contributors and high-risk changes must use a pull request."
    }

    & gh auth status *> $null
    Assert-LastExitCode "GitHub CLI is not authenticated"

    & git fetch $Remote $Branch
    Assert-LastExitCode "Could not fetch $Remote/$Branch"
    $localHead = (& git rev-parse HEAD).Trim()
    $remoteHead = (& git rev-parse "$Remote/$Branch").Trim()
    if ($localHead -ne $remoteHead) {
        throw "Local HEAD must equal $Remote/$Branch before publishing. Pull/reconcile changes first."
    }

    & git diff --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Unstaged tracked changes exist. Stage the exact intended files before publishing."
    }
    $untracked = @(& git ls-files --others --exclude-standard)
    if ($untracked.Count -gt 0) {
        throw "Untracked files exist. Stage the intended files or remove them from the publish scope: $($untracked -join ', ')"
    }
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        throw "No staged changes are available to commit."
    }

    & (Join-Path $PSScriptRoot "ValidateChange.ps1") -PythonExe $PythonExe
    Assert-LastExitCode "Local validation failed; nothing was committed or pushed"

    & git commit -m $CommitMessage
    Assert-LastExitCode "Commit failed"
    $commit = (& git rev-parse HEAD).Trim()

    & git push $Remote $Branch
    Assert-LastExitCode "Push failed"

    Write-Host "[PUBLISH] Waiting for GitHub CI for $commit..." -ForegroundColor Cyan
    $deadline = (Get-Date).AddSeconds($RunDiscoveryTimeoutSeconds)
    $run = $null
    while ((Get-Date) -lt $deadline) {
        $json = & gh run list --commit $commit --workflow ci.yml --limit 1 `
            --json databaseId,status,conclusion,url
        Assert-LastExitCode "Could not query GitHub Actions"
        $parsedRuns = $json | ConvertFrom-Json
        if ($null -ne $parsedRuns -and $parsedRuns.Count -gt 0) {
            $run = $parsedRuns[0]
            break
        }
        Start-Sleep -Seconds 3
    }
    if ($null -eq $run) {
        throw "The push succeeded, but no GitHub CI run appeared within $RunDiscoveryTimeoutSeconds seconds. Verify Actions manually before further publishing or tagging."
    }

    Write-Host "[PUBLISH] CI run: $($run.url)"
    & gh run watch $run.databaseId --exit-status
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CI failed for pushed commit $commit. Fix forward immediately; do not tag or publish another change until main is green."
    }

    Write-Host "[PASS] Commit $commit is pushed and GitHub CI passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
