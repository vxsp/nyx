"""Read-only Subsonic/OpenSubsonic Navidrome library reporting for Nyx."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import md5
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Any

import requests


class NavidromeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def as_list(value: Any) -> list[dict]:
    if not value:
        return []
    if isinstance(value, list):
        return [i for i in value if isinstance(i, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def cleaned(value: Any) -> str:
    return str(value or "").strip()


def normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", cleaned(value)).casefold()


def mark(value: Any) -> str:
    """Prevent markdown injection in displayed fields."""
    return cleaned(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("`", "'")


class NavidromeClient:
    def __init__(self, url: str, username: str, password: str, timeout: int = 12):
        self.base = url.rstrip("/")
        if not self.base.startswith("https://"):
            raise NavidromeError("Navidrome URL must use HTTPS.")
        if not username or not password:
            raise NavidromeError("Set NAVIDROME_USERNAME and NAVIDROME_PASSWORD in config/.env.")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Nyx/0.1 (read-only library reporting)"})

    def get(self, endpoint: str, **kwargs: Any) -> dict:
        salt = secrets.token_hex(8)
        token = md5((self.password + salt).encode("utf-8")).hexdigest()
        params = {
            "u": self.username, "t": token, "s": salt,
            "v": "1.16.1", "c": "nyx", "f": "json", **kwargs,
        }
        try:
            response = self.session.get(
                f"{self.base}/rest/{endpoint}.view", params=params,
                timeout=(5, self.timeout),
            )
            response.raise_for_status()
            document = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Avoid including a URL with the authenticated query parameters in errors.
            raise NavidromeError(f"{endpoint} request failed (network/server error).") from None
        payload = document.get("subsonic-response", {})
        if payload.get("status") != "ok":
            error = payload.get("error", {})
            raise NavidromeError(
                f"{endpoint} failed: {cleaned(error.get('message')) or 'unknown API error'}"
            )
        return payload


def load_previous(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def collect(client: NavidromeClient, page_size: int, max_albums: int, max_seconds: int) -> dict:
    start = time.monotonic()
    client.get("ping")
    scan = client.get("getScanStatus").get("scanStatus", {})
    artists_reply = client.get("getArtists").get("artists", {})
    artists = [a for group in as_list(artists_reply.get("index")) for a in as_list(group.get("artist"))]
    playlists = as_list(client.get("getPlaylists").get("playlists", {}).get("playlist"))
    albums: list[dict] = []
    offset = 0
    while offset < max_albums:
        page = as_list(client.get(
            "getAlbumList2", type="alphabeticalByName",
            size=min(page_size, max_albums - offset), offset=offset,
        ).get("albumList2", {}).get("album"))
        albums.extend(page)
        if len(page) < min(page_size, max_albums - offset):
            break
        offset += len(page)
    else:
        raise NavidromeError("Album safety limit reached. Increase max_albums to get complete results.")

    songs: list[dict] = []
    for index, album in enumerate(albums, start=1):
        if time.monotonic() - start > max_seconds:
            raise NavidromeError(f"Exceeded {max_seconds}s time budget during album retrieval.")
        album_id = cleaned(album.get("id"))
        if not album_id:
            continue
        data = client.get("getAlbum", id=album_id).get("album", {})
        for song in as_list(data.get("song")):
            song = dict(song)
            song.setdefault("album", album.get("name", ""))
            song.setdefault("artist", album.get("artist", ""))
            songs.append(song)
        if index % 20 == 0:
            time.sleep(0.1)  # gentle on a remote server

    return {
        "captured_at": utc_now(),
        "server": client.base,
        "scan": scan,
        "artists": artists,
        "albums": albums,
        "songs": songs,
        "playlists": playlists,
        "duration_seconds": round(time.monotonic() - start, 1),
    }


def summarize(current: dict, previous: dict) -> dict:
    songs = current["songs"]
    album_list = current["albums"]
    formats: Counter[str] = Counter()
    problems: dict[str, list[dict]] = {
        "missing_artist": [], "missing_album": [], "missing_track_number": [],
        "missing_cover_art_reference": []
    }
    groups: dict[tuple, list[dict]] = defaultdict(list)
    total_bytes = 0
    for song in songs:
        path = cleaned(song.get("path"))
        fmt = Path(path).suffix.lower().lstrip(".") or cleaned(song.get("suffix")) or "unknown"
        formats[fmt] += 1
        total_bytes += int(song.get("size") or 0)
        for field, failure in (
            ("artist", "missing_artist"), ("album", "missing_album"),
            ("track", "missing_track_number"), ("coverArt", "missing_cover_art_reference"),
        ):
            if not cleaned(song.get(field)):
                problems[failure].append(song)
        key = (normalized(song.get("artist")), normalized(song.get("title")))
        if all(key):
            groups[key].append(song)

    duplicate_candidates: list[list[dict]] = []
    for similar in groups.values():
        if len(similar) < 2:
            continue
        ordered = sorted(similar, key=lambda song: int(song.get("duration") or 0))
        cluster: list[dict] = []
        for song in ordered:
            length = int(song.get("duration") or 0)
            if cluster and length - int(cluster[0].get("duration") or 0) > 3:
                if len(cluster) > 1:
                    duplicate_candidates.append(cluster)
                cluster = []
            cluster.append(song)
        if len(cluster) > 1:
            duplicate_candidates.append(cluster)
    duplicate_candidates.sort(key=lambda group: (-len(group), normalized(group[0].get("title"))))

    current_ids = {cleaned(i.get("id")) for i in songs if i.get("id")}
    previous_ids = {cleaned(i.get("id")) for i in previous.get("songs", []) if i.get("id")}
    added = current_ids - previous_ids if previous else set()
    removed = previous_ids - current_ids if previous else set()
    return {
        "tracks": len(songs),
        "albums": len(album_list),
        "artists": len({cleaned(a.get("id")) for a in current["artists"] if a.get("id")}),
        "playlists": len(current["playlists"]),
        "formats": dict(formats.most_common()),
        "reported_file_bytes": total_bytes,
        "problems": problems,
        "duplicate_candidates": duplicate_candidates,
        "added_tracks": [s for s in songs if cleaned(s.get("id")) in added],
        "removed_count": len(removed),
        "has_previous": bool(previous),
    }


def render(current: dict, summary: dict) -> str:
    scan = current.get("scan", {})
    dt = current["captured_at"]
    lines = [
        "# Nyx / Navidrome Library Report", "",
        f"Generated: {dt} (UTC)",
        f"Server: {mark(current['server'])}", "",
        "## Library", "",
        "| Metric | Value |", "|---|---:|",
        f"| Tracks | {summary['tracks']:,} |",
        f"| Albums | {summary['albums']:,} |",
        f"| Artists | {summary['artists']:,} |",
        f"| Playlists | {summary['playlists']:,} |",
        f"| Indexed file sizes | {summary['reported_file_bytes'] / (1024 ** 3):.2f} GiB |",
        f"| Data collection | {current['duration_seconds']:.1f} seconds |", "",
        "## Server and scan", "",
        "- API authentication and ping: successful",
        f"- Currently scanning: {'yes' if scan.get('scanning') else 'no'}",
        f"- Scan progress count (server-reported): {scan.get('count', 'unavailable')}",
        f"- Last scan (server-reported): {mark(scan.get('lastScan') or 'unavailable')}", "",
        "## Audio formats", "",
        "| Format | Tracks |", "|---|---:|",
    ]
    lines.extend(f"| {mark(ext)} | {count:,} |" for ext, count in summary["formats"].items())
    lines.extend(["", "## Metadata diagnostics", ""])
    labels = {
        "missing_artist": "Missing artist tag",
        "missing_album": "Missing album tag",
        "missing_track_number": "Missing track number",
        "missing_cover_art_reference": "No cover-art reference (not proof of missing image)",
    }
    for key, label in labels.items():
        lines.append(f"- {label}: {len(summary['problems'][key])}")
    lines.extend(["", "## Possible duplicates", ""])
    lines.append(f"{len(summary['duplicate_candidates'])} groups share artist, title, and similar duration. Review manually.")
    for group in summary["duplicate_candidates"][:15]:
        song = group[0]
        lines.append(f"- {mark(song.get('artist'))} / {mark(song.get('title'))}: {len(group)} tracks")
    if not summary["duplicate_candidates"]:
        lines.append("- None found under this heuristic.")
    lines.extend(["", "## Library changes", ""])
    if summary["has_previous"]:
        lines.append(f"- Added track IDs since last complete snapshot: {len(summary['added_tracks'])}")
        lines.append(f"- Removed track IDs since last complete snapshot: {summary['removed_count']}")
        for song in summary["added_tracks"][:15]:
            lines.append(f"  - {mark(song.get('artist'))} / {mark(song.get('title'))}")
    else:
        lines.append("First snapshot. Changes will appear after the next run.")
    lines.extend([
        "", "## Scope", "",
        "Read-only Subsonic API report. Counts reflect music accessible to this Navidrome account.",
        "Possible duplicates are metadata matches, not confirmed identical audio files.",
        "Lyrics availability and embedded artwork are not inspected in this version.", "",
    ])
    return "\n".join(lines)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def run_report(project_dir: Path, settings: dict) -> Path:
    config = settings.get("navidrome", {})
    url = os.environ.get("NAVIDROME_URL", "https://vxsp.pikapod.net")
    client = NavidromeClient(
        url, os.getenv("NAVIDROME_USERNAME", ""), os.getenv("NAVIDROME_PASSWORD", ""),
        int(config.get("request_timeout_seconds", 12)),
    )
    current = collect(
        client, int(config.get("page_size", 200)),
        int(config.get("max_albums", 2000)),
        int(config.get("max_report_seconds", 600)),
    )
    previous_path = project_dir / "state" / "navidrome-last.json"
    previous = load_previous(previous_path)
    summary = summarize(current, previous)
    output = render(current, summary)
    report_dir = Path(os.getenv("NYX_REPORT_DIR") or str(project_dir / "reports")).expanduser()
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    dated_path = report_dir / "Navidrome" / f"{today}.md"
    latest_path = report_dir / "Navidrome" / "Latest.md"
    atomic_write(dated_path, output)
    atomic_write(latest_path, output)
    # Only commit the snapshot when all API requests and report writes succeeded.
    atomic_write(previous_path, json.dumps(current, indent=2, ensure_ascii=False))
    return dated_path
