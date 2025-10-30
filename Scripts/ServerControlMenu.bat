@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"
title Vein Server Control Menu

:menu
cls
echo =====================================
echo          VEIN SERVER MENU
echo =====================================
echo  1) Start Server (+ Monitors)
echo  2) Start Server only
echo  3) Restart Server
echo  4) Shutdown Server
echo  ------------------------------
echo  5) Start Log Monitor
echo  6) Stop  Log Monitor
echo  7) Start Crash Monitor
echo  8) Stop  Crash Monitor
echo  9) Start ALL Monitors
echo  10) Stop  ALL Monitors
echo  ------------------------------
echo 11) Start Web Admin
echo 12) Health Check
echo 13) Exit
echo.
set /p choice=Select an option: 

if "%choice%"=="1"  call "%~dp0StartServerWithMonitors.bat" & pause & goto menu
if "%choice%"=="2" call "%~dp0StartServerOnly.bat" & pause & goto menu
if "%choice%"=="3"  call "%~dp0RestartServer.bat" & pause & goto menu
if "%choice%"=="4"  call "%~dp0ShutdownServer.bat" & pause & goto menu

if "%choice%"=="5"  call "%~dp0StartLogMonitor.bat" & pause & goto menu
if "%choice%"=="6"  call "%~dp0StopLogMonitor.bat"  & pause & goto menu
if "%choice%"=="7"  call "%~dp0StartCrashMonitor.bat" & pause & goto menu
if "%choice%"=="8"  call "%~dp0StopCrashMonitor.bat"  & pause & goto menu
if "%choice%"=="9"  call "%~dp0StartAllMonitors.bat" & pause & goto menu
if "%choice%"=="10"  call "%~dp0StopAllMonitors.bat"  & pause & goto menu
if "%choice%"=="11" call "%~dp0StartWebAdmin.bat" & pause & goto menu
if "%choice%"=="12" call "%~dp0HealthCheck.bat"     & pause & goto menu
if "%choice%"=="13" exit /b 0

echo Invalid selection.
timeout /t 1 >nul
goto menu
