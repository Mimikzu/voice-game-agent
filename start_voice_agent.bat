@echo off
setlocal
cd /d "%~dp0"
echo Select a game profile:
echo   1. Minecraft
echo   2. Rocket League
echo   3. Generic WASD controls
set /p GAME_PROFILE=Enter 1, 2, or 3: 
if "%GAME_PROFILE%"=="1" set PROFILE=minecraft
if "%GAME_PROFILE%"=="2" set PROFILE=rocket-league
if "%GAME_PROFILE%"=="3" set PROFILE=generic
if not defined PROFILE (
    echo Invalid selection.
    pause
    exit /b 1
)
python "%~dp0voice_game_agent.py" --profile "%PROFILE%" %*
echo.
echo Mimikzu Voice Game Agent closed.
pause
