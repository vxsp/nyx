"""Read-only Subsonic/OpenSubsonic Navidrome library reporting for Nyx."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import md5, sha256
import html
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from typing import Any, Callable
from urllib.parse import urlsplit

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
    text = html.escape(cleaned(value), quote=False).replace("\n", " ").replace("\r", " ").replace("`", "'")
    for char in ("\\", "|", "[", "]", "*", "_"):
        text = text.replace(char, "\\" + char)
    return text


class NavidromeClient:
    READ_ENDPOINTS = {"ping", "getScanStatus", "getArtists", "getPlaylists", "getAlbumList2", "getAlbum"}

    def __init__(self, url: str, username: str, password: str, timeout: int = 12):
        self.base = url.rstrip("/")
        try:
            parsed = urlsplit(self.base)
            valid = parsed.scheme == "https" and parsed.hostname and not (
                parsed.username or parsed.password or parsed.query or parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise NavidromeError("Navidrome URL must use HTTPS without embedded credentials, query, or fragment.")
        if not username or not password:
            raise NavidromeError("Set NAVIDROME_USERNAME and NAVIDROME_PASSWORD in config/.env.")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Nyx/0.1 (read-only library reporting)"})

    def get(self, endpoint: str, *, remaining_seconds: float | None = None, **kwargs: Any) -> dict:
        if endpoint not in self.READ_ENDPOINTS:
            raise NavidromeError("Only the reporter's read-only API endpoints are allowed.")
        salt = secrets.token_hex(8)
        token = md5((self.password + salt).encode("utf-8")).hexdigest()
        params = {
            "u": self.username, "t": token, "s": salt,
            "v": "1.16.1", "c": "nyx", "f": "json", **kwargs,
        }
        try:
            response = self.session.get(
                f"{self.base}/rest/{endpoint}.view", params=params,
                allow_redirects=False,
                timeout=(min(5, remaining_seconds) if remaining_seconds is not None else 5,
                         min(self.timeout, remaining_seconds) if remaining_seconds is not None else self.timeout),
            )
            response.raise_for_status()
            document = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Avoid including a URL with the authenticated query parameters in errors.
            raise NavidromeError(f"{endpoint} request failed (network/server error).") from None
        payload = document.get("subsonic-response", {}) if isinstance(document, dict) else {}
        if not isinstance(payload, dict):
            raise NavidromeError(f"{endpoint} returned an invalid API response.")
        if payload.get("status") != "ok":
            error = payload.get("error", {})
            code = error.get("code") if isinstance(error, dict) else None
            label = str(code) if isinstance(code, int) and not isinstance(code, bool) else "unknown"
            # Server messages are untrusted and may echo credentials/query parameters.
            raise NavidromeError(f"{endpoint} failed (API error {label}). Check server availability and account access.")
        return payload


def load_previous(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(value, dict) or not isinstance(value.get("songs", []), list):
            return {}
        return value
    except (json.JSONDecodeError, OSError):
        return {}


def collect(client: NavidromeClient, page_size: int, max_albums: int, max_seconds: int,
            progress: Callable[[str, int, int | None], None] | None = None) -> dict:
    start = time.monotonic()
    def request(endpoint: str, **params) -> dict:
        remaining = max_seconds - (time.monotonic() - start)
        if remaining <= 0:
            raise NavidromeError(f"Exceeded {max_seconds}s collection time budget.")
        result = client.get(endpoint, remaining_seconds=remaining, **params)
        if time.monotonic() - start > max_seconds:
            raise NavidromeError(f"Exceeded {max_seconds}s collection time budget.")
        return result

    if progress:
        progress("connecting", 0, None)
    request("ping")
    raw_scan = request("getScanStatus").get("scanStatus", {})
    scan = raw_scan if isinstance(raw_scan, dict) else {}
    artists_reply = request("getArtists").get("artists", {})
    artists = [a for group in as_list(artists_reply.get("index")) for a in as_list(group.get("artist"))]
    playlists = as_list(request("getPlaylists").get("playlists", {}).get("playlist"))
    albums: list[dict] = []
    offset = 0
    while offset < max_albums:
        page = as_list(request(
            "getAlbumList2", type="alphabeticalByName",
            size=min(page_size, max_albums - offset), offset=offset,
        ).get("albumList2", {}).get("album"))
        albums.extend(page)
        if progress:
            progress("album index", len(albums), None)
        if len(page) < min(page_size, max_albums - offset):
            break
        offset += len(page)
    else:
        raise NavidromeError("Album safety limit reached. Increase max_albums to get complete results.")

    songs: list[dict] = []
    seen_songs: set[str] = set()
    seen_albums: set[str] = set()
    unique_albums: list[dict] = []
    for index, album in enumerate(albums, start=1):
        if time.monotonic() - start > max_seconds:
            raise NavidromeError(f"Exceeded {max_seconds}s time budget during album retrieval.")
        album_id = cleaned(album.get("id"))
        if not album_id:
            raise NavidromeError("Album response is missing an ID; refusing an incomplete snapshot.")
        if album_id in seen_albums:
            continue
        seen_albums.add(album_id)
        unique_albums.append(album)
        data = request("getAlbum", id=album_id).get("album", {})
        for song in as_list(data.get("song")):
            song = dict(song)
            song_id = cleaned(song.get("id"))
            if not song_id:
                raise NavidromeError("Track response is missing an ID; refusing an incomplete snapshot.")
            if song_id in seen_songs:
                continue
            seen_songs.add(song_id)
            song.setdefault("album", album.get("name", ""))
            song.setdefault("artist", album.get("artist", ""))
            songs.append(song)
        if index % 20 == 0:
            if progress:
                progress("album tracks", index, len(albums))
            time.sleep(0.1)  # gentle on a remote server
    if progress:
        progress("collected", len(albums), len(albums))

    return {
        "captured_at": utc_now(),
        "server": client.base,
        "scan": scan,
        "artists": artists,
        "albums": unique_albums,
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
    previous_ids = {cleaned(i.get("id")) for i in as_list(previous.get("songs")) if i.get("id")}
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
        "previous_captured_at": previous.get("captured_at"),
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
        f"- Currently scanning: {('yes' if scan['scanning'] else 'no') if isinstance(scan.get('scanning'), bool) else 'unavailable'}",
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
        lines.append(f"- Compared with snapshot: {mark(summary.get('previous_captured_at') or 'timestamp unavailable')}")
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
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(content)
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)  # Only our own newly created temporary file.


def run_report(project_dir: Path, settings: dict,
               progress: Callable[[str, int, int | None], None] | None = None) -> Path:
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
        progress=progress,
    )
    previous_path = project_dir / "state" / "navidrome-last.json"
    previous = load_previous(previous_path)
    summary = summarize(current, previous)
    output = render(current, summary)
    report_dir = Path(os.getenv("NYX_REPORT_DIR") or str(project_dir / "reports")).expanduser()
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    dated_path = report_dir / "Navidrome" / f"Navidrome report - {today}.md"
    latest_path = report_dir / "Navidrome" / "Navidrome report - latest.md"
    atomic_write(dated_path, output)
    atomic_write(latest_path, output)
    saved_summary = {
        "scope_id": sha256(("metrics-v1\0" + cleaned(current.get("server")) + "\0" + os.getenv("NAVIDROME_USERNAME", "")).encode()).hexdigest(),
        "captured_at": current["captured_at"], "duration_seconds": current["duration_seconds"],
        "scan": current["scan"],
        **{key: summary[key] for key in ("tracks", "albums", "artists", "playlists", "formats", "reported_file_bytes", "removed_count", "has_previous")},
        "missing_metadata": {key: len(value) for key, value in summary["problems"].items()},
        "duplicate_groups": len(summary["duplicate_candidates"]), "added_count": len(summary["added_tracks"]),
    }
    atomic_write(project_dir / "state" / "navidrome-summary.json", json.dumps(saved_summary, indent=2))
    # Only commit the snapshot when all API requests and report writes succeeded.
    atomic_write(previous_path, json.dumps(current, indent=2, ensure_ascii=False))
    return dated_path
