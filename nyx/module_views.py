"""Independent saved-data module workspaces; job execution belongs to the app shell."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Markdown, Static, TabPane

from nyx.modules import Module
from nyx.saved import DashboardStore, ModuleData


def metric(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else "--"


def records(value: object) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def summary_text(key: str, snapshot: dict) -> str:
    if not snapshot:
        return "No usable saved data for this module. Review its setup instructions, then explicitly generate a report."
    if key == "navidrome":
        scan = snapshot.get("scan") if isinstance(snapshot.get("scan"), dict) else {}
        scanning = "yes" if scan.get("scanning") is True else "no" if scan.get("scanning") is False else "unavailable"
        size = snapshot.get("reported_file_bytes")
        size_label = f"{size / 1024**3:.2f} GiB" if isinstance(size, (int, float)) and not isinstance(size, bool) and size >= 0 else "unavailable"
        changes = (f"Added: {metric(snapshot.get('added_count'))}   Removed: {metric(snapshot.get('removed_count'))}"
                   if snapshot.get("has_previous") else "Library change history: no comparison saved")
        return f"Indexed sizes: {size_label} | Scan status at capture: {scanning}\nCollection: {snapshot.get('duration_seconds', 'unavailable')} seconds\n{changes}"
    if key == "dev":
        if not isinstance(snapshot.get("repositories"), list):
            return "Saved project statistics are unavailable. Generate a Dev report explicitly."
        projects = records(snapshot.get("repositories"))
        checks = [check for project in projects for check in records(project.get("checks"))]
        requested = "yes" if snapshot.get("checks_requested") is True else "no" if snapshot.get("checks_requested") is False else "unavailable"
        return (f"Projects in last report: {len(projects)} | Inspected: {sum(p.get('status') == 'inspected' for p in projects)}\n"
                f"Project commands requested: {requested} | Check results recorded: {len(checks)}\n"
                "Report completion does not mean every project check passed.")
    if key == "audio":
        scope = "complete" if snapshot.get("complete") is True else "partial or unavailable"
        return (f"Audio files: {metric(snapshot.get('audio_files'))} | FL Studio projects: {metric(snapshot.get('fl_studio_projects'))}\n"
                f"Configured roots: {metric(snapshot.get('configured_roots'))} | Scope: {scope}\n"
                "Same-name/size matches are candidates; FLP sample-reference analysis is unavailable.")
    if key == "research":
        if not isinstance(snapshot.get("items"), list) or not isinstance(snapshot.get("sources"), list):
            return "Saved research statistics are unavailable. Generate a research digest explicitly."
        items, sources = records(snapshot.get("items")), records(snapshot.get("sources"))
        return (f"Retained entries: {len(items)} | Explicitly read: {sum(bool(item.get('read_at')) for item in items)}\n"
                f"Sources collected: {sum(item.get('status') == 'collected' for item in sources)} | Unavailable: {sum(item.get('status') == 'unavailable' for item in sources)}\n"
                "Marking articles read is explicit through CLI research-read --item-id; browsing does not mark them read.")
    return f"Recorded measurements: {metric(snapshot.get('measurement_count'))}\nTrends require comparable observations; missing history stays unavailable."


class ModulePane(TabPane):
    """A module owns its status, history, report selection and preview."""

    def __init__(self, module: Module, number: int):
        super().__init__(f"{number} {module.title}", id=module.key)
        self.module = module
        self._reports: list[Path] = []
        self._selected: Path | None = None
        self._store: DashboardStore | None = None
        self._preview_signature: tuple | None = None

    def compose(self) -> ComposeResult:
        key = self.module.key
        with VerticalScroll(classes="module-content"):
            yield Static(self.module.title.upper(), classes="section")
            action_id = "run-report" if key == "navidrome" else f"run-{key}"
            yield Button(self.module.action, id=action_id, variant="primary", classes="module-run")
            yield Static(self.module.help, classes="hint")
            yield Static("", id=f"{key}-status", markup=False, classes="hint")
            if key == "navidrome":
                with Horizontal(id="metrics"):
                    for name in ("tracks", "albums", "artists", "playlists"):
                        yield Static("--", id=name, classes="metric")
                yield Static("", id="capture", markup=False)
                yield Static("", id="overview-detail", markup=False, classes="panel")
                yield Static("", id="notices", markup=False)
                yield Static("AUDIO FORMATS", classes="section")
                yield DataTable(id="formats", cursor_type="row", zebra_stripes=True)
                yield Static("LIBRARY DIAGNOSTICS", classes="section")
                yield DataTable(id="diagnostics", cursor_type="row", zebra_stripes=True)
                yield Static("Duplicate groups are candidates; missing artwork references do not prove missing embedded artwork.", classes="hint")
            else:
                yield Static("", id=f"{key}-summary", markup=False, classes="panel")
            yield Static("MODULE HISTORY / SAVED EVENTS", classes="section")
            yield DataTable(id=f"{key}-history", cursor_type="row", zebra_stripes=True, classes="module-history")
            yield Static("THIS MODULE'S REPORTS", classes="section")
            yield DataTable(id=f"{key}-reports", cursor_type="row", zebra_stripes=True, classes="module-reports")
            with VerticalScroll(classes="module-preview"):
                yield Markdown("# No saved report\n\nGenerate this module's report explicitly.", id=f"{key}-body", open_links=False)

    def on_mount(self) -> None:
        key = self.module.key
        self.query_one(f"#{key}-history", DataTable).add_columns("UTC", "Status", "Phase / detail")
        self.query_one(f"#{key}-reports", DataTable).add_columns("Saved module report")
        if key == "navidrome":
            self.query_one("#formats", DataTable).add_columns("Format", "Tracks")
            self.query_one("#diagnostics", DataTable).add_columns("Diagnostic", "Count")

    def update_saved(self, data: ModuleData, store: DashboardStore) -> None:
        self._store = store
        key, snapshot = self.module.key, data.snapshot
        latest = data.history[-1] if data.history else {}
        self.query_one(f"#{key}-status", Static).update(Text(
            f"Last saved event: {latest.get('status', 'unavailable')} | {latest.get('at', '--')}\n"
            f"Last successful report: {data.last_run.get('completed_at', 'unavailable')}\n"
            f"Data captured: {snapshot.get('captured_at', 'unavailable')} (UTC). Saved running events may be stale."
        ))
        summary_id = "overview-detail" if key == "navidrome" else f"{key}-summary"
        self.query_one(f"#{summary_id}", Static).update(Text(summary_text(key, snapshot)))
        if key == "navidrome":
            for name in ("tracks", "albums", "artists", "playlists"):
                self.query_one(f"#{name}", Static).update(Text(f"{metric(snapshot.get(name))}\n{name.upper()}"))
            self.query_one("#capture", Static).update(Text(f"Captured: {snapshot.get('captured_at') or 'unavailable'} (UTC) | Refresh reads disk only"))
            for table_id, field in (("formats", "formats"), ("diagnostics", "missing_metadata")):
                table = self.query_one(f"#{table_id}", DataTable)
                table.clear()
                values = snapshot.get(field, {})
                if isinstance(values, dict):
                    for name, count in values.items():
                        label = str(name).upper() if table_id == "formats" else str(name).replace("_", " ")
                        table.add_row(Text(label), Text(metric(count)))
            self.query_one("#diagnostics", DataTable).add_row(Text("Possible duplicate groups"), Text(metric(snapshot.get("duplicate_groups"))))
        history = self.query_one(f"#{key}-history", DataTable)
        history.clear()
        for event in reversed(data.history):
            history.add_row(*[Text(str(value)) for value in (
                event.get("at", "--"), event.get("status", "--"),
                event.get("phase") or event.get("reason") or event.get("error_type") or "--",
            )])
        self._reports = data.reports
        reports = self.query_one(f"#{key}-reports", DataTable)
        reports.clear()
        for index, path in enumerate(self._reports):
            reports.add_row(Text(path.name), key=str(index))
        if self._selected not in self._reports:
            self._selected = next((path for path in self._reports if path.name.endswith(" - latest.md")),
                                  self._reports[0] if self._reports else None)
        self._update_preview()

    def _update_preview(self) -> None:
        try:
            stat = self._selected.stat() if self._selected else None
            signature = (self._selected, stat.st_mtime_ns, stat.st_size) if stat else (None,)
        except OSError:
            signature = (None,)
        if signature == self._preview_signature:
            return
        content = self._store.read_report(self._selected) if self._store and self._selected else "# No saved report\n\nGenerate this module's report explicitly."
        self.query_one(f"#{self.module.key}-body", Markdown).update(content)
        self._preview_signature = signature

    @on(DataTable.RowSelected, ".module-reports")
    def select_report(self, event: DataTable.RowSelected) -> None:
        event.stop()
        if event.row_key.value is not None:
            index = int(event.row_key.value)
            if 0 <= index < len(self._reports):
                self._selected = self._reports[index]
                self._update_preview()
