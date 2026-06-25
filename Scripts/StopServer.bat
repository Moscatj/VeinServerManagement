@echo off
setlocal EnableExtensions
title Vein Server — Stop

rem --- Go to this script's folder
cd /d "%~dp0"

rem --- Resolve ROOT (one level up from Scripts)
for %%I in ("%~dp0..") do set "ROOT=%%~fI"

rem --- Load env if available (safe to skip)
if exist "%ROOT%\env_setup.bat" call "%ROOT%\env_setup.bat"

rem --- Fallbacks if env_setup didn’t define them
if not defined VEIN_MGMT_ROOT set "VEIN_MGMT_ROOT=%ROOT%"
if not defined VEIN_MGMT_CONTROLLER set "VEIN_MGMT_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"
if not defined VEIN_CONFIG if exist "%VEIN_MGMT_ROOT%\Config\config.yaml" set "VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.yaml"
if not defined VEIN_CONFIG set "VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json"

echo [INFO] Using ROOT=%VEIN_MGMT_ROOT%
echo [INFO] Using VEIN_CONFIG=%VEIN_CONFIG%
echo [INFO] Running shutdown_server.py ...

rem --- Visible Python so you can see output
py -3 "%VEIN_MGMT_CONTROLLER%\shutdown_server.py"
set "ERR=%ERRORLEVEL%"

if %ERR% EQU 0 (
  echo [OK] Shutdown script completed successfully.
) else (
  echo [ERROR] Shutdown script exited with code %ERR%.
)

pause
exit /b %ERR%
