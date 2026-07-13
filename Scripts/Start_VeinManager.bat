@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem Resolve repo root (this file is in ...\Scripts\)
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "VEIN_MGMT_ROOT=%%~fI"
set "VEIN_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"
set "VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.yaml"
if not exist "%VEIN_CONFIG%" set "VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json"

rem Prefer the project venv. Otherwise use an installed windowless Python
rem launcher, preferring the tested Python 3.12 development runtime.
set "PYWIN="
set "PYARGS="
if exist "%VEIN_MGMT_ROOT%\venv\Scripts\pythonw.exe" (
  set "PYWIN=%VEIN_MGMT_ROOT%\venv\Scripts\pythonw.exe"
) else (
  where pyw.exe >nul 2>nul
  if not errorlevel 1 (
    set "PYWIN=pyw.exe"
    py -3.12 -c "import PySide6" >nul 2>nul
    if not errorlevel 1 (
      set "PYARGS=-3.12"
    ) else (
      set "PYARGS=-3"
    )
  ) else (
    where pythonw.exe >nul 2>nul
    if not errorlevel 1 set "PYWIN=pythonw.exe"
  )
)

if not defined PYWIN (
  echo [ERROR] No usable windowless Python runtime was found.
  echo Install the development requirements for Python 3.12 and try again.
  pause
  exit /b 1
)

echo [env] ROOT=%VEIN_MGMT_ROOT%
echo [env] CONFIG=%VEIN_CONFIG%
echo [env] PYTHON=%PYWIN% %PYARGS%

rem Internal bounded probe used by automated/local diagnostics.
if /i "%~1"=="__PROBE__" (
  pushd "%VEIN_CONTROLLER%"
  "%PYWIN%" %PYARGS% launch_manager.py --startup-probe --config "%VEIN_CONFIG%"
  set "PROBE_RC=!ERRORLEVEL!"
  popd
  exit /b !PROBE_RC!
)

rem Launch detached, no console window, working dir = Controller
start "" /D "%VEIN_CONTROLLER%" "%PYWIN%" %PYARGS% launch_manager.py --config "%VEIN_CONFIG%"

if errorlevel 1 (
  echo [ERROR] Windows could not launch Vein Server Manager.
  echo Check Logs\gui\bootstrap for startup details.
  pause
  exit /b 1
)

endlocal & exit /b 0
