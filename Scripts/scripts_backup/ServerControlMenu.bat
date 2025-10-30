@echo off
title Vein Server Control Menu

:menu
cls
echo =================================
echo      VEIN SERVER CONTROL PANEL
echo =================================
echo 1. Start Server (with update)
echo 2. Shutdown Server (safe backup)
echo 3. Restart Server (safe full cycle)
echo 4. Run Log Monitor (manual only)
echo 5. Exit
echo =================================
set /p choice="Select option: "

:: SET PATHS
set "PYTHON_PATH=C:\Users\Josh\AppData\Local\Programs\Python\Python311\python.exe"
set "TOOLS_DIR=G:\Servers\VeinServer\Tools"

if "%choice%"=="1" (
    echo Starting server...
    "%PYTHON_PATH%" "%TOOLS_DIR%\start_server.py"
    pause
)

if "%choice%"=="2" (
    echo Shutting down server...
    "%PYTHON_PATH%" "%TOOLS_DIR%\shutdown_server.py"
    pause
)

if "%choice%"=="3" (
    echo Restarting server...
    "%PYTHON_PATH%" "%TOOLS_DIR%\shutdown_server.py"
    "%PYTHON_PATH%" "%TOOLS_DIR%\start_server.py"
    pause
)

if "%choice%"=="4" (
    echo Running monitor_log.py manually...
    "%PYTHON_PATH%" "%TOOLS_DIR%\monitor_log.py"
    pause
)

if "%choice%"=="5" (
    exit
)

goto menu
