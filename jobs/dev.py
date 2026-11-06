"""Configured repository health reports; project commands require explicit opt-in."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from jobs.navidrome import atomic_write, mark, utc_now
from nyx.config import ConfigurationError
from nyx.logging import redact


def repositories(root: Path, settings: dict) -> list[dict]:
    config = settings.get("dev", {})
    private = root / "config" / "projects.local.json"
    if private.exists():
        try:
            config = json.loads(private.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ConfigurationError("Cannot read config/projects.local.json as valid JSON.") from None
    if not isinstance(config, dict):
        raise ConfigurationError("Dev configuration must be an object.")
    values = config.get("repositories", [])
    if not isinstance(values, list) or len(values) > 50:
        raise ConfigurationError("Dev repositories must be a list of at most 50 entries.")
    result = []
    for entry in values:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"].strip():
            raise ConfigurationError("Each Dev repository needs a nonempty path string.")
        name = entry.get("name", "Project")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ConfigurationError("Dev repository names must be nonempty strings of at most 80 characters.")
        checks = entry.get("checks", [])
        if not isinstance(checks, list) or len(checks) > 20:
            raise ConfigurationError("Each Dev repository supports at most 20 declared checks.")
        for check in checks:
            if not isinstance(check, dict):
                raise ConfigurationError("Each Dev check must be an object.")
            command = check.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg and "\0" not in arg for arg in command):
                raise ConfigurationError("Dev check commands must be nonempty argument arrays without null characters.")
            if Path(command[0]).suffix.lower() in (".bat", ".cmd"):
                raise ConfigurationError("Dev checks must use an executable runner, not a .bat/.cmd shell script.")
            timeout = check.get("timeout_seconds", 120)
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 3600:
                raise ConfigurationError("Dev check timeouts must be integers from 1 to 3600 seconds.")
            if check.get("kind", "test") not in ("test", "build", "dependencies", "custom"):
                raise ConfigurationError("Dev check kind must be test, build, dependencies, or custom.")
            if not isinstance(check.get("name", "Check"), str):
                raise ConfigurationError("Dev check names must be strings.")
        result.append({"name": name, "path": (root / Path(entry["path"]).expanduser()).resolve(), "checks": checks})
    return result


def stop_tree(process: subprocess.Popen) -> None:
    """Stop only the process tree launched by this check."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        import signal
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait()


def run_check(path: Path, check: dict, timeout: float) -> dict:
    started = time.monotonic()
    result = {"name": check.get("name", "Check"), "kind": check.get("kind", "test"), "status": "error"}
    options = os.environ.copy()
    options.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", PYTHONDONTWRITEBYTECODE="1")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    # Disk-backed capture avoids unbounded output held in RAM; only the tail is retained.
    with tempfile.TemporaryFile() as output:
        process = None
        try:
            command = list(check["command"])
            if not Path(command[0]).is_absolute() and ("/" in command[0] or "\\" in command[0]):
                command[0] = str(path / command[0])
            process = subprocess.Popen(command, cwd=path, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT, env=options, **flags)
            deadline = started + timeout
            while True:
                remaining = deadline - time.monotonic()
                if os.fstat(output.fileno()).st_size > 1024 * 1024:
                    stop_tree(process)
                    result["status"] = "output limit"
                    break
                if remaining <= 0:
                    stop_tree(process)
                    result["status"] = "timeout"
                    break
                try:
                    code = process.wait(timeout=min(0.05, remaining))
                    result.update(status="passed" if code == 0 else "failed", exit_code=code)
                    if os.fstat(output.fileno()).st_size > 1024 * 1024:
                        result["status"] = "output limit"
                    break
                except subprocess.TimeoutExpired:
                    continue
        except OSError as exc:
            result["error_type"] = type(exc).__name__
        finally:
            if process is not None and process.poll() is None:
                stop_tree(process)
        length = output.seek(0, os.SEEK_END)
        output.seek(max(0, length - 16384))
        text = redact(output.read(16384).decode("utf-8", errors="replace"))
        result["output_tail"] = text
        result["output_truncated"] = length > 16384
        if result["kind"] == "dependencies" and result["status"] == "passed" and not result["output_truncated"]:
            try:
                packages = json.loads(text)
                if isinstance(packages, list) and all(isinstance(p, dict) and "latest_version" in p for p in packages):
                    result["outdated_packages"] = len(packages)
            except ValueError:
                pass
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def inspect_repository(entry: dict, run_checks: bool, deadline: float) -> dict:
    path = entry["path"]
    result = {"name": entry["name"], "path": str(path), "status": "unavailable", "checks": []}
    if not path.is_dir():
        result["reason"] = "Configured directory does not exist."
        return result
    options = os.environ.copy()
    options.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    def git(*args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("git", 0)
        with tempfile.TemporaryFile() as output:
            subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(path), *args],
                           timeout=min(10, remaining), stdout=output, stderr=subprocess.DEVNULL,
                           env=options, check=True)
            if output.seek(0, os.SEEK_END) > 1024 * 1024:
                raise OSError("Git output exceeds inspection budget")
            output.seek(0)
            return output.read()
    try:
        top = Path(git("rev-parse", "--show-toplevel").decode("utf-8", errors="replace").strip()).resolve()
        if top != path:
            result["reason"] = "Configure the repository root, not a nested directory."
            return result
        status = git("status", "--porcelain=v1", "--untracked-files=normal").decode("utf-8", errors="replace")
        result.update(status="inspected", branch=git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
                      dirty=bool(status.strip()), changed_entries=len(status.splitlines()))
    except (OSError, subprocess.SubprocessError):
        result["reason"] = "Git inspection failed; check repository access, trust, and initialized history."
        return result
    for check in entry["checks"]:
        if not run_checks:
            result["checks"].append({"name": check.get("name", "Check"), "kind": check.get("kind", "test"), "status": "not requested"})
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            result["checks"].append({"name": check.get("name", "Check"), "status": "budget exhausted"})
            continue
        result["checks"].append(run_check(path, check, min(remaining, check.get("timeout_seconds", 120))))
    return result


