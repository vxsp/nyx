import unittest
from jobs.navidrome import as_list, summarize, render


class ReportTests(unittest.TestCase):
    def test_singleton_payload(self):
        self.assertEqual(as_list({"id": "x"}), [{"id": "x"}])
        self.assertEqual(as_list(None), [])

    def test_duplicates_and_changes(self):
        song1 = {"id": "1", "artist": "A", "title": "T", "duration": 193, "size": 100, "path": "T.mp3", "album": "B", "track": 1}
        song2 = {"id": "2", "artist": "a", "title": "t", "duration": 194, "size": 200, "path": "T2.mp3", "album": "B", "track": 2}
        current = {"captured_at": "2026-11-05T00:00:00+00:00", "server": "https://example.org", "duration_seconds": 1.0, "scan": {}, "artists": [{"id": "a"}], "albums": [{"id": "b"}], "playlists": [], "songs": [song1, song2]}
        previous = {"songs": [song1]}
        result = summarize(current, previous)
        self.assertEqual(result["tracks"], 2)
        self.assertEqual(len(result["duplicate_candidates"]), 1)
        self.assertEqual(len(result["added_tracks"]), 1)
        self.assertIn("Possible duplicates", render(current, result))


if __name__ == "__main__":
    unittest.main()
