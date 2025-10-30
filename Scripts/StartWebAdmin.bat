@echo off
call "%~dp0env_setup.bat"
if errorlevel 1 (
  echo [StartWebAdmin] env_setup failed.
  if defined KEEP_OPEN pause
  exit /b 1
)

if not exist "%WEBADMIN_DIR%" (
  echo [!] Web Admin folder not found:
  echo     %WEBADMIN_DIR%
  set KEEP_OPEN=1
  if defined KEEP_OPEN pause
  exit /b 1
)

if not defined WEBADMIN (
  echo [!] No entry *.py found in:
  echo     %WEBADMIN_DIR%
  echo [i] Expected: web_admin.py, app.py, main.py, run.py (or any *.py)
  set KEEP_OPEN=1
  if defined KEEP_OPEN pause
  exit /b 1
)

rem Idempotency: running already?
for %%P in (python.exe py.exe) do (
  for /f "tokens=2 delims=," %%I in ('
    wmic process where "name='%%P' and CommandLine like '%%%WEBADMIN_DIR:\=\\%%%'" get ProcessId /format:csv ^| find ","
  ') do set "RUNNING=1"
)
if defined RUNNING (
  echo [i] Web Admin already running; skipping.
  exit /b 0
)

start "Web Admin" /low cmd /k "title Web Admin & color 09 & echo [Web Admin] Starting... & "%PYEXE%" "%WEBADMIN%""
exit /b 0
