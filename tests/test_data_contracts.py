import subprocess
import sys
import unittest
from pathlib import Path


class DataContractTests(unittest.TestCase):
    def test_canonical_data_contracts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts/validate_data.py")],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
