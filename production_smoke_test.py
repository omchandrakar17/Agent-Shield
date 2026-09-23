#!/usr/bin/env python3
"""Backward-compatible entrypoint — delegates to scripts/production_smoke_test.py."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "scripts" / "production_smoke_test.py"

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, str(SCRIPT), *sys.argv[1:]]))
