@echo off
setlocal EnableExtensions
title Vein Server — Start

rem --- Go to this script's folder
cd /d "%~dp0"

rem --- ROOT is parent of Scripts
for %%I in ("%~dp0..") do set "ROOT=%%~fI"

rem --- Load env if present (safe to skip)
if exist "%ROOT%\env_setup.bat" call "%ROOT%\env_setup.bat"

rem --- Fallbacks if env_setup didn’t set them
if not defined VEIN_MGMT_ROOT set "VEIN_MGMT_ROOT=%ROOT%"
if not defined VEIN_MGMT_CONTROLLER set "VEIN_MGMT_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"
if not defined VEIN_CONFIG if exist "%VEIN_MGMT_ROOT%\Config\config.json" set "VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json"

rem --- Pick a Python launcher:
rem Try windowless via "py -3w" (newer launcher). If that fails, try "pyw -3".
rem If both fail, fall back to visible "py -3".
set "PYEXE="
py -3w -c "import sys" >nul 2>&1 && set "PYEXE=py -3w"
if not defined PYEXE (
  pyw -3 -c "import sys" >nul 2>&1 && set "PYEXE=pyw -3"
)
if not defined PYEXE set "PYEXE=py -3"

echo [INFO] Python: %PYEXE%
echo [INFO] Using ROOT=%VEIN_MGMT_ROOT%
echo [INFO] Using VEIN_CONFIG=%VEIN_CONFIG%
echo [INFO] Launching "%VEIN_MGMT_CONTROLLER%\start_server.py" ...

%PYEXE% "%VEIN_MGMT_CONTROLLER%\start_server.py"
set "ERR=%ERRORLEVEL%"

if %ERR% NEQ 0 (
  echo(
  echo [ERROR] Start script exited with code %ERR%.
  pause
)

exit /b %ERR%
