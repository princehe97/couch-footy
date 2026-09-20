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
