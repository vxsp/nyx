# Nyx

Nyx is a personal Windows 11 automation project built with Rust and Python. It targets an Intel i3-1115G4 laptop with 16 GB RAM, prioritizing low resource use, read-only integrations, and maintainable modules.

Version 0.1 implements a Navidrome library reporter and a one-shot Rust launcher. Windows Task Scheduler supplies idle scheduling. The existing reporter has generated a real report successfully; its credentials, reports, and library snapshots stay outside Git.

## Development status

| Capability | Status |
| --- | --- |
| Read-only Navidrome/Subsonic collection over HTTPS | Implemented |
| Library counts, formats, indexed sizes, metadata diagnostics | Implemented |
| Possible duplicates and changes since the previous snapshot | Implemented; metadata heuristics and track IDs only |
| Dated/latest Markdown reports and local JSON state | Implemented |
| Scheduled-run cooldown and battery/CPU/RAM prechecks | Implemented |
| Rust launcher forwarding one command to Python | Implemented; compilation unverified during preparation |
| PowerShell setup and idle-task registration | Scripts present; registration unverified during preparation |
| Native Rust idle detection, modular scheduling, cancellation | Planned |
| Repository maintenance, research, music/FL Studio analysis | Planned |
| Incremental backups, system maintenance, historical analytics, TUI | Planned |

Nyx accesses an existing Navidrome server; it does not install or host one. Current comparison uses the last complete snapshot, not a historical analytics database.

Persistent project context lives in [AGENTS.md](AGENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [ROADMAP.md](ROADMAP.md). The roadmap records the owner's priorities, first-report baseline, and accepted future `Navidrome report` filename prefix; current filenames below remain unchanged.

## Windows setup

Use native Windows 11 and PowerShell. WSL, Docker, and additional background services are not required.

Prerequisites:

- Python 3.10 or newer with the Windows `py` launcher. The local preparation environment uses Python 3.14.6.
- Git for source control.
- Optional: stable Rust with the Windows MSVC toolchain and Visual Studio C++ Build Tools.
- An existing HTTPS Navidrome server and a library-reading account. Prefer only the permissions needed for reporting.

Open PowerShell in the project root:

```powershell
.\scripts\install-dependencies.ps1
```

This creates `.venv`, installs the three direct dependencies in `requirements.txt`, and copies `config/.env.example` to `config/.env` only if the private file does not exist. Confirm pip succeeded. If PowerShell policy blocks scripts, follow your machine's policy or use the individual commands below; no permanent policy change is required.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Run only when config\.env does not already exist:
Copy-Item config\.env.example config\.env
```

Edit the private `config/.env`:

| Variable | Purpose |
| --- | --- |
| `NAVIDROME_URL` | Your HTTPS server; replace the example hostname |
| `NAVIDROME_USERNAME` | Your private username |
| `NAVIDROME_PASSWORD` | Your private password |
| `NYX_REPORT_DIR` | Optional report directory; defaults to the project's `reports/` |

Process environment variables take precedence over `.env`. Set the URL explicitly: a personal-server fallback remains in `jobs/navidrome.py` to preserve starter behavior. New installs should use their own URL.

## Commands

Run from the project root:

```powershell
.\.venv\Scripts\python.exe main.py status
.\.venv\Scripts\python.exe main.py report
.\.venv\Scripts\python.exe main.py run
```

- `status` reads the last successful run record without contacting Navidrome.
- `report` runs manually, bypassing the enabled flag, cooldown, and resource prechecks. It contacts Navidrome and writes local reports/state.
- `run` respects the enabled flag, cooldown, and resource prechecks. Skipped runs exit successfully.
- `scripts/manual-report.ps1` invokes the same manual `report` command.

Successful runs write `reports/Navidrome/YYYY-MM-DD.md`, `Latest.md`, `state/navidrome-last.json`, and `state/last-run.json`. The report directory override does not move state. Same-day runs replace that day's report. Filenames use local dates; snapshot timestamps use UTC.

Shared defaults in `config/settings.json`:

| Setting | Default |
| --- | ---: |
| Minimum hours between scheduled reports | 24 |
| Minimum available RAM | 3 GiB |
| Maximum CPU usage at precheck | 35% |
| Require AC when battery information is available | true |
| Album page size / maximum albums | 200 / 2000 |
| HTTP read timeout | 12 seconds |
| Album retrieval budget | 600 seconds |

Resource checks occur once; they do not throttle an active job. Initial API calls and pagination are outside the time-budget check, and in-flight requests can overrun the remaining budget.

## Optional Rust launcher and idle task

```powershell
cargo build --release
.\target\release\nyx.exe status
```

The launcher accepts `run`, `report`, or `status`, defaulting to `run`. Its working directory must be the project root. It prefers `.venv\Scripts\python.exe`, falling back to `python` on PATH. It exits when its Python child finishes.

After a manual report succeeds, inspect any existing task named `Nyx` before registration:

```powershell
.\scripts\register-idle-task.ps1
```

The existing script creates **or replaces** that task. Obtain the owner's approval before replacing an existing task. Registration is an explicit setup step, never part of tests. The task uses the current interactive account and least privilege, requires idle/AC conditions, stops on activity or battery power, ignores overlapping scheduled instances, and has a 15-minute limit. It does not wake the PC. Windows determines idle timing; no exact idle duration is promised. Inspect the task in `taskschd.msc`.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
cargo test
```

Python tests use synthetic data, mocks, and temporary directories without live credentials or server requests. Rust has no unit tests yet; `cargo test` checks compilation when a toolchain is available. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

```text
nyx/
  main.py                   Python CLI, resource gates, status
  jobs/
    __init__.py
    navidrome.py            API, collection, analysis, reports
  src/main.rs               One-shot Rust launcher
  Cargo.toml                Rust manifest; no external dependencies
  requirements.txt          Python dependency ranges
  config/
    .env.example            Safe template
    settings.json           Shared defaults
  scripts/                  PowerShell install, manual report, idle-task helpers
  tests/                    Offline Python tests
  logs/.gitkeep
  reports/.gitkeep
  state/.gitkeep
  README.md
  ARCHITECTURE.md
  ROADMAP.md
  CONTRIBUTING.md
  AGENTS.md
```

Private `.env`, `.venv`, build output, the starter ZIP, reports, logs, and state remain local and ignored. No project license has been selected.

## Limits and next milestone

Collection is sequential and holds library metadata in memory. It never edits server files, tags, playlists, or scan state. Duplicates are candidates, not proof of identical audio. Lyrics and embedded artwork are not inspected.

Writes are atomic per file, not across all output files. Manual runs have no shared lock, and interruption can leave reports ahead of the snapshot. Configuration validation and automated Windows lifecycle coverage remain incomplete.

The next milestone should verify the Rust build and idle-task lifecycle on Windows, then harden configuration, execution bounds, and concurrent-run protection before adding another job. See [ARCHITECTURE.md](ARCHITECTURE.md).
