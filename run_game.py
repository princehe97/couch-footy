"""
Launch QootyPy from the refactored tree.

Changes the working directory to the classic project folder (next to python_qooty.py)
so TeamSelection.csv (preferred) or TeamSelection.xls, images, and outputs use the same paths as the original.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REFACTORED_ROOT = Path(__file__).resolve().parent
if str(_REFACTORED_ROOT) not in sys.path:
	sys.path.insert(0, str(_REFACTORED_ROOT))


def _entry() -> None:
	from qooty.paths import ensure_project_root_cwd

	ensure_project_root_cwd()
	from qooty.engine import main

	main()


if __name__ == "__main__":
	_entry()
