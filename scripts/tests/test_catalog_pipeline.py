import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog_pipeline import automated_rejection, candidate_score


class CatalogPipelineTest(unittest.TestCase):
    def test_rejects_reaction_and_ai_titles(self):
        self.assertTrue(automated_rejection("Reacting to Norm Macdonald for the first time"))
        self.assertTrue(automated_rejection("AI Norm Macdonald tells a new joke"))

    def test_scores_official_exact_title_above_unknown(self):
        source = {"priority": 8}
        info = {"title": "Norm Macdonald full interview", "duration": 600}
        official = candidate_score(info, source, "official")
        fan = candidate_score(info, source, "fan")
        self.assertGreater(official, fan)


if __name__ == "__main__":
    unittest.main()
