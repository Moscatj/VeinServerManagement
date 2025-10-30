@echo off
setlocal
cd /d "%~dp0"

echo === Vein Health Check ===
echo.
echo [Server processes]
tasklist /fi "imagename eq VeinServer.exe"
tasklist /fi "imagename eq VeinServer-Win64-Test.exe"
echo.
echo [Monitors]
tasklist /v /fi "imagename eq cmd.exe" | findstr /i /c:"Vein Log Monitor" /c:"Vein Crash Monitor"

for %%P in (python.exe py.exe) do (
  echo.
  echo [Python %%P with monitor scripts]
  wmic process where "name='%%P' and (CommandLine like '%%monitor_log.py%%' or CommandLine like '%%crash_monitor.py%%')" get ProcessId,CommandLine /format:list
)
echo.
pause
