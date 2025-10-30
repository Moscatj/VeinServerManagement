@echo off
call "%~dp0env_setup.bat" || exit /b 1
taskkill /fi "WINDOWTITLE eq Vein Log Monitor" /f >nul 2>&1
for %%P in (python.exe py.exe) do (
  for /f "tokens=2 delims=," %%I in ('wmic process where "name='%%P' and CommandLine like '%%monitor_log.py%%'" get ProcessId /format:csv ^| find ","') do taskkill /pid %%I /f >nul 2>&1
)
echo [i] Log monitor stopped (if it was running).
exit /b 0
