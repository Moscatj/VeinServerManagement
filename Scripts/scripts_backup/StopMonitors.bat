@echo off
setlocal
cd /d "%~dp0"
title RHG Stop Monitors
color 0E

echo =====================================
echo     RHG - Stop Monitoring Scripts
echo =====================================
echo.

REM --- detect if psutil is available for Python (optional) ---
set "HAS_PYTHON="
where py >nul 2>&1
if %errorlevel%==0 set "HAS_PYTHON=1"

REM --- function to kill monitors using tasklist/taskkill ---
echo [1/2] Stopping Log Monitor...
for /f "tokens=2 delims=," %%A in ('tasklist /FI "WINDOWTITLE eq Vein Log Monitor" /FO CSV 2^>nul') do (
    taskkill /PID %%~A /T /F >nul 2>&1
)
REM fallback: kill by filename
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq Vein Log Monitor" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Vein Log Monitor" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq VeinLogMonitor" /T /F >nul 2>&1

echo [2/2] Stopping Crash Monitor...
for /f "tokens=2 delims=," %%A in ('tasklist /FI "WINDOWTITLE eq Vein Crash Monitor" /FO CSV 2^>nul') do (
    taskkill /PID %%~A /T /F >nul 2>&1
)
REM fallback: kill by filename
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq Vein Crash Monitor" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Vein Crash Monitor" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq VeinCrashMonitor" /T /F >nul 2>&1

echo.
echo =====================================
echo   Monitors stop attempt complete
echo =====================================
echo (If they were not running, this is normal.)
echo.
timeout /t 3 /nobreak >nul
endlocal
exit /b 0
