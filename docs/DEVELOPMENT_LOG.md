# Development log

## 2026-11-05: repository foundation

- Preserved the working Python Navidrome reporter, one-shot Rust launcher, existing scripts, private credentials, reports, and snapshots.
- Created local `main` history: `c2af3fb` prepared source/docs/tests; `496e3ad` established persistent context and a prioritized roadmap. No history rewrite or license was added.
- Validation baseline: 15 offline Python tests passed; dependency consistency and three PowerShell syntax checks passed. Rust toolchain was not found; Windows idle scheduling remains unverified.
- The owner now authorizes public `vxsp/nyx`, validated commits/pushes, and autonomous milestones A-I. Ignored local credentials are permitted; only exposure in tracked history/publication material blocks publication.
- GitHub connector identifies `vxsp` but cannot create repositories with its exposed tools. Git Credential Manager has a noninteractive login under the owner's Windows account; credentials are never printed or written to project files. Repository availability will be rechecked through that authenticated path.
- Current task: audit complete tracked history and candidate material, publish without replacing unrelated work, then implement the Navidrome filename prefix and reliability improvements before the Textual TUI.
- Known gaps: configuration/API/state validation, complete collection time budgets, concurrent runs, cross-file write consistency, Rust build/lifecycle validation. No unattended scheduling was activated.

## 2026-11-05: publication and first Navidrome reliability increment

- Published [vxsp/nyx](https://github.com/vxsp/nyx), `main`, preserving prior commits. All 26 initial remote file paths/blob hashes matched the local published tree; public visibility/default main verified. No license, private data, or credentials were published.
- Implemented the exact `Navidrome report - YYYY-MM-DD.md` / `Navidrome report - latest.md` names without touching legacy reports; retained snapshots and added a compact saved summary.
- Added known-setting validation, OS file locking, redacted rotating JSON logging, bounded execution history/progress state, safer API envelope/errors and read-endpoint allowlist, cooperative collection-wide budgets, unique temporary files, and installer failure propagation.
- Added a repeatable redacted pre-push audit and a regression test detecting a removed credential-shaped value in historical commits. Audits supplement review, not proof of secret absence.
- Validation: 31 offline tests passed; dependency check passed. No live server requests or personal report writes were used for this increment. The Rust toolchain remains unavailable; native setup/lifecycle checklist is in `docs/WINDOWS_VALIDATION.md`.
- Remaining limits: cross-file writes are not transactional; native resource/activity enforcement, strict nested API validation, measured performance, and multi-page coverage need further work. Next: Textual dashboard consuming saved state, with explicit manual execution and headless tests.

## 2026-11-05: initial interactive dashboard

- Added optional pinned Textual 8.2.8, separate from core reporting dependencies. The dashboard provides overview, formats/diagnostics, jobs/history/output, report browsing, and error logs with keyboard controls.
- Startup/refresh only read saved files. Existing private snapshots/reports work without a fresh scan; legacy summaries are cached. Explicit manual execution uses a separate CLI process and the shared lock; cancellation targets only the dashboard-owned process and quit is guarded.
- Added multi-page/deduplication and missing-ID collection checks, avoiding redundant album requests while keeping requests sequential/read-only. Comparisons identify the previous snapshot timestamp.
- Validation: 40 offline tests passed, including real native Windows synthetic process execution, duplicate prevention, cancellation, navigation, malformed data, and no network on startup/refresh; pip consistency and redacted audit passed. A 120x36 SVG preview uses synthetic demo data only.
- Preserved concurrent local commit `981bfca`; reliability follow-up `bac84f8` was pushed without rewriting history.
- D blocker: no Rust/Cargo; Visual Studio discovery found no required MSVC C++ tools. See `docs/WINDOWS_VALIDATION.md`. No unattended scheduling activated. Native terminal appearance/live server refresh and measured performance remain integration follow-ups. Next safe independent milestone: E, bounded configured project checks.
