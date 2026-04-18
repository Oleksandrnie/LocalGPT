@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 run_localgpt.py %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python run_localgpt.py %*
  exit /b %ERRORLEVEL%
)

echo Python is not installed or not available in PATH.
exit /b 1
