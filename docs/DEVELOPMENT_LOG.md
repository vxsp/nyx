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

## 2026-11-05: initial Nyx Dev health reporting

- Added configured repository-only Git inspection and explicitly opted-in test/build/dependency/custom command execution. No drive discovery or automatic changes to unrelated projects; real user repositories were not run during tests.
- Added private configuration with a safe example, 600-second job budget, per-check limits, disk-backed bounded output/tails, timeout tree termination, and pip-style outdated-count parsing without installing/upgrading dependencies.
- Added Dev Markdown/JSON reports, separate last-success state, module-tagged history/progress, and report-browser support. Metadata-only tests verify source and Git index bytes remain unchanged; Navidrome cooldown isolation is tested.
- Validation: 48 offline tests passed; pip consistency and secret audit passed. Remaining limitation: daemonized descendants after the parent exits need native Windows containment (D); declared checks remain trusted/opt-in with no unattended activation.
- Checkpoint: public main includes the initial dashboard (`4ec74fc`); this increment follows with preserved history. D remains blocked on Rust/MSVC. Next independent task is F's read-only inventory, while native/live integration follow-ups remain explicit.

## 2026-11-05: read-only Nyx Audio inventory

- Added explicitly configured, entry/time-bounded music/FL Studio inventory with link/reparse avoidance, overlapping-root deduplication, partial-scope flags, format/FLP counts, naming flags, same-name/size duplicate candidates, and large lossless/export candidates.
- Added optional pinned Mutagen 1.48.1 tag/artwork diagnostics through read-only handles. Unsupported/corrupt data remains unavailable; no mutation APIs are called. No personal music/production directories were scanned.
- Private Markdown/JSON output is integrated into the report browser. FLP sample usage, unused-file analysis, and confirmed content identity remain unimplemented and are labeled unavailable; no deletion advice is asserted.
- Validation: 55 offline tests passed, including source-byte/mtime preservation, actual synthetic WAV parsing, bounds, overlap, configuration, and unavailable metadata. Pip consistency and redacted audit passed; media ignore/audit exclusions were expanded.
- Next: G's configured RSS/release digests. D remains blocked on Rust/MSVC; B/C live/terminal checks, native containment, and advanced FLP analysis remain follow-ups. No unattended behavior activated.

## 2026-11-05: opt-in Nyx Research digests

- Added explicitly configured HTTPS RSS/Atom and public stable GitHub release collection with byte/source/entry/deadline bounds and conditional requests. Redirects and implicit .netrc credentials are disabled; XML DTD/entities are rejected.
- Added canonical article deduplication, cumulative daily categorized digests, bounded seen/reading history, explicit read acknowledgement, source/date provenance and unavailable statuses. Source failures retain history; seen is never counted as read.
- Hardened Markdown field escaping and disabled Navidrome API redirects to avoid authenticated HTTP downgrade behavior. All requests remain read-only.
- Validation: 62 offline tests passed; pip consistency passed. Research responses are synthetic; no live feeds or personal data were queried. Periodic monitoring remains disabled. Next: H's backup/maintenance boundary, then evidence-based historical insights.

## 2026-11-05: roadmap cancellation and local Insights checkpoint

- Detected the owner's authoritative roadmap edit scrapping H. Removed only the unpublished backup prototype, example/password additions, tests/installer, and the portable tool installed for it. No backup feature or binary was pushed. Disposable test fixtures were cleaned; no personal source or backup was changed. Re-read the roadmap before each next milestone.
- Implemented local Insights with honest unavailable states, comparable library/metadata deltas, project-check observations, completed-job outcomes, and bounded actual controller duration/CPU/RSS measurements. Failed jobs do not reuse stale statistics, and telemetry errors cannot fail working reports.
- Added the sixth TUI tab and explicit I local-report action. R/startup remain read-only; UI command-routing tests prevent accidentally launching Navidrome collection for Insights.
- Validation: 72 offline tests passed in the retained suite; pip consistency passed. A native local Insights CLI smoke check forbade HTTP and verified original Navidrome snapshot/cooldown hashes unchanged. Preview uses synthetic data only; the actual Insights report stays ignored locally.
- Checkpoint: B/C/E/F/G/I have verified initial implementations, D remains blocked on Rust/MSVC, H is scrapped. Unattended scheduling remains disabled. Personal integrations, manual terminal UX, containment, FLP references, and measured multi-run trends remain follow-ups; no background work is claimed after the session ends.

- Final security review strengthened the pre-push audit for retired config credentials and historical private paths that share a blob with another filename. Regression tests cover both cases; the full retained suite has 72 passing tests and the complete reachable-history/publication audit has no findings.
- Native Rust prerequisite work is tracked in [issue #1](https://github.com/vxsp/nyx/issues/1). The GitHub connector returned an issue-write permission error; the existing authorized native owner login created the issue successfully without exposing credentials.

## 2026-11-05: published session checkpoint

- Code checkpoint `7f98f67` is pushed to public `vxsp/nyx`, `main`, with all prior commits preserved. Initial B/C/E/F/G/I implementations and the owner-scrapped H decision are documented; no backup prototype/tool remains.
- Final retained validation: 72 passing tests, consistent installed dependencies, Python 3.10 syntax checks, PowerShell syntax checks, and a clean redacted publication/history audit. Ordinary Git status/log also work under the owning Windows account without the temporary sandbox trust override.
- A proposed manual read-only Navidrome validation was blocked before execution by automatic approval review, citing `AGENTS.md`'s prohibition on live reports as tests. No request was sent; the owner was asked for explicit approval. Live integration remains unverified unless that approval and successful check are recorded later.
- The native local Insights smoke check used existing state only, blocked HTTP, and preserved original Navidrome snapshot/cooldown hashes. Generated reports, logs, credentials, and measurements remain local and excluded from Git.
- Remaining work: Rust/MSVC prerequisite and D lifecycle, manual terminal/live integration, hard process containment, advanced FLP references, and enough real samples for multi-run trends. Unattended behavior remains disabled. This is a checkpoint, not a claim of background work after the session ends.
