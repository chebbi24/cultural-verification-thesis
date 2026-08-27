"""Optional live test for the local Ollama structured-output contract.

Run only when Qwen is installed and the local Ollama server is running:
RUN_OLLAMA_INTEGRATION=1 python -m unittest tests.test_ollama_integration -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from verifier import CulturalVerifier, OllamaClient


@unittest.skipUnless(
    os.getenv("RUN_OLLAMA_INTEGRATION") == "1",
    "Set RUN_OLLAMA_INTEGRATION=1 to exercise the local Ollama server.",
)
class OllamaIntegrationTests(unittest.TestCase):
    def test_dimension_plan_matches_the_enforced_schema(self) -> None:
        verifier = CulturalVerifier(OllamaClient(model="qwen3:4b"))
        plan = verifier.plan_dimensions(
            "How should I write a first email to a German professor?",
            "Germany",
            "D02",
        )
        self.assertEqual(plan[0].dimension_id, "D02")
        self.assertEqual(plan[0].relevance, "primary")
        self.assertLessEqual(len(plan), 3)


if __name__ == "__main__":
    unittest.main()
