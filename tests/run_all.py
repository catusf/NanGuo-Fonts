"""Single entry point invoked after every font rebuild.

Just delegates to pytest so the suite has one source of truth. Exits with
pytest's return code so CI / wrapper scripts can gate on it.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    return subprocess.call(
        [sys.executable, "-m", "pytest", "tests"],
        cwd=str(root),
    )


if __name__ == "__main__":
    sys.exit(main())
