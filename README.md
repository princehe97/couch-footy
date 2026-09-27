# Couch Footy

A desktop Australian-rules football match simulator.

## Play

Download `CouchFooty.exe` from the [latest release](https://github.com/princehe97/couch-footy/releases/latest),
place it in a writable folder, and double-click it. Python is not required.
The app creates `TeamSelection.csv` on first launch and writes reports to `outputs/`.

Choose **Play Footy**, select each team from the CSV or **Saved teams**, then **Start match**.
Use **Edit** to change names, allocate points or swap positions.

- **Save as new** creates a separate saved team; **Save changes** updates it.
- **Apply changes** keeps CSV-team edits in match setup; use **Save as new** to keep them between sessions.
- **Reload CSV** reloads both teams. **Update saved...** replaces a chosen saved roster after confirmation.
- **Cancel** or Escape discards editor changes. **File issues** explains loading errors.

Each team needs 20 players, one per position. Player names must be unique across both teams,
ignoring case and surrounding spaces. Use names without accents, emojis or special symbols.
Each player has up to 100 points across seven attributes.

Keep `TeamSelection.csv` and `saved_teams/` when upgrading. Saved teams work without the CSV;
season, round and match ID are set separately for each match.

## Development

Requires Python 3.11+ on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_game.py
```

Build: `./build_executable.ps1` replaces `CouchFooty.exe` and removes temporary build files.
