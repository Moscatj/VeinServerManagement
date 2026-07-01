@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "SCRIPTS=%%~fI"
set "ROOT=%SCRIPTS%\.."
set "CTRL=%ROOT%\Controller"

if not defined VEIN_CONFIG (
  if exist "%ROOT%\Config\config.yaml" set "VEIN_CONFIG=%ROOT%\Config\config.yaml"
  if not defined VEIN_CONFIG if exist "%ROOT%\Config\config.json" set "VEIN_CONFIG=%ROOT%\Config\config.json"
)

if exist "%SystemRoot%\py.exe" (
  py -3 "%CTRL%\health_check.py" %*
) else (
  python "%CTRL%\health_check.py" %*
)
exit /b %ERRORLEVEL%
