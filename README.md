# 🎮 Mimikzu Voice Game Agent

Voice controls for **Minecraft** and **Rocket League**, made by Mimikzu.

Speak a command and the program sends the matching keyboard or mouse input. Speech recognition runs locally after the model downloads.

## Windows setup

1. Install Python 3.10 or later.
2. Download or clone this repository and open its folder.
3. Double-click `setup_windows.bat` once.
4. Start the game profile you want:
   - Minecraft: `start_minecraft.bat`
   - Rocket League: `start_rocket_league.bat`
5. Wait for **Listening**, focus the game, and speak. Press **F12** to stop.

The first run downloads the speech model and needs an internet connection. Keep the console window open while playing.

## Voice commands

**Minecraft:** `jump`, `forward`, `back`, `left`, `right`, `sprint`, `sneak`, `use`, `attack`, `inventory`, and `slot 1` through `slot 9`.

**Rocket League:** `jump`, `double jump`, `boost`, `accelerate`, `reverse`, `left`, `right`, `powerslide`, and `ball cam`.

You can also say commands such as `hold forward for one second`. Holds are capped at two seconds.

## Controls

The profiles use common keyboard and mouse bindings. If they don’t match your in-game settings, edit `MINECRAFT_BINDINGS` or `ROCKET_LEAGUE_BINDINGS` in `voice_game_agent.py`.

## Tests

Run the command tests with:

```powershell
python -m unittest -v
