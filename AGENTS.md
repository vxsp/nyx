# Instructions for coding agents

## Project contract

Nyx is a native Windows 11 Rust + Python automation project. Preserve the working Navidrome reporter. Do not rebuild the starter or move working files without a concrete need. Prioritize low resource use on an Intel i3-1115G4 laptop with 16 GB RAM.

Read this file, `ARCHITECTURE.md`, `ROADMAP.md`, `README.md`, and `CONTRIBUTING.md` before changes. These files are the persistent project context; do not depend on earlier chat history. Inspect source, tests, Git status, and remotes before describing implementation or changing behavior. Follow the user's requested scope. Distinguish implemented behavior from plans.

## Product priorities and baseline

The owner's original product priorities are below. The autonomous directive now sets execution order to milestones A-I in `ROADMAP.md`: foundation/publication, Navidrome improvements, TUI, Rust controller, Dev, Audio, Research, Backup, Insights.

1. Navidrome reporting for `https://vxsp.pikapod.net`.
2. Coding project testing and maintenance.
3. Music and FL Studio organization.
4. Automated research reports.
5. Backups and PC maintenance.
6. An interactive visual terminal dashboard (TUI).

The initial Navidrome reporter already works. The owner supplied this first-report baseline: **1,736 tracks, 398 albums, 214 artists, and 12 playlists**. These approved aggregate counts are historical context, not a live assertion, test fixture, or expected result for every account. Do not contact the live server just to refresh documentation.

## Accepted development decisions

- Native Windows 11; no WSL or Docker requirement.
- Rust owns the future background engine and performance-sensitive operations; Python owns API integrations, analysis, and reports. The current Rust launcher is only the first step toward that engine.
- Keep resource use low and dependencies minimal. Do not add unnecessary resident services.
- Music operations are read-only by default, both for Navidrome and future local/FL Studio work. Moving, renaming, retagging, deleting, or deduplicating files requires explicit scope and approval for destructive actions.
- The reporter writes `Navidrome report - YYYY-MM-DD.md` and `Navidrome report - latest.md`. Preserve historical date-only/`Latest.md` files; do not rename or remove them automatically.
- The initial Python Textual dashboard is implemented (`main.py tui`, optional `requirements-tui.txt`). Keep it separate from the engine; startup/refresh read saved data only. Manual N starts a locked CLI subprocess; X cancels only its owned process, and Q is guarded while that job runs.
- Dashboard themes are Nyx, Catppuccin Mocha, and AMOLED Black, selected in the toolbar or with T. Keep styles theme-driven. Only explicit theme changes write ignored `state/tui-preferences.json`; startup/refresh remain read-only. Preserve pure black main surfaces for AMOLED and tolerate unavailable/corrupt preferences or save failures.
- Preserve working code, private configuration, reports, and snapshots. Work through authorized milestones in verified increments rather than rebuilding the starter.

## Runtime boundaries

- `src/main.rs` is currently a one-shot launcher, not a resident controller. It needs the project root as its working directory. Task Scheduler owns idle detection.
- `main.py` loads `config/.env`, validates settings, applies gates for `run`, and dispatches the reporter under an OS file lock. Manual `report` bypasses enabled/cooldown/resource gates but respects the lock. `status` reads local state without loading settings.
- `jobs/navidrome.py` handles read-only HTTPS collection, diagnostics, snapshot comparison, and reports. Preserve endpoint behavior and credential redaction.
- `jobs/dev.py` inspects only configured repository roots. `dev-report` is metadata-only; `--run-checks` explicitly opts into declared executable argument arrays. Private paths/checks belong in ignored `config/projects.local.json`. No automatic fetching, installation, commits, pushes, resets, or cleanup in inspected projects. Commands can have their own side effects; keep them trusted and opt-in.
- `jobs/audio.py` inventories only configured roots from ignored `config/audio.local.json`. `audio-report` reads directory metadata; `--read-tags` opts into Mutagen through read-only file handles. Never follow links/reparse points or rename, retag, hash, or delete files incidentally. Duplicate identity and FLP sample usage are not established by this inventory.
- `jobs/research.py` fetches only configured HTTPS RSS/Atom/public-release sources on explicit `research-report`. Cap source count, bytes, entries, and duration; reject XML DTD/entities and redirects. Digests are private, deduplicated, and cumulative within a day. Seen is not read: `research-read --item-id` is an explicit acknowledgement. Never fetch on TUI startup or enable unattended monitoring incidentally.
- The owner marked milestone H (backups and maintenance) scrapped in `ROADMAP.md`. Do not implement or install tools for it unless the owner reverses that decision. Historical backup metrics remain unavailable.
- `jobs/insights.py` derives local reports from saved state/events and at most 1,000 observed job measurements. Never invent missing history, backdate telemetry, infer reads from seen articles, or compare library metrics across different server/account/metric-definition scopes. Telemetry failure must not fail a working report. CPU/RSS measure the Python controller, not external child processes. TUI I explicitly generates this local report; startup/refresh remain read-only.
- Keep Python for integrations/analytics and Rust for coordination/performance-sensitive work. Avoid unnecessary dependencies and services.
- Use native PowerShell. Account for Windows paths and native-command exit codes. Never require WSL or Docker.

