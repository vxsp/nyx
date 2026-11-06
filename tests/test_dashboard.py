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
    from textual.widgets import DataTable, Footer, Header, Select, Static, TabbedContent
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
                    for key, expected in (("2", "library"), ("3", "jobs"), ("4", "reports"), ("5", "errors"), ("6", "insights"), ("1", "overview")):
                        await pilot.press(key)
                        self.assertEqual(app.query_one("#workspace", TabbedContent).active, expected)
                    await pilot.press("r")
                    self.assertEqual(app.query_one("#formats", DataTable).row_count, 1)
                    launch.assert_not_called()
                    network.assert_not_called()
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["state"])

    async def test_theme_switches_preserve_data_and_restore_without_work(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / "state"
            state.mkdir()
            snapshot = state / "navidrome-summary.json"
            snapshot.write_text('{"tracks":9}', encoding="utf-8")
            original = snapshot.read_bytes()
            preference = state / "tui-preferences.json"
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as launch, \
                    patch("requests.sessions.Session.request", side_effect=AssertionError("No network")) as network:
                app = NyxApp(root)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    self.assertEqual(app.theme, "nyx-dark")
                    self.assertFalse(preference.exists())
                    await pilot.press("t")
                    self.assertEqual(app.theme, "catppuccin-mocha")
                    self.assertEqual(app.screen.styles.background.hex, "#181825")
                    await pilot.press("t")
                    await pilot.pause()
                    self.assertEqual(app.theme, "amoled-black")
                    for widget in (app.screen, app.query_one(Header), app.query_one(Footer),
                                   app.query_one("#tracks", Static), app.query_one("#overview-detail", Static)):
                        self.assertEqual(widget.styles.background.hex, "#000000")
                    self.assertEqual(app.query_one("#theme-select", Select).value, "amoled-black")
                    self.assertEqual(json.loads(preference.read_text())["theme"], "amoled-black")
                saved_preference = preference.read_bytes()
                saved_mtime = preference.stat().st_mtime_ns
                restored = NyxApp(root)
                async with restored.run_test(size=(100, 32)) as pilot:
                    await pilot.press("r", "2", "4")
                    self.assertEqual(restored.theme, "amoled-black")
                    self.assertEqual(restored.query_one("#theme-select", Select).value, "amoled-black")
                launch.assert_not_called()
                network.assert_not_called()
            self.assertEqual(preference.read_bytes(), saved_preference)
            self.assertEqual(preference.stat().st_mtime_ns, saved_mtime)
            self.assertEqual(snapshot.read_bytes(), original)
            self.assertEqual(sorted(path.name for path in state.iterdir()),
                             ["navidrome-summary.json", "tui-preferences.json"])

    async def test_theme_selector_survives_corrupt_state_and_save_failure(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            preference = root / "state" / "tui-preferences.json"
            preference.parent.mkdir()
            preference.write_text("not-json", encoding="utf-8")
            app = NyxApp(root)
            with patch("nyx.tui.save_theme", side_effect=PermissionError("Synthetic read-only state")) as save:
                async with app.run_test(size=(100, 32)) as pilot:
                    self.assertEqual(app.theme, "nyx-dark")
                    save.assert_not_called()
                    await pilot.click("#theme-select")
                    await pilot.press("home", "down", "enter")
                    await pilot.pause()
                    self.assertEqual(app.theme, "catppuccin-mocha")
                    save.assert_called_once_with(root, "catppuccin-mocha")
                    await pilot.press("r", "2")
                    self.assertEqual(app.query_one("#workspace", TabbedContent).active, "library")
            self.assertEqual(preference.read_text(), "not-json")

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

    async def test_insights_key_launches_only_the_local_insights_command(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "main.py").write_text('''import pathlib, sys
root = pathlib.Path(__file__).parent
(root / "invoked.txt").write_text(sys.argv[1])
report = root / "reports" / "Insights" / "Nyx Insights report - latest.md"
report.parent.mkdir(parents=True)
report.write_text("# Synthetic insights report")
print("Synthetic local history report complete", flush=True)
''', encoding="utf-8")
            app = NyxApp(root)
            with patch("requests.Session.get", side_effect=AssertionError("No network")):
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.press("6", "i")
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertEqual((root / "invoked.txt").read_text(), "insights-report")
                    self.assertTrue(any(path.parent.name == "Insights" for path in app.saved.reports))


if __name__ == "__main__":
    unittest.main()
