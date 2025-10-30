@echo off
setlocal
cd /d "%~dp0"

:: ---- Elevation check ----
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting Administrator permissions...
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

title Vein Server Shutdown (Admin)
color 0C
echo =====================================
echo   Vein Server - Shutdown Server & Monitors
echo =====================================

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0shutdown_server.py"
) else (
  python "%~dp0shutdown_server.py"
)

set RC=%ERRORLEVEL%
echo.
echo [Exit] shutdown_server.py returned %RC%
echo =====================================
echo   Done. You can close this window.
echo =====================================
timeout /t 2 /nobreak >nul
endlocal
exit /b %RC%
