@echo off
rem Keep it simple: NO setlocal / endlocal block

rem --- Resolve ServerManagment root (parent of Scripts) ---
pushd "%~dp0\.." >nul 2>&1
set "VEIN_MGMT_ROOT=%CD%"
set "VEIN_MGMT_SCRIPTS=%VEIN_MGMT_ROOT%\Scripts"
set "VEIN_MGMT_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"
set "VEIN_MGMT_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json"

rem Preferred Python launcher (caller can override)
set "PYEXE=py -3"

rem Default VEIN_CONFIG if not already set
if not defined VEIN_CONFIG if exist "%VEIN_MGMT_CONFIG%" set "VEIN_CONFIG=%VEIN_MGMT_CONFIG%"

echo [env] VEIN_MGMT_ROOT=%VEIN_MGMT_ROOT%
echo [env] VEIN_MGMT_SCRIPTS=%VEIN_MGMT_SCRIPTS%
echo [env] VEIN_MGMT_CONTROLLER=%VEIN_MGMT_CONTROLLER%
if defined VEIN_CONFIG (echo [env] VEIN_CONFIG=%VEIN_CONFIG%) else (echo [env] VEIN_CONFIG=(unset))
echo [env] PYEXE=%PYEXE%

popd >nul 2>&1
exit /b 0
