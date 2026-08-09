"""Small command-line entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-data", help="Run canonical data-contract checks")
    args = parser.parse_args()

    if args.command == "validate-data":
        script = Path(__file__).resolve().parents[2] / "scripts" / "validate_data.py"
        raise SystemExit(subprocess.call([sys.executable, str(script)]))
