from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from xyzgl.grounding.corpus import Corpus
from xyzgl.grounding.prompting import build_grounding
from xyzgl.grounding.retrieval import Snippet


class GroundingPromptingHeaderTests(unittest.TestCase):
    def test_skips_oversized_first_header_and_keeps_later_fitting_snippet(self) -> None:
        huge_id = "a" * 500
        huge_title = "B" * 500
        snippets = [
            Snippet(source_id=huge_id, source_title=huge_title, passage_ordinal=0, score=1.0, excerpt="arc length control"),
            Snippet(source_id="fitup_notes", source_title="Fit-up notes", passage_ordinal=1, score=0.9, excerpt="fit up and tack weld spacing matter"),
        ]

        with patch("xyzgl.grounding.prompting._cached_corpus", return_value=Corpus(sources=[], passages=[])):
            with patch("xyzgl.grounding.prompting.retrieve_snippets", return_value=snippets):
                text, meta = build_grounding(Path("."), "fit up spacing", max_snippets=2, max_chars=120)

        self.assertIn("[src:fitup_notes:1] Fit-up notes", text)
        self.assertNotIn(huge_id[:80], text)
        self.assertEqual(meta["snippets"], [{"source_id": "fitup_notes", "passage_ordinal": 1, "score": 0.9}])

    def test_clamps_header_source_id_and_title_before_emitting_grounding(self) -> None:
        huge_id = "demo_source_" + ("x" * 240)
        huge_title = "Long curriculum title " + ("Y" * 240)
        snippets = [
            Snippet(
                source_id=huge_id,
                source_title=huge_title,
                passage_ordinal=3,
                score=1.0,
                excerpt="travel speed and heat control need balance across the puddle",
            )
        ]

        with patch("xyzgl.grounding.prompting._cached_corpus", return_value=Corpus(sources=[], passages=[])):
            with patch("xyzgl.grounding.prompting.retrieve_snippets", return_value=snippets):
                text, meta = build_grounding(Path("."), "travel speed", max_snippets=1, max_chars=220)

        self.assertTrue(text)
        first_line = text.splitlines()[0]
        self.assertLessEqual(len(first_line), 193)
        self.assertIn("[src:", first_line)
        self.assertIn(":3]", first_line)
        self.assertNotIn(huge_id, first_line)
        self.assertNotIn(huge_title, first_line)
        self.assertEqual(meta["snippets"], [{"source_id": huge_id, "passage_ordinal": 3, "score": 1.0}])


if __name__ == "__main__":
    unittest.main()