## Privacy and safety

- Never print or commit credentials, `.env`, authenticated URLs, personal reports, detailed library metadata, music, snapshots, local state, environments, logs, binaries, or starter archives. The owner-approved server URL and aggregate baseline above may appear in project context; this does not authorize publishing private reports or snapshots.
- Keep `config/.env.example` safe with a placeholder hostname and empty/fake credentials; never copy local values into it.
- Inspect Git state/remotes and staged contents before publication. Scan working files, archives, staged content, and history without printing values.
- An ignored, untracked local credential is explicitly permitted and does not block publication. If a credential is exposed in tracked history or material intended for publication, stop publishing and report only its location/category; request intervention. Never print values.
- Do not rotate credentials, delete local data, rewrite history, force-push, or replace unrelated repositories without explicit authorization.
- Do not add an open-source license without approval.
- Navidrome stays read-only by default. Do not start scans, edit playlists/tags, or change server files incidentally.
- Do not run live reports or register tasks as tests. A separate manual live validation requires explicit owner approval for its target and private output writes; a one-time approval does not authorize future live tests or unattended runs. `register-idle-task.ps1` can replace an existing `Nyx` task; inspect it and obtain approval before replacement.
- No destructive file operations without approval. Preserve working local credentials, output, and task configuration.

## Development and checks

Use `rg` for searches and run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
cargo test
git diff --check
```

Run applicable checks and report unavailable prerequisites honestly. Rust currently has no unit tests; compilation does not validate idle scheduling. Ordinary project dependencies and appropriate user-level Rust installation are authorized where permissions allow; do not make destructive system changes or enable unattended behavior without verification.

Use meaningful offline tests with synthetic data, temporary directories, and mocks. Do not contact the live server or alter personal output. Keep dependency changes minimal. Commit `Cargo.lock` once generated for the application; ignore `target/`.

Keep changes modular and reviewable. Avoid unrelated refactors and formatting changes. The owner authorizes implementing planned modules, tests/docs, justified refactors, dependency installation, local builds, commits, and pushes of validated work to `vxsp/nyx`. Preserve published history. Do not automatically push changes to other repositories. Continue related tasks without asking the owner to choose each implementation detail; document blockers and continue safe independent work. Request approval for deleting user data, unrelated-project changes, paid services, destructive system changes, history rewrites, visibility changes, or unverified unattended activation.

## Keeping context current

Update these documents in the same change as the relevant implementation or decision:

- `AGENTS.md`: durable priorities, constraints, safety rules, and instructions for the next agent.
- `ARCHITECTURE.md`: actual module boundaries, data flow, persistence, limitations, and validation evidence.
- `ROADMAP.md`: milestone status, acceptance criteria, blockers, and the next actionable work.
- `README.md`: user-visible behavior, installation, commands, and current feature status.
- `docs/DEVELOPMENT_LOG.md`: completed increments, decisions, validation, blockers, and next steps.

Mark work completed only after inspecting its implementation and running applicable checks. Distinguish owner-reported results, locally verified behavior, unverified integration code, and future plans. Record missing prerequisites or blockers without storing credentials or private output. Remove stale claims as work progresses. Any new ChatGPT conversation should read these files through its repository tools, or receive their contents from the owner; files do not automatically carry into an unrelated chat.

## Publication handoff

The owner explicitly approves creating/publishing public `vxsp/nyx`, configuring `origin`, and pushing validated `main` commits while preserving all existing commits. Check authenticated ownership and existing repository contents before creation/reuse; never overwrite an unrelated repository. Do not add a license without approval. See the roadmap and development log for current publication status.

The owner has resolved the earlier local-credential publication gate: `config/.env` must stay local, ignored, and untracked; its presence alone is not exposure. Audit complete tracked history and exact publication material before every push. Stop only for exposed credentials or an actual authentication/publication blocker; document it and continue safe independent tasks.

Known gaps: unverified Rust/Windows unattended lifecycle, cooperative rather than hard runtime/resource enforcement, cross-file transactional output, and the personal-server fallback retained in `run_report`. Configuration validation, collection-wide budget checks, redacted rotating logs, progress state, bounded event history, and a Python job lock now exist. Run `.venv\Scripts\python.exe scripts/check-secrets.py` before each push.
