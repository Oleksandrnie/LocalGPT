@echo off
setlocal
for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_localgpt.ps1" %*
exit /b %ERRORLEVEL%
