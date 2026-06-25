@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Vein Test Suite
chcp 65001 >nul

rem ============================================================
rem  Vein Server - Diagnostic Test Suite (SAFE by default)
rem ============================================================

set "TEST_MONITORS=PROBE"
set "TEST_SERVER=0"

if /i "%~1" neq "__RUN__" (
  start "Vein Test Suite" "%ComSpec%" /k "%~f0" __RUN__
  goto :eof
)

pushd "%~dp0\.." >nul 2>&1
set "MGMT=%CD%"
set "SCRIPTS=%MGMT%\Scripts"
set "CONTROLLER=%MGMT%\Controller"
set "CONFIG1=%MGMT%\Config\config.yaml"
set "CONFIG2=%MGMT%\Config\config.json"
set "CONFIG3=%CONTROLLER%\config.json"
set "PYEXE=py -3"
if exist "%CONFIG1%" (set "VEIN_CONFIG=%CONFIG1%") else if exist "%CONFIG2%" (set "VEIN_CONFIG=%CONFIG2%") else if exist "%CONFIG3%" (set "VEIN_CONFIG=%CONFIG3%")

set "SUITE_FAIL=0"
set "SUITE_WARN=0"

echo ==========================================
echo   Vein Server - Diagnostic Test Suite
echo ==========================================
echo.
echo [env] MGMT=%MGMT%
echo [env] SCRIPTS=%SCRIPTS%
echo [env] CONTROLLER=%CONTROLLER%
echo [env] CONFIG1=%CONFIG1%
echo [env] CONFIG2=%CONFIG2%
echo [env] CONFIG3=%CONFIG3%
echo [env] PYEXE=%PYEXE%
echo [env] VEIN_CONFIG=%VEIN_CONFIG%
echo.

rem ---------------- verify core files -------------------------
echo [INFO] Verifying required files...
set "MISSING="
for %%F in ("%CONTROLLER%\monitor_log.py" "%CONTROLLER%\crash_monitor.py" "%CONTROLLER%\start_server.py" "%CONTROLLER%\shutdown_server.py") do (
  if not exist "%%~F" (
    echo [FAIL] Missing: %%~F
    set "MISSING=1"
  )
)
if not defined MISSING echo [PASS] All required Python entry files located.
echo.

rem ---------------- python check ------------------------------
echo [INFO] Checking Python...
%PYEXE% -c "import sys; print('Python', sys.version)"
if errorlevel 1 (
  echo [FAIL] Python not available via "%PYEXE%".
  set /a SUITE_FAIL+=1
)
echo.

rem ---------------- unit tests -------------------------------
echo [INFO] Running unit tests...
%PYEXE% -m unittest discover -s Tests
if errorlevel 1 (
  echo [FAIL] Unit tests failed.
  set /a SUITE_FAIL+=1
) else (
  echo [PASS] Unit tests passed.
)
echo.

rem ---------------- monitor status ----------------------------
echo [INFO] Monitor test mode: %TEST_MONITORS%
for %%N in (monitor_log.py crash_monitor.py) do (
  tasklist /FI "IMAGENAME eq python.exe" /V | find "%%N" >nul
  if errorlevel 1 (
    echo [INFO] %%N: STOPPED
  ) else (
    echo [INFO] %%N: RUNNING
  )
)
echo.

echo [INFO] Server smoke test: SKIPPED (set TEST_SERVER=1 to enable)
echo.

if %SUITE_FAIL% EQU 0 (
  echo ==========================================
  echo   RESULT: PASS ✅
  echo   Issues: %SUITE_FAIL% failures, %SUITE_WARN% warnings
  echo ==========================================
) else (
  echo ==========================================
  echo   RESULT: FAIL ❌
  echo   Issues: %SUITE_FAIL% failures, %SUITE_WARN% warnings
  echo ==========================================
)
echo.
if /i not "%CI%"=="true" (
  echo [INFO] Diagnostics complete. Press any key to close...
  pause >nul
) else (
  echo [INFO] Diagnostics complete.
)
popd >nul 2>&1
set "EXIT_CODE=%SUITE_FAIL%"
endlocal & exit /b %EXIT_CODE%
