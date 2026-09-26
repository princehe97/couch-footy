"""Resolve writable app files and bundled resources in source or PyInstaller builds."""

import shutil
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    # User-editable files and reports live beside CouchFooty.exe.
    PROJECT_ROOT: Path = Path(sys.executable).resolve().parent
    # A one-file build extracts bundled resources into this temporary folder.
    RESOURCE_ROOT: Path = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    RESOURCE_ROOT = PROJECT_ROOT


def get_resource_path(filename: str) -> Path:
    """Return an application asset path in source and frozen builds."""
    return RESOURCE_ROOT / filename


def ensure_project_root_cwd() -> None:
    """Use the app folder and create its editable default roster on first run."""
    import os

    os.chdir(PROJECT_ROOT)
    roster = PROJECT_ROOT / "TeamSelection.csv"
    bundled_roster = RESOURCE_ROOT / "TeamSelection.csv"
    if not roster.exists() and bundled_roster.exists() and roster != bundled_roster:
        shutil.copy2(bundled_roster, roster)


def get_output_path(filename: str) -> str:
    """Returns an absolute path to a file in the 'outputs' directory, creating the directory if needed."""
    out_dir = PROJECT_ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return str(out_dir / filename)
