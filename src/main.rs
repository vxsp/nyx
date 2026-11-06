//! Nyx Core: zero-dependency Rust job launcher. Windows Task Scheduler owns idle detection.
use std::env;
use std::path::PathBuf;
use std::process::{Command, ExitCode, Stdio};

fn main() -> ExitCode {
    let command = env::args().nth(1).unwrap_or_else(|| "run".into());
    if !["run", "report", "status"].contains(&command.as_str()) {
        eprintln!("Usage: nyx.exe [run|report|status]");
        return ExitCode::from(2);
    }
    let root = match env::current_dir() {
        Ok(dir) => dir,
        Err(err) => {
            eprintln!("Nyx: cannot read working directory: {err}");
            return ExitCode::from(1);
        }
    };
    let local_python: PathBuf = root.join(".venv").join("Scripts").join("python.exe");
    let python = if local_python.exists() {
        local_python.to_string_lossy().to_string()
    } else {
        "python".to_string()
    };
    let runner = root.join("main.py");
    if !runner.exists() {
        eprintln!("Nyx: cannot find main.py in {}", root.display());
        eprintln!("Start the executable with the Nyx project directory as its working directory.");
        return ExitCode::from(1);
    }
    let status = Command::new(&python)
        .arg(runner)
        .arg(command)
        .current_dir(&root)
        .stdin(Stdio::null())
        .status();
    match status {
        Ok(status) if status.success() => ExitCode::SUCCESS,
        Ok(status) => ExitCode::from(status.code().unwrap_or(1).clamp(1, 255) as u8),
        Err(err) => {
            eprintln!("Nyx: failed to launch Python job: {err}");
            ExitCode::from(1)
        }
    }
}
