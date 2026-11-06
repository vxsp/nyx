from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import main as runner
from jobs import dev
from nyx.config import ConfigurationError


class DevTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"NYX_REPORT_DIR": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def repository(self, root):
        path = root / "project"
        path.mkdir()
        def git(*args):
            return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
        git("init", "-b", "main")
        (path / "source.txt").write_text("synthetic\n", encoding="utf-8")
        git("add", "source.txt")
        git("-c", "user.name=Nyx Test", "-c", "user.email=nyx@example.com", "commit", "-m", "synthetic project")
        return path

    def test_metadata_only_detects_dirty_state_without_executing_checks(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.repository(root)
            source = path / "source.txt"
            source.write_text("dirty content\n", encoding="utf-8")
            index_before = (path / ".git" / "index").read_bytes()
            entry = {"name": "Synthetic", "path": path, "checks": [{"command": [sys.executable, "-c", "raise SystemExit(1)"]}]}
            with patch.object(dev, "run_check", side_effect=AssertionError("Not opted in")):
                result = dev.inspect_repository(entry, False, time.monotonic() + 30)
            self.assertTrue(result["dirty"])
            self.assertEqual(result["changed_entries"], 1)
            self.assertEqual(result["checks"][0]["status"], "not requested")
            self.assertEqual(source.read_text(), "dirty content\n")
            self.assertEqual((path / ".git" / "index").read_bytes(), index_before)

    def test_opted_in_test_and_dependency_checks(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.repository(root)
            entry = {"name": "Synthetic", "path": path, "checks": [
                {"name": "Tiny tests", "command": [sys.executable, "-c", "import unittest\nclass Example(unittest.TestCase):\n def test_answer(self): self.assertEqual(2 + 2, 4)\nunittest.main(argv=['test'])"]},
                {"name": "Outdated fixture", "kind": "dependencies", "command": [sys.executable, "-c", "print('[{\"name\":\"synthetic\",\"latest_version\":\"2\"}]')"]},
            ]}
            result = dev.inspect_repository(entry, True, time.monotonic() + 30)
            self.assertFalse(result["dirty"])
            self.assertTrue(all(check["status"] == "passed" for check in result["checks"]))
            self.assertIn("Ran 1 test", result["checks"][0]["output_tail"])
            self.assertEqual(result["checks"][1]["outdated_packages"], 1)

    def test_timeout_stops_own_process(self):
        with TemporaryDirectory() as folder:
            result = dev.run_check(Path(folder), {"command": [sys.executable, "-c", "import time; time.sleep(30)"]}, 0.1)
            self.assertEqual(result["status"], "timeout")
            self.assertLess(result["duration_seconds"], 10)

    def test_output_tail_and_failure_are_bounded_and_redacted(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ, {"NAVIDROME_PASSWORD": "synthetic-private-value"}):
            result = dev.run_check(Path(folder), {"command": [sys.executable, "-c", "print('x'*20000); print('synthetic-private-value'); raise SystemExit(3)"]}, 5)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["output_truncated"])
            self.assertLessEqual(len(result["output_tail"]), 16384)
            self.assertNotIn("synthetic-private-value", result["output_tail"])

    def test_large_output_is_an_explicit_limit_result(self):
        with TemporaryDirectory() as folder:
            result = dev.run_check(Path(folder), {"command": [sys.executable, "-c", "print('x' * (2 * 1024 * 1024))"]}, 5)
            self.assertEqual(result["status"], "output limit")
            self.assertTrue(result["output_truncated"])

    def test_no_config_is_actionable_and_does_not_scan_other_projects(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(dev, "inspect_repository", side_effect=AssertionError("No configured repository")):
                report = dev.run_dev_report(root, {})
            self.assertIn("No repositories configured", report.read_text(encoding="utf-8"))
            self.assertTrue((root / "state" / "dev-last.json").exists())

    def test_private_configuration_and_validation(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            config = root / "config" / "projects.local.json"
            config.write_text(json.dumps({"repositories": [{"path": ".", "checks": []}]}), encoding="utf-8")
            self.assertEqual(dev.repositories(root, {})[0]["path"], root.resolve())
            for invalid in ({"repositories": "invalid"}, {"repositories": [{"path": ".", "checks": [{"command": "python -m tests"}]}]},
                            {"repositories": [{"path": ".", "checks": [{"command": ["npm.cmd"], "timeout_seconds": 0}]}]}):
                config.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaises(ConfigurationError):
                    dev.repositories(root, {})

    def test_dev_cli_does_not_change_navidrome_cooldown(self):
        with TemporaryDirectory() as folder, patch.object(runner, "ROOT", Path(folder)), \
                patch.object(runner, "settings", return_value={}), \
                patch("sys.argv", ["main.py", "dev-report"]), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(), 0)
            self.assertFalse(runner.last_run_path().exists())
            self.assertTrue((Path(folder) / "state" / "dev-last-run.json").exists())
            state = json.loads((Path(folder) / "state" / "current-job.json").read_text())
            self.assertEqual(state["module"], "dev")


if __name__ == "__main__":
    unittest.main()
