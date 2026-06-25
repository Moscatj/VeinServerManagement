@echo off
setlocal EnableExtensions
title Vein Coverage Report

pushd "%~dp0\.." >nul 2>&1

py -3 -m coverage --version >nul 2>&1
if errorlevel 1 (
  echo [FAIL] coverage.py is not installed.
  echo Install dev requirements first:
  echo   py -3 -m pip install -r requirements-dev.txt
  popd >nul 2>&1
  exit /b 1
)

py -3 -m coverage erase
py -3 -m coverage run --source=Controller -m unittest discover -s Tests
if errorlevel 1 (
  echo [FAIL] Unit tests failed under coverage.
  popd >nul 2>&1
  exit /b 1
)

py -3 -m coverage report -m
popd >nul 2>&1
endlocal
