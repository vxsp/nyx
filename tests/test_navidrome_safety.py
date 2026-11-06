"""Synthetic HTTP and filesystem checks; never access a real library."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from jobs import navidrome


def snapshot():
    return {
        "captured_at": "2026-01-01T00:00:00+00:00",
        "server": "https://navidrome.example.com",
        "duration_seconds": 1.0,
        "scan": {}, "artists": [], "albums": [], "songs": [], "playlists": [],
    }


class NavidromeSafetyTests(unittest.TestCase):
    def test_multiple_pages_and_duplicate_ids_do_not_repeat_album_requests(self):
        client = Mock()
        client.base = "https://navidrome.example.com"
        def response(endpoint, **params):
            if endpoint == "getAlbumList2":
                page = [{"id": "a"}, {"id": "b"}] if params["offset"] == 0 else [{"id": "a"}]
                return {"albumList2": {"album": page}}
            if endpoint == "getAlbum":
                return {"album": {"song": [{"id": "same-track"}]}}
            return {}
        client.get.side_effect = response
        progress = Mock()
        result = navidrome.collect(client, 2, 10, 600, progress=progress)
        self.assertEqual(len(result["albums"]), 2)
        self.assertEqual(len(result["songs"]), 1)
        album_calls = [call for call in client.get.call_args_list if call.args[0] == "getAlbum"]
        self.assertEqual(len(album_calls), 2)
        progress.assert_any_call("collected", 3, 3)

    def test_missing_album_id_aborts_instead_of_saving_partial_data(self):
        client = Mock()
        client.get.side_effect = lambda endpoint, **kwargs: (
            {"albumList2": {"album": [{"name": "Synthetic album"}]}} if endpoint == "getAlbumList2" else {}
        )
        with self.assertRaisesRegex(navidrome.NavidromeError, "missing an ID"):
            navidrome.collect(client, 200, 2000, 600)

    def test_report_names_summary_and_old_reports_preserved(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "reports" / "Navidrome" / "Latest.md"
            old.parent.mkdir(parents=True)
            old.write_text("old report", encoding="utf-8")
            with patch.object(navidrome, "NavidromeClient"), \
                    patch.object(navidrome, "collect", return_value=snapshot()), \
                    patch.dict(os.environ, {"NYX_REPORT_DIR": str(root / "reports")}):
                output = navidrome.run_report(root, {})
            self.assertRegex(output.name, r"^Navidrome report - \d{4}-\d{2}-\d{2}\.md$")
            self.assertTrue(output.exists())
            self.assertTrue((output.parent / "Navidrome report - latest.md").exists())
            self.assertEqual(old.read_text(), "old report")
            self.assertEqual(json.loads((root / "state" / "navidrome-summary.json").read_text())["tracks"], 0)
            self.assertTrue((root / "state" / "navidrome-last.json").exists())

    def test_api_error_body_cannot_echo_secret(self):
        with patch.object(navidrome.requests, "Session") as session:
            session.return_value.get.return_value.json.return_value = {
                "subsonic-response": {"status": "failed", "error": {"code": 40, "message": "synthetic-private-value"}}
            }
            client = navidrome.NavidromeClient("https://navidrome.example.com", "test-user", "test-password")
            with self.assertRaises(navidrome.NavidromeError) as error:
                client.get("ping")
            self.assertNotIn("synthetic-private-value", str(error.exception))
            self.assertIn("40", str(error.exception))
            with self.assertRaises(navidrome.NavidromeError):
                client.get("startScan")
            self.assertEqual(session.return_value.get.call_count, 1)

    def test_malformed_api_payload_is_controlled_error(self):
        with patch.object(navidrome.requests, "Session") as session:
            session.return_value.get.return_value.json.return_value = {"subsonic-response": []}
            client = navidrome.NavidromeClient("https://navidrome.example.com", "test-user", "test-password")
            with self.assertRaises(navidrome.NavidromeError):
                client.get("ping")

    def test_time_budget_includes_initial_requests(self):
        now = [0.0]
        client = Mock()
        def response(endpoint, **kwargs):
            now[0] += 2
            return {}
        client.get.side_effect = response
        with patch.object(navidrome.time, "monotonic", side_effect=lambda: now[0]):
            with self.assertRaisesRegex(navidrome.NavidromeError, "collection time budget"):
                navidrome.collect(client, 200, 2000, 3)
        self.assertEqual(client.get.call_count, 2)

    def test_atomic_replace_failure_preserves_old_file_and_cleans_temp(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "report.md"
            path.write_text("old", encoding="utf-8")
            with patch.object(navidrome.os, "replace", side_effect=OSError("synthetic failure")):
                with self.assertRaises(OSError):
                    navidrome.atomic_write(path, "new")
            self.assertEqual(path.read_text(), "old")
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_https_and_credentials_required(self):
        for url, user, password in (
            ("http://navidrome.example.com", "test-user", "test-password"),
            ("https://navidrome.example.com", "", ""),
        ):
            with self.subTest(url=url), self.assertRaises(navidrome.NavidromeError):
                navidrome.NavidromeClient(url, user, password)

    def test_http_errors_do_not_echo_authenticated_url(self):
        with patch.object(navidrome.requests, "Session") as session:
            session.return_value.get.side_effect = requests.ConnectionError(
                "https://navidrome.example.com/rest/ping.view?u=test-user&t=synthetic-token"
            )
            client = navidrome.NavidromeClient(
                "https://navidrome.example.com", "test-user", "test-password"
            )
            with self.assertRaises(navidrome.NavidromeError) as error:
                client.get("ping")
        self.assertNotIn("test-user", str(error.exception))
        self.assertNotIn("synthetic-token", str(error.exception))
        self.assertNotIn("https://", str(error.exception))

    def test_collection_uses_only_read_endpoints(self):
        replies = {
            "ping": {}, "getScanStatus": {}, "getArtists": {}, "getPlaylists": {},
            "getAlbumList2": {"albumList2": {"album": [{"id": "album-1"}]}},
            "getAlbum": {"album": {"song": [{"id": "song-1"}]}},
        }
        client = Mock()
        client.base = "https://navidrome.example.com"
        client.get.side_effect = lambda endpoint, **kwargs: replies[endpoint]
        result = navidrome.collect(client, page_size=200, max_albums=2000, max_seconds=600)
        self.assertEqual(result["songs"], [{"id": "song-1", "album": "", "artist": ""}])
        self.assertEqual([call.args[0] for call in client.get.call_args_list], [
            "ping", "getScanStatus", "getArtists", "getPlaylists", "getAlbumList2", "getAlbum",
        ])

    def test_album_limit_aborts_collection(self):
        client = Mock()
        client.get.side_effect = lambda endpoint, **kwargs: (
            {"albumList2": {"album": [{"id": "album-1"}]}} if endpoint == "getAlbumList2" else {}
        )
        with self.assertRaisesRegex(navidrome.NavidromeError, "Album safety limit"):
            navidrome.collect(client, page_size=1, max_albums=1, max_seconds=600)
        self.assertNotIn("getAlbum", [call.args[0] for call in client.get.call_args_list])

    def test_failed_collection_preserves_previous_snapshot(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            previous = root / "state" / "navidrome-last.json"
            previous.parent.mkdir()
            original = json.dumps(snapshot())
            previous.write_text(original, encoding="utf-8")
            with patch.object(navidrome, "NavidromeClient"), \
                    patch.object(navidrome, "collect", side_effect=navidrome.NavidromeError("synthetic failure")), \
                    patch.dict(os.environ, {"NYX_REPORT_DIR": str(root / "reports")}):
                with self.assertRaises(navidrome.NavidromeError):
                    navidrome.run_report(root, {})
            self.assertEqual(previous.read_text(encoding="utf-8"), original)
            self.assertFalse((root / "reports").exists())

    def test_failed_latest_write_preserves_previous_snapshot(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            previous = root / "state" / "navidrome-last.json"
            previous.parent.mkdir()
            original = '{"songs": [{"id": "old-song"}]}'
            previous.write_text(original, encoding="utf-8")
            original_write = navidrome.atomic_write

            def fail_latest(path, content):
                if path.name == "Navidrome report - latest.md":
                    raise OSError("synthetic write failure")
                original_write(path, content)

            with patch.object(navidrome, "NavidromeClient"), \
                    patch.object(navidrome, "collect", return_value=snapshot()), \
                    patch.object(navidrome, "atomic_write", side_effect=fail_latest), \
                    patch.dict(os.environ, {"NYX_REPORT_DIR": str(root / "reports")}):
                with self.assertRaises(OSError):
                    navidrome.run_report(root, {})
            self.assertEqual(previous.read_text(encoding="utf-8"), original)
            self.assertEqual(len(list((root / "reports").rglob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
