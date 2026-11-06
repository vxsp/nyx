from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import main as runner
from jobs import insights
from jobs.navidrome import atomic_write
from nyx.runtime import record_event


class InsightsTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"NYX_REPORT_DIR": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def save_library(self, root, scope, tracks, missing):
        atomic_write(root / "state" / "navidrome-summary.json", json.dumps({
            "scope_id": scope, "tracks": tracks, "missing_metadata": {"missing_artist": missing},
        }))

    def test_missing_history_stays_unavailable_without_network(self):
        with TemporaryDirectory() as folder, patch("requests.Session.get", side_effect=AssertionError("No network")):
            root = Path(folder)
            path = insights.run_insights_report(root, {})
            text = path.read_text(encoding="utf-8")
            self.assertIn("at least two comparable", text)
            self.assertIn("success rate unavailable", text)
            self.assertIn("milestone H was scrapped", text)
            self.assertEqual(insights.measurements(root), [])

    def test_comparable_library_growth_and_metadata_improvement(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.save_library(root, "same-account", 10, 8)
            insights.record_measurement(root, "navidrome", "success", duration=1, cpu_seconds=0.1, rss_bytes=10 * 1024**2)
            self.save_library(root, "same-account", 12, 3)
            insights.record_measurement(root, "navidrome", "success", duration=2)
            result = insights.analyze(root)
            self.assertEqual(result["library_deltas"]["tracks"], 2)
            self.assertEqual(result["library_deltas"]["missing_metadata_fields"], -5)

    def test_different_accounts_and_failed_jobs_do_not_create_fake_growth(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.save_library(root, "one-account", 10, 0)
            insights.record_measurement(root, "navidrome", "success", duration=1)
            self.save_library(root, "another-account", 20, 0)
            insights.record_measurement(root, "navidrome", "success", duration=1)
            insights.record_measurement(root, "navidrome", "failed", duration=1)
            result = insights.analyze(root)
            self.assertEqual(result["comparable_library_samples"], 1)
            self.assertEqual(result["library_deltas"], {})
            self.assertEqual(result["recent_measurements"][-1]["metrics"], {})

    def test_outcome_window_excludes_skips_starts_and_insights(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for status in ("running", "skipped", "success", "failed", "interrupted"):
                record_event(root, status)
            record_event(root, "success", module="insights")
            result = insights.analyze(root)
            self.assertEqual(result["outcomes"], {"navidrome": {"success": 1, "failed": 1, "interrupted": 1}})

    def test_measurement_retention_and_corrupt_lines(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "state" / "insights-history.jsonl"
            path.parent.mkdir()
            path.write_text("invalid\n" + "{}\n" * 1100, encoding="utf-8")
            insights.record_measurement(root, "dev", "failed", duration=1)
            self.assertEqual(len(path.read_text().splitlines()), 1000)
            self.assertEqual(len(insights.measurements(root)), 1)

    def test_local_insights_cli_preserves_navidrome_cooldown(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)), \
                patch.object(runner, "settings", return_value={}), \
                patch("sys.argv", ["main.py", "insights-report"]), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                patch("requests.Session.get", side_effect=AssertionError("No network")):
            self.assertEqual(runner.main(), 0)
            self.assertFalse(runner.last_run_path().exists())
            self.assertTrue((Path(folder) / "state" / "insights-last-run.json").exists())
            self.assertEqual(insights.measurements(Path(folder)), [])

    def test_optional_telemetry_failure_cannot_fail_a_working_report(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)), \
                patch.object(runner, "settings", return_value={}), \
                patch.object(runner, "run_report", return_value=Path(folder) / "synthetic.md"), \
                patch.object(runner, "record_measurement", side_effect=RuntimeError("synthetic-private-value")), \
                patch("sys.argv", ["main.py", "report"]), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(), 0)
            self.assertEqual(json.loads(runner.last_run_path().read_text())["status"], "success")
            self.assertNotIn("synthetic-private-value", (Path(folder) / "logs" / "nyx.log").read_text())


if __name__ == "__main__":
    unittest.main()
