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
from textual.widgets import Button, DataTable, Footer, Header, Log, Markdown, Select, Static, TabbedContent, TabPane

from nyx.logging import redact
from nyx.modules import MODULES, BY_COMMAND
from nyx.module_views import ModulePane
from nyx.runtime import JobBusyError, job_lock, record_event
from nyx.saved import DashboardStore
from nyx.themes import AMOLED_THEME, NYX_THEME, THEME_CHOICES, THEME_NAMES, load_theme, save_theme


class NyxApp(App):
    TITLE = "NYX"
    SUB_TITLE = "Idle automation / module workspaces"
    CSS_PATH = "tui.tcss"
    BINDINGS = [
        Binding("r", "refresh_saved", "Refresh saved"),
        Binding("n", "run_report", "Navidrome report"),
        Binding("x", "cancel_report", "Cancel owned job"),
        Binding("1", "tab('overview')", "Overview", show=False),
        Binding("2", "tab('navidrome')", "Navidrome", show=False),
        Binding("3", "tab('dev')", "Dev", show=False),
        Binding("4", "tab('audio')", "Audio", show=False),
        Binding("5", "tab('research')", "Research", show=False),
        Binding("6", "tab('insights')", "Insights", show=False),
        Binding("7", "tab('jobs')", "Jobs", show=False),
        Binding("8", "tab('reports')", "Reports", show=False),
        Binding("9", "tab('errors')", "Errors", show=False),
        Binding("i", "insights_report", "Local insights"),
        Binding("t", "cycle_theme", "Theme"),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self, root: Path):
        super().__init__()
        self.root = root.resolve()
        self._theme_ready = False
        self.register_theme(NYX_THEME)
        self.register_theme(AMOLED_THEME)
        self.theme = load_theme(self.root)
        self.store = DashboardStore(self.root)
        self.running_report = False
        self.process: asyncio.subprocess.Process | None = None
        self._cancel_requested = False
        self._owned_command = "report"
        self._selected_report: Path | None = None
        self.saved = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="toolbar"):
            yield Static("SAVED STATE  /  No scan on startup  /  Native Windows", id="mode")
            yield Select(THEME_CHOICES, value=self.theme, allow_blank=False, id="theme-select",
                         tooltip="Theme / press T to cycle; saved locally")
        with TabbedContent(initial="overview", id="workspace"):
            with TabPane("1 Overview", id="overview"):
                with VerticalScroll():
                    yield Static("YOUR MODULES", classes="section")
                    yield Static("Select a module below or use 2-6. Each workspace has its own saved status, actions, history and reports.", classes="hint")
                    yield DataTable(id="module-list", cursor_type="row", zebra_stripes=True)
                    yield Button("Refresh saved [R]", id="refresh")
                    yield Static("", id="shared-notices", markup=False)
                    yield Static("Opening modules and refreshing only read saved files. Jobs run only when explicitly requested.", classes="hint")
            for number, module in enumerate(MODULES, start=2):
                yield ModulePane(module, number)
            with TabPane("7 Jobs", id="jobs"):
                yield Static("", id="job-status", markup=False, classes="panel")
                yield Static("EXECUTION HISTORY / LAST 500 EVENTS", classes="section")
                yield DataTable(id="history", cursor_type="row", zebra_stripes=True)
                yield Static("MANUAL JOB OUTPUT", classes="section")
                yield Log(id="job-output", max_lines=200, highlight=False)
            with TabPane("8 All reports", id="reports"):
                yield Static("Select a report and press Enter. Both new and legacy filenames are supported.", classes="hint")
                yield DataTable(id="report-list", cursor_type="row", zebra_stripes=True)
                with VerticalScroll(id="report-preview"):
                    yield Markdown("# No saved report\n\nGenerate a module report explicitly.", id="report-body", open_links=False)
            with TabPane("9 Errors", id="errors"):
                yield Static("WARNINGS & ERRORS / PRIVATE ROTATING LOG", classes="section")
                yield Log(id="error-log", max_lines=500, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#module-list", DataTable).add_columns("Module", "Last saved event", "Last successful report (UTC)", "Reports")
        self.query_one("#history", DataTable).add_columns("UTC", "Module", "Status", "Phase / detail")
        self.query_one("#report-list", DataTable).add_columns("Saved report")
        self.action_refresh_saved()
        self._theme_ready = True

    @on(Select.Changed, "#theme-select")
    def select_theme(self, event: Select.Changed) -> None:
        if event.value in THEME_NAMES and event.value != self.theme:
            self.theme = event.value

    def action_cycle_theme(self) -> None:
        index = THEME_NAMES.index(self.theme) if self.theme in THEME_NAMES else -1
        self.theme = THEME_NAMES[(index + 1) % len(THEME_NAMES)]

    def watch_theme(self, name: str) -> None:
        # Textual applies its own theme watcher; this public watcher handles our preference.
        if not getattr(self, "_theme_ready", False) or name not in THEME_NAMES:
            return
        self.query_one("#theme-select", Select).value = name
        try:
            save_theme(self.root, name)
        except OSError:
            self.notify("Theme applied for this session; the preference could not be saved.", severity="warning")

    def action_tab(self, tab: str) -> None:
        # A focused control in a hidden pane can otherwise reactivate its old tab.
        self.set_focus(None)
        self.query_one("#workspace", TabbedContent).active = tab
        for widget in self.query_one(f"#{tab}", TabPane).query("Button, DataTable, Log"):
            if not widget.disabled:
                widget.focus(scroll_visible=False)
                break

    def action_refresh_saved(self) -> None:
        self.saved = self.store.load()
        modules = self.query_one("#module-list", DataTable)
        modules.clear()
        for module in MODULES:
            data = self.saved.modules[module.key]
            self.query_one(f"#{module.key}", ModulePane).update_saved(data, self.store)
            latest = data.history[-1] if data.history else {}
            modules.add_row(Text(module.title), Text(str(latest.get("status", "No saved event"))),
                            Text(str(data.last_run.get("completed_at", "No saved report"))),
                            Text(str(len(data.reports))), key=module.key)
        self.query_one("#shared-notices", Static).update(Text("\n".join(dict.fromkeys(self.saved.notices))))
        self.query_one("#notices", Static).update(Text("No usable saved Navidrome data." if not self.saved.summary else ""))
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
        else:
            self.query_one("#report-body", Markdown).update("# No saved report\n\nGenerate a module report explicitly.")
        errors = self.query_one("#error-log", Log)
        errors.clear()
        errors.write_lines(self.saved.errors or ["No saved warnings or errors."])

    @on(DataTable.RowSelected, "#module-list")
    def select_module(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is not None:
            self.action_tab(str(event.row_key.value))

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

    @on(Button.Pressed, ".module-run")
    def run_module(self, event: Button.Pressed) -> None:
        for module in MODULES:
            button_id = "run-report" if module.key == "navidrome" else f"run-{module.key}"
            if event.button.id == button_id:
                self.start_job(module.command)
                return

    def action_run_report(self) -> None:
        self.start_job("report")

    def action_insights_report(self) -> None:
        self.start_job("insights-report")

    def start_job(self, command: str) -> None:
        if command not in BY_COMMAND:
            self.notify("Unsupported module action.", severity="warning")
            return
        if self.running_report:
            self.notify("This dashboard already owns a running report.", severity="warning")
            return
        self.running_report = True
        self._owned_command = command
        self._cancel_requested = False
        for button in self.query(".module-run"):
            button.disabled = True
        self.action_tab("jobs")
        self.query_one("#job-output", Log).clear()
        self.collect_report()

    @work(group="manual-report", exit_on_error=False)
    async def collect_report(self) -> None:
        output = self.query_one("#job-output", Log)
        try:
            flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, str(self.root / "main.py"), self._owned_command, cwd=self.root,
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
            for button in self.query(".module-run"):
                button.disabled = False
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
                    record_event(self.root, "interrupted", reason="Dashboard-owned process stopped",
                                 module=BY_COMMAND[self._owned_command].key)
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
