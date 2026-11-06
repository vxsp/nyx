# Native Windows validation

The Python environment is running natively on Windows with Python 3.14.6. Offline tests exercise real Windows file locking and temporary-file replacement. The PowerShell helpers are syntax-checked; the installer now stops when environment creation or pip fails. These checks do not establish unattended scheduling reliability.

## Rust prerequisite

No `cargo`/`rustc` was found on PATH or at the usual user-level Cargo location during preparation. Rust installation and compilation remain pending. Use the official [Rust installer](https://rustup.rs/) for a user-level toolchain, with the Windows MSVC C++ build tools it requires. Do not install WSL or Docker. System build-tool installation may require separate permissions; document the blocker if unavailable.

After installation, open a fresh PowerShell in the project root:

```powershell
rustc --version
cargo --version
cargo test
cargo build --release
.\target\release\nyx.exe status
```

Commit the generated application's `Cargo.lock`; never commit `target/`. Verify invalid commands return exit code 2 and Python failures propagate to the launcher. Rust currently has no unit tests.

## Idle lifecycle checklist — not yet verified

Only after a successful manual report and inspected task configuration, test idle admission, AC/battery constraints, activity interruption, timeout, ignore-new instance policy, sleep/wake behavior, and crash recovery. Use synthetic work where possible before live collection. Confirm private snapshots remain usable after interruption.

`scripts/register-idle-task.ps1` creates or replaces the task named `Nyx`. Inspect any existing task and obtain approval before replacement. No task has been registered or unattended behavior activated by this development session. Do not enable unattended scheduling by default until these checks pass.
