@echo off
setlocal ENABLEDELAYEDEXPANSION
title Vein Log Monitor - Start Only

rem --- Go to this script's folder ---
cd /d "%~dp0"

rem --- Resolve ROOT = parent of Scripts (absolute path) ---
for %%I in ("%~dp0..") do set "ROOT=%%~fI"

set "CONTROLLER=%ROOT%\Controller"
set "CONFIG=%ROOT%\Config\config.json"

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

rem --- Resolve Python (do NOT quote %%PYEXE%% when it has args) ---
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

rem --- Resolve log monitor script:
rem      prefer LOGMON, then legacy MON, else default to Controller\monitor_log.py
if defined LOGMON (
  set "LOG_MON=%LOGMON%"
) else if defined MON (
  set "LOG_MON=%MON%"
) else (
  set "LOG_MON=%CONTROLLER%\monitor_log.py"
)

echo [INFO] Controller dir: %CONTROLLER%
echo [INFO] Log monitor   : %LOG_MON%

if not exist "%LOG_MON%" (
  echo [ERROR] Log monitor script not found at:
  echo         %LOG_MON%
  echo         Expected default location is:
  echo         %CONTROLLER%\monitor_log.py
  set "ERR=2"
  goto :end
)

rem --- Already-running check (window title) ---
set "RUNNING="
for /f "tokens=*" %%A in ('tasklist /v /fi "imagename eq cmd.exe" ^| findstr /i /c:"Vein Log Monitor"') do set "RUNNING=1"
if defined RUNNING (
  echo [INFO] Log monitor already running; skipping start.
  set "ERR=0"
  goto :end
)

rem --- Launch (minimized, low priority) ---
echo [INFO] Launching log monitor...
start "Vein Log Monitor" /min /low cmd /k ^
  "title Vein Log Monitor & echo [Log Monitor] Starting... & %PYEXE% "%LOG_MON%""
set "ERR=%ERRORLEVEL%"

:end
if not "%1"=="-nopause" (
  if not "%ERR%"=="0" (
    echo(
    echo [ERROR] StartLogMonitor exited with code %ERR%.
    pause
  )
)
exit /b %ERR%
