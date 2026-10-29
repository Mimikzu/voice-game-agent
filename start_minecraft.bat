@echo off
setlocal
cd /d "%~dp0"
python "%~dp0voice_game_agent.py" --profile minecraft %*
echo.
echo Mimikzu Minecraft voice controls closed.
pause
