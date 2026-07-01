"""Tiny cached HTTP helper for build-time downloads.

Keeps downloaded source files on disk under ``data/raw/`` so rebuilds are fast
and offline-friendly, and so we stay polite to upstream servers.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "hanzihub/0.1 (personal Sinitic-pronunciation dataset builder)"


def _urlopen_retry(req, *, timeout: int = 60, retries: int = 5):
    """urlopen with exponential backoff on HTTP 429/503 (rate limiting)."""
    delay = 2.0
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries - 1:
                wait = float(e.headers.get("Retry-After", delay))
                time.sleep(wait)
                delay *= 2
                continue
            raise


def fetch_text(url: str, cache_path: Path, *, force: bool = False,
               min_interval: float = 0.0, encoding: str = "utf-8") -> str:
    """Return the text body of ``url``, caching it at ``cache_path``.

    ``min_interval`` sleeps before a *network* fetch (ignored on cache hit) to
    rate-limit bulk crawls.
    """
    cache_path = Path(cache_path)
    if cache_path.exists() and not force:
        return cache_path.read_text(encoding=encoding)
    if min_interval:
        time.sleep(min_interval)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_retry(req) as r:
        data = r.read().decode(encoding, "replace")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(data, encoding=encoding)
    return data


def fetch_json(url: str, *, min_interval: float = 0.0) -> dict:
    import json
    if min_interval:
        time.sleep(min_interval)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_retry(req) as r:
        return json.loads(r.read().decode("utf-8"))
