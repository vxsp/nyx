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

## 2026-11-05: approved manual Navidrome integration validation

- The owner explicitly approved one manual read-only validation against the configured `https://vxsp.pikapod.net`, resolving the earlier automatic approval rejection for this run. Resource admission passed before dispatch; the CLI completed successfully. This approval does not extend to future live tests or unattended runs.
- Verified the prefixed dated/latest reports, full snapshot, compact summary, success state, and matching successful real job measurement. Existing legacy reports retained identical hashes. Private credentials, reports, state, measurements, and logs remain ignored by Git; detailed results were neither printed nor added to documentation.
- The dashboard loaded the new saved data with network calls forbidden. Fresh-terminal appearance and dashboard-triggered live child integration still need separate validation; no performance improvement or multi-run trend is inferred from one run.
- Documentation-only follow-up: clarified the explicit manual-validation boundary in `AGENTS.md` and updated architecture/roadmap status. The retained code suite previously passed 72 offline tests; source code is unchanged in this follow-up. Native D remains blocked on Rust/MSVC and H remains scrapped.

## 2026-11-05: selectable dashboard themes

- Added Nyx, bundled Catppuccin Mocha, and AMOLED Black via a toolbar selector and T cycling. Replaced fixed dashboard colors with theme variables; AMOLED main backgrounds/panels/cards are pure black. No dependency was added.
- Explicit changes atomically save only the supported theme name in ignored `state/tui-preferences.json`. Startup/refresh remain read-only; corrupt/unavailable preferences fall back to Nyx. Save errors leave the session's selection usable and show a safe notification.
- Validation: all 74 offline tests passed, including dropdown/keyboard switching, rendered main-surface colors, remembered choice, restart without writes, unchanged synthetic snapshot, no network/process launches, and recovery from corrupt/read-only state. Dependency consistency and Python 3.10 syntax checks passed. Tests used temporary synthetic data; no live integration was run for this change.
- Updated persistent context and user instructions. Next milestone remains native Rust/MSVC setup and then D's Windows idle/cancellation lifecycle; H remains scrapped and unattended activation remains disabled.

## 2026-11-05: separate module workspaces

- Reorganized the dashboard around a shared overview and separate Navidrome, Dev, Audio / FL Studio, Research, and Insights workspaces. Each owns its summary/status, history, report list/selection/preview, setup guidance, and explicit action. Jobs, All reports, and Errors remain shared. Existing CLI commands and working job implementations are preserved.
- Added fixed UI metadata in `nyx/modules.py` and saved-data views in `nyx/module_views.py`; `nyx/tui.py` retains shared navigation/themes/process ownership. Module snapshots and unchanged previews are cached; report allowances are independent per module, contained to module folders, and previews stay bounded. Missing/corrupt statistics remain unavailable.
- Default actions inspect Dev metadata, inventory Audio without tag parsing, explicitly fetch configured Research, and generate local Insights. Tests/builds, tag reading, and research read acknowledgements remain CLI opt-ins. All run buttons disable during an owned job; cancellation records its actual module. Fixed focus handling so a hidden report table cannot reactivate its previous page.
- Validation: 77 offline tests passed, including scoped saved data/report allowances, navigation and independent report selection, source-byte preservation, safe exact command routing through synthetic native child jobs, duplicate prevention, correct Dev cancellation identity, and existing theme persistence. Dependency consistency and Python 3.10 syntax checks passed. No live server, personal-folder scan, or real configured job was run. Updated the dashboard preview using synthetic data only.
- Next: native Rust/MSVC prerequisite and D lifecycle remain blocked. Personal configuration/integration and manual UX checks remain separate; no unattended activation or backup milestone was introduced.

## 2026-11-05: private module configuration and bounded research follow lists

- Prepared ignored Dev/Audio/Research settings from the owner's selected local roots and topics. Bounded directory discovery avoided links/generated trees; local Git metadata mapped existing checkouts without altering other projects. No test/build commands were inferred. GitHub-only projects remain a private catalog pending an explicitly authorized checkout; none was cloned.
- Imported owned/starred/watched repository metadata through the existing authenticated account using read-only requests. The connector lacks star/watch methods, so native credentials were held in memory only. Paths, repository names/counts, credentials, and imported source selections remain private; no credential was persisted. The Navidrome environment file retained its hash.
- Verified selected public RSS endpoints with bounded HTTPS fetches and the real parser during configuration, rejecting an incompatible source and using a compatible fallback. This was source setup, separate from offline development tests; no personal report/history or audio inventory was generated. All three configuration loaders and ignore checks passed.
- Added an optional public repository pool with fixed per-run source limits, case-insensitive deduplication, resumable attempted-source rotation, pool-change reset, and budget/HTTP 403/429 deferral. State-write failure cannot advance the cursor. UI/report coverage distinguishes a pool from one batch. Imported lists are snapshots, not automatic account synchronization; private repositories stay excluded from unauthenticated research requests.
- Validation: all 81 offline tests, dependency consistency, Python 3.10 syntax, and private loader/path/ignore checks passed. Focused offline research tests cover rotation/wraparound, source limits, duplicates, conditional/history preservation, budget deferral, pool changes, rate-limit stops, malformed config, and failed state writes. Existing CLI behavior and Navidrome reporter remain preserved. Native Rust/MSVC and unattended lifecycle are still outstanding; no background service, scheduling, file mutation, or backup milestone was added.

## 2026-11-06: native check lifetime containment and Rust prerequisite handoff

- Reviewed public main through `9f39bf8` and selected incomplete milestone D. Fresh discovery still found no Rust/Cargo, MSVC C++ tools, or Windows SDK; the session is not Windows Administrator. Added `scripts/setup-rust.ps1` with read-only diagnostics and separate explicit system-build-tools/user-Rust modes, verified-download checks, postcondition checks, existing-install preservation, and no automatic reboot. Syntax/default diagnostics and the non-administrator no-change guard passed; installation and Rust compilation have not run. Downloads are ignored under `.tools/`.
- Advanced D/E's independent native lifecycle boundary: explicit Windows Dev checks now start inside an unnamed kill-on-close Job Object, using creation-time job assignment and a restricted inherited-handle list. Completion, timeout/output limits, exceptions and runner termination clean contained descendants; creation failures do not fall back to an uncontained process. Other processes remain outside the job. Python output defaults to UTF-8; checks remain trusted, explicit commands rather than a security sandbox.
- Added six native Windows tests for detached/breakaway descendants, normal exit/timeout/owner termination, unrelated-process preservation, Unicode paths/arguments/environment/output, failure before launch and handle retention after repeated successful/failed starts. Tests use the base interpreter to avoid a virtual-environment launcher's own lifetime behavior obscuring the mechanism under test. Only disposable self-ending synthetic jobs were used.
- Full validation: 87 offline Python tests passed; all six native containment checks also passed in a focused base-interpreter run. Dependency consistency, Python 3.10 syntax, and PowerShell parsing/default diagnostics passed. A full-suite failure exposed a timing-dependent pre-existing duplicate-launch fixture; replaced its short delay with an explicit completion signal, then reran successfully. No live reports, personal project commands, music scans, task registration, tool installation, or private configuration changes were performed.
- Updated the roadmap, architecture, agent instructions, user setup/testing docs and Windows checklist. D's Rust idle/AC/resource controller remains blocked; next external action is the Administrator C++/SDK setup followed by normal-user Rust setup and launcher compilation. H stays scrapped; unattended activation remains disabled.
