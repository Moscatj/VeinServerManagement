@echo off
setlocal ENABLEDELAYEDEXPANSION
title Vein Crash Monitor - Start Only

rem --- Go to this script's folder ---
cd /d "%~dp0"

rem --- Resolve ROOT = parent of Scripts (absolute path) ---
for %%I in ("%~dp0..") do set "ROOT=%%~fI"

set "CONTROLLER=%ROOT%\Controller"
set "CONFIG=%ROOT%\Config\config.yaml"
if not exist "%CONFIG%" set "CONFIG=%ROOT%\Config\config.json"

rem --- Try env_setup (optional) ---
set "ENV_SETUP1=%~dp0env_setup.bat"
set "ENV_SETUP2=%ROOT%\env_setup.bat"
if exist "%ENV_SETUP1%" (
  echo [INFO] Loading environment from "%ENV_SETUP1%"
  call "%ENV_SETUP1%"
) else if exist "%ENV_SETUP2%" (
  echo [INFO] Loading environment from "%ENV_SETUP2%"
  call "%ENV_SETUP2%"
) else (
  echo [INFO] env_setup.bat not found; continuing with minimal environment.
)

rem --- Resolve Python (do NOT quote %PYEXE% when it has args) ---
if not defined PYEXE (
  set "PYEXE="
  where py >nul 2>&1 && set "PYEXE=py -3"
  if not defined PYEXE where python >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
  echo [ERROR] No Python found on PATH. Install Python 3 or add it to PATH.
  set "ERR=9009"
  goto :end
)
for /f "tokens=2,*" %%A in ('%PYEXE% -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%A"
echo [INFO] Python: %PYEXE%  %PYVER%

rem --- Resolve crash_monitor.py (respect CRASH if set; else default) ---
if not defined CRASH set "CRASH=%CONTROLLER%\crash_monitor.py"
echo [INFO] Controller dir: %CONTROLLER%
echo [INFO] Crash monitor : %CRASH%

if not exist "%CRASH%" (
  echo [ERROR] crash_monitor.py not found at:
  echo         %CRASH%
  echo         Expected default location is:
  echo         %CONTROLLER%\crash_monitor.py
  echo(
  echo [HINT] Verify the file exists. From CMD you can run:
  echo        dir "%CONTROLLER%\crash_monitor.py"
  set "ERR=2"
  goto :end
)

rem --- Already-running check (window title) ---
set "RUNNING="
for /f "tokens=*" %%A in ('tasklist /v /fi "imagename eq cmd.exe" ^| findstr /i /c:"Vein Crash Monitor"') do set "RUNNING=1"
if defined RUNNING (
  echo [INFO] Crash monitor already running; skipping start.
  set "ERR=0"
  goto :end
)

rem --- Launch (minimized, low priority) ---
echo [INFO] Launching monitor...
start "Vein Crash Monitor" /min /low cmd /k ^
  "title Vein Crash Monitor & echo [Crash Monitor] Starting... & %PYEXE% "%CRASH%""
set "ERR=%ERRORLEVEL%"

:end
if not "%1"=="-nopause" (
  if not "%ERR%"=="0" (
    echo(
    echo [ERROR] StartCrashMonitor exited with code %ERR%.
    pause
  )
)
exit /b %ERR%
