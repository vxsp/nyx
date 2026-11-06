"""Evidence-based local insights; missing history remains unavailable."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import math
import os
from pathlib import Path

from jobs.navidrome import atomic_write, mark, utc_now
from nyx.saved import DashboardStore, read_json, tail


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def current_metrics(root: Path, module: str) -> tuple[str | None, dict]:
    filename = {"navidrome": "navidrome-summary.json", "dev": "dev-last.json", "audio": "audio-last.json", "research": "research-last.json"}.get(module)
    state = read_json(root / "state" / filename) if filename else {}
    metrics = {}
    if module == "navidrome":
        metrics = {key: state[key] for key in ("tracks", "albums", "artists", "playlists", "duplicate_groups") if number(state.get(key)) is not None}
        missing = state.get("missing_metadata")
        if isinstance(missing, dict) and all(number(value) is not None for value in missing.values()):
            metrics["missing_metadata_fields"] = sum(missing.values())
    elif module == "dev":
        repos = state.get("repositories")
        if isinstance(repos, list):
            checks = [check for repo in repos if isinstance(repo, dict) for check in repo.get("checks", []) if isinstance(check, dict)]
            metrics = {"repositories_observed": len(repos), "checks_requested": state.get("checks_requested") is True,
                       "repositories_unavailable": sum(repo.get("status") != "inspected" for repo in repos if isinstance(repo, dict)),
                       "checks_passed": sum(check.get("status") == "passed" for check in checks),
                       "checks_failed": sum(check.get("status") in ("failed", "timeout", "error", "output limit") for check in checks),
                       "checks_unavailable": sum(check.get("status") not in ("passed", "failed", "timeout", "error", "output limit") for check in checks)}
    elif module == "audio":
        metrics = {key: state[key] for key in ("audio_files", "fl_studio_projects") if number(state.get(key)) is not None}
        if "complete" in state:
            metrics["scope_complete"] = state["complete"] is True
    elif module == "research":
        items = state.get("items")
        if isinstance(items, list):
            metrics = {"retained_items": len(items), "read_items": sum(bool(item.get("read_at")) for item in items if isinstance(item, dict))}
    return state.get("scope_id"), metrics


def record_measurement(root: Path, module: str, status: str, *, duration: float, cpu_seconds=None, rss_bytes=None) -> None:
    """Caller holds the job lock. Record observed process metrics, not child CPU."""
    if module == "insights":
        return
    scope, metrics = current_metrics(root, module) if status == "success" else (None, {})
    point = {"at": utc_now(), "module": module, "status": status, "duration_seconds": round(max(0, duration), 3),
             "scope_id": scope, "metrics": metrics}
    if number(cpu_seconds) is not None:
        point["controller_cpu_seconds"] = round(max(0, cpu_seconds), 3)
    if number(rss_bytes) is not None:
        point["controller_rss_bytes"] = rss_bytes
    path = root / "state" / "insights-history.jsonl"
    lines = tail(path, 1024 * 1024)[-999:]
    lines.append(json.dumps(point, ensure_ascii=False))
    atomic_write(path, "\n".join(lines) + "\n")


def measurements(root: Path) -> list[dict]:
    points = []
    for line in tail(root / "state" / "insights-history.jsonl", 1024 * 1024)[-1000:]:
        try:
            point = json.loads(line)
            if isinstance(point, dict) and isinstance(point.get("module"), str) and isinstance(point.get("metrics"), dict):
                points.append(point)
        except ValueError:
            pass
    return points


def analyze(root: Path) -> dict:
    points = measurements(root)
    outcomes = defaultdict(lambda: {"success": 0, "failed": 0, "interrupted": 0})
    for line in tail(root / "state" / "history.jsonl")[-500:]:
        try:
            event = json.loads(line)
            if not isinstance(event, dict) or event.get("module") == "insights":
                continue
            module, status = event.get("module"), event.get("status")
            if isinstance(module, str) and status in ("success", "failed", "interrupted"):
                outcomes[module][status] += 1
        except ValueError:
            pass
    successful = [point for point in points if point["module"] == "navidrome" and point.get("status") == "success" and point.get("scope_id")]
    comparable = [point for point in successful if point["scope_id"] == successful[-1]["scope_id"]] if successful else []
    deltas = {}
    if len(comparable) >= 2:
        for key in ("tracks", "albums", "artists", "playlists", "missing_metadata_fields", "duplicate_groups"):
            first, last = comparable[0]["metrics"].get(key), comparable[-1]["metrics"].get(key)
            if number(first) is not None and number(last) is not None:
                deltas[key] = last - first
    return {"captured_at": utc_now(), "measurement_count": len(points), "outcomes": dict(outcomes),
            "comparable_library_samples": len(comparable), "library_deltas": deltas,
            "recent_measurements": points[-20:], "backup_history": "unavailable: milestone H was scrapped by the owner"}


def run_insights_report(root: Path, settings: dict, *, progress=None) -> Path:
    result = analyze(root)
    latest = DashboardStore(root).load().summary
    lines = ["# Nyx Insights / observed history", "", f"Generated: {result['captured_at']} (UTC)", "",
             "## Latest saved library", ""]
    if latest:
        lines.append(f"Captured: {mark(latest.get('captured_at') or 'unavailable')}")
        for key in ("tracks", "albums", "artists", "playlists"):
            value = latest.get(key)
            lines.append(f"- {key}: {value:,}" if number(value) is not None else f"- {key}: unavailable")
    else:
        lines.append("Unavailable: no usable saved library snapshot/summary.")
    lines.extend(["", "## Library growth and metadata change", ""])
    if result["library_deltas"]:
        lines.append(f"Compared {result['comparable_library_samples']} successful recorded samples for the same server/account scope.")
        lines.extend(f"- {key.replace('_', ' ')}: {value:+,}" for key, value in result["library_deltas"].items())
        lines.append("Negative missing-metadata/duplicate counts mean fewer findings, not proof of corrected audio files.")
    else:
        lines.append("Unavailable: at least two comparable successful library measurements are needed. Existing snapshots are not backdated into invented telemetry.")
    lines.extend(["", "## Recorded job outcomes", "", "Last 500 execution events only; skipped/started actions and this Insights job are excluded.", "",
                  "| Module | Successful | Failed | Interrupted | Observed success rate |", "|---|---:|---:|---:|---:|"])
    for module, counts in sorted(result["outcomes"].items()):
        total = sum(counts.values())
        rate = counts["success"] / total * 100
        lines.append(f"| {mark(module)} | {counts['success']} | {counts['failed']} | {counts['interrupted']} | {rate:.1f}% |")
    if not result["outcomes"]:
        lines.append("No completed job outcomes recorded; success rate unavailable.")
    lines.extend(["", "## Recent measured jobs and project health", "", "| UTC | Module | Outcome | Duration s | Controller CPU s | Controller RSS MiB |", "|---|---|---|---:|---:|---:|"])
    for point in result["recent_measurements"]:
        duration = point.get("duration_seconds")
        cpu = point.get("controller_cpu_seconds")
        rss = point.get("controller_rss_bytes")
        cpu_label = f"{cpu:.3f}" if number(cpu) is not None else "unavailable"
        rss_label = f"{rss / 1024**2:.1f}" if number(rss) is not None else "unavailable"
        duration_label = f"{duration:.3f}" if number(duration) is not None else "unavailable"
        lines.append(f"| {mark(point.get('at'))} | {mark(point['module'])} | {mark(point.get('status'))} | {duration_label} | {cpu_label} | {rss_label} |")
    lines.extend(["", "### Project-check observations", ""])
    for point in result["recent_measurements"]:
        if point["module"] == "dev":
            metrics = point["metrics"]
            if metrics.get("checks_requested"):
                lines.append(f"\nProject checks observed at {mark(point.get('at'))}: passed {metrics.get('checks_passed', 'unavailable')}; failed {metrics.get('checks_failed', 'unavailable')}; not run/unavailable {metrics.get('checks_unavailable', 'unavailable')}; repositories unavailable {metrics.get('repositories_unavailable', 'unavailable')}.\n")
    lines.extend(["", "Measurements start with this instrumentation and retain at most 1,000 points. CPU/RSS describe the Python controller only, not external test/build child processes. RSS is one completion observation, not a peak or system-wide usage trend.",
                  "A successful automation report does not mean every project check passed; inspect the separate check observations.",
                  "No resource history is inferred from the owner's historical reference measurements.", "", "## Backup history", "", result["backup_history"], ""])
    report_dir = Path(os.getenv("NYX_REPORT_DIR") or root / "reports").expanduser() / "Insights"
    dated = report_dir / f"Nyx Insights report - {datetime.now().astimezone():%Y-%m-%d}.md"
    atomic_write(dated, "\n".join(lines))
    atomic_write(report_dir / "Nyx Insights report - latest.md", "\n".join(lines))
    atomic_write(root / "state" / "insights-summary.json", json.dumps(result, indent=2))
    return dated
