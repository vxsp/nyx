from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import io
import json
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import main as runner
from nyx.config import ConfigurationError, load_settings, validate_settings
from nyx.logging import JsonFormatter
from nyx.runtime import JobBusyError, job_lock, record_event


class ConfigurationTests(unittest.TestCase):
    def test_defaults_and_unknown_future_section(self):
        config = validate_settings({"future_job": {"enabled": False}})
        self.assertEqual(config["navidrome"]["page_size"], 200)
        self.assertEqual(config["future_job"], {"enabled": False})

    def test_invalid_shapes_types_and_ranges(self):
        invalid = [[], {"navidrome": []}, {"resources": None},
                   {"navidrome": {"enabled": "false"}}, {"navidrome": {"page_size": True}},
                   {"navidrome": {"page_size": 501}}, {"navidrome": {"max_albums": 0}},
                   {"navidrome": {"max_report_seconds": 1.5}},
                   {"resources": {"maximum_cpu_percent": 101}},
                   {"resources": {"minimum_available_ram_gb": -1}},
                   {"navidrome": {"minimum_hours_between_reports": float("nan")}}]
        for document in invalid:
            with self.subTest(document=document), self.assertRaises(ConfigurationError):
                validate_settings(document)

    def test_invalid_json_does_not_echo_contents(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('invalid synthetic-private-value', encoding="utf-8")
            with self.assertRaises(ConfigurationError) as error:
                load_settings(path)
            self.assertNotIn("synthetic-private-value", str(error.exception))


class RuntimeTests(unittest.TestCase):
    def test_os_lock_blocks_second_holder_and_releases(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with job_lock(root):
                with self.assertRaises(JobBusyError):
                    with job_lock(root):
                        self.fail("Concurrent lock acquired")
            with job_lock(root):
                pass

    def test_event_history_is_bounded(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "state" / "history.jsonl"
            path.parent.mkdir()
            path.write_text("{}\n" * 510, encoding="utf-8")
            record_event(root, "success")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 500)
            self.assertEqual(json.loads((path.parent / "current-job.json").read_text())["status"], "success")

    def test_naive_and_malformed_cooldown_do_not_crash(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)):
            path = runner.last_run_path()
            path.parent.mkdir()
            for value in ([], {"completed_at": None}, {"completed_at": datetime.now().isoformat()}):
                path.write_text(json.dumps(value), encoding="utf-8")
                self.assertTrue(runner.due({}))

    def test_failure_preserves_success_record_and_redacts_exception(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)):
            path = runner.last_run_path()
            path.parent.mkdir()
            path.write_text('{"status": "previous-success"}', encoding="utf-8")
            stderr = io.StringIO()
            with patch("sys.argv", ["main.py", "report"]), \
                    patch.object(runner, "settings", return_value={}), \
                    patch.object(runner, "run_report", side_effect=RuntimeError("synthetic-private-value")), \
                    redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            self.assertNotIn("synthetic-private-value", stderr.getvalue())
            self.assertNotIn("synthetic-private-value", (Path(folder) / "logs" / "nyx.log").read_text())
            self.assertEqual(json.loads(path.read_text())["status"], "previous-success")
            self.assertEqual(json.loads((path.parent / "current-job.json").read_text())["status"], "failed")

    def test_status_does_not_need_valid_configuration(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)), \
                patch("sys.argv", ["main.py", "status"]), \
                patch.object(runner, "settings") as settings, redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(), 0)
            settings.assert_not_called()

    def test_log_redaction(self):
        with patch.dict(os.environ, {"NAVIDROME_PASSWORD": "synthetic-private-value"}):
            record = logging.LogRecord("nyx", logging.ERROR, "", 0,
                                       "synthetic-private-value https://example.com/?t=synthetic", (), None)
            text = JsonFormatter().format(record)
        self.assertNotIn("synthetic-private-value", text)
        self.assertNotIn("?t=", text)


if __name__ == "__main__":
    unittest.main()
