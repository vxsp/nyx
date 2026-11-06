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
                if path.name == "Latest.md":
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
