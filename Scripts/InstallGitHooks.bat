@echo off
REM ================================================================
REM InstallGitHooks.bat
REM Configures Git to use the repo-tracked .githooks folder.
REM After running once, your pre-commit hook will auto-run
REM whenever you commit Config\*.yaml or Config\*.yml.
REM ================================================================

cd /d "%~dp0"
echo [INFO] Configuring repo-tracked hooks...

REM Move up to project root (Scripts\..)
cd ..

REM Verify we’re inside a Git repo
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This folder is not a Git repository.
    echo Run this script from within your VeinServerManagement project.
    pause
    exit /b 1
)

REM Set the hooks path to the versioned .githooks directory
git config core.hooksPath .githooks
if %errorlevel% neq 0 (
    echo [ERROR] Failed to set Git hooks path.
    pause
    exit /b 1
)

REM Ensure the hooks folder exists
if not exist ".githooks" (
    mkdir ".githooks"
    echo [INFO] Created .githooks directory.
)

REM Confirm that the pre-commit hook exists
if exist ".githooks\\pre-commit" (
    echo [OK] Found pre-commit hook (.githooks\\pre-commit)
) else (
    echo [WARN] No pre-commit hook found yet.
    echo You can create one using the sample from ChatGPT.
)

echo [SUCCESS] Git is now configured to use .githooks for hooks.
echo Hooks will run automatically on commit.
pause
