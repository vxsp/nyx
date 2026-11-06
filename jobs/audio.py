"""Bounded read-only music/production inventory, never automatic cleanup."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import time

from jobs.navidrome import atomic_write, mark, utc_now
from nyx.config import ConfigurationError


AUDIO = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus", ".aiff", ".aif", ".wma"}
SKIP = {".git", ".venv", "target", "$recycle.bin", "system volume information"}


def configuration(root: Path, settings: dict) -> dict:
    config = settings.get("audio", {})
    private = root / "config" / "audio.local.json"
    if private.exists():
        try:
            config = json.loads(private.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ConfigurationError("Cannot read config/audio.local.json as valid JSON.") from None
    if not isinstance(config, dict) or not isinstance(config.get("roots", []), list):
        raise ConfigurationError("Audio configuration needs a roots list.")
    roots = config.get("roots", [])
    if len(roots) > 20 or not all(isinstance(path, str) and path.strip() for path in roots):
        raise ConfigurationError("Audio roots must contain at most 20 nonempty path strings.")
    result = {"roots": [(root / Path(path).expanduser()).resolve() for path in roots]}
    for key, default, maximum in (("max_entries", 10000, 1000000), ("max_seconds", 120, 3600), ("large_export_mb", 100, 100000)):
        value = config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ConfigurationError(f"Audio {key} must be a positive integer within its safety limit.")
        result[key] = value
    return result


def metadata(path: Path, loader) -> dict:
    """Load tags through a read-only file handle; never expose mutation methods."""
    try:
        with path.open("rb") as handle:
            audio = loader(handle, easy=False)
        if audio is None:
            return {"status": "unavailable"}
        tags = audio.tags or {}
        aliases = {
            "title": ("title", "TIT2", "\xa9nam", "Title"),
            "artist": ("artist", "TPE1", "\xa9ART", "Author"),
            "album": ("album", "TALB", "\xa9alb", "WM/AlbumTitle"),
            "track_number": ("tracknumber", "TRCK", "trkn", "WM/TrackNumber"),
        }
        missing = [field for field, keys in aliases.items() if not any(tags.get(key) for key in keys)]
        keys = [str(key).casefold() for key in tags.keys()]
        picture = bool(getattr(audio, "pictures", [])) or any(
            key.startswith("apic") or key in ("covr", "metadata_block_picture", "coverart", "wm/picture") for key in keys
        )
        return {"status": "read", "missing": missing, "artwork_reference": picture}
    except Exception as exc:
        # Parser errors can embed private filenames/tag values; keep only their type.
        return {"status": "unavailable", "error_type": type(exc).__name__}


def inventory(config: dict, *, loader=None, progress=None) -> dict:
    started = time.monotonic()
    deadline = started + config["max_seconds"]
    files = []
    seen: set[Path] = set()
    visited = 0
    errors = 0
    skipped_links = 0
    complete = True
    for root in config["roots"]:
        if not root.is_dir():
            errors += 1
            complete = False
            continue
        pending = [root]
        while pending:
            if visited >= config["max_entries"] or time.monotonic() >= deadline:
                complete = False
                break
            directory = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if visited >= config["max_entries"] or time.monotonic() >= deadline:
                            complete = False
                            break
                        visited += 1
                        info = entry.stat(follow_symlinks=False)
                        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                            skipped_links += 1
                            continue
                        path = Path(entry.path)
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.casefold() not in SKIP:
                                pending.append(path)
                            continue
                        if not entry.is_file(follow_symlinks=False) or path.suffix.lower() not in AUDIO | {".flp"}:
                            continue
                        if path in seen:
                            continue
                        seen.add(path)
                        item = {"path": str(path), "name": path.name, "extension": path.suffix.lower(), "bytes": info.st_size,
                                "naming_flags": ["repeated whitespace"] if re.search(r"\s{2,}", path.stem) else []}
                        if loader is not None and path.suffix.lower() in AUDIO:
                            item["metadata"] = metadata(path, loader)
                        files.append(item)
                        if progress and len(files) % 100 == 0:
                            progress("audio inventory", len(files), None)
            except OSError:
                errors += 1
                complete = False
        if visited >= config["max_entries"] or time.monotonic() >= deadline:
            break
    groups = defaultdict(list)
    for item in files:
        if item["extension"] in AUDIO:
            key = (re.sub(r"\s+", " ", item["name"]).casefold(), item["bytes"])
            groups[key].append(item["path"])
    formats = Counter(item["extension"].lstrip(".") for item in files if item["extension"] in AUDIO)
    return {
        "captured_at": utc_now(), "duration_seconds": round(time.monotonic() - started, 3),
        "complete": complete, "configured_roots": len(config["roots"]), "entries_visited": visited,
        "access_errors": errors, "links_skipped": skipped_links, "files": files,
        "audio_files": sum(formats.values()), "fl_studio_projects": sum(item["extension"] == ".flp" for item in files),
        "formats": dict(formats), "duplicate_candidates": [paths for paths in groups.values() if len(paths) > 1],
        "large_exports": [item["path"] for item in files if item["extension"] in {".wav", ".aiff", ".flac"} and item["bytes"] >= config["large_export_mb"] * 1024**2],
        "metadata_requested": loader is not None,
        "fl_studio_sample_usage": "unavailable: FLP reference parsing is not implemented",
    }


def run_audio_report(root: Path, settings: dict, *, read_tags: bool = False, progress=None) -> Path:
    config = configuration(root, settings)
    loader = None
    if read_tags:
        try:
            from mutagen import File
        except ImportError:
            raise ConfigurationError("Install optional tag reading: python -m pip install -r requirements-audio.txt") from None
        loader = File
    result = inventory(config, loader=loader, progress=progress)
    lines = ["# Nyx Audio / read-only inventory", "", f"Generated: {result['captured_at']} (UTC)", "",
             f"- Configured roots: {result['configured_roots']}", f"- Complete within configured scope: {result['complete']}",
             f"- Audio files observed: {result['audio_files']}", f"- FL Studio projects observed: {result['fl_studio_projects']}",
             f"- Access errors: {result['access_errors']}", f"- Symbolic links/reparse points skipped: {result['links_skipped']}", ""]
    if not config["roots"]:
        lines.extend(["No directories configured. Copy config/audio.example.json to config/audio.local.json and edit locally.", ""])
    if not result["complete"]:
        lines.extend(["Inventory is partial or a configured root was inaccessible. Counts describe observed files only.", ""])
    lines.extend(["## Formats", ""])
    lines.extend(f"- {mark(fmt)}: {count}" for fmt, count in result["formats"].items())
    lines.extend(["", "## Duplicate candidates", "", "Same normalized filename and size only; content identity was not checked."])
    for group in result["duplicate_candidates"][:100]:
        lines.append("- " + " / ".join(mark(Path(path).name) for path in group))
    lines.extend(["", "## Naming and large-export review", ""])
    flagged = [item for item in result["files"] if item["naming_flags"]]
    lines.append(f"- Repeated-whitespace naming candidates: {len(flagged)}")
    lines.append(f"- Large lossless/export candidates: {len(result['large_exports'])}")
    lines.extend("- " + mark(Path(path).name) for path in result["large_exports"][:100])
    lines.extend(["", "## Metadata", ""])
    if loader is None:
        lines.append("Not requested. Use --read-tags with optional Mutagen for read-only metadata diagnostics.")
    else:
        counts = Counter(field for item in result["files"] for field in item.get("metadata", {}).get("missing", []))
        parsed = [item["metadata"] for item in result["files"] if "metadata" in item]
        lines.append(f"- Parsed: {sum(item['status'] == 'read' for item in parsed)}; unavailable: {sum(item['status'] != 'read' for item in parsed)}")
        lines.extend(f"- Missing {field}: {count}" for field, count in counts.items())
        lines.append(f"- No artwork reference found in parsed tags: {sum(item.get('artwork_reference') is False for item in parsed)}")
    lines.extend(["", "## FL Studio scope", "", result["fl_studio_sample_usage"],
                  "Unused samples cannot be established from this inventory. No file is designated safe to delete.",
                  "All findings are suggestions for manual review; no file was moved, renamed, retagged, or deleted.", ""])
    report_dir = Path(os.getenv("NYX_REPORT_DIR") or root / "reports").expanduser() / "Audio"
    dated = report_dir / f"Nyx Audio report - {datetime.now().astimezone():%Y-%m-%d}.md"
    atomic_write(dated, "\n".join(lines))
    atomic_write(report_dir / "Nyx Audio report - latest.md", "\n".join(lines))
    atomic_write(root / "state" / "audio-last.json", json.dumps(result, indent=2))
    return dated
