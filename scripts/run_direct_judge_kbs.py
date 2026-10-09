"""Run the final 360x1 direct LLM-as-a-judge baseline on L3S/KBS."""

from __future__ import annotations

import sys

from run_final_baselines import main


if __name__ == "__main__":
    raise SystemExit(main(["--baseline", "direct-judge", *sys.argv[1:]]))
