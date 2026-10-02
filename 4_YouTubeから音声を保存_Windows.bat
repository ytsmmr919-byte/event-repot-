@echo off
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Setup has not been completed. Run the setup file "1_..." first.
    pause
    exit /b 1
)

rem YouTube changes often; keep yt-dlp up to date (ignored when offline)
uv sync --no-dev -q --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs >nul 2>nul
uv run --no-dev python -m event_report --youtube-audio
pause
