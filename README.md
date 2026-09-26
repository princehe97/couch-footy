# Couch Footy

A desktop Australian-rules football match simulator.

## Easiest option

Download `CouchFooty.exe`, place it in its own writable folder, and double-click
it. On first launch it creates an editable `TeamSelection.csv` beside the
executable. Match reports are written to an `outputs` folder in the same place.

## First run

1. Install Python 3.11 or newer from <https://www.python.org/downloads/>.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Start the game:

   ```powershell
   python run_game.py
   ```

Edit `TeamSelection.csv` before starting if you want to change the teams,
players, or player attributes. Match reports are created automatically in a
new `outputs` folder after the game runs.

## Save and reuse teams

1. Choose **Play Footy** to open match setup. The current CSV teams appear first.
2. Choose **Save as new** under either team to keep its roster and all seven
   player point allocations. Each team is saved independently.
3. Next time you open Couch Footy, choose **Saved teams** under Home or Away.
   Select a team, review its players with the arrow buttons, and choose **Start match**.
   Saved teams work even if the original CSV is unavailable.

To edit a saved roster, select it under **Saved teams**, then choose **Edit**.
Select a player to edit their name or use the **+ / -** controls to adjust their
allocations. Each player has at most 100 points; reduce an allocation before
adding points elsewhere. Choose **Swap position...**, then another player
(on either page) to exchange positions, keeping their names and attributes together.
Blank or duplicate player names are rejected, including differences only in case
or surrounding spaces. You can also edit the team name. Team and player names must use ASCII characters
(unaccented letters, numbers and standard punctuation); unsupported names show a validation error.
**Save changes** updates that saved team; **Cancel** or Escape discards all edits.
For CSV teams, **Apply changes** returns to setup, where **Save as new** stores them.
You can still use **Reload CSV** and **Update saved...** to replace a saved roster.
**Save as new** creates a separate copy. The picker displays
each team's unique ID so teams with identical names remain distinguishable.

Teams live in the `saved_teams` folder beside `CouchFooty.exe` (or beside
`run_game.py` for source runs), with one JSON file per team. Keep this folder
when upgrading or moving the app. Season, round, and match ID belong to the
match setup and can be edited there; they are not stored in team files.
The roster preview shows strength, speed, agility, skill, endurance, pressure,
and aura in that order. **File issues** explains any roster or saved-file errors.

Run the automated storage and setup checks with `python -m unittest discover -s tests -v`.
