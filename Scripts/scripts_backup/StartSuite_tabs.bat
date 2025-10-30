@echo off
setlocal
cd /d "%~dp0"

set "BASE=%~dp0"
set "TOOLS=%BASE%Tools"
set "START=%TOOLS%\start_server.py"
set "MONITOR=%TOOLS%\monitor_log.py"
set "CRASH=%TOOLS%\crash_monitor.py"

REM ---- Windows Terminal (tabs) if available ----
where wt >nul 2>&1
if %errorlevel%==0 (
    wt -w 0 ^
      nt --title "Vein Server" cmd /k "cd /d ""%TOOLS%"" && title Vein Server && color 0A && py -3 ""%START%""" ^
      ; nt --title "Vein Log Monitor" cmd /k "cd /d ""%TOOLS%"" && title Vein Log Monitor && color 0E && py -3 ""%MONITOR%""" ^
      ; nt --title "Vein Crash Monitor" cmd /k "cd /d ""%TOOLS%"" && title Vein Crash Monitor && color 0C && py -3 ""%CRASH%"""
    exit /b 0
)

REM ---- Fallback: classic three windows ----
start "" cmd /k "cd /d ""%TOOLS%"" & title Vein Server & color 0A & py -3 ""%START%"""
start "" cmd /k "cd /d ""%TOOLS%"" & title Vein Log Monitor & color 0E & py -3 ""%MONITOR%"""
start "" cmd /k "cd /d ""%TOOLS%"" & title Vein Crash Monitor & color 0C & py -3 ""%CRASH%"""
exit /b 0
