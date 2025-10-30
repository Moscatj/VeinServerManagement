@echo off
call "%~dp0env_setup.bat"
if errorlevel 1 (
  echo [Wrapper] env_setup failed.
  if defined KEEP_OPEN pause
  exit /b 1
)

call "%~dp0StartAllMonitors.bat"
if errorlevel 1 (
  echo [Wrapper] Failed to start monitors.
  if defined KEEP_OPEN pause
  exit /b 1
)

call "%~dp0StartServerOnly.bat"
exit /b %errorlevel%
