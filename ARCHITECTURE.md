# Nyx architecture

## Scope

Nyx 0.1 has one Python job and one Rust executable. It preserves the working Navidrome reporter and uses Windows Task Scheduler without adding a resident service. Native Windows 11 on an Intel i3-1115G4 laptop with 16 GB RAM is the target; resource efficiency is a goal, not a measured performance guarantee.

## Persistent product context

The owner's priority order is Navidrome reporting, coding project testing/maintenance, music and FL Studio organization, automated research reports, backups/PC maintenance, then a visual terminal dashboard. `ROADMAP.md` records the milestone sequence and acceptance criteria; `AGENTS.md` records durable decisions and the documentation-update contract.

The existing Navidrome integration targets `https://vxsp.pikapod.net` through private environment configuration. Its first successful report, as supplied by the owner, found **1,736 tracks, 398 albums, 214 artists, and 12 playlists**. This historical aggregate is approved project context, not a fresh server measurement or a fixed test expectation. Detailed reports, paths, playlists, and snapshots remain private.

Accepted boundaries are native Windows without WSL/Docker, Rust for the future background engine and performance-sensitive operations, and Python for integrations, analysis, and reporting. Music operations remain read-only by default. Preserve existing working code and keep resource use low. A visual terminal interface is planned; its framework and engine interface have not been selected.

## Current boundaries

| Component | Responsibility | Current limit |
| --- | --- | --- |
| `src/main.rs` | Validate command, select Python, start one child, forward exit status | No idle detection or scheduling loop |
| `main.py` | Validated configuration, CLI, admission, locked dispatch, progress/history | No general job registry |
| `nyx/config.py` | Strict known-setting type/range validation and defaults | Unknown future sections preserved |
| `nyx/runtime.py` | OS-managed exclusive job lock, progress and bounded event history | No native idle controller |
| `nyx/logging.py` | Rotating redacted JSON logs | No server bodies/raw exceptions |
| `jobs/navidrome.py` | HTTPS client, collection, diagnostics, comparison, rendering, writes | Only implemented job |
| `config/settings.json` | Versioned resource and collection defaults | Known fields validated before work |
| `config/.env` | Private server/login/output settings | Local only |
| `scripts/*.ps1` | Setup, manual invocation, opt-in task registration | Registration modifies Windows state |
| `tests/` | Offline behavior checks | No real server or Task Scheduler integration |

Python has three direct dependencies: `requests`, `python-dotenv`, and `psutil`. Versions use bounded ranges, not a lock. Rust uses only the standard library. Existing paths remain in place to preserve scripts and imports.

## Execution flow

```mermaid
flowchart TD
    TS[Windows Task Scheduler: idle and AC] --> R[Rust launcher: run]
    R --> P[Python CLI]
    M[Manual Python or Rust command] --> P
    P --> S{Command}
    S -->|status| L[Read local last-run record]
    S -->|run| G[Enabled flag, cooldown, battery, RAM, CPU]
    G -->|allowed| N[Navidrome reporter]
    G -->|skip| X[Successful exit]
    S -->|report| N
    N --> O[Reports, snapshot, last-run record]
```

The launcher requires the project root as its working directory, closes child stdin, waits, and returns success or a bounded failure code. It is not a daemon. Task Scheduler controls idle admission and interruption.

`run` checks the enabled flag, successful-run cooldown, then resources while holding the job lock. CPU sampling waits 0.8 seconds. Checks occur once, not continuously. `report` bypasses these gates but holds the same lock and updates the successful-run timestamp. `status` reads local state without HTTP or loading settings. Malformed/naive cooldown records are treated as due.

The OS file lock in `state/job.lock` serializes Python report/run processes and releases on process exit; the lock file stays on disk. Manual contention returns code 2; a scheduled contention is a successful skip. JSONL event history retains at most 500 entries; `current-job.json` records progress. A crash can leave a last-recorded running event; it is not proof a process is still active.

The registration script uses an interactive-token account, least privilege, idle/AC conditions, stop/restart on idle changes, no waking, and a 15-minute execution limit. Ignore-new prevents overlapping scheduled instances only. Its create-or-update call can replace a task named `Nyx`; inspect it and obtain approval before replacement.

## Navidrome data flow

1. The runner loads `config/.env` and `config/settings.json`; existing process environment values take precedence.
2. `NavidromeClient` requires HTTPS and nonempty login fields.
3. Each HTTP GET uses Subsonic token-and-salt authentication. The protocol's MD5 construction is for API compatibility, not password storage. Network errors omit authenticated request URLs.
4. Collection calls `ping`, `getScanStatus`, `getArtists`, and `getPlaylists`.
5. `getAlbumList2` pages through albums; sequential `getAlbum` requests fetch their tracks. Reaching the album safety limit aborts instead of saving a deliberately truncated snapshot.
6. Pure summary/render functions compare metadata with the previous snapshot and produce Markdown. Progress callbacks expose phase/counts without titles or authenticated URLs.
7. The reporter replaces the dated report, `Navidrome report - latest.md`, the saved aggregate summary, then the library snapshot.
8. The runner writes `last-run.json` only after the reporter returns successfully.

