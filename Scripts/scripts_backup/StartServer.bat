@echo off
title RHG Vein Server Control - Full Startup

echo =====================================
echo  Starting Monitor Processes
echo =====================================

:: Launch monitors in separate persistent window
start "RHG Monitor Control" cmd /c G:\Servers\VeinServer\StartMonitors_tab.bat

echo =====================================
echo  Launching Vein Server Process
echo =====================================

cd /d G:\Servers\VeinServer\Tools

python start_server.py

echo =====================================
echo  Startup Complete
echo =====================================
pause
