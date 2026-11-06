"""Saved-state terminal dashboard; report execution stays in a separate process."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Log, Markdown, Static, TabbedContent, TabPane

from nyx.logging import redact
from nyx.runtime import JobBusyError, job_lock, record_event
from nyx.saved import DashboardStore


def metric(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else "--"


class NyxApp(App):
    TITLE = "NYX"
    SUB_TITLE = "Idle automation / saved library workspace"
    CSS_PATH = "tui.tcss"
    BINDINGS = [
        Binding("r", "refresh_saved", "Refresh saved"),
        Binding("n", "run_report", "Run report"),
        Binding("x", "cancel_report", "Cancel owned job"),
        Binding("1", "tab('overview')", "Overview", show=False),
        Binding("2", "tab('library')", "Library", show=False),
        Binding("3", "tab('jobs')", "Jobs", show=False),
        Binding("4", "tab('reports')", "Reports", show=False),
        Binding("5", "tab('errors')", "Errors", show=False),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self, root: Path):
        super().__init__()
        self.root = root.resolve()
        self.store = DashboardStore(self.root)
        self.running_report = False
        self.process: asyncio.subprocess.Process | None = None
        self._cancel_requested = False
        self._selected_report: Path | None = None
        self.saved = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("SAVED STATE  /  No scan on startup  /  Native Windows", id="mode")
        with TabbedContent(initial="overview", id="workspace"):
            with TabPane("1 Overview", id="overview"):
                with VerticalScroll():
                    yield Static("YOUR LIBRARY, AT A GLANCE", classes="section")
                    with Horizontal(id="metrics"):
                        for key in ("tracks", "albums", "artists", "playlists"):
                            yield Static("--", id=key, classes="metric")
                    yield Static("No saved report", id="capture", markup=False)
                    yield Static("", id="overview-detail", markup=False, classes="panel")
                    yield Static("", id="notices", markup=False)
                    with Horizontal(classes="actions"):
                        yield Button("Refresh saved [R]", id="refresh")
                        yield Button("Run report [N]", id="run-report", variant="primary")
                    yield Static("Manual reports bypass cooldown/resource admission checks. Music files and server metadata stay read-only.", classes="hint")
            with TabPane("2 Library", id="library"):
                with VerticalScroll():
                    yield Static("AUDIO FORMATS", classes="section")
                    yield DataTable(id="formats", cursor_type="row", zebra_stripes=True)
                    yield Static("LIBRARY DIAGNOSTICS", classes="section")
                    yield DataTable(id="diagnostics", cursor_type="row", zebra_stripes=True)
                    yield Static("Duplicate groups are candidates; missing artwork references do not prove missing embedded artwork.", classes="hint")
            with TabPane("3 Jobs", id="jobs"):
                yield Static("", id="job-status", markup=False, classes="panel")
                yield Static("EXECUTION HISTORY / LAST 500 EVENTS", classes="section")
                yield DataTable(id="history", cursor_type="row", zebra_stripes=True)
                yield Static("MANUAL JOB OUTPUT", classes="section")
                yield Log(id="job-output", max_lines=200, highlight=False)
            with TabPane("4 Reports", id="reports"):
                yield Static("Select a report and press Enter. Both new and legacy filenames are supported.", classes="hint")
                yield DataTable(id="report-list", cursor_type="row", zebra_stripes=True)
                with VerticalScroll(id="report-preview"):
                    yield Markdown("# No saved report\n\nRun a report explicitly to collect library data.", id="report-body", open_links=False)
            with TabPane("5 Errors", id="errors"):
                yield Static("WARNINGS & ERRORS / PRIVATE ROTATING LOG", classes="section")
                yield Log(id="error-log", max_lines=500, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#formats", DataTable).add_columns("Format", "Tracks")
        self.query_one("#diagnostics", DataTable).add_columns("Diagnostic", "Count")
        self.query_one("#history", DataTable).add_columns("UTC", "Module", "Status", "Phase / detail")
        self.query_one("#report-list", DataTable).add_columns("Saved report")
        self.action_refresh_saved()

    def action_tab(self, tab: str) -> None:
        self.query_one("#workspace", TabbedContent).active = tab

    def action_refresh_saved(self) -> None:
        self.saved = self.store.load()
        summary = self.saved.summary
        for name in ("tracks", "albums", "artists", "playlists"):
            self.query_one("#" + name, Static).update(Text(f"{metric(summary.get(name))}\n{name.upper()}"))
        self.query_one("#capture", Static).update(Text(f"Captured: {summary.get('captured_at') or 'unavailable'} (UTC) | Refresh reads disk only"))
        scan = summary.get("scan") if isinstance(summary.get("scan"), dict) else {}
        scanning = "yes" if scan.get("scanning") is True else "no" if scan.get("scanning") is False else "unavailable"
        size = summary.get("reported_file_bytes")
        size_label = f"{size / 1024**3:.2f} GiB" if isinstance(size, (int, float)) and size >= 0 else "unavailable"
        changes = (f"Added: {metric(summary.get('added_count'))}   Removed: {metric(summary.get('removed_count'))}"
                   if summary.get("has_previous") else "Library change history: no comparison saved")
        self.query_one("#overview-detail", Static).update(Text(
            f"Indexed sizes: {size_label}   |   Scan status at capture: {scanning}\n"
            f"Collection: {summary.get('duration_seconds', 'unavailable')} seconds\n{changes}\n"
            f"Last successful job: {self.saved.last_run.get('completed_at', 'unavailable')}"
        ))
        self.query_one("#notices", Static).update(Text("\n".join(dict.fromkeys(self.saved.notices))))
        formats = self.query_one("#formats", DataTable)
        formats.clear()
        values = summary.get("formats", {})
        if isinstance(values, dict):
            for name, count in values.items():
                formats.add_row(Text(str(name).upper()), Text(metric(count)))
        diagnostics = self.query_one("#diagnostics", DataTable)
        diagnostics.clear()
        values = summary.get("missing_metadata", {})
        if isinstance(values, dict):
            for name, count in values.items():
                diagnostics.add_row(Text(str(name).replace("_", " ")), Text(metric(count)))
        diagnostics.add_row(Text("Possible duplicate groups"), Text(metric(summary.get("duplicate_groups"))))
        status = self.saved.job
        owned = "Running (owned manual process)" if self.running_report else "No manual process owned by this dashboard"
        self.query_one("#job-status", Static).update(Text(
            f"{owned}\nLast recorded state: {status.get('module', '--')} / {status.get('status', 'unavailable')} / {status.get('phase', '--')}\n"
            f"Progress: {status.get('completed', '--')} / {status.get('total', '--')}   Recorded: {status.get('at', '--')}\n"
            "Saved running state may be stale after a crash; it does not prove an active process."
        ))
        history = self.query_one("#history", DataTable)
        history.clear()
        for event in reversed(self.saved.history):
            history.add_row(*[Text(str(value)) for value in (
                event.get("at", "--"), event.get("module", "--"), event.get("status", "--"),
                event.get("phase") or event.get("reason") or event.get("error_type") or "--",
            )])
        reports = self.query_one("#report-list", DataTable)
        reports.clear()
        for index, path in enumerate(self.saved.reports):
            reports.add_row(Text(str(path.relative_to(self.store.report_dir))), key=str(index))
        if self._selected_report not in self.saved.reports:
            self._selected_report = next((p for p in self.saved.reports if p.name == "Navidrome report - latest.md"),
                                         self.saved.reports[0] if self.saved.reports else None)
        if self._selected_report:
            self.query_one("#report-body", Markdown).update(self.store.read_report(self._selected_report))
        errors = self.query_one("#error-log", Log)
        errors.clear()
        errors.write_lines(self.saved.errors or ["No saved warnings or errors."])

    @on(DataTable.RowSelected, "#report-list")
    def select_report(self, event: DataTable.RowSelected) -> None:
        if self.saved and event.row_key.value is not None:
            index = int(event.row_key.value)
            if 0 <= index < len(self.saved.reports):
                self._selected_report = self.saved.reports[index]
                self.query_one("#report-body", Markdown).update(self.store.read_report(self._selected_report))

    @on(Button.Pressed, "#refresh")
    def refresh_button(self) -> None:
        self.action_refresh_saved()

    @on(Button.Pressed, "#run-report")
    def run_button(self) -> None:
        self.action_run_report()

    def action_run_report(self) -> None:
        if self.running_report:
            self.notify("This dashboard already owns a running report.", severity="warning")
            return
        self.running_report = True
        self._cancel_requested = False
        self.query_one("#run-report", Button).disabled = True
        self.action_tab("jobs")
        self.query_one("#job-output", Log).clear()
        self.collect_report()

    @work(group="manual-report", exit_on_error=False)
    async def collect_report(self) -> None:
        output = self.query_one("#job-output", Log)
        try:
            flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, str(self.root / "main.py"), "report", cwd=self.root,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **flags,
            )
            if self._cancel_requested:
                await self.stop_owned_process()
            assert self.process.stdout is not None
            while line := await self.process.stdout.readline():
                output.write_line(redact(line.decode("utf-8", errors="replace").rstrip()))
                self.action_refresh_saved()
            code = await self.process.wait()
            output.write_line(f"Report process exited with code {code}.")
            self.notify("Report finished." if code == 0 else "Report did not complete; inspect job output.",
                        severity="information" if code == 0 else "warning")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            output.write_line(f"Could not complete report process: {type(exc).__name__} (details withheld).")
        finally:
            await self.stop_owned_process()
            self.process = None
            self.running_report = False
            self.query_one("#run-report", Button).disabled = False
            self.action_refresh_saved()

    async def stop_owned_process(self) -> None:
        process = self.process
        if process is None or process.returncode is not None:
            return
        try:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            try:
                with job_lock(self.root):
                    record_event(self.root, "interrupted", reason="Dashboard-owned process stopped")
            except (JobBusyError, OSError):
                pass
        except ProcessLookupError:
            pass

    async def action_cancel_report(self) -> None:
        if self.running_report:
            self._cancel_requested = True
            await self.stop_owned_process()

    async def action_quit(self) -> None:
        if self.running_report:
            self.notify("Report active. Press X to cancel your manual job, then Q to quit.", severity="warning")
            return
        self.exit()
