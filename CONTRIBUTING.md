# Contributing to Nyx

Preserve the working Navidrome reporter and make focused, reviewable changes. No project license has been selected; do not add one without the owner's approval.

## Environment and conventions

Follow [README.md](README.md) using native Windows 11 and PowerShell. Run commands from the repository root using `.venv\Scripts\python.exe`; environment activation is optional. Do not introduce WSL or Docker requirements.

- Keep integrations and analytics in Python under `jobs/`; use Rust under `src/` for coordination and performance-sensitive work.
- Support the existing Python 3.10+ syntax and Rust 2021 edition. Prefer standard libraries and explain new dependencies.
- Preserve CLI commands, configuration keys, imports, and report locations unless the requested change requires otherwise.
- Separate analysis/rendering from HTTP/filesystem work so tests can use synthetic inputs.
- Keep Navidrome operations read-only by default. Do not incidentally add services, mutation endpoints, or scheduled tasks.
- Avoid unrelated rewrites, moves, formatting sweeps, and speculative abstractions.
- Use UTF-8 and the repository's `.editorconfig` and `.gitattributes` conventions. Check `cargo fmt --check` when editing Rust.
- Use descriptive commits. For later development, work in a branch and describe the behavior, validation, and limitations in the pull request.
- Update documentation when a feature moves from planned to implemented.
- Commit `Cargo.lock` when generated for this application; keep `target/` untracked.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
cargo test
git diff --check
```

Use `unittest`, temporary directories, and `unittest.mock` without additional test dependencies. Add meaningful behavior tests, particularly for gates, read-only API usage, and failure paths that must preserve prior data. Never contact the live server, alter personal output, or register tasks during tests.

Rust currently has no unit tests. `cargo test` verifies compilation, not idle scheduling. Windows launcher/idle/AC behavior needs explicit integration validation when that flow changes. Report missing toolchains and skipped checks honestly.

A manual live report is an integration check that writes private data. Task registration modifies Windows state and stays opt-in. The existing registration script replaces a task named `Nyx`; inspect it and obtain approval before replacement.

## Secrets and publication

Never print credentials, authenticated URLs, personal library metadata, or private `.env` contents. Keep the tracked template's hostname fake and login fields empty. Use synthetic fixtures and reserved example hostnames.

Before committing or publishing:

1. Review `git status --short`, the diff, and `git diff --cached --name-only`.
2. Verify ignored paths with `git check-ignore -v config/.env .venv reports/Navidrome/Latest.md state/navidrome-last.json Nyx_Starter_v0.1.zip`.
3. Scan working files, staged content, archives, and reachable Git history with a trusted scanner or a redacted local audit. Pattern scans have false positives and cannot prove absence of secrets. Never echo matched values.
4. Inspect staged content for private data. Ignore rules do not remove already tracked files or historical secrets.
5. If any secret is detected, stop publication and tell the owner its location/category only. Do not silently rotate credentials, delete files, or rewrite history; obtain direction before continuing.

Environments, archives, music, reports, logs, snapshots, state, and binaries remain local. Preserve working credentials and generated output. If a credential was actually shared or committed, the owner must revoke/rotate it; history cleanup alone is insufficient. Confirm repository ownership and purpose before setting `origin` or pushing. Never overwrite unrelated work or force-push without authorization.
