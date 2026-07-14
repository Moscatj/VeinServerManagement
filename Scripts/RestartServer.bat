@echo off
call "%~dp0StopServer.bat"
if errorlevel 1 exit /b %errorlevel%
call "%~dp0StartServer.bat"
exit /b %errorlevel%
