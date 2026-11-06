import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import requests

from jobs import research
from jobs.navidrome import mark
from nyx.config import ConfigurationError


RSS = b'<rss><channel><item><title>Example article</title><link>https://example.com/article?utm_source=test</link><pubDate>2026-01-01</pubDate></item></channel></rss>'


class Response:
    def __init__(self, body=RSS, status=200):
        self.body, self.status_code = body, status
        self.headers = {"ETag": '"synthetic-etag"'}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("synthetic-private-value")
    def iter_content(self, size):
        for offset in range(0, len(self.body), size):
            yield self.body[offset:offset + size]


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers, self.calls = {}, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"NYX_REPORT_DIR": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def test_rss_atom_and_tracking_deduplication(self):
        rss = research.parse_feed(RSS, "https://example.com/feed", "Test")[0]
        atom = research.parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Example</title><link href="https://example.com/article"/><updated>2026-01-02</updated></entry></feed>', "https://example.com/atom", "Test")[0]
        self.assertEqual(rss["id"], atom["id"])
        self.assertEqual(atom["published_at"], "2026-01-02")

    def test_entities_invalid_format_and_oversized_responses_rejected(self):
        for value in (b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>', b'<html>not a feed</html>'):
            with self.assertRaises(ValueError):
                research.parse_feed(value, "https://example.com/feed", "Test")
        with self.assertRaises(ValueError):
            research.fetch(Session([Response(b'x' * (1024**2 + 1))]), "https://example.com/feed", {}, time.monotonic() + 10)

    def test_dedup_read_acknowledgement_and_conditional_headers(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            config = {"research": {"feeds": [{"url": "https://example.com/feed"}]}}
            sessions = [Session([Response()]), Session([Response()]), Session([Response(status=304)])]
            with patch.object(research.requests, "Session", side_effect=sessions):
                first = research.run_research_report(root, config)
                self.assertIn("New entries: 1", first.read_text())
                state = json.loads((root / "state" / "research-last.json").read_text())
                key = state["items"][0]["id"]
                self.assertIsNone(state["items"][0]["read_at"])
                research.mark_read(root, key[:12])
                second = research.run_research_report(root, config)
                self.assertIn("New entries: 0", second.read_text())
                self.assertIn("Example article", second.read_text())
                research.run_research_report(root, config)
            self.assertIn("If-None-Match", sessions[1].calls[0][1]["headers"])
            state = json.loads((root / "state" / "research-last.json").read_text())
            self.assertIsNotNone(state["items"][0]["read_at"])
            self.assertEqual(len(state["items"]), 1)

    def test_source_failure_keeps_reading_history_and_redacts_server_error(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            config = {"research": {"feeds": [{"url": "https://example.com/feed"}]}}
            with patch.object(research.requests, "Session", return_value=Session([Response()])):
                research.run_research_report(root, config)
            with patch.object(research.requests, "Session", return_value=Session([Response(status=503)])):
                path = research.run_research_report(root, config)
            self.assertNotIn("synthetic-private-value", path.read_text())
            state = json.loads((root / "state" / "research-last.json").read_text())
            self.assertEqual(len(state["items"]), 1)
            self.assertEqual(state["sources"][0]["status"], "unavailable")

    def test_stable_public_releases_only(self):
        values = [{"html_url": "https://github.com/example/project/releases/tag/v1", "name": "v1"},
                  {"html_url": "https://github.com/example/project/releases/tag/v2", "name": "v2", "prerelease": True}]
        with TemporaryDirectory() as folder, patch.object(research.requests, "Session", return_value=Session([Response(json.dumps(values).encode())])):
            root = Path(folder)
            path = research.run_research_report(root, {"research": {"github_repositories": ["example/project"]}})
            self.assertIn("New entries: 1", path.read_text())

    def test_empty_configuration_no_requests_and_invalid_sources(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            session = Session([])
            with patch.object(research.requests, "Session", return_value=session):
                path = research.run_research_report(root, {})
            self.assertEqual(session.calls, [])
            self.assertIn("No sources configured", path.read_text())
            with self.assertRaises(ConfigurationError):
                research.configuration(root, {"research": {"feeds": [{"url": "http://example.com"}]}})
            with self.assertRaises(ConfigurationError):
                research.mark_read(root, "a" * 12)

    def test_repository_pool_rotates_without_exceeding_source_budget(self):
        pool = [f"example/project{index}" for index in range(25)]
        config = {"research": {"feeds": [{"url": "https://example.com/feed"}],
                               "github_repositories": ["example/fixed"],
                               "github_repository_pool": pool + ["EXAMPLE/PROJECT0", "EXAMPLE/FIXED"],
                               "github_batch_size": 18}}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            observed = set()
            for expected_cursor in (18, 11):
                session = Session([Response(RSS)] + [Response(b"[]") for _ in range(19)])
                with patch.object(research.requests, "Session", return_value=session):
                    path = research.run_research_report(root, config)
                self.assertEqual(len(session.calls), 20)
                self.assertIn("example/fixed/releases", session.calls[1][0])
                self.assertNotIn("Authorization", session.headers)
                self.assertFalse(session.trust_env)
                observed.update(url.split("/repos/", 1)[1].split("/releases", 1)[0] for url, _ in session.calls[2:])
                state = json.loads((root / "state/research-last.json").read_text())
                self.assertEqual(state["rotation"]["next_index"], expected_cursor)
                self.assertEqual(state["rotation"]["pool_size"], 25)
                self.assertIn("Only a bounded batch", path.read_text())
            self.assertEqual(observed, set(pool))

    def test_budget_defers_pool_without_advancing_and_changed_pool_resets_cursor(self):
        clock = [0.0]
        def feed_uses_budget(*args):
            clock[0] = 2
            return RSS, {}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            config = {"research": {"feeds": [{"url": "https://example.com/feed"}],
                                   "github_repository_pool": ["example/first", "example/second"],
                                   "github_batch_size": 1, "max_seconds": 1}}
            with patch.object(research.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(research, "fetch", side_effect=feed_uses_budget) as fetch:
                research.run_research_report(root, config)
            self.assertEqual(fetch.call_count, 1)
            state_path = root / "state/research-last.json"
            state = json.loads(state_path.read_text())
            self.assertEqual(state["rotation"]["next_index"], 0)
            self.assertEqual(state["rotation"]["attempted_count"], 0)
            state["rotation"]["next_index"] = 1
            state_path.write_text(json.dumps(state))
            config["research"]["feeds"] = []
            config["research"]["github_repository_pool"] = ["example/new", "example/first"]
            session = Session([Response(b"[]")])
            with patch.object(research.requests, "Session", return_value=session):
                research.run_research_report(root, config)
            self.assertIn("example/new/releases", session.calls[0][0])

    def test_rate_limit_stops_batch_and_failed_state_write_preserves_cursor(self):
        config = {"research": {"github_repository_pool": ["example/first", "example/second", "example/third"],
                               "github_batch_size": 2}}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            response = requests.Response()
            response.status_code = 403
            with patch.object(research, "fetch", side_effect=requests.HTTPError("synthetic-private-value", response=response)) as fetch:
                path = research.run_research_report(root, config)
            self.assertEqual(fetch.call_count, 1)
            self.assertNotIn("synthetic-private-value", path.read_text())
            state_path = root / "state/research-last.json"
            previous = state_path.read_bytes()
            self.assertEqual(json.loads(previous)["rotation"]["next_index"], 1)
            original_write = research.atomic_write
            def fail_state(path, content):
                if path == state_path:
                    raise OSError("Synthetic write failure")
                return original_write(path, content)
            session = Session([Response(b"[]"), Response(b"[]")])
            with patch.object(research.requests, "Session", return_value=session), patch.object(research, "atomic_write", side_effect=fail_state):
                with self.assertRaises(OSError):
                    research.run_research_report(root, config)
            self.assertEqual(state_path.read_bytes(), previous)
            self.assertIn("example/second/releases", session.calls[0][0])

    def test_repository_pool_validation_preserves_twenty_source_limit(self):
        with TemporaryDirectory() as folder:
            for invalid in ({"github_repository_pool": "example/project"},
                            {"github_repository_pool": ["invalid"]},
                            {"github_repository_pool": ["example/project"] * 2001},
                            {"github_repository_pool": ["example/project"], "github_batch_size": True},
                            {"github_repository_pool": ["example/project"], "github_batch_size": 0},
                            {"github_repository_pool": ["example/project"], "feeds": [{"url": "https://example.com"}] * 20}):
                with self.subTest(invalid_keys=list(invalid)), self.assertRaises(ConfigurationError):
                    research.configuration(Path(folder), {"research": invalid})

    def test_markdown_fields_cannot_create_html_or_links(self):
        value = mark('<img src="https://example.com/track"> [click](javascript:bad)')
        self.assertNotIn("<img", value)
        self.assertIn("\\[click\\]", value)


if __name__ == "__main__":
    unittest.main()
