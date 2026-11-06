"""Redacted pre-push audit of publication files and all reachable Git history.

This conservative pattern/known-value check supplements review; it is not proof
that arbitrary secrets are absent. Ignored local credentials are permitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values


PATTERNS = {
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "provider token": rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|(?:AKIA|ASIA)[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{32,}|xox[baprs]-[A-Za-z0-9-]{20,})",
    "credential URL": rb"https?://[^\s/:]+:[^\s/@]+@",
}


def credential_assignments(path: str, data: bytes) -> bool:
    """Catch non-placeholder config credentials, including retired passwords."""
    sensitive = re.compile(r"PASSWORD|TOKEN|SECRET|API_KEY|AUTHORIZATION", re.I)
    def literal(value):
        if not isinstance(value, str):
            return False
        value = value.strip().strip("\"'")
        return bool(value) and not value.casefold().startswith(("your_", "replace_", "example", "synthetic", "test-", "<", "$"))
    if Path(path).suffix.lower() == ".json":
        try:
            document = json.loads(data)
        except (ValueError, UnicodeError):
            return False
        def walk(value):
            if isinstance(value, dict):
                return any((sensitive.search(str(key)) and literal(item)) or walk(item) for key, item in value.items())
            return isinstance(value, list) and any(walk(item) for item in value)
        return bool(walk(document))
    if Path(path).name.startswith(".env") or Path(path).suffix.lower() in (".yml", ".yaml"):
        for line in data.decode("utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("#"):
                continue
            match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(.*)", line)
            if match and sensitive.search(match[1]) and literal(match[2]):
                return True
    return False


def private_path(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name
    return (
        name == ".env" or (name.startswith(".env.") and not name.endswith(".example"))
        or (path.startswith("config/") and ".local." in name)
        or any(part in (".venv", "target", "__pycache__") for part in parts)
        or (path.startswith(("logs/", "reports/", "state/")) and not path.endswith("/.gitkeep"))
        or Path(path).suffix.lower() in {".zip", ".7z", ".rar", ".exe", ".dll", ".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".aif", ".aiff", ".wma", ".flp", ".mid", ".midi", ".sf2", ".sfz", ".fst", ".pem", ".key"}
    )


def audit(root: Path) -> tuple[list[str], int]:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)

    values = [value.encode() for key, value in dotenv_values(root / "config" / ".env").items()
              if value and re.search(r"PASSWORD|TOKEN|SECRET|API_KEY|PRIVATE_KEY", key, re.I)]
    findings: set[str] = set()
    count = 0

    def scan(label: str, path: str, data: bytes) -> None:
        nonlocal count
        count += 1
        if private_path(path):
            findings.add(label + ": private/generated path")
        if credential_assignments(path, data):
            findings.add(label + ": non-placeholder credential configuration (value withheld)")
        if any(value in data for value in values):
            findings.add(label + ": matches a local credential (value withheld)")
        for category, pattern in PATTERNS.items():
            if re.search(pattern, data):
                findings.add(label + ": " + category + " (value withheld)")

    indexed = set(git("ls-files", "-z").decode().strip("\0").split("\0")) - {""}
    candidates = set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().strip("\0").split("\0")) - {""}
    if "config/.env" in indexed:
        findings.add("config/.env: tracked private configuration")
    ignored = subprocess.run(["git", "check-ignore", "-q", "config/.env"], cwd=root, capture_output=True)
    if ignored.returncode != 0:
        findings.add("config/.env: not ignored")
    for path in sorted(candidates):
        if path in indexed:
            scan("index:" + path, path, git("show", ":" + path))
        file = root / path
        if file.is_file():
            scan("working:" + path, path, file.read_bytes())
    # Object names alone are insufficient: one blob can occur at several paths,
    # and config-specific rules must apply to every historical path alias.
    aliases: dict[str, set[str]] = {}
    for commit in git("rev-list", "--all").decode().splitlines():
        for entry in git("ls-tree", "-r", "-z", commit).decode().strip("\0").split("\0"):
            if not entry:
                continue
            metadata, path = entry.split("\t", 1)
            _, kind, sha = metadata.split()
            if kind == "blob":
                aliases.setdefault(sha, set()).add(path)
            if path and private_path(path):
                findings.add("history:" + path + ": private/generated path")
    for item in git("rev-list", "--objects", "--all").decode().splitlines():
        sha, _, path = item.partition(" ")
        kind = git("cat-file", "-t", sha).strip()
        if kind in (b"blob", b"commit"):
            data = git("cat-file", "-p", sha)
            for alias in aliases.get(sha, {path}):
                scan("history:" + (alias or sha), alias, data)
    return sorted(findings), count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        findings, count = audit(args.root)
    except (OSError, subprocess.SubprocessError):
        print("Audit could not complete; resolve Git/file access before publication.")
        return 2
    print(f"Secret audit: {count} candidate/history contents checked; {len(findings)} findings.")
    for finding in findings:
        print("BLOCKER:", finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
