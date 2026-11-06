# Nyx roadmap

The owner's autonomous directive authorizes verified development increments, commits, and pushes to public `vxsp/nyx`. Preserve working code and existing history. Native Windows 11, Intel i3-1115G4, 16 GB RAM; no WSL/Docker requirement. Rust owns the future engine and performance-sensitive work; Python owns integrations, analysis, reports, and the initial Textual TUI. Keep dependencies and resource use low.

This file is the primary task queue. Read it with `AGENTS.md`, `ARCHITECTURE.md`, `README.md`, `CONTRIBUTING.md`, and `docs/DEVELOPMENT_LOG.md`. Update them with relevant implementation changes. Record evidence and blockers; never present plans as completed. No delivery dates are promised.

## Baseline and reference measurements

Implemented: read-only Navidrome reporting, metadata diagnostics, duplicate candidates, previous-snapshot comparison, Markdown reports/JSON state, Python admission checks, one-shot Rust launcher source, and PowerShell setup/task helpers. There are 72 passing offline Python tests, including headless dashboard and synthetic real-process tests. Rust compilation and Windows idle/AC scheduling are unverified.

Owner-reported first run at `https://vxsp.pikapod.net`: 1,736 tracks, 398 albums, 214 artists, 12 playlists, 5.97 GiB indexed sizes; 1,253 M4A, 476 MP3, 4 FLAC, 3 WAV; 1,006 missing track numbers, 20 missing artwork references, 3 duplicate candidate groups; collection took 46 seconds. These approved aggregates are historical observations, never hardcoded live results or test expectations. Detailed reports and snapshots stay private.

## A: repository foundation — in progress

