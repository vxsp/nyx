import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from nyx.saved import DashboardStore

try:
    from nyx.tui import NyxApp
    from textual.widgets import DataTable, Static, TabbedContent
except ImportError:
    NyxApp = None


class SavedDataTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"NYX_REPORT_DIR": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_no_saved_data_and_no_writes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            result = DashboardStore(root).load()
            self.assertEqual(result.summary, {})
            self.assertTrue(result.notices)
            self.assertEqual(list(root.iterdir()), [])

    def test_legacy_snapshot_and_report_support(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "state").mkdir()
            snapshot = {"captured_at": "2026-01-01T00:00:00Z", "duration_seconds": 1,
                        "scan": {}, "artists": [], "albums": [], "playlists": [],
                        "songs": [{"id": "synthetic", "title": "Test", "path": "test.mp3"}]}
            (root / "state" / "navidrome-last.json").write_text(json.dumps(snapshot), encoding="utf-8")
            reports = root / "reports" / "Navidrome"
            reports.mkdir(parents=True)
            (reports / "Latest.md").write_text("# Synthetic legacy report", encoding="utf-8")
            store = DashboardStore(root)
            result = store.load()
            self.assertEqual(result.summary["tracks"], 1)
            self.assertEqual(result.reports[0].name, "Latest.md")
            self.assertIn("Synthetic legacy", store.read_report(result.reports[0]))
            self.assertFalse((root / "state" / "navidrome-summary.json").exists())

    def test_corrupt_state_does_not_crash(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "state").mkdir()
            (root / "state" / "navidrome-summary.json").write_text("[]", encoding="utf-8")
            (root / "state" / "navidrome-last.json").write_text("{}", encoding="utf-8")
            (root / "state" / "history.jsonl").write_text('invalid\n{"status":"success"}\n', encoding="utf-8")
            result = DashboardStore(root).load()
            self.assertEqual(len(result.history), 1)
            self.assertEqual(result.summary, {})

    def test_report_preview_cannot_read_unrelated_file(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            outside = root / "unrelated.md"
            outside.write_text("synthetic-private-value", encoding="utf-8")
            self.assertNotIn("synthetic-private-value", DashboardStore(root).read_report(outside))


@unittest.skipIf(NyxApp is None, "Install requirements-tui.txt for headless dashboard tests")
class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"NYX_REPORT_DIR": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_startup_refresh_and_navigation_never_launch_or_scan(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "state").mkdir()
            (root / "state" / "navidrome-summary.json").write_text(json.dumps({
                "tracks": 9, "albums": 3, "artists": 2, "playlists": 1,
                "formats": {"mp3": 9}, "missing_metadata": {"missing_track_number": 2},
            }), encoding="utf-8")
            app = NyxApp(root)
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as launch, \
                    patch("requests.Session.get", side_effect=AssertionError("Unexpected network")) as network:
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    self.assertIn("9", str(app.query_one("#tracks", Static).render()))
                    for key, expected in (("2", "library"), ("3", "jobs"), ("4", "reports"), ("5", "errors"), ("1", "overview")):
                        await pilot.press(key)
                        self.assertEqual(app.query_one("#workspace", TabbedContent).active, expected)
                    await pilot.press("r")
                    self.assertEqual(app.query_one("#formats", DataTable).row_count, 1)
                    launch.assert_not_called()
                    network.assert_not_called()
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["state"])

    async def test_manual_execution_uses_real_child_and_blocks_duplicates(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            # A synthetic local job proves the UI -> process -> state -> UI flow.
            # It imports no integration code and cannot contact Navidrome.
            (root / "main.py").write_text('''import json, pathlib, time
root = pathlib.Path(__file__).parent
launches = root / "launches.txt"
launches.write_text(str(int(launches.read_text()) + 1) if launches.exists() else "1")
print("Synthetic collection started", flush=True)
time.sleep(0.8)
(root / "state").mkdir(exist_ok=True)
(root / "state" / "navidrome-summary.json").write_text(json.dumps({"tracks": 12}))
print("Synthetic collection complete", flush=True)
''', encoding="utf-8")
            app = NyxApp(root)
            async with app.run_test(size=(110, 36)) as pilot:
                await pilot.press("n", "n")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertFalse(app.running_report)
                self.assertEqual((root / "launches.txt").read_text(), "1")
                self.assertEqual(app.saved.summary["tracks"], 12)

    async def test_quit_guard_and_owned_process_cancellation(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "main.py").write_text('import time\nprint("Synthetic waiting job", flush=True)\ntime.sleep(30)\n', encoding="utf-8")
            app = NyxApp(root)
            async with app.run_test(size=(110, 36)) as pilot:
                await pilot.press("n")
                for _ in range(30):
                    if app.process is not None:
                        break
                    await asyncio.sleep(0.02)
                self.assertIsNotNone(app.process)
                await pilot.press("q")
                self.assertTrue(app.running_report)
                await pilot.press("x")
                await app.workers.wait_for_complete()
                self.assertFalse(app.running_report)
                state = json.loads((root / "state" / "current-job.json").read_text())
                self.assertEqual(state["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