def run_dev_report(root: Path, settings: dict, *, run_checks: bool = False, progress=None) -> Path:
    entries = repositories(root, settings)
    started = time.monotonic()
    deadline = started + 600
    results = []
    for index, entry in enumerate(entries, start=1):
        if progress:
            progress("repository checks" if run_checks else "repository inspection", index - 1, len(entries))
        results.append(inspect_repository(entry, run_checks, deadline))
    captured = utc_now()
    lines = ["# Nyx Dev / project health", "", f"Generated: {captured} (UTC)", "",
             f"Project commands explicitly requested: {'yes' if run_checks else 'no'}", "",
             "Git inspection never fetches, installs dependencies, commits, pushes, resets, or cleans projects.",
             "Opted-in project commands execute arbitrary project code and may have their own side effects.", ""]
    if not results:
        lines.append("No repositories configured. Copy config/projects.example.json to config/projects.local.json and edit locally.")
    for result in results:
        lines.extend([f"## {mark(result['name'])}", "", f"- Status: {result['status']}"])
        if result["status"] != "inspected":
            lines.extend([f"- {result['reason']}", ""])
            continue
        lines.extend([f"- Branch: {mark(result['branch'])}", f"- Uncommitted entries: {result['changed_entries']}", ""])
        for check in result["checks"]:
            lines.append(f"- {mark(check['name'])}: {check['status']}")
            if "outdated_packages" in check:
                lines.append(f"  - Outdated packages reported by the declared check: {check['outdated_packages']}")
            if check.get("output_tail"):
                lines.extend(["", "```text", check["output_tail"].replace("```", "'''"), "```", ""])
            if check.get("output_truncated"):
                lines.append("Output limited to the final 16 KiB; package counts unavailable if truncated.")
        lines.append("")
    report_dir = Path(os.getenv("NYX_REPORT_DIR") or root / "reports").expanduser() / "Dev"
    dated = report_dir / f"Nyx Dev report - {datetime.now().astimezone():%Y-%m-%d}.md"
    atomic_write(dated, "\n".join(lines) + "\n")
    atomic_write(report_dir / "Nyx Dev report - latest.md", "\n".join(lines) + "\n")
    atomic_write(root / "state" / "dev-last.json", json.dumps({
        "captured_at": captured, "duration_seconds": round(time.monotonic() - started, 3),
        "checks_requested": run_checks, "repositories": results,
    }, indent=2))
    if progress:
        progress("repositories complete", len(entries), len(entries))
    return dated
