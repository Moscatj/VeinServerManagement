@echo off

call "%~dp0env_setup.bat"
if errorlevel 1 (
  echo [Stop/Shutdown] env_setup failed.
  if defined KEEP_OPEN pause
  exit /b 1
)

call "%~dp0StopLogMonitor.bat"
call "%~dp0StopCrashMonitor.bat"
exit /b 0
