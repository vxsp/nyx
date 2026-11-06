# Nyx roadmap

The owner's autonomous directive authorizes verified development increments, commits, and pushes to public `vxsp/nyx`. Preserve working code and existing history. Native Windows 11, Intel i3-1115G4, 16 GB RAM; no WSL/Docker requirement. Rust owns the future engine and performance-sensitive work; Python owns integrations, analysis, reports, and the initial Textual TUI. Keep dependencies and resource use low.

This file is the primary task queue. Read it with `AGENTS.md`, `ARCHITECTURE.md`, `README.md`, `CONTRIBUTING.md`, and `docs/DEVELOPMENT_LOG.md`. Update them with relevant implementation changes. Record evidence and blockers; never present plans as completed. No delivery dates are promised.

## Baseline and reference measurements

Implemented: read-only Navidrome reporting, metadata diagnostics, duplicate candidates, previous-snapshot comparison, Markdown reports/JSON state, Python admission checks, one-shot Rust launcher source, and PowerShell setup/task helpers. There are 15 passing offline Python tests. Rust compilation and Windows idle/AC scheduling are unverified.

Owner-reported first run at `https://vxsp.pikapod.net`: 1,736 tracks, 398 albums, 214 artists, 12 playlists, 5.97 GiB indexed sizes; 1,253 M4A, 476 MP3, 4 FLAC, 3 WAV; 1,006 missing track numbers, 20 missing artwork references, 3 duplicate candidate groups; collection took 46 seconds. These approved aggregates are historical observations, never hardcoded live results or test expectations. Detailed reports and snapshots stay private.

## A: repository foundation — in progress

- [x] Inspect/preserve the starter and existing commits.
- [x] Establish ignore rules, safe examples, developer docs, persistent context, and offline safety tests.
- [x] Resolve the earlier publication gate: the owner explicitly permits ignored, untracked `config/.env`.
- [x] Confirm connected GitHub identity `vxsp` and noninteractive native Git credentials under the owner's Windows account.
- [ ] Audit complete tracked history and exact publication material; verify private `.env` is ignored/untracked.
- [ ] Recheck repository availability/ownership, create public `vxsp/nyx` only if absent, configure `origin`, push `main`, verify remote files.
- [ ] Validate native Windows setup and propagate installer failures reliably.
- [ ] Validate configuration, structured error handling, and safe logging; strengthen regression tests.
- [ ] Check Rust availability; install at user level where permitted or document prerequisites/blocker.

Do not publish credentials, private reports, snapshots, or media. An ignored local credential alone is not a blocker. Exposed credentials in tracked history/publication material require intervention. Preserve history, never force-push over unrelated work, and do not add a license without approval.

## B: improved Navidrome reporting — next

- [ ] Use `Navidrome report - YYYY-MM-DD.md` and `Navidrome report - latest.md` under the existing `Navidrome/` output folder; retain JSON snapshots and preserve old private reports.
- [ ] Improve availability/scan reporting, library counts, formats, metadata/artwork diagnostics, duplicate candidates, and historical changes using actual API data.
- [ ] Add safe error/progress feedback and bounded paginated collection without unnecessary server load.
- [ ] Cover success, failure, partial-write, pagination, and naming behavior with offline tests.
- [ ] Investigate measured performance improvements; retain read-only operation.

Acceptance: useful, correctly named reports and snapshots; explicit incomplete/unavailable data; failures preserve usable state; no music/server mutation or fabricated metrics. Current output names remain date-only/`Latest.md` until implementation.

## C: interactive TUI — planned

Use Python Textual initially unless inspection demonstrates a stronger reason for Ratatui. Keep UI independent of execution logic.

- [ ] Overview, saved Navidrome statistics, diagnostics, job status, task history.
- [ ] Reports browser, error logs, keyboard navigation, refresh controls.
- [ ] Manual job execution with progress/error feedback and no duplicate launch.
- [ ] Load saved state on startup; never require or start a fresh scan just to open the UI.
- [ ] Headless navigation/execution tests and native Windows launch validation.

Acceptance: a cohesive, responsive Windows terminal application with low overhead and no additional service.

## D: Rust background controller — planned

Implement native idle detection (approximately 10 minutes), CPU/RAM monitoring, AC-aware admission, priorities, cooldowns, lifecycle management, single-instance locking, resource budgets, cancellation, persistent state, and resumable useful progress.

Acceptance: one resource-intensive job at a time; no duplicate job; constrained resources/battery prevent starts; activity cancels or safely suspends work; verify Windows behavior before enabling unattended execution. Keep existing launch paths working.

## E: Nyx Dev — planned

Inspect configured/allowlisted repositories, run declared tests, report build health, outdated dependencies, and dirty state. Treat test commands as executable code and bound execution. Never automatically push, reset, clean, or rewrite unrelated repositories. Acceptance: useful project-health Markdown with explicit execution policy and no incidental project changes.

## F: Nyx Audio — planned

Read-only music/FL Studio inventory, duplicate candidates, naming and metadata diagnostics, oversized exports, unused-file candidates, and suggested cleanup. Acceptance: useful findings with confidence limits and original files unchanged; never automatically edit, delete, move, or retag music.

## G: Nyx Research — planned

Configured RSS/release monitoring, article deduplication, categorized Markdown digests, and reading history. Bound fetch/execution budgets; record sources and timestamps; do not add paid services without approval.

## H: backups and maintenance — scrapped

Incremental Restic backups scrapped, verification/restore checks, disk-space/large-file analysis, maintenance reports, configurable retention. Never delete originals or permanently purge backups without explicit approval. Validate resolved Windows paths and keep destinations private. scrapped dont do this one

## I: Nyx Insights — planned

Use accumulated evidence for library growth, metadata improvements, project health, backup history, success rates, and resource trends. Missing history must be shown as unavailable; never fabricate metrics.

## Autonomous workflow and checkpoint

For each coherent increment: inspect, implement, test, fix failures, review scope/secrets, update documentation/log, commit, push validated work, then continue. Request approval only for the owner's safety boundaries: user-data deletion, unrelated-project changes, private-data publication, paid services, destructive system changes, history rewrites, visibility changes, or unverified unattended activation.

If blocked, record the cause and continue safe independent tasks. At the end of a session leave an accurate checkpoint; do not claim work continues after the session ends.

Current sequence: finish secure publication; complete the minimum foundation reliability needed for B; implement B, then C. Remaining native-Rust prerequisites may be documented while safe Python work continues.
