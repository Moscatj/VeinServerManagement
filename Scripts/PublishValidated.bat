@echo off
setlocal
pushd "%~dp0\.." >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PublishValidated.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul 2>&1
endlocal & exit /b %EXIT_CODE%