The client is internally generic, but the current reporting flow calls only read endpoints. It never starts scans, edits playlists, downloads audio, or changes tags.

## Persistence and privacy

| Path | Data | Git policy |
| --- | --- | --- |
| `config/.env.example` | Placeholder hostname and empty login fields | Tracked |
| `config/.env` | Private settings | Ignored |
| `config/settings.json` | Nonsecret defaults | Tracked |
| `reports/Navidrome/*.md` | Latest and dated reports | Ignored |
| `state/navidrome-last.json` | Previous successful library metadata | Ignored |
| `state/last-run.json` | Success time, status, module, local report path | Ignored |
| `logs/nyx.log` | Redacted JSON events; 256 KiB rotation with two backups | Ignored |
| `state/navidrome-summary.json` | Compact latest statistics/diagnostics | Ignored |
| `state/history.jsonl` | Last 500 execution events | Ignored |
| `state/current-job.json` | Last recorded job phase/status | Ignored |
| `state/job.lock` | OS-managed report/run exclusion | Ignored |

An optional `NYX_REPORT_DIR` moves report output, not state. Filenames use the host's local date; timestamps use UTC. Same-day runs replace the dated report.

The implemented names are `Navidrome/Navidrome report - YYYY-MM-DD.md` and `Navidrome/Navidrome report - latest.md`, matching the owner's prefix and separator. Legacy date-only/`Latest.md` files are left untouched. JSON snapshots continue; returned paths and last-run records use the new dated name.

`atomic_write` creates a unique sibling temporary file, closes it before `os.replace` for Windows compatibility, and cleans up its own temporary file on ordinary failure. This protects individual replacement, not a multi-file transaction. Report/summary files can advance before a later write fails; abrupt process termination can leave a temporary file. Only one previous library snapshot is retained.

Snapshots can contain library paths, artists, titles, and playlist metadata. Treat them and reports as private even without credentials. Do not publish starter archives or use real snapshots as fixtures.

## Known gaps

- Rust is a launcher, not the planned controller. Native idle detection, priorities, modular scheduling/cancellation, and the TUI are absent.
- Rust compilation and Task Scheduler behavior were not verified during repository preparation because the Rust toolchain was unavailable.
- Collection checks a deadline before/after every API call, including initial calls/pagination, and caps connect/read timeouts to the remaining budget. This is cooperative; socket activity/read-timeout semantics and cancellation still require native lifecycle enforcement.
- Known settings are type/range validated. The client validates its response envelope, HTTPS URL, and read-endpoint allowlist; some nested malformed library payloads still need stricter checks. Untrusted server error messages are not echoed.
- Library metadata stays in memory. No streaming aggregation or memory cap exists.
- The Python job lock prevents concurrent report/run writers; output writes are still not one transaction.
- A personal-server fallback remains in `run_report` to preserve starter behavior. New installations must explicitly configure their server.
- Python dependencies are not locked. Rust has no unit tests. Offline tests cover a subset of failure modes.
- The installer now stops on venv/pip failure. Task registration can still overwrite an existing task; no unattended behavior was activated.

## Planned responsibilities

Future Rust work should own lightweight scheduling, Windows state observation, lifecycle/cancellation, and performance-sensitive coordination. Python should own network integrations, analysis, research, and reports. Keep jobs independently callable and testable; agree on configuration, results, and failure contracts before introducing a persistent controller.

The planned TUI should expose the engine's job state, resource admission decisions, progress, and report locations without owning integration logic. It must not require elevated privileges or keep an extra service running solely for the dashboard. This is a design direction, not an implemented interface or chosen technology.

Repository maintenance, local music/FL Studio analysis, research, backups, system maintenance, historical analytics, and a TUI are plans, not implemented modules. Validate the current Windows execution lifecycle before expanding jobs. Future file mutation or cleanup requires an explicit safety design and approval for destructive operations.

## Validation and documentation maintenance

There are 31 passing offline Python tests, including configuration failures, Windows OS locking, atomic-write failure, naming, error redaction, initial-call time budgets, and historical-secret detection. Dependency consistency passes. PowerShell syntax validation does not establish installation or scheduling behavior. Rust/native idle lifecycle validation remains pending; see `docs/WINDOWS_VALIDATION.md`. No fresh live report was run for these changes.

Public repository: `https://github.com/vxsp/nyx`, branch `main`, remote `origin`. Initial publication was verified by comparing all 26 remote file paths/blob hashes with the published local tree. Every push requires a redacted candidate/history audit.

Keep this description aligned with source changes, update milestone state in `ROADMAP.md`, and carry durable decisions into `AGENTS.md` in the same change. Recheck implementation before promoting any planned capability to completed. Unrelated ChatGPT conversations need repository access or these documents supplied explicitly to recover the context.
