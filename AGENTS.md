# Instructions for coding agents

## Project contract

Nyx is a native Windows 11 Rust + Python automation project. Preserve the working Navidrome reporter. Do not rebuild the starter or move working files without a concrete need. Prioritize low resource use on an Intel i3-1115G4 laptop with 16 GB RAM.

Read `README.md`, `ARCHITECTURE.md`, and `CONTRIBUTING.md` before changes. Follow the user's requested scope. Distinguish implemented behavior from plans.

## Runtime boundaries

- `src/main.rs` is currently a one-shot launcher, not a resident controller. It needs the project root as its working directory. Task Scheduler owns idle detection.
- `main.py` loads `config/.env`, applies gates for `run`, and dispatches the reporter. Manual `report` bypasses enabled/cooldown/resource gates. `status` reads local state.
- `jobs/navidrome.py` handles read-only HTTPS collection, diagnostics, snapshot comparison, and reports. Preserve endpoint behavior and credential redaction.
- Keep Python for integrations/analytics and Rust for coordination/performance-sensitive work. Avoid unnecessary dependencies and services.
- Use native PowerShell. Account for Windows paths and native-command exit codes. Never require WSL or Docker.

## Privacy and safety

- Never print or commit credentials, `.env`, authenticated URLs, personal reports, library metadata, music, snapshots, local state, environments, logs, binaries, or starter archives.
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

Known gaps: schema validation, complete time-budget coverage, manual-run locking, multi-file transactional output, and the personal-server fallback retained in `run_report`. Refer to `ARCHITECTURE.md` before designing around them.
