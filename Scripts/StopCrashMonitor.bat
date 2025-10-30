@echo off
call "%~dp0env_setup.bat"
if errorlevel 1 (
  echo [Stop/Shutdown] env_setup failed.
  if defined KEEP_OPEN pause
  exit /b 1
)

taskkill /fi "WINDOWTITLE eq Vein Crash Monitor" /f >nul 2>&1
for %%P in (python.exe py.exe) do (
  for /f "tokens=2 delims=," %%I in ('wmic process where "name='%%P' and CommandLine like '%%crash_monitor.py%%'" get ProcessId /format:csv ^| find ","') do taskkill /pid %%I /f >nul 2>&1
)
echo [i] Crash monitor stopped (if it was running).
exit /b 0
