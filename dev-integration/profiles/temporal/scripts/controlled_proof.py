#!/usr/bin/env python3
from pathlib import Path
import sys


PROFILE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROFILE_ROOT))

from controlled_proof.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
