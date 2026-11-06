"""Read saved dashboard data without network requests or state writes."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from jobs.navidrome import summarize
from nyx.logging import redact
from nyx.modules import MODULES, event_module


def read_json(path: Path) -> dict:
    try:
        if path.stat().st_size > 64 * 1024 * 1024:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def tail(path: Path, limit: int = 256 * 1024) -> list[str]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            start = max(0, handle.tell() - limit)
            handle.seek(start)
            if start:
                handle.readline()
            return handle.read(limit).decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


@dataclass
class ModuleData:
    snapshot: dict = field(default_factory=dict)
    last_run: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    reports: list[Path] = field(default_factory=list)


@dataclass
class SavedData:
    summary: dict = field(default_factory=dict)
    job: dict = field(default_factory=dict)
    last_run: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    reports: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    modules: dict[str, ModuleData] = field(default_factory=dict)


class DashboardStore:
    def __init__(self, root: Path):
        self.root = root
        self._snapshot_signature = None
        self._snapshot_summary: dict = {}
        self._module_cache: dict[str, tuple[tuple, dict]] = {}

    def _module_snapshot(self, filename: str) -> dict:
        path = self.root / "state" / filename
        try:
            stat = path.stat()
        except OSError:
            self._module_cache.pop(filename, None)
            return {}
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._module_cache.get(filename)
        if cached is None or cached[0] != signature:
            self._module_cache[filename] = (signature, read_json(path))
        return self._module_cache[filename][1]

    @property
    def report_dir(self) -> Path:
        return Path(os.getenv("NYX_REPORT_DIR") or self.root / "reports").expanduser().resolve()

    def _legacy_summary(self) -> dict:
        path = self.root / "state" / "navidrome-last.json"
        try:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            return {}
        if signature != self._snapshot_signature:
            snapshot = read_json(path)
            self._snapshot_summary = {}
            try:
                stats = summarize(snapshot, {})
                self._snapshot_summary = {
                    **{key: stats[key] for key in ("tracks", "albums", "artists", "playlists", "formats", "reported_file_bytes")},
                    "captured_at": snapshot.get("captured_at"),
                    "duration_seconds": snapshot.get("duration_seconds"),
                    "scan": snapshot.get("scan", {}),
                    "missing_metadata": {key: len(value) for key, value in stats["problems"].items()},
                    "duplicate_groups": len(stats["duplicate_candidates"]),
                    "has_previous": False,
                }
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
            self._snapshot_signature = signature
        return self._snapshot_summary

    def load(self) -> SavedData:
        data = SavedData()
        data.summary = read_json(self.root / "state" / "navidrome-summary.json")
        if not data.summary:
            data.summary = self._legacy_summary()
            if data.summary:
                data.notices.append("Statistics derived from the saved legacy snapshot; no server scan was started.")
        if not data.summary:
            data.notices.append("No usable saved library data. Run a report explicitly to collect it.")
        data.job = read_json(self.root / "state" / "current-job.json")
        data.last_run = read_json(self.root / "state" / "last-run.json")
        for line in tail(self.root / "state" / "history.jsonl")[-500:]:
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    data.history.append(event)
            except ValueError:
                data.notices.append("An invalid history entry was skipped.")
        module_reports: dict[str, list[Path]] = {}
        for module in MODULES:
            try:
                folder = self.report_dir / module.folder
                candidates = [path for path in folder.glob("*.md") if path.is_file() and path.resolve().is_relative_to(folder)]
                module_reports[module.key] = sorted(candidates, key=lambda path: path.stat().st_mtime_ns, reverse=True)[:200]
            except (OSError, ValueError):
                module_reports[module.key] = []
                data.notices.append(f"The {module.title} report directory could not be read.")
        try:
            data.reports = sorted((path for paths in module_reports.values() for path in paths),
                                  key=lambda path: path.stat().st_mtime_ns, reverse=True)[:200]
        except OSError:
            data.notices.append("The shared report list changed while it was being read; refresh to retry.")
        for module in MODULES:
            data.modules[module.key] = ModuleData(
                snapshot=data.summary if module.key == "navidrome" else self._module_snapshot(module.snapshot),
                last_run=data.last_run if module.key == "navidrome" else read_json(self.root / "state" / f"{module.key}-last-run.json"),
                history=[event for event in data.history if event_module(event) == module.key],
                reports=module_reports[module.key],
            )
        for line in tail(self.root / "logs" / "nyx.log")[-500:]:
            try:
                entry = json.loads(line)
                if isinstance(entry, dict) and entry.get("level") in ("ERROR", "WARNING", "CRITICAL"):
                    data.errors.append(redact(f"{entry.get('at', '')} {entry.get('level', '')} {entry.get('message', '')}"))
            except ValueError:
                data.errors.append("An invalid log entry was skipped.")
        return data

    def read_report(self, path: Path) -> str:
        try:
            if not path.resolve().is_relative_to(self.report_dir) or path.suffix.lower() != ".md":
                return "# Report unavailable\n\nThe selected file is outside the configured report directory."
            if path.stat().st_size > 512 * 1024:
                return "# Report too large\n\nOpen this report in your editor (preview limit: 512 KiB)."
            return path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            return "# Report unavailable\n\nThe selected report could not be read."
