@echo off
title RHG Vein Server Control - Web Admin

echo =====================================
echo   Launching RHG Web Admin Interface
echo =====================================

cd /d G:\Servers\VeinServer\Tools\WebAdmin

:: OPTIONAL - Activate virtual environment if you have one
:: call venv\Scripts\activate

python web_admin.py

echo =====================================
echo   Web Admin process exited.
echo =====================================
pause
