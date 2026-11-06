"""Nyx Phase 1 Python runner: read-only Navidrome analysis and local reports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from dotenv import load_dotenv
import psutil
from jobs.navidrome import NavidromeError, atomic_write, run_report
from jobs.dev import run_dev_report
from nyx.config import ConfigurationError, load_settings
from nyx.logging import configure_logging
from nyx.runtime import JobBusyError, job_lock, record_event, record_progress

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / "config" / ".env")


def settings() -> dict:
    return load_settings(ROOT / "config" / "settings.json")


def resource_check(config: dict) -> tuple[bool, str]:
    resources = config.get("resources", {})
    battery = psutil.sensors_battery()
    if resources.get("only_when_plugged_in", True) and battery and not battery.power_plugged:
        return False, "On battery power"
    available_gb = psutil.virtual_memory().available / (1024**3)
    if available_gb < float(resources.get("minimum_available_ram_gb", 3)):
        return False, f"Available memory only {available_gb:.1f} GiB"
    cpu = psutil.cpu_percent(interval=0.8)
    if cpu > float(resources.get("maximum_cpu_percent", 35)):
        return False, f"CPU usage {cpu:.1f}% above configured threshold"
    return True, "Resources available"


def last_run_path() -> Path:
    return ROOT / "state" / "last-run.json"


def due(config: dict) -> bool:
    path = last_run_path()
    if not path.exists():
        return True
    try:
        last = json.loads(path.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(last["completed_at"])
        if ts.tzinfo is None:
            return True
        elapsed = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return elapsed >= float(config.get("navidrome", {}).get("minimum_hours_between_reports", 24))
    except (ValueError, KeyError, OSError, TypeError):
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Nyx personal background automation runner")
    parser.add_argument("command", choices=["report", "run", "status", "tui", "dev-report"], help="report=manual Navidrome; run=scheduled; status=last run; tui=dashboard; dev-report=project health")
    parser.add_argument("--run-checks", action="store_true", help="Explicitly execute declared project checks with dev-report")
    args = parser.parse_args()
    if args.run_checks and args.command != "dev-report":
        parser.error("--run-checks is only supported with dev-report")
    module = "dev" if args.command == "dev-report" else "navidrome"
    logger = None
    try:
        if args.command == "tui":
            try:
                from nyx.tui import NyxApp
            except ImportError:
                print("Install dashboard dependencies: python -m pip install -r requirements-tui.txt", file=sys.stderr)
                return 2
            NyxApp(ROOT).run()
            return 0
        if args.command == "status":
            if last_run_path().exists():
                print(last_run_path().read_text(encoding="utf-8"))
            else:
                print("Nyx has not completed a report yet.")
            return 0
        logger = configure_logging(ROOT)
        config = settings()
        with job_lock(ROOT):
            if args.command == "run":
                reason = None
                if not config.get("navidrome", {}).get("enabled", True):
                    reason = "Navidrome job disabled in settings.json"
                elif not due(config):
                    reason = "Navidrome report already completed within cooldown; skipped."
                else:
                    safe, message = resource_check(config)
                    if not safe:
                        reason = f"Skipping Nyx run: {message}"
                if reason:
                    print(reason)
                    logger.info(reason)
                    record_event(ROOT, "skipped", reason=reason)
                    return 0
            record_event(ROOT, "running", phase="starting", module=module)
            logger.info("%s report started", module)

            def progress(phase: str, completed: int, total: int | None) -> None:
                record_progress(ROOT, phase, completed, total, module=module)
                count = f"{completed}/{total}" if total is not None else str(completed)
                print(f"Nyx: {phase} ({count})", file=sys.stderr, flush=True)

            try:
                output = (run_dev_report(ROOT, config, run_checks=args.run_checks, progress=progress)
                          if module == "dev" else run_report(ROOT, config, progress=progress))
                status_path = ROOT / "state" / "dev-last-run.json" if module == "dev" else last_run_path()
                atomic_write(status_path, json.dumps({
                    "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "report_path": str(output), "module": module, "status": "success",
                }, indent=2))
                record_event(ROOT, "success", report_path=str(output), module=module)
                logger.info("%s report completed", module)
                print(f"Nyx report written: {output}")
                return 0
            except Exception as exc:
                try:
                    record_event(ROOT, "failed", error_type=type(exc).__name__, module=module)
                except OSError:
                    pass
                raise
    except JobBusyError as exc:
        print(str(exc), file=sys.stderr)
        return 0 if args.command == "run" else 2
    except (ConfigurationError, NavidromeError) as exc:
        if logger:
            logger.error("%s: %s", type(exc).__name__, exc)
        category = "configuration" if isinstance(exc, ConfigurationError) else "Navidrome"
        print(f"Nyx {category} error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, ConfigurationError) else 1
    except Exception as exc:
        if logger:
            logger.error("Job failed: %s (details withheld)", type(exc).__name__)
        print(f"Nyx unexpected {type(exc).__name__}; check settings, connectivity, and writable output directories.", file=sys.stderr)
        return 1
    finally:
        if logger:
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
