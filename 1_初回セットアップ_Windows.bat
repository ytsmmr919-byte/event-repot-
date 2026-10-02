@echo off
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv, the Python package manager...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
)
where uv >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] uv could not be installed. Please contact your administrator.
    pause
    exit /b 1
)

echo Installing Python and required libraries. This may take a few minutes...
uv sync --no-dev
if errorlevel 1 (
    echo.
    echo [ERROR] Setup failed. Check your internet connection and try again.
    pause
    exit /b 1
)

uv run --no-dev python -m event_report --setup
pause
