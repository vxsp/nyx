"""Opt-in bounded RSS/Atom and public GitHub release digests."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import requests

from jobs.navidrome import atomic_write, mark, utc_now
from nyx.config import ConfigurationError
from nyx.saved import read_json


def https_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("Invalid URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("HTTPS required without embedded credentials")
    return value


def configuration(root: Path, settings: dict) -> dict:
    config = settings.get("research", {})
    path = root / "config" / "research.local.json"
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ConfigurationError("Cannot read config/research.local.json as valid JSON.") from None
    try:
        if not isinstance(config, dict):
            raise ValueError()
        feeds = config.get("feeds", [])
        repos = config.get("github_repositories", [])
        pool = config.get("github_repository_pool", [])
        budget = config.get("max_seconds", 120)
        if not isinstance(feeds, list) or not isinstance(repos, list) or not isinstance(pool, list) or len(feeds) > 20 or len(repos) > 20 or len(pool) > 2000:
            raise ValueError()
        for feed in feeds:
            if not isinstance(feed, dict) or not isinstance(feed.get("category", "Research"), str) or len(feed.get("category", "Research")) > 80:
                raise ValueError()
            https_url(feed.get("url"))
        if not all(isinstance(repo, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) for repo in repos + pool):
            raise ValueError()
        # GitHub repository identities are case-insensitive; never fetch the same repo twice.
        unique = {}
        for repo in repos:
            unique.setdefault(repo.casefold(), repo)
        repos = list(unique.values())
        pool_unique = {}
        for repo in pool:
            if repo.casefold() not in unique:
                pool_unique.setdefault(repo.casefold(), repo)
        pool = list(pool_unique.values())
        slots = 20 - len(feeds) - len(repos)
        batch = config.get("github_batch_size", slots if slots > 0 else 1)
        if slots < 0 or isinstance(batch, bool) or not isinstance(batch, int) or not 1 <= batch <= 20 or (pool and batch > slots):
            raise ValueError()
        if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 600:
            raise ValueError()
    except (ValueError, TypeError):
        raise ConfigurationError("Research needs at most 20 sources per run, valid HTTPS feeds/repository names, a pool up to 2000, a fitting 1-20 repository batch, and a 1-600 second budget.") from None
    return {"feeds": feeds, "github_repositories": repos, "github_repository_pool": pool,
            "github_batch_size": batch, "max_seconds": budget}


def repository_batch(config: dict, previous: dict) -> tuple[list[str], str, int]:
    pool = config["github_repository_pool"]
    fingerprint = sha256("\n".join(repo.casefold() for repo in pool).encode()).hexdigest()
    rotation = previous.get("rotation", {})
    cursor = rotation.get("next_index", 0) if isinstance(rotation, dict) and rotation.get("pool_fingerprint") == fingerprint else 0
    if isinstance(cursor, bool) or not isinstance(cursor, int) or not 0 <= cursor < len(pool):
        cursor = 0
    selected = [pool[(cursor + offset) % len(pool)] for offset in range(min(config["github_batch_size"], len(pool)))]
    return selected, fingerprint, cursor


def identity(url: str, fallback: str) -> str:
    if url:
        parsed = urlsplit(url)
        query = urlencode(sorted((key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                                 if not key.casefold().startswith("utm_")))
        value = urlunsplit((parsed.scheme, parsed.netloc.casefold(), parsed.path, query, ""))
    else:
        value = fallback
    return sha256(value.encode("utf-8")).hexdigest()


def parse_feed(data: bytes, source: str, category: str) -> list[dict]:
    # Restrict to UTF-8 and reject DTD/entities before parsing untrusted XML.
    text = data.decode("utf-8-sig")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
        raise ValueError("DTD/entity declarations are unsupported")
    document = ET.fromstring(text)
    def tag(node):
        return node.tag.rsplit("}", 1)[-1]
    if tag(document) not in ("rss", "feed", "RDF"):
        raise ValueError("Not an RSS/Atom document")
    items = [node for node in document.iter() if tag(node) in ("item", "entry")][:50]
    result = []
    for node in items:
        fields = {}
        link = ""
        for child in node:
            key = tag(child)
            fields.setdefault(key, "".join(child.itertext()).strip())
            if key == "link" and child.attrib.get("rel", "alternate") == "alternate":
                link = child.attrib.get("href") or fields[key]
        try:
            link = https_url(urljoin(source, link)) if link else ""
        except ValueError:
            link = ""
        title = fields.get("title") or "Untitled source entry"
        published = fields.get("pubDate") or fields.get("published") or fields.get("updated")
        published = published[:1000] if published else None
        fallback = source + "\0" + (fields.get("guid") or fields.get("id") or title + str(published))
        result.append({"id": identity(link, fallback), "title": title[:1000], "url": link,
                       "published_at": published, "source": source, "category": category})
    return result


def fetch(session, url: str, cached: dict, deadline: float) -> tuple[bytes | None, dict]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Research budget exhausted")
    headers = {}
    for key, header in (("etag", "If-None-Match"), ("modified", "If-Modified-Since")):
        value = cached.get(key)
        if isinstance(value, str) and len(value) < 1024 and "\r" not in value and "\n" not in value:
            headers[header] = value
    with session.get(url, headers=headers, timeout=(min(5, remaining), min(12, remaining)), stream=True, allow_redirects=False) as response:
        if response.status_code == 304:
            return None, cached
        if 300 <= response.status_code < 400:
            raise ValueError("Configure the final HTTPS source URL; redirects are not followed")
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_content(16384):
            if time.monotonic() >= deadline:
                raise TimeoutError("Research budget exhausted")
            body.extend(chunk)
            if len(body) > 1024 * 1024:
                raise ValueError("Research response exceeds 1 MiB")
        return bytes(body), {"etag": response.headers.get("ETag"), "modified": response.headers.get("Last-Modified")}


def run_research_report(root: Path, settings: dict, *, progress=None) -> Path:
    config = configuration(root, settings)
    state_path = root / "state" / "research-last.json"
    previous = read_json(state_path)
    rotating, fingerprint, cursor = repository_batch(config, previous)
    rotating_urls = {f"https://api.github.com/repos/{repo}/releases?per_page=10" for repo in rotating}
    old_items = previous.get("items", [])
    old_items = [item for item in old_items if isinstance(item, dict) and isinstance(item.get("id"), str)] if isinstance(old_items, list) else []
    old_seen = previous.get("seen_ids", [])
    seen = list(dict.fromkeys([key for key in old_seen if isinstance(key, str)] + [item["id"] for item in old_items])) if isinstance(old_seen, list) else [item["id"] for item in old_items]
    known = set(seen)
    cache = previous.get("cache", {})
    cache = dict(cache) if isinstance(cache, dict) else {}
    sources = [(feed["url"], "feed", feed.get("category", "Research")) for feed in config["feeds"]]
    sources += [(f"https://api.github.com/repos/{repo}/releases?per_page=10", "releases", "GitHub releases") for repo in config["github_repositories"] + rotating]
    deadline = time.monotonic() + config["max_seconds"]
    new_items = []
    statuses = []
    captured = utc_now()
    pool_attempts = 0
    with requests.Session() as session:
        session.trust_env = False  # No implicit .netrc authentication for research sources.
        session.headers.update({"User-Agent": "Nyx/0.1 (opt-in research digest)", "Accept": "application/json, application/atom+xml, application/rss+xml, application/xml"})
        for index, (url, kind, category) in enumerate(sources, start=1):
            if time.monotonic() >= deadline:
                break
            if progress:
                progress("research sources", index - 1, len(sources))
            if url in rotating_urls:
                pool_attempts += 1
            key = sha256(url.encode()).hexdigest()
            cached = cache.get(key, {})
            try:
                body, updated = fetch(session, url, cached if isinstance(cached, dict) else {}, deadline)
                if body is None:
                    statuses.append({"source": url, "status": "not modified"})
                    continue
                if kind == "feed":
                    entries = parse_feed(body, url, category)
                else:
                    values = json.loads(body)
                    if not isinstance(values, list):
                        raise ValueError("Invalid release payload")
                    entries = []
                    for release in values[:10]:
                        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                            continue
                        link = https_url(release.get("html_url"))
                        entries.append({"id": identity(link, url + str(release.get("id"))), "title": str(release.get("name") or release.get("tag_name") or "Release")[:1000],
                                        "url": link, "published_at": release.get("published_at"), "source": url, "category": category})
                for item in entries:
                    if item["id"] not in known:
                        item.update(first_seen_at=captured, read_at=None)
                        new_items.append(item)
                        seen.append(item["id"])
                        known.add(item["id"])
                cache[key] = updated
                statuses.append({"source": url, "status": "collected", "entries_observed": len(entries)})
            except (requests.RequestException, ValueError, UnicodeError, ET.ParseError, TimeoutError) as exc:
                statuses.append({"source": url, "status": "unavailable", "error_type": type(exc).__name__})
                if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (403, 429):
                    break  # Preserve the unattempted remainder instead of hammering a limited source.
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    retained = (old_items + new_items)[-1000:]
    daily = previous.get("daily_ids", []) if previous.get("digest_date") == today else []
    daily = [key for key in daily if isinstance(key, str)] if isinstance(daily, list) else []
    daily_ids = list(dict.fromkeys(daily + [item["id"] for item in new_items]))[-1000:]
    daily_set = set(daily_ids)
    day_items = [item for item in retained if item["id"] in daily_set]
    shown = day_items[:200]
    lines = ["# Nyx Research / digest", "", f"Collected: {captured} (UTC)", "", f"New entries: {len(new_items)}",
             f"Retained entries collected today: {len(day_items)} (up to 200 displayed)",
             f"Selected sources: {len(sources)}; attempted: {len(statuses)}; deferred by budget/source limit: {len(sources) - len(statuses)}", ""]
    rotation = {"pool_fingerprint": fingerprint, "pool_size": len(config["github_repository_pool"]),
                "selected_count": len(rotating), "attempted_count": pool_attempts,
                "next_index": (cursor + pool_attempts) % len(config["github_repository_pool"]) if config["github_repository_pool"] else 0}
    if config["github_repository_pool"]:
        lines.extend([f"Repository pool: {rotation['pool_size']}; selected: {len(rotating)}; attempted: {pool_attempts}.",
                      "Only a bounded batch is checked per explicit run. Further manual runs rotate through the remaining repositories; this is release monitoring, not all repository activity.", ""])
    if not sources:
        lines.extend(["No sources configured. Copy config/research.example.json to config/research.local.json and edit locally.", ""])
    lines.extend(["## Source status", ""])
    for source in statuses:
        lines.append(f"- {mark(source['source'])}: {source['status']}" + (f" ({source['error_type']})" if "error_type" in source else ""))
    for category in dict.fromkeys(item["category"] for item in shown):
        lines.extend(["", f"## {mark(category)}", ""])
        for item in shown:
            if item["category"] != category:
                continue
            title = mark(item["title"])
            link = quote(item["url"], safe=":/?=&%#@+~")
            lines.append(f"- [{title}]({link})" if link else "- " + title)
            lines.append(f"  - Publisher date: {mark(item['published_at'] or 'unavailable')}; ID: {item['id'][:12]}")
    lines.extend(["", "Seen does not mean read. Mark a known entry read explicitly with research-read --item-id ID.",
                  "Configure final HTTPS source URLs; redirects are not followed and implicit .netrc authentication is disabled.",
                  "Each feed is limited to 50 entries; releases to 10 stable entries per repository. Seen IDs retain the last 5,000 entries; reading metadata the last 1,000. This is not an exhaustive archive.", ""])
    report_dir = Path(os.getenv("NYX_REPORT_DIR") or root / "reports").expanduser() / "Research"
    dated = report_dir / f"Nyx Research report - {today}.md"
    atomic_write(dated, "\n".join(lines))
    atomic_write(report_dir / "Nyx Research report - latest.md", "\n".join(lines))
    atomic_write(state_path, json.dumps({"captured_at": captured, "items": retained, "digest_date": today, "daily_ids": daily_ids,
                                        "seen_ids": seen[-5000:], "cache": cache, "sources": statuses,
                                        "rotation": rotation}, indent=2))
    return dated


def mark_read(root: Path, prefix: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{8,64}", prefix):
        raise ConfigurationError("Research item ID must be an 8-64 character hexadecimal prefix.")
    path = root / "state" / "research-last.json"
    state = read_json(path)
    items = state.get("items", [])
    matches = [item for item in items if isinstance(item, dict) and str(item.get("id", "")).startswith(prefix)] if isinstance(items, list) else []
    if len(matches) != 1:
        raise ConfigurationError("Research item ID is unknown or ambiguous; use a longer known ID.")
    matches[0]["read_at"] = utc_now()
    atomic_write(path, json.dumps(state, indent=2))
