@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem --- Resolve management root from this file path ---
set "THIS_DIR=%~dp0"
for %%~ in (.) do rem noop
rem If env_setup.bat lives in Scripts\, VEIN_MGMT_ROOT is .. from there:
pushd "%THIS_DIR%\.."
set "VEIN_MGMT_ROOT=%CD%"
popd

set "VEIN_MGMT_SCRIPTS=%VEIN_MGMT_ROOT%\Scripts"
set "VEIN_MGMT_CONTROLLER=%VEIN_MGMT_ROOT%\Controller"

rem --- SAFE logging (avoid parentheses or escape them) ---
echo [env] VEIN_MGMT_ROOT=%VEIN_MGMT_ROOT%
echo [env] VEIN_MGMT_SCRIPTS=%VEIN_MGMT_SCRIPTS%
echo [env] VEIN_MGMT_CONTROLLER=%VEIN_MGMT_CONTROLLER%

rem Example: if you must touch PATH, do NOT echo it and always quote sets:
rem set "PATH=%PATH%;C:\Program Files\Common Files\SomeTool\bin"
rem If you must echo text with parentheses, escape them like: echo ^(Controller^)

exit /b 0
