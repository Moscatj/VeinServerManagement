@echo off
setlocal
cd /d "%~dp0"

REM Resolve script paths (prefer .\Tools\*.py)
set "BASE=%~dp0"
set "TOOLS=%BASE%Tools"
set "MONITOR=%TOOLS%\monitor_log.py"
set "CRASH=%TOOLS%\crash_monitor.py"
if not exist "%MONITOR%" set "MONITOR=%BASE%\monitor_log.py"
if not exist "%CRASH%"  set "CRASH=%BASE%\crash_monitor.py"

REM ---- If Windows Terminal is available, use tabs ----
where wt >nul 2>&1
if %errorlevel%==0 (
    REM One window, two tabs: Log Monitor + Crash Monitor
    REM NOTE: inner quotes must be doubled ("") inside the outer quotes
    wt -w 0 ^
      nt --title "Vein Log Monitor" cmd /k "cd /d ""%~dp0Tools"" && title Vein Log Monitor && color 0E && echo [Log Monitor] Starting... && py -3 ""%MONITOR%""" ^
      ; nt --title "Vein Crash Monitor" cmd /k "cd /d ""%~dp0Tools"" && title Vein Crash Monitor && color 0C && echo [Crash Monitor] Starting... && py -3 ""%CRASH%"""
    exit /b 0
)

REM ---- Fallback: classic two windows (if wt.exe not present) ----
start "" cmd /k "title Vein Log Monitor & color 0E & echo [Log Monitor] Starting... & py -3 ""%MONITOR%"""
start "" cmd /k "title Vein Crash Monitor & color 0C & echo [Crash Monitor] Starting... & py -3 ""%CRASH%"""
exit /b 0
