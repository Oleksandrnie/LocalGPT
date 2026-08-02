@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 goto run_py
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 goto run_python

echo Python 3.10+ is missing.
set /p INSTALL_PYTHON="Install Python with winget now? [Y/n] "
if /I "%INSTALL_PYTHON%"=="n" exit /b 1
if /I "%INSTALL_PYTHON%"=="no" exit /b 1

where winget >nul 2>nul
if not %ERRORLEVEL% EQU 0 (
  echo winget is unavailable. Install Microsoft App Installer and rerun bootstrap.
  exit /b 1
)

winget install --id Python.Python.3.13 --exact --accept-package-agreements --accept-source-agreements
if not %ERRORLEVEL% EQU 0 exit /b %ERRORLEVEL%

echo Python was installed. If the launcher cannot detect it, reopen PowerShell and rerun this file.

:run_py
py -3 tools\bootstrap_localgpt.py %*
set BOOTSTRAP_EXIT=%ERRORLEVEL%
pause
exit /b %BOOTSTRAP_EXIT%

:run_python
python tools\bootstrap_localgpt.py %*
set BOOTSTRAP_EXIT=%ERRORLEVEL%
pause
exit /b %BOOTSTRAP_EXIT%
