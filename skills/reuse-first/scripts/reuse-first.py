#!/usr/bin/env python3
"""Run reuse-first from a copied skill folder: python3 scripts/reuse-first.py <command>."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reuse_first.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
