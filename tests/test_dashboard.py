import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from nyx.saved import DashboardStore
from nyx.modules import MODULES

try:
    from nyx.tui import NyxApp
    from textual.widgets import Button, DataTable, Footer, Header, Markdown, Select, Static, TabbedContent
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

    def test_saved_module_data_is_isolated_and_cache_handles_changes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / "state"
            state.mkdir()
            for module in MODULES:
                (state / module.snapshot).write_text(json.dumps({"captured_at": module.key}), encoding="utf-8")
                success = "last-run.json" if module.key == "navidrome" else f"{module.key}-last-run.json"
                (state / success).write_text(json.dumps({"completed_at": module.key}), encoding="utf-8")
                report = root / "reports" / module.folder / "Synthetic.md"
                report.parent.mkdir(parents=True)
                report.write_text(module.key, encoding="utf-8")
            events = [{"status": "legacy"}] + [{"module": module.key, "status": module.key} for module in MODULES]
            (state / "history.jsonl").write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            store = DashboardStore(root)
            saved = store.load()
            for module in MODULES:
                own = saved.modules[module.key]
                self.assertEqual(own.snapshot["captured_at"], module.key)
                self.assertEqual(own.last_run["completed_at"], module.key)
                self.assertEqual([path.parent.name for path in own.reports], [module.folder])
                self.assertEqual([item["status"] for item in own.history],
                                 (["legacy"] if module.key == "navidrome" else []) + [module.key])
            # One busy module cannot consume another module's report allowance.
            for index in range(201):
                report = root / "reports" / "Dev" / f"Synthetic {index}.md"
                report.write_text("synthetic", encoding="utf-8")
                os.utime(report, (2000000000, 2000000000))
            saved = store.load()
            self.assertEqual(len(saved.reports), 200)
            self.assertEqual(len(saved.modules["audio"].reports), 1)
            (state / "audio-last.json").write_text('{"audio_files":12345}', encoding="utf-8")
            self.assertEqual(store.load().modules["audio"].snapshot["audio_files"], 12345)
            (state / "audio-last.json").unlink()
            (state / "dev-last.json").write_text("[]", encoding="utf-8")
            saved = store.load()
            self.assertEqual(saved.modules["audio"].snapshot, {})
            self.assertEqual(saved.modules["dev"].snapshot, {})


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
                    for key, expected in (("2", "navidrome"), ("3", "dev"), ("4", "audio"), ("5", "research"),
                                          ("6", "insights"), ("7", "jobs"), ("8", "reports"), ("9", "errors"), ("1", "overview")):
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
                    self.assertEqual(app.query_one("#workspace", TabbedContent).active, "navidrome")
            self.assertEqual(preference.read_text(), "not-json")

    async def test_module_workspaces_keep_previews_and_history_separate(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / "state"
            state.mkdir()
            for module in MODULES:
                snapshot = {"captured_at": "synthetic"}
                if module.key == "research":
                    snapshot.update(items=[], sources=[], rotation={"pool_size": 25, "attempted_count": 18})
                (state / module.snapshot).write_text(json.dumps(snapshot), encoding="utf-8")
                reports = root / "reports" / module.folder
                reports.mkdir(parents=True)
                (reports / "Earlier.md").write_text(f"# Earlier {module.key}", encoding="utf-8")
                (reports / "Synthetic report - latest.md").write_text(f"# Latest {module.key}", encoding="utf-8")
            (state / "history.jsonl").write_text("\n".join(json.dumps({"module": module.key, "status": "success"}) for module in MODULES), encoding="utf-8")
            original = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            app = NyxApp(root)
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as launch, \
                    patch("requests.sessions.Session.request", side_effect=AssertionError("No network")) as network:
                async with app.run_test(size=(120, 40)) as pilot:
                    self.assertEqual(app.query_one("#module-list", DataTable).row_count, 5)
                    for number, module in enumerate(MODULES, start=2):
                        await pilot.press(str(number))
                        self.assertEqual(app.query_one("#workspace", TabbedContent).active, module.key)
                        self.assertEqual(app.query_one(f"#{module.key}-history", DataTable).row_count, 1)
                        if module.key == "dev":
                            self.assertIn("unavailable", str(app.query_one(f"#{module.key}-summary", Static).render()))
                        if module.key == "research":
                            self.assertIn("Repository pool: 25; attempted this run: 18", str(app.query_one("#research-summary", Static).render()))
                        reports = app.query_one(f"#{module.key}-reports", DataTable)
                        self.assertEqual(reports.row_count, 2)
                        body = app.query_one(f"#{module.key}-body", Markdown)
                        self.assertEqual(body.source, f"# Latest {module.key}")
                        for index, path in enumerate(app.saved.modules[module.key].reports):
                            if path.name == "Earlier.md":
                                reports.move_cursor(row=index)
                        reports.focus()
                        await pilot.press("enter", "r")
                        self.assertEqual(body.source, f"# Earlier {module.key}")
                    launch.assert_not_called()
                    network.assert_not_called()
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, original)

    async def test_module_buttons_route_safe_commands_and_cancel_the_right_module(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "main.py").write_text('''import json, pathlib, sys, time
root = pathlib.Path(__file__).parent
with (root / "invocations.jsonl").open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
print("Synthetic module job", flush=True)
time.sleep(30 if sys.argv[1] == "dev-report" else 0.1)
''', encoding="utf-8")
            app = NyxApp(root)
            with patch("requests.sessions.Session.request", side_effect=AssertionError("No network")):
                async with app.run_test(size=(120, 40)) as pilot:
                    for number, module in enumerate(MODULES, start=2):
                        await pilot.press(str(number))
                        button_id = "run-report" if module.key == "navidrome" else f"run-{module.key}"
                        self.assertEqual(app.query_one("#workspace", TabbedContent).active, module.key)
                        self.assertTrue(await pilot.click(f"#{button_id}"))
                        if module.key == "dev":
                            for _ in range(50):
                                if len((root / "invocations.jsonl").read_text().splitlines()) >= 2:
                                    break
                                await asyncio.sleep(0.02)
                            self.assertTrue(app.running_report)
                            self.assertTrue(all(button.disabled for button in app.query(".module-run")))
                            app.start_job("audio-report")
                            await pilot.press("x")
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        self.assertFalse(app.running_report)
                        self.assertTrue(all(not button.disabled for button in app.query(".module-run")))
                    calls = [json.loads(line) for line in (root / "invocations.jsonl").read_text().splitlines()]
                    self.assertEqual(calls, [[module.command] for module in MODULES])
                    state = json.loads((root / "state" / "current-job.json").read_text())
                    self.assertEqual((state["module"], state["status"]), ("dev", "interrupted"))

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
deadline = time.monotonic() + 30
while not (root / "release.txt").exists():
    if time.monotonic() >= deadline:
        raise SystemExit(2)
    time.sleep(0.02)
(root / "state").mkdir(exist_ok=True)
(root / "state" / "navidrome-summary.json").write_text(json.dumps({"tracks": 12}))
print("Synthetic collection complete", flush=True)
''', encoding="utf-8")
            app = NyxApp(root)
            async with app.run_test(size=(110, 36)) as pilot:
                try:
                    await pilot.press("n", "n")
                    self.assertTrue(app.running_report)
                finally:
                    (root / "release.txt").write_text("release", encoding="utf-8")
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
