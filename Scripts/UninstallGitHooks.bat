@echo off
REM ================================================================
REM UninstallGitHooks.bat
REM Restores Git's hook path to its default (.git\hooks)
REM Disables use of the repo-tracked .githooks folder.
REM ================================================================

cd /d "%~dp0"
echo [INFO] Restoring Git hook path to default (.git\hooks)...

REM Move to project root (Scripts\..)
cd ..

REM Verify we’re in a Git repo
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This folder is not a Git repository.
    echo Run this script from within your VeinServerManagement project.
    pause
    exit /b 1
)

REM Reset the hook path to Git’s default
git config --unset core.hooksPath
if %errorlevel% neq 0 (
    echo [WARN] No custom hooks path was set, or failed to unset.
) else (
    echo [OK] Git hooks path restored to default.
)

REM Optional: confirm status
setlocal enabledelayedexpansion
for /f "tokens=*" %%H in ('git config --get core.hooksPath 2^>nul') do set CUR_HOOKS=%%H
if defined CUR_HOOKS (
    echo [WARN] core.hooksPath still set to: !CUR_HOOKS!
    echo You may need to reset manually with: git config --unset core.hooksPath
) else (
    echo [SUCCESS] core.hooksPath is now unset. Git will use .git\hooks.
)
endlocal

pause
