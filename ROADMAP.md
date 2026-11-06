# Nyx roadmap

## Purpose and decisions

Nyx is a personal native Windows 11 idle automation system for an Intel i3-1115G4 laptop with 16 GB RAM. Rust is intended for the background engine and performance-sensitive work; Python is intended for API integrations, analysis, and reports. No WSL or Docker requirement, minimal dependencies, low resource use, and preservation of working code are permanent constraints unless the owner changes them.

Music operations are read-only by default. An analysis finding is never permission to move, rename, retag, deduplicate, or delete files. Destructive operations require approval. No new resident service or open-source license should be added incidentally.

Use this roadmap with `AGENTS.md` for persistent instructions and `ARCHITECTURE.md` for actual implementation. The sequence below reflects the owner's priorities; it is not a claim that later modules exist or authorization to implement every item now. No delivery dates have been committed.

## Inspected baseline

| Area | Status and evidence |
| --- | --- |
| Navidrome reporter | Working Python module; read-only HTTPS collection, diagnostics, Markdown output, previous-snapshot comparison |
| First successful report | Owner-reported: 1,736 tracks, 398 albums, 214 artists, 12 playlists at `https://vxsp.pikapod.net`; historical context, not freshly queried |
| Python admission checks | Implemented: enabled flag, cooldown, battery/RAM/CPU prechecks for `run`; manual `report` bypasses them |
| Rust controller | One-shot launcher source only; background engine/native idle detection not implemented; compilation unverified |
| Windows scheduling | PowerShell registration script exists; Task Scheduler integration unverified |
| Local validation | 15 offline Python tests passed; dependency check and three PowerShell syntax checks passed during preparation |
| GitHub preparation | Local `main` repository and initial commit exist; safe examples, ignore rules, source/tests/docs tracked |
| Public publication | Pending; no remote configured at this context update; secret gate below remains unresolved |
| Other priority modules and TUI | Planned; no implemented modules or placeholder functionality should be counted as working |

The baseline was established by inspecting source, scripts, configuration, tests, and Git state. Do not infer completed functionality from a module name or roadmap entry. Detailed music metadata, report contents, credentials, and state remain outside Git.

## Foundation: context and safe publication

Current focus: establish durable context and finish safe repository preparation without implementing new product features.

- [x] Preserve and inspect the existing Python reporter and Rust launcher.
- [x] Document Windows setup, commands, implemented/planned status, boundaries, and development conventions.
- [x] Exclude credentials, environments, generated data, archives, binaries, and private media from Git.
- [x] Add meaningful offline safety tests and validate the current Python environment.
- [x] Establish `AGENTS.md`, `ARCHITECTURE.md`, and this roadmap as the project handoff.
- [ ] Resolve the owner's publication secret gate: the preparation audit detected a password in ignored `config/.env`; no matching credential was found in the initial committed tree/history. Preserve it locally. Obtain the owner's direction before publication; do not rotate, delete, or bypass the rule. This finding alone does not prove exposure.
- [x] Verify the connected GitHub identity: the read-only connector returned account `vxsp`.
- [ ] Resolve repository availability before creation/reuse. The connector lookup for `vxsp/nyx` returned 404, which can mean absent or inaccessible; it does not establish availability. Recheck ownership/purpose and never overwrite an unrelated repository. Repository creation/push permissions are not yet verified.
- [ ] Repeat secret and private-data checks against the exact candidate commit and reachable history before publishing.
- [ ] Publish the approved source/docs/tests to public `nyx`, configure `origin`, push `main`, and verify remote contents. Do not add a license without approval.

Completion means a verified public repository containing the intended files, with private files excluded and no unresolved publication blocker. Record its actual URL and validation results when available; do not invent a target URL from an assumed account.

## Priority 1: Navidrome reporting and reliable idle execution

Status: the reporter works; the following improvements are planned.

