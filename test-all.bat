@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\test-all.ps1"
exit /b %ERRORLEVEL%
