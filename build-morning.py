#!/usr/bin/env python3
"""Entry point: build one morning edition.

  ./build-morning.py --date 2026-09-08 --send-feishu --alert
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from morning.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
