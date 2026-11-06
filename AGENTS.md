# Instructions for coding agents

## Project contract

Nyx is a native Windows 11 Rust + Python automation project. Preserve the working Navidrome reporter. Do not rebuild the starter or move working files without a concrete need. Prioritize low resource use on an Intel i3-1115G4 laptop with 16 GB RAM.

Read this file, `ARCHITECTURE.md`, `ROADMAP.md`, `README.md`, and `CONTRIBUTING.md` before changes. These files are the persistent project context; do not depend on earlier chat history. Inspect source, tests, Git status, and remotes before describing implementation or changing behavior. Follow the user's requested scope. Distinguish implemented behavior from plans.

## Product priorities and baseline

Develop in this priority order, subject to the owner's explicit instructions:

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
- Use `Navidrome report` as the report filename prefix when implementing the naming change. The current reporter still writes `YYYY-MM-DD.md` and `Latest.md`; do not claim the prefix is implemented. See the migration task in `ROADMAP.md`.
- Plan a visual terminal interface. No TUI exists yet; select its implementation only when that milestone is authorized.
- Preserve working code, private configuration, reports, and snapshots. Do not implement roadmap features during documentation or publication preparation.

## Runtime boundaries

- `src/main.rs` is currently a one-shot launcher, not a resident controller. It needs the project root as its working directory. Task Scheduler owns idle detection.
- `main.py` loads `config/.env`, applies gates for `run`, and dispatches the reporter. Manual `report` bypasses enabled/cooldown/resource gates. `status` reads local state.
- `jobs/navidrome.py` handles read-only HTTPS collection, diagnostics, snapshot comparison, and reports. Preserve endpoint behavior and credential redaction.
- Keep Python for integrations/analytics and Rust for coordination/performance-sensitive work. Avoid unnecessary dependencies and services.
- Use native PowerShell. Account for Windows paths and native-command exit codes. Never require WSL or Docker.

## Privacy and safety

- Never print or commit credentials, `.env`, authenticated URLs, personal reports, detailed library metadata, music, snapshots, local state, environments, logs, binaries, or starter archives. The owner-approved server URL and aggregate baseline above may appear in project context; this does not authorize publishing private reports or snapshots.
- Keep `config/.env.example` safe with a placeholder hostname and empty/fake credentials; never copy local values into it.
- Inspect Git state/remotes and staged contents before publication. Scan working files, archives, staged content, and history without printing values.
- If any secret is detected, stop publishing and report only its location/category. Obtain the owner's direction before continuing.
- Do not rotate credentials, delete local data, rewrite history, force-push, or replace unrelated repositories without explicit authorization.
- Do not add an open-source license without approval.
- Navidrome stays read-only by default. Do not start scans, edit playlists/tags, or change server files incidentally.
- Do not run live reports or register tasks as tests. `register-idle-task.ps1` can replace an existing `Nyx` task; inspect it and obtain approval before replacement.
- No destructive file operations without approval. Preserve working local credentials, output, and task configuration.

## Development and checks

Use `rg` for searches and run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
cargo test
git diff --check
```

Run applicable checks and report unavailable prerequisites honestly. Rust currently has no unit tests; compilation does not validate idle scheduling. Do not install system tools merely to hide a missing prerequisite.

Use meaningful offline tests with synthetic data, temporary directories, and mocks. Do not contact the live server or alter personal output. Keep dependency changes minimal. Commit `Cargo.lock` once generated for the application; ignore `target/`.

Keep changes modular and reviewable. Avoid unrelated refactors and formatting changes. Update docs with behavior changes. Do not implement roadmap features during repository preparation.

## Keeping context current

Update these documents in the same change as the relevant implementation or decision:

- `AGENTS.md`: durable priorities, constraints, safety rules, and instructions for the next agent.
- `ARCHITECTURE.md`: actual module boundaries, data flow, persistence, limitations, and validation evidence.
- `ROADMAP.md`: milestone status, acceptance criteria, blockers, and the next actionable work.
- `README.md`: user-visible behavior, installation, commands, and current feature status.

Mark work completed only after inspecting its implementation and running applicable checks. Distinguish owner-reported results, locally verified behavior, unverified integration code, and future plans. Record missing prerequisites or blockers without storing credentials or private output. Remove stale claims as work progresses. Any new ChatGPT conversation should read these files through its repository tools, or receive their contents from the owner; files do not automatically carry into an unrelated chat.

## Publication handoff

The local repository uses `main`. The owner prefers a public GitHub repository named `nyx`; check the authenticated account and repository ownership/purpose before creation or reuse. A read-only GitHub connector check confirmed account `vxsp`; the `vxsp/nyx` lookup returned 404 (absent or inaccessible to that connection), so availability is not proven. Recheck before creating or reusing a repository. No remote or GitHub publication has been configured as of this context update. Do not add a license without approval.

The preparation audit found a password in ignored `config/.env`, while the initial committed tree/history had no secret findings. Publication was stopped under the owner's explicit stop-on-any-secret rule. This is not evidence of prior exposure. Preserve the local file and do not interpret a request for more preparation as approval to bypass that rule. Resolve the publication gate with the owner before any remote write; update this handoff when its status changes.

Known gaps: schema validation, complete time-budget coverage, manual-run locking, multi-file transactional output, and the personal-server fallback retained in `run_report`. Refer to `ARCHITECTURE.md` before designing around them.
