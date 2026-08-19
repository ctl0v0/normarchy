import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog_lib import (
    canonical_url,
    validate_candidates,
    validate_catalog,
    video_id_from_url,
)


class CatalogLibTest(unittest.TestCase):
    def test_video_id_parsing(self):
        video_id = "HJtLhTjEWAg"
        self.assertEqual(video_id_from_url(f"https://www.youtube.com/watch?v={video_id}"), video_id)
        self.assertEqual(video_id_from_url(f"https://www.youtube.com/shorts/{video_id}"), video_id)
        self.assertEqual(video_id_from_url(f"https://youtu.be/{video_id}"), video_id)
        self.assertEqual(video_id_from_url("https://example.com/watch?v=HJtLhTjEWAg"), "")
        self.assertEqual(canonical_url(video_id), f"https://www.youtube.com/watch?v={video_id}")

    def test_catalog_requires_complete_items(self):
        self.assertTrue(validate_catalog({"items": [{"id": "HJtLhTjEWAg"}]}))

    def test_candidate_status_is_strict(self):
        candidate = {
            "id": "HJtLhTjEWAg",
            "url": "https://www.youtube.com/watch?v=HJtLhTjEWAg",
            "category": "conan",
            "source_tier": "official",
            "status": "maybe",
        }
        self.assertTrue(validate_candidates({"candidates": [candidate]}))


if __name__ == "__main__":
    unittest.main()
