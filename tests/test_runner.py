"""Offline checks for CLI admission gates and successful-run state."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import main as runner


class RunnerTests(unittest.TestCase):
    def test_missing_and_recent_cooldown(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)):
            self.assertTrue(runner.due({}))
            path = runner.last_run_path()
            path.parent.mkdir()
            path.write_text(json.dumps({
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
            self.assertFalse(runner.due({}))
            self.assertTrue(runner.due({
                "navidrome": {"minimum_hours_between_reports": 0},
            }))

    def test_expired_and_corrupt_cooldown(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)):
            path = runner.last_run_path()
            path.parent.mkdir()
            path.write_text(json.dumps({
                "completed_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
            }), encoding="utf-8")
            self.assertTrue(runner.due({}))
            path.write_text("incomplete JSON", encoding="utf-8")
            self.assertTrue(runner.due({}))

    def test_battery_prevents_cpu_sampling(self):
        with patch.object(runner.psutil, "sensors_battery", return_value=SimpleNamespace(power_plugged=False)), \
                patch.object(runner.psutil, "cpu_percent") as cpu:
            allowed, reason = runner.resource_check({})
        self.assertFalse(allowed)
        self.assertIn("battery", reason)
        cpu.assert_not_called()

    def test_low_memory_prevents_cpu_sampling(self):
        with patch.object(runner.psutil, "sensors_battery", return_value=None), \
                patch.object(runner.psutil, "virtual_memory", return_value=SimpleNamespace(available=2 * 1024**3)), \
                patch.object(runner.psutil, "cpu_percent") as cpu:
            allowed, _ = runner.resource_check({})
        self.assertFalse(allowed)
        cpu.assert_not_called()

    def test_cpu_threshold(self):
        with patch.object(runner.psutil, "sensors_battery", return_value=None), \
                patch.object(runner.psutil, "virtual_memory", return_value=SimpleNamespace(available=8 * 1024**3)), \
                patch.object(runner.psutil, "cpu_percent", return_value=36) as cpu:
            self.assertFalse(runner.resource_check({})[0])
            cpu.return_value = 35
            self.assertTrue(runner.resource_check({})[0])

    def test_disabled_run_does_not_dispatch(self):
        with patch("sys.argv", ["main.py", "run"]), \
                patch.object(runner, "settings", return_value={"navidrome": {"enabled": False}}), \
                patch.object(runner, "run_report") as report, \
                patch.object(runner, "resource_check") as check, redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(), 0)
        report.assert_not_called()
        check.assert_not_called()

    def test_manual_report_bypasses_gates_and_records_success(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "report.md"
            with patch.object(runner, "ROOT", root), \
                    patch("sys.argv", ["main.py", "report"]), \
                    patch.object(runner, "settings", return_value={"navidrome": {"enabled": False}}), \
                    patch.object(runner, "due") as due, \
                    patch.object(runner, "resource_check") as check, \
                    patch.object(runner, "run_report", return_value=output) as report, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 0)
            report.assert_called_once()
            due.assert_not_called()
            check.assert_not_called()
            record = json.loads((root / "state" / "last-run.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "success")
            self.assertEqual(record["report_path"], str(output))


if __name__ == "__main__":
    unittest.main()
