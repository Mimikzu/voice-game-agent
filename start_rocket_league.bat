@echo off
setlocal
cd /d "%~dp0"
python "%~dp0voice_game_agent.py" --profile rocket-league %*
echo.
echo Mimikzu Rocket League voice controls closed.
pause
