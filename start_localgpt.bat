@echo off
setlocal

cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
  "%~dp0venv\Scripts\python.exe" run_localgpt.py %*
  exit /b %ERRORLEVEL%
)

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

echo Python 3.11+ is not installed or not available in PATH.
exit /b 1
