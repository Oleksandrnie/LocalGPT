@echo off
setlocal

cd /d "%~dp0"
call "%~dp0start_localgpt.bat" %* --host 0.0.0.0
exit /b %ERRORLEVEL%
