"""Nyx Phase 1 Python runner: read-only Navidrome analysis and local reports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import psutil
from jobs.navidrome import NavidromeError, atomic_write, run_report

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / "config" / ".env")


def settings() -> dict:
    return json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))


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
        elapsed = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return elapsed >= float(config.get("navidrome", {}).get("minimum_hours_between_reports", 24))
    except (ValueError, KeyError, OSError):
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Nyx personal background automation runner")
    parser.add_argument("command", choices=["report", "run", "status"], help="report=manual; run=scheduled; status=last run")
    args = parser.parse_args()
    config = settings()
    if args.command == "status":
        if last_run_path().exists():
            print(last_run_path().read_text(encoding="utf-8"))
        else:
            print("Nyx has not completed a report yet.")
        return 0
    if args.command == "run":
        if not config.get("navidrome", {}).get("enabled", True):
            print("Navidrome job disabled in settings.json")
            return 0
        if not due(config):
            print("Navidrome report already completed within cooldown; skipped.")
            return 0
        safe, reason = resource_check(config)
        if not safe:
            print(f"Skipping Nyx run: {reason}")
            return 0
    try:
        output = run_report(ROOT, config)
        atomic_write(last_run_path(), json.dumps({
            "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "report_path": str(output),
            "module": "navidrome",
            "status": "success",
        }, indent=2))
        print(f"Nyx report written: {output}")
        return 0
    except NavidromeError as exc:
        print(f"Nyx Navidrome error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Nyx unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
