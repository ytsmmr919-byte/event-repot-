@echo off
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Setup has not been completed. Run the setup file "1_..." first.
    pause
    exit /b 1
)

uv run --no-dev python -m event_report
pause
