# Native Windows validation

The Python environment is running natively on Windows with Python 3.14.6. Offline tests exercise real Windows file locking and temporary-file replacement. The PowerShell helpers are syntax-checked; the installer now stops when environment creation or pip fails. These checks do not establish unattended scheduling reliability.

## Rust prerequisite

Rechecked on 2026-11-06: no Rust/Cargo, MSVC C++ tools, or Windows SDK libraries were found; the session has no Windows Administrator elevation. The existing Visual Studio discovery utility reports no installed product instances. Compilation remains blocked ([issue #1](https://github.com/vxsp/nyx/issues/1)). Rust's [MSVC prerequisites](https://rust-lang.github.io/rustup/installation/windows-msvc.html) need the linker and SDK; Microsoft's [installer instructions](https://learn.microsoft.com/en-us/visualstudio/install/command-line-parameter-examples?view=vs-2022) require administrator elevation. WSL/Docker are not needed.

Inspect without installing or changing Windows state:

```powershell
.\scripts\setup-rust.ps1
```

The script exposes two separate explicit installation modes:

```powershell
# Run in an Administrator PowerShell to install the C++ tools/Windows SDK:
.\scripts\setup-rust.ps1 -InstallBuildTools
# Then run in your normal user PowerShell to install a minimal stable MSVC Rust toolchain:
.\scripts\setup-rust.ps1 -InstallRust
```

The Microsoft bootstrapper is downloaded from its official endpoint and must pass Authenticode publisher verification. The Rust bootstrapper must match its official SHA-256 checksum. Downloads stay in ignored `.tools/setup/`. Installer failures/missing postconditions stop setup; existing user Rust installations are preserved. No automatic reboot occurs. Rust installation is rejected from an Administrator shell to avoid installing into the wrong account. Syntax, default read-only diagnostics, and the no-change non-administrator installation guard passed locally; download/install modes have **not** been executed or validated end to end.

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

## Dashboard validation

Optional Textual 8.2.8 is installed in the local virtual environment. Headless tests on native Windows verify keyboard navigation, saved-only startup/refresh, and real synthetic subprocess execution/cancellation. These are not a manual terminal UX review or a fresh live Navidrome scan. Launch `python main.py tui` after installing `requirements-tui.txt`; opening it does not query the server. No required MSVC C++ tools were found by Visual Studio discovery.

## Dev check lifetime containment

Native Windows tests verify creation-time Job Object assignment, normal-exit cleanup of detached workers, timeout cleanup, abrupt runner-termination cleanup, breakaway flags without surviving workers, unrelated-process preservation, Unicode paths/arguments/environment/output, and failure without an uncontained fallback. Repeated successful/failed starts check kernel-handle retention. Fixtures are temporary and self-ending; no personal project commands or live reports are used.

This closes the previously documented daemonized-descendant lifetime gap for explicit Windows Dev checks. It does not validate idle/AC/resource scheduling, enforce a security sandbox, or make unattended activation safe. Output/runtime limits are still cooperative. Rust remains the future controller; these checks require no Rust compiler or extra Python dependency.
