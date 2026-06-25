@echo off
setlocal
title Vein Server - Steam Update (Python)

rem Resolve repo root from this script’s folder
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "SCRIPTS=%%~fI"
set "ROOT=%SCRIPTS%\.."
set "CTRL=%ROOT%\Controller"

rem Optional: prefer existing VEIN_CONFIG if you already export it
if not defined VEIN_CONFIG (
  if exist "%ROOT%\Config\config.yaml" set "VEIN_CONFIG=%ROOT%\Config\config.yaml"
  if not defined VEIN_CONFIG if exist "%ROOT%\Config\config.json" set "VEIN_CONFIG=%ROOT%\Config\config.json"
)

echo [INFO] ROOT=%ROOT%
echo [INFO] Using VEIN_CONFIG=%VEIN_CONFIG%

if exist "%SystemRoot%\py.exe" (
  py -3 "%CTRL%\tools\update_steam.py" %*
  set ERR=%ERRORLEVEL%
) else (
  python "%CTRL%\tools\update_steam.py" %*
  set ERR=%ERRORLEVEL%
)

if "%ERR%"=="0" (
  echo [OK] Steam update completed.
) else (
  echo [ERROR] Steam update failed.
)

exit /b %ERR%
