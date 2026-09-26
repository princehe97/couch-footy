$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name CouchFooty `
    --add-data "start.png;." `
    --add-data "gamescreen.png;." `
    --add-data "TeamSelection.csv;." `
    --add-data "qooty/commentary.json;qooty" `
    run_game.py

Write-Host "Built dist\CouchFooty.exe"
