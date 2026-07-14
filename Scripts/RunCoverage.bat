@echo off
setlocal EnableExtensions
title Vein Coverage Report

pushd "%~dp0\.." >nul 2>&1
set "VEIN_DISABLE_DISCORD=1"

if not defined PYTHON_BIN (
  py -3.12 -m coverage --version >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_BIN=py -3.12"
  ) else (
    set "PYTHON_BIN=py -3"
  )
)

%PYTHON_BIN% -m coverage --version >nul 2>&1
if errorlevel 1 (
  echo [FAIL] coverage.py is not installed.
  echo Install dev requirements first:
  echo   py -3.12 -m pip install -r requirements-dev.txt
  popd >nul 2>&1
  exit /b 1
)

%PYTHON_BIN% -m coverage erase
%PYTHON_BIN% -m coverage run --source=Controller -m unittest discover -s Tests
if errorlevel 1 (
  echo [FAIL] Unit tests failed under coverage.
  popd >nul 2>&1
  exit /b 1
)

%PYTHON_BIN% -m coverage report -m
popd >nul 2>&1
endlocal
