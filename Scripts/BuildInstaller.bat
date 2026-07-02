@echo off
setlocal EnableExtensions
set "ERR=0"
title Vein Server Management - Build Installer

rem --- Move to repo root (parent of Scripts)
cd /d "%~dp0"
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

echo [INFO] Repo root: %ROOT%

set "PACKAGE_VERSION=%VEIN_PACKAGE_VERSION%"
if not defined PACKAGE_VERSION (
  for /f "delims=" %%V in ('git describe --tags --abbrev^=0 2^>nul') do set "PACKAGE_VERSION=%%V"
)
if not defined PACKAGE_VERSION set "PACKAGE_VERSION=0.0.0-dev"
if /i "%PACKAGE_VERSION:~0,1%"=="v" set "PACKAGE_VERSION=%PACKAGE_VERSION:~1%"
echo [INFO] Package version: %PACKAGE_VERSION%

echo [INFO] Checking for PyInstaller...
py -3 -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PyInstaller not found. Run: py -3 -m pip install -r requirements-packaging.txt
  goto :error
)
echo [INFO] Step 1/2 - Building VeinManager/VeinTools bundle...
py -3 Controller\Tools\packing\build_gui_exe.py
if errorlevel 1 goto :error

echo [INFO] Step 2/2 - Compiling installer via Inno Setup...
set "ISCC_BIN=%ISCC%"
if not defined ISCC_BIN (
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_BIN=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC_BIN (
  if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_BIN=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC_BIN (
  echo [ERROR] Could not find ISCC.exe. Install Inno Setup 6 or set ISCC env var to its path.
  goto :error
)

"%ISCC_BIN%" /DMyAppVersion=%PACKAGE_VERSION% "%ROOT%\Installer\VeinServerManager.iss"
if errorlevel 1 goto :error

echo(
echo [SUCCESS] Installer available in dist\installer\VeinServerManagement-Setup.exe
goto :done

:error
echo(
echo [FAILED] Packaging or installer build failed.
set "ERR=1"

:done
echo(
pause
exit /b %ERR%