- Adopt the accepted report filename prefix `Navidrome report`: planned dated name `Navidrome report YYYY-MM-DD.md` and latest name `Navidrome report Latest.md`, retaining the `Navidrome/` subdirectory. Existing `YYYY-MM-DD.md` and `Latest.md` output is current behavior, not compliance with the new prefix yet.
- Implement naming in a separately authorized change with offline path tests, correct last-run paths, and updated usage documentation. Preserve private historical reports/snapshots; no automatic cleanup or renaming during preparation.
- Validate the Rust launcher build, command forwarding, working-directory assumptions, and failure exit behavior on native Windows.
- Validate idle admission, stop-on-activity, AC/battery behavior, no waking, and task instance policy. Inspect any existing `Nyx` task and obtain approval before replacement.
- Harden settings/API/state validation, full-operation runtime bounds, concurrent-run protection, and interrupted-write recovery.
- Measure CPU, memory, elapsed time, and request volume on the target laptop using private local output. Set measurable budgets from evidence rather than claiming limits are enforced continuously today.
- Define the Rust background engine's lifecycle and Python job contract before adding persistent execution or native idle detection. Keep Task Scheduler behavior available until an explicitly approved replacement is verified.

Acceptance: reporting remains read-only and successful; output uses the agreed prefix after implementation; failures preserve usable prior state; native Windows lifecycle checks are recorded; measured resource use is acceptable to the owner. Do not contact the live server as part of offline tests.

## Priority 2: Coding project testing and maintenance

Status: planned. Existing Nyx unit tests are development checks, not an automation module for other repositories.

Start with explicitly allowlisted local repositories and project-declared test commands. Run bounded, cancellable checks and generate Markdown results. Treat repository commands as executable code, not inherently read-only. Report dirty state and proposed maintenance; do not commit, reset, clean, install dependencies, or update projects without the required scope/approval. Never publish repository secrets or private test output.

Acceptance: one explicitly selected project's checks run with a clear execution policy and produce a useful report without incidental changes to its files or Git state.

## Priority 3: Music and FL Studio organization

Status: planned. Navidrome metadata diagnostics do not provide local audio inspection or FL Studio project analysis.

Begin with allowlisted directories and read-only inventory, metadata diagnostics, duplicate candidates, and FL Studio project/sample-reference reporting. Explain supported formats and confidence limits. Produce proposed organization actions for review; do not move, rename, retag, or delete originals by default.

Acceptance: synthetic fixtures and an approved local scan demonstrate useful diagnostics with original files unchanged and private paths excluded from public output.

## Priority 4: Automated research reports

Status: planned. Define explicit topics, approved sources, execution/fetch budgets, report cadence, and source attribution. Keep API credentials private. Avoid adding an AI provider, subscription, browser service, or research framework before the requirement is defined.

Acceptance: one approved topic produces a dated Markdown report with traceable sources, timestamps, limitations, bounded execution, and no secret disclosure. Historical analytics across jobs remains planned until its storage and retention are implemented and tested.

## Priority 5: Backups and PC maintenance

Status: planned. Begin with read-only health/inventory reports, then design incremental backup sources, destinations, retention, integrity verification, and restore checks. Backup output remains private. Validate resolved Windows paths and keep source files unchanged.

Acceptance: an explicitly approved backup can be restored and verified. Cleanup, pruning, overwriting unrelated destinations, system changes, or deletion require separate approval and a reviewed plan; no destructive default maintenance.

## Priority 6: Interactive terminal dashboard

Status: planned. Plan a visual terminal interface for job status, idle/resource decisions, progress, history, and report locations. It should consume the engine's state/results rather than duplicate job logic. Select a suitable implementation after the engine interface is defined; no TUI library is chosen yet.

Acceptance: a native Windows terminal session displays real engine state responsively with low overhead, supports safe navigation, and closes without disrupting jobs or requiring another service. Controls that mutate data need explicit safety behavior.

## Keeping the roadmap current

For each relevant development change, update its status here, actual behavior in `ARCHITECTURE.md`, durable decisions in `AGENTS.md`, and user-facing behavior in `README.md`. Record what was implemented, how it was validated, missing prerequisites, and the next actionable milestone. Mark completion only with implementation and evidence; keep owner-reported observations distinct from fresh checks. Preserve the priority order unless the owner changes it.

Next action: finish documentation and candidate-commit checks, resolve the publication gate, then recheck repository availability and verify write/push access. Product work starts with Priority 1 after preparation; do not implement later modules opportunistically.
