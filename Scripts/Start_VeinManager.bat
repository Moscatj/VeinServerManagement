@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem Resolve repo root (this file is in ...\Scripts\)
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "VEIN_MGMT_ROOT=%%~fI"
set "VEIN_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"
set "VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json"

rem Prefer venv\pythonw.exe; else try pyw -3 (windowless launcher); else pythonw.exe on PATH
if exist "%VEIN_MGMT_ROOT%\venv\Scripts\pythonw.exe" (
  set "PYWIN=%VEIN_MGMT_ROOT%\venv\Scripts\pythonw.exe"
) else (
  where pyw >nul 2>nul
  if %ERRORLEVEL%==0 (
    set "PYWIN=pyw -3"
  ) else (
    set "PYWIN=pythonw.exe"
  )
)

echo [env] ROOT=%VEIN_MGMT_ROOT%
echo [env] CONFIG=%VEIN_CONFIG%
rem Launch detached, no console window, working dir = Controller
start "" /D "%VEIN_CONTROLLER%" %PYWIN% vein_manager.py --config "%VEIN_CONFIG%"

endlocal & exit /b 0