- [x] Inspect/preserve the starter and existing commits.
- [x] Establish ignore rules, safe examples, developer docs, persistent context, and offline safety tests.
- [x] Resolve the earlier publication gate: the owner explicitly permits ignored, untracked `config/.env`.
- [x] Confirm connected GitHub identity `vxsp` and noninteractive native Git credentials under the owner's Windows account.
- [x] Audit complete tracked history and publication material; private `.env` is ignored/untracked. A repeatable redacted audit now lives in `scripts/check-secrets.py`.
- [x] Create public [vxsp/nyx](https://github.com/vxsp/nyx), configure `origin`, push `main` preserving history, verify all 26 initial remote paths/blob hashes and public/main settings.
- [x] Propagate venv/pip failures in the native setup script; PowerShell syntax checked. Full fresh-machine setup remains unverified.
- [x] Validate known configuration fields, add safe rotating JSON logs/error handling, job locking, progress/events, and strengthen tests (31 passing).
- [x] Check Rust availability and document missing toolchain/MSVC prerequisites in `docs/WINDOWS_VALIDATION.md`. Compilation and native idle lifecycle remain blocked pending installation.

Do not publish credentials, private reports, snapshots, or media. An ignored local credential alone is not a blocker. Exposed credentials in tracked history/publication material require intervention. Preserve history, never force-push over unrelated work, and do not add a license without approval.

## B: improved Navidrome reporting — initial increment implemented

- [x] Use `Navidrome report - YYYY-MM-DD.md` and `Navidrome report - latest.md` under `Navidrome/`; retain snapshots, add a compact saved summary, preserve old reports.
- [x] Preserve existing counts/formats/metadata/artwork/duplicate/change diagnostics; show missing scan status as unavailable, reference the comparison snapshot timestamp, and expose saved summaries to the UI.
- [x] Add safe error/progress feedback, a read-endpoint allowlist, and collection-wide cooperative deadlines including pagination; keep sequential requests and existing gentle pauses.
- [x] Cover read endpoints, limits, initial-call budgets, redaction, failures, partial writes, naming, and old-report preservation with offline tests. Multi-page and malformed nested payload coverage remains to extend.
- [x] Avoid redundant album requests/counted tracks by deduplicating API IDs; add multi-page regression coverage. No new requests/concurrency or unmeasured speedup claims. Live performance measurements remain pending.

Acceptance: useful, correctly named reports and snapshots; explicit incomplete/unavailable data; failures preserve usable state; no music/server mutation or fabricated metrics. New filenames are implemented; old files remain untouched. In-flight socket reads are not a hard process time limit.

## C: interactive TUI — initial version implemented

Use Python Textual initially unless inspection demonstrates a stronger reason for Ratatui. Keep UI independent of execution logic.

- [x] Overview, saved Navidrome statistics, diagnostics, job status, bounded task history.
- [x] Reports browser with legacy support/bounded previews, error logs, keyboard navigation, saved-only refresh.
- [x] Manual CLI subprocess with streamed progress/error feedback, UI duplicate guard, shared job lock, owned-process cancellation, guarded quit.
- [x] Load saved state on startup with no network or state writes; cache legacy-snapshot summaries.
- [x] Headless navigation/no-scan tests and real synthetic Windows child execution/cancellation passed.
- [ ] Fresh-terminal manual UX check and explicit live server integration check; no live scan was run during development.

Acceptance: a cohesive, responsive Windows terminal application with low overhead and no additional service.

## D: Rust background controller — blocked on native toolchain

Rust/Cargo are unavailable, and Visual Studio discovery did not find the required MSVC C++ tools. Prerequisites and the validation checklist are documented; no uncompiled controller or unattended task was introduced. Continue safe independent work while these prerequisites are unresolved.

Tracked blocker: [Set up and validate the native Windows Rust toolchain](https://github.com/vxsp/nyx/issues/1).

Implement native idle detection (approximately 10 minutes), CPU/RAM monitoring, AC-aware admission, priorities, cooldowns, lifecycle management, single-instance locking, resource budgets, cancellation, persistent state, and resumable useful progress.

Acceptance: one resource-intensive job at a time; no duplicate job; constrained resources/battery prevent starts; activity cancels or safely suspends work; verify Windows behavior before enabling unattended execution. Keep existing launch paths working.

## E: Nyx Dev — initial version implemented

- [x] Inspect only configured repository roots, with dirty-state/branch reporting and optional Git index writes/fsmonitor disabled.
- [x] Run explicitly declared test/build/dependency/custom commands only with `dev-report --run-checks`; default reporting never executes them.
- [x] Bound duration/output, retain safe private result tails, and generate Markdown/JSON health reports. Pip-style dependency-check JSON can report outdated counts.
- [x] Use a shared job lock and module-tagged history; preserve Navidrome cooldown and expose Dev reports in the browser.
- [x] Regression checks verify unchanged source/index during metadata inspection, opt-in execution, timeouts, failures/output limits, private configuration, and cooldown isolation.
- [ ] Native Windows process containment for daemonizing check descendants and fresh-machine/user-declared project integration remain follow-ups; do not schedule Dev unattended.

Never automatically fetch, install, commit, push, reset, clean, or rewrite inspected repositories. Check commands are trusted executable code and may have their own side effects. A generated report is not a claim that checks passed.

## F: Nyx Audio — initial read-only inventory implemented

- [x] Explicit roots, bounded entry/time inventory, skip links/reparse points, overlapping-root deduplication, and partial-scope reporting.
- [x] Music formats, FLP presence, same-name/size duplicate candidates, repeated-whitespace flags, and large lossless/export review candidates.
- [x] Optional pinned Mutagen tag/artwork-reference diagnostics through read-only handles; corrupt/unsupported files remain unavailable.
- [x] Markdown/JSON reports and browser integration; synthetic tests verify source bytes/mtime unchanged and parser behavior.
- [ ] FLP sample-reference parsing, confirmed content duplicates, and unused-file analysis remain unimplemented; do not infer them from inventory.

Never automatically edit, delete, move, or retag music. No file is designated safe to delete. Complete inventory means within configured accessible scope and limits, not the whole machine.

## G: Nyx Research — initial opt-in digests implemented

- [x] Configured HTTPS RSS/Atom and stable public GitHub releases with bounded bytes/entries/source count/deadline and conditional requests.
- [x] Article deduplication, categorized cumulative daily Markdown digests, explicit source failures and publisher dates, bounded seen/reading history.
- [x] Explicit unique-ID read acknowledgements, safe Markdown, private state/report-browser integration, and synthetic fetch/failure/XML-security tests.
- [ ] Live configured-source integration and periodic scheduling remain unverified/disabled. No paid service or private GitHub token was introduced.

## H: backups and maintenance — scrapped

The owner marked this milestone scrapped: do not implement backups or PC maintenance. The unpublished prototype and its portable tool were removed when this edit was detected; no backup commands, password settings, or binaries were published. Reintroducing this milestone requires the owner's explicit reversal. Backup metrics remain unavailable.

## I: Nyx Insights — initial local history reporting implemented

- [x] Local saved-state/history report with no network and latest real library counts, leaving missing data unavailable.
- [x] Growth/metadata changes require two successful same-server/account/metric-definition observations.
- [x] Bounded measured history, project-check status observations, completed-job success rates, actual Python-controller duration/CPU/RSS, and safe telemetry-failure isolation.
- [x] Sixth TUI tab and explicit I action generate/read local Insights; opening/refreshing never scans or writes.
- [x] Tests cover comparable/incomparable history, failure/stale-data exclusion, retention/corruption, outcome denominators, isolated cooldown, telemetry errors, and UI command routing. Native local smoke check preserved the original snapshot/cooldown.
- [ ] Multiple live observations and full child/system resource trends remain unavailable until measured. Backup history is unavailable because H is scrapped; do not fabricate or resurrect it.

## Autonomous workflow and checkpoint

For each coherent increment: inspect, implement, test, fix failures, review scope/secrets, update documentation/log, commit, push validated work, then continue. Request approval only for the owner's safety boundaries: user-data deletion, unrelated-project changes, private-data publication, paid services, destructive system changes, history rewrites, visibility changes, or unverified unattended activation.

If blocked, record the cause and continue safe independent tasks. At the end of a session leave an accurate checkpoint; do not claim work continues after the session ends.

Current checkpoint: publication and initial B/C increments verified; native D is blocked on Rust/MSVC prerequisites. Keep B/C integration/performance follow-ups explicit. E now has a verified initial health reporter with opt-in checks. F now has a verified initial read-only inventory; G has verified opt-in RSS/release digests. H is scrapped per the owner; I has verified local historical reporting. Retain D containment, FLP-reference, and B/C live integration follow-ups. Do not enable unattended jobs.

### Current session checkpoint

Public `vxsp/nyx` contains preserved history and verified initial B/C/E/F/G increments. I is the current verified local Insights increment. Native D remains blocked on Rust/MSVC prerequisites; H is scrapped. No unattended behavior, paid services, private-data publication, license, or history rewrite was introduced. Next useful work: resolve the native compiler prerequisite and validate D's Windows lifecycle, or harden the documented B/C/E/F/G integration/containment gaps. Re-read this queue for owner edits before starting each milestone.
