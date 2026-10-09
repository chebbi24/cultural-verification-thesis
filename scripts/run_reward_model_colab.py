"""Run the final 360x1 Skywork Reward V2 baseline.

Designed for Google Colab or another CUDA machine. Install dependencies with:
    pip install -e '.[rm]'
"""

from __future__ import annotations

import sys

from run_final_baselines import main


if __name__ == "__main__":
    raise SystemExit(main(["--baseline", "reward-model", *sys.argv[1:]]))
