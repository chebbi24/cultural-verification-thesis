import unittest

from cultural_verifier.ids import (
    CANDIDATE_RE,
    normalize_legacy_prompt_id,
    normalize_subdimension_id,
)


class IdTests(unittest.TestCase):
    def test_normalize_subdimension_id(self) -> None:
        self.assertEqual(normalize_subdimension_id("D01S1"), "D01S01")
        self.assertEqual(normalize_subdimension_id("D10S03"), "D10S03")

    def test_normalize_legacy_prompt_id(self) -> None:
        self.assertEqual(normalize_legacy_prompt_id("G6"), "LG006")
        self.assertEqual(normalize_legacy_prompt_id("G60"), "LG060")

    def test_candidate_ids(self) -> None:
        self.assertIsNotNone(CANDIDATE_RE.fullmatch("RT001-C1"))
        self.assertIsNotNone(CANDIDATE_RE.fullmatch("PLT030-C4"))
        self.assertIsNone(CANDIDATE_RE.fullmatch("VT001-a"))
