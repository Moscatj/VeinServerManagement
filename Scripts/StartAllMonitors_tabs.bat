@echo off
setlocal
cd /d "%~dp0"

where wt >nul 2>&1
if not %errorlevel%==0 (
  call "%~dp0StartMonitors.bat"
  exit /b %errorlevel%
)

call "%~dp0env_setup.bat" || exit /b 1
wt -w 0 ^
  nt --title "Vein Log Monitor"    cmd /k "title Vein Log Monitor    && color 0E && call "%~dp0StartLogMonitor.bat"" ^
  ; nt --title "Vein Crash Monitor" cmd /k "title Vein Crash Monitor  && color 0C && call "%~dp0StartCrashMonitor.bat""
exit /b 0
