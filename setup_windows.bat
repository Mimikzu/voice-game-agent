@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo Setup failed. Check that Python is installed and available as "python".
    pause
    exit /b 1
)
echo.
echo Setup complete. Double-click start_voice_agent.bat to launch.
pause
