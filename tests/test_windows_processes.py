"""Native Windows lifetime tests using only disposable, self-ending synthetic jobs."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from jobs import dev
from nyx import processes

# Avoid a venv launcher's own process/job wrapper obscuring the containment under test.
CHECK_PYTHON = getattr(sys, "_base_executable", sys.executable)


@unittest.skipUnless(os.name == "nt", "Native Windows Job Object integration")
class WindowsProcessTests(unittest.TestCase):
    def root_script(self, root: Path, *, parent_wait: bool) -> tuple[Path, Path, Path]:
        marker, ready = root / "child-survived.txt", root / "root-ready.txt"
        script = root / "synthetic check.py"
        child = f"import time; from pathlib import Path; time.sleep(2); Path({str(marker)!r}).write_text('escaped', encoding='utf-8')"
        script.write_text(f'''import os, subprocess, sys, time
from pathlib import Path
subprocess.Popen([sys.executable, '-c', {child!r}], stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 8)
Path({str(ready)!r}).write_text('ready', encoding='utf-8')
print('Argument=' + (sys.argv[1] if len(sys.argv) > 1 else 'none'), flush=True)
print('Environment=' + os.environ.get('NYX_TEST_VALUE', 'none'), flush=True)
time.sleep({30 if parent_wait else 0})
''', encoding="utf-8")
        return script, marker, ready

    def test_normal_exit_cleans_detached_descendant_and_preserves_unrelated_process(self):
        with TemporaryDirectory(prefix="nyx-owned-") as folder:
            root = Path(folder) / "spaces and Unicode Ω"
            root.mkdir()
            script, marker, ready = self.root_script(root, parent_wait=False)
            outsider = subprocess.Popen([CHECK_PYTHON, "-c", "import time; time.sleep(30)"],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                argument = 'spaces "quotes" Ω'
                with patch.dict(os.environ, {"NYX_TEST_VALUE": "Unicode Ω and spaces"}):
                    result = dev.run_check(root, {"command": [CHECK_PYTHON, str(script), argument]}, 5)
                self.assertEqual(result["status"], "passed", result.get("error_type"))
                self.assertTrue(ready.exists())
                self.assertIn("Argument=" + argument, result["output_tail"])
                self.assertIn("Environment=Unicode Ω and spaces", result["output_tail"])
                time.sleep(2.2)
                self.assertFalse(marker.exists(), "A detached descendant outlived the completed check")
                self.assertIsNone(outsider.poll(), "An unrelated process was stopped")
            finally:
                if outsider.poll() is None:
                    outsider.terminate()
                outsider.wait(timeout=5)

    def test_timeout_stops_the_entire_job(self):
        with TemporaryDirectory(prefix="nyx-owned-") as folder:
            root = Path(folder)
            script, marker, ready = self.root_script(root, parent_wait=True)
            result = dev.run_check(root, {"command": [CHECK_PYTHON, str(script)]}, 0.8)
            self.assertEqual(result["status"], "timeout", result.get("error_type"))
            self.assertTrue(ready.exists())
            time.sleep(2.2)
            self.assertFalse(marker.exists(), "A descendant survived check timeout")

    def test_abrupt_runner_exit_closes_job_and_stops_descendants(self):
        with TemporaryDirectory(prefix="nyx-owned-") as folder:
            root = Path(folder)
            script, marker, ready = self.root_script(root, parent_wait=True)
            repository = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join([str(repository), str(Path(sys.prefix) / "Lib" / "site-packages")])
            wrapper = ("from pathlib import Path; import sys; from jobs.dev import run_check; "
                       f"run_check(Path({str(root)!r}), {{'command':[sys.executable,{str(script)!r}]}}, 30)")
            runner = subprocess.Popen([CHECK_PYTHON, "-c", wrapper], cwd=root, env=environment,
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 8
                while not ready.exists() and runner.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "Synthetic job did not reach its ready signal")
                runner.terminate()
                runner.wait(timeout=5)
                time.sleep(2.2)
                self.assertFalse(marker.exists(), "The runner's descendants survived its termination")
            finally:
                if runner.poll() is None:
                    runner.terminate()
                runner.wait(timeout=5)

    def test_breakaway_flag_cannot_escape_lifetime_containment(self):
        with TemporaryDirectory(prefix="nyx-owned-") as folder:
            root = Path(folder)
            marker = root / "breakaway-survived.txt"
            child = f"import time; from pathlib import Path; time.sleep(2); Path({str(marker)!r}).write_text('escaped')"
            command = f'''import subprocess, sys
try:
    subprocess.Popen([sys.executable, '-c', {child!r}], creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except OSError:
    print('breakaway denied')
else:
    print('breakaway flag accepted; child must still be contained')
'''
            result = dev.run_check(root, {"command": [CHECK_PYTHON, "-c", command]}, 5)
            self.assertEqual(result["status"], "passed", result.get("error_type"))
            time.sleep(2.2)
            self.assertFalse(marker.exists(), "A breakaway child escaped the owned lifetime")

    def test_containment_failure_never_falls_back_to_an_uncontained_process(self):
        with TemporaryDirectory(prefix="nyx-owned-") as folder, \
                patch.object(processes, "CreateJobObject", return_value=None), \
                patch.object(processes, "CreateProcess") as create, \
                patch.object(processes.subprocess, "Popen") as fallback:
            result = dev.run_check(Path(folder), {"command": [CHECK_PYTHON, "-c", "raise SystemExit(0)"]}, 5)
            self.assertEqual(result["status"], "error")
            create.assert_not_called()
            fallback.assert_not_called()

    def test_repeated_success_and_creation_failure_do_not_leak_kernel_handles(self):
        import ctypes as c
        from ctypes import wintypes as w
        count_handles = processes._api("GetProcessHandleCount", w.BOOL, [w.HANDLE, c.POINTER(w.DWORD)])
        def count():
            value = w.DWORD()
            processes._checked(count_handles(processes.GetCurrentProcess(), c.byref(value)))
            return value.value
        with TemporaryDirectory(prefix="nyx-owned-") as folder:
            root = Path(folder)
            before = count()
            for _ in range(8):
                result = dev.run_check(root, {"command": [CHECK_PYTHON, "-c", "pass"]}, 5)
                self.assertEqual(result["status"], "passed")
            # Fail after job/output/NUL/attribute-list allocation, before any child starts.
            with patch.object(processes, "UpdateAttribute", return_value=False), patch.object(processes, "CreateProcess") as create:
                for _ in range(8):
                    result = dev.run_check(root, {"command": [CHECK_PYTHON, "-c", "pass"]}, 5)
                    self.assertEqual(result["status"], "error")
                create.assert_not_called()
            self.assertLessEqual(count(), before + 2)


if __name__ == "__main__":
    unittest.main()
