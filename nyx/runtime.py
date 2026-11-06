"""Cross-process job admission and small, private execution records."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from jobs.navidrome import atomic_write


class JobBusyError(RuntimeError):
    pass


@contextmanager
def job_lock(root: Path):
    """Hold an OS-managed lock; process exit releases it, including after a crash."""
    path = root / "state" / "job.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise JobBusyError("A Nyx job is already running.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_event(root: Path, status: str, *, module: str = "navidrome", **details) -> dict:
    """Caller holds the job lock. Retain at most 500 execution events."""
    event = {"at": timestamp(), "module": module, "status": status, **details}
    path = root / "state" / "history.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-499:]
    except OSError:
        lines = []
    lines.append(json.dumps(event, ensure_ascii=False))
    atomic_write(path, "\n".join(lines) + "\n")
    atomic_write(root / "state" / "current-job.json", json.dumps(event, indent=2))
    return event


def record_progress(root: Path, phase: str, completed: int, total: int | None, *, module: str = "navidrome") -> None:
    event = {
        "at": timestamp(), "module": module, "status": "running",
        "phase": phase, "completed": completed, "total": total,
    }
    atomic_write(root / "state" / "current-job.json", json.dumps(event, indent=2))
