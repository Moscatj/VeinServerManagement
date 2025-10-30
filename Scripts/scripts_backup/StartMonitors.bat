@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

:: ===========================================================
::  RHG Server Monitoring Launcher
:: ===========================================================

title RHG Monitor Launcher
color 0A
echo =====================================
echo   Starting RHG Monitoring Processes
echo =====================================

:: Resolve script locations (prefer .\Tools\*.py, else same dir)
set "BASE=%~dp0"
set "TOOLS=%BASE%Tools"
if exist "%TOOLS%\monitor_log.py" (
  set "MONITOR=%TOOLS%\monitor_log.py"
  set "CRASH=%TOOLS%\crash_monitor.py"
) else (
  set "MONITOR=%BASE%\monitor_log.py"
  set "CRASH=%BASE%\crash_monitor.py"
)

:: Quick sanity print (comment out later if you want)
echo Using MONITOR: %MONITOR%
echo Using CRASH  : %CRASH%
echo.

:: --- Launch Log Monitor ---
echo Launching Log Monitor...
for /f "tokens=*" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /V ^| find /I "monitor_log.py"') do set FOUND_LOG=1
if not defined FOUND_LOG (
  start "" %ComSpec% /k pushd "%~dp0" ^&^& pushd "%~dp0Tools" ^&^& title Vein Log Monitor ^&^& color 0E ^&^& echo [Log Monitor] Starting... ^&^& py -3 "%MONITOR%"
) else (
  echo   Log monitor already running; skipping.
)
set FOUND_LOG=

:: --- Launch Crash Monitor ---
echo Launching Crash Monitor...
for /f "tokens=*" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /V ^| find /I "crash_monitor.py"') do set FOUND_CRASH=1
if not defined FOUND_CRASH (
  start "" %ComSpec% /k pushd "%~dp0" ^&^& pushd "%~dp0Tools" ^&^& title Vein Crash Monitor ^&^& color 0C ^&^& echo [Crash Monitor] Starting... ^&^& py -3 "%CRASH%"
) else (
  echo   Crash monitor already running; skipping.
)
set FOUND_CRASH=

echo.
echo =====================================
echo   Monitors launched successfully
echo   - Each has its own console window.
echo   - This launcher can now be closed.
echo =====================================

timeout /t 2 /nobreak >nul
exit /b 0
