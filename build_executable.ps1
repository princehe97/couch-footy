$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

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

Copy-Item -LiteralPath ".\dist\CouchFooty.exe" -Destination ".\CouchFooty.exe" -Force
Remove-Item -LiteralPath ".\build" -Recurse -Force
Remove-Item -LiteralPath ".\dist" -Recurse -Force
Remove-Item -LiteralPath ".\CouchFooty.spec" -Force

Write-Host "Built CouchFooty.exe"
