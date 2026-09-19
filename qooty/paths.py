"""Project root resolution so assets and spreadsheets load next to the original game files."""

from pathlib import Path

# The root directory of the refactored project (containing start.png, gamescreen.png, etc.)
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def ensure_project_root_cwd() -> None:
    """Match the original game behaviour: relative paths resolve from the classic project folder."""
    import os

    os.chdir(PROJECT_ROOT)


def get_output_path(filename: str) -> str:
    """Returns an absolute path to a file in the 'outputs' directory, creating the directory if needed."""
    out_dir = PROJECT_ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return str(out_dir / filename)
