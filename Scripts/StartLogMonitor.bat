@echo off
setlocal
title Vein Log Monitor - Start Only

rem -- cd to Scripts folder
cd /d "%~dp0"

rem -- Resolve ROOT = parent of Scripts
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "CONTROLLER=%ROOT%\Controller"
set "CONFIG_JSON=%ROOT%\Config\config.json"

rem -- Try env_setup (optional) — use CALL and don’t rely on ELSE in IF lines
if exist "%~dp0env_setup.bat" call "%~dp0env_setup.bat"
if exist "%ROOT%\env_setup.bat"  call "%ROOT%\env_setup.bat"

rem -- Ensure VEIN_CONFIG is set
if not defined VEIN_CONFIG if exist "%CONFIG_JSON%" set "VEIN_CONFIG=%CONFIG_JSON%"

rem -- Python launcher (from env_setup or default)
if not defined PYEXE set "PYEXE=py -3"

rem -- Target script
set "LOG_MON=%CONTROLLER%\monitor_log.py"

echo [INFO] VEIN_MGMT_ROOT=%ROOT%
echo [INFO] CONTROLLER=%CONTROLLER%
echo [INFO] VEIN_CONFIG=%VEIN_CONFIG%
echo [INFO] PYEXE=%PYEXE%

if not exist "%LOG_MON%" (
  echo [ERROR] monitor_log.py not found at "%LOG_MON%"
  exit /b 2
)

rem -- Launch minimized; avoid nested quotes by passing args separately to cmd /c
echo [INFO] Launching log monitor...
start "Vein Log Monitor" /min "%SystemRoot%\System32\cmd.exe" /c ^
  "%PYEXE%" "%LOG_MON%" --follow

exit /b 0
