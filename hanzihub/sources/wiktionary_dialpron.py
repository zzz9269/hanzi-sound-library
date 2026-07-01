"""Loader for Wiktionary dialectal pronunciation data — the big coverage lever.

en.wiktionary stores per-character modern-dialect IPA in
``Module:zh/data/dial-pron/<char>`` as a positional Lua table:

    return {
        { "人", { "ʐən35", "ʐən24|in24", ..., "zin31|naŋ31訓儂" } },
    }

The inner list is positional: entry *i* corresponds to ``schema.LOCALITIES[i]``
(39 localities across every Sinitic branch, incl. the Min varieties absent from
the existing dataset). A character may have several entries (multiple readings).

Strategy:
  * enumerate the subpages via the MediaWiki ``allpages`` API (namespace 828),
  * fetch raw module text in batches of 50 via ``revisions`` (≈50× fewer requests
    than per-page), caching the parsed result so rebuilds are instant/offline,
  * map positions → localities and emit one record per (char, locality, reading).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

from . import record, is_single_han
from .._http import fetch_json
from ..paths import WIKTIONARY_CACHE
from ..schema import LOCALITIES, SRC_WIKTIONARY, locality_col

API = "https://en.wiktionary.org/w/api.php"
MODULE_NS = 828
PREFIX = "zh/data/dial-pron/"
PARSED_CACHE = WIKTIONARY_CACHE / "dial_pron_parsed.json"

# inner readings list: { "<head>", { "r1", "r2", ... } }
_ENTRY_RE = re.compile(r'\{\s*"(?:[^"\\]|\\.)*"\s*,\s*\{(.*?)\}\s*\}', re.S)
_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _q(params: dict) -> str:
    return API + "?" + urllib.parse.urlencode(params)


def enumerate_titles(*, min_interval: float = 0.3) -> list[tuple[str, str]]:
    """Return ``(char, full_title)`` for every dial-pron subpage of a single char."""
    out: list[tuple[str, str]] = []
    apcontinue = None
    while True:
        params = {
            "action": "query", "list": "allpages", "apnamespace": MODULE_NS,
            "apprefix": PREFIX, "aplimit": "500", "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        data = fetch_json(_q(params), min_interval=min_interval)
        for p in data.get("query", {}).get("allpages", []):
            title = p["title"]
            char = title.rsplit("/", 1)[-1]
            if is_single_han(char):
                out.append((char, title))
        cont = data.get("continue", {}).get("apcontinue")
        if not cont:
            break
        apcontinue = cont
    return out


def parse_module(text: str) -> list[list[str]]:
    """Parse raw Lua module text → list of positional reading-lists."""
    sets: list[list[str]] = []
    for blob in _ENTRY_RE.findall(text):
        readings = _QUOTED_RE.findall(blob)
        if readings:
            sets.append([r.strip() for r in readings])
    return sets


def _fetch_contents(titles: list[str], *, min_interval: float) -> dict[str, str]:
    """Batch-fetch raw content for ``titles`` (≤50) → {char: module_text}."""
    params = {
        "action": "query", "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "titles": "|".join(titles), "format": "json",
    }
    data = fetch_json(_q(params), min_interval=min_interval)
    out: dict[str, str] = {}
    for page in data.get("query", {}).get("pages", {}).values():
        title = page.get("title", "")
        char = title.rsplit("/", 1)[-1]
        revs = page.get("revisions")
        if not revs:
            continue
        content = revs[0].get("slots", {}).get("main", {}).get("*", "")
        if content:
            out[char] = content
    return out


def crawl(*, limit: int | None = None, min_interval: float = 1.0,
          verbose: bool = True) -> dict[str, list[list[str]]]:
    """Fetch + parse dial-pron modules, caching to ``PARSED_CACHE``. Resumable.

    ``limit`` caps the number of *new* characters fetched this run (for testing).
    """
    WIKTIONARY_CACHE.mkdir(parents=True, exist_ok=True)
    cache: dict[str, list[list[str]]] = {}
    if PARSED_CACHE.exists():
        cache = json.loads(PARSED_CACHE.read_text(encoding="utf-8"))

    titles = enumerate_titles(min_interval=min_interval)
    missing = [(c, t) for c, t in titles if c not in cache]
    if limit is not None:
        missing = missing[:limit]
    if verbose:
        print(f"[wiktionary] {len(titles):,} dial-pron pages; "
              f"{len(cache):,} cached; fetching {len(missing):,} new")

    for i in range(0, len(missing), 50):
        batch = missing[i:i + 50]
        contents = _fetch_contents([t for _, t in batch], min_interval=min_interval)
        for char, _title in batch:
            cache[char] = parse_module(contents.get(char, ""))
        # save after every batch so the crawl is fully resumable on interruption
        PARSED_CACHE.write_text(json.dumps(cache, ensure_ascii=False),
                                encoding="utf-8")
        if verbose:
            print(f"[wiktionary]   {min(i + 50, len(missing)):,}/{len(missing):,}")

    PARSED_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def records_from_cache(cache: dict[str, list[list[str]]]) -> list[dict]:
    records: list[dict] = []
    for char, sets in cache.items():
        if not is_single_han(char):
            continue
        seen: set[tuple[str, str]] = set()
        for readings in sets:
            for i, reading in enumerate(readings):
                if i >= len(LOCALITIES) or not reading:
                    continue
                loc = LOCALITIES[i]
                col = locality_col(loc)
                key = (col, reading)
                if key in seen:
                    continue
                seen.add(key)
                records.append(record(char, col, reading, SRC_WIKTIONARY,
                                      locality=loc.name))
    return records


def load(*, limit: int | None = None, refresh: bool = False) -> list[dict]:
    """Load dial-pron records. Uses the parsed cache unless ``refresh``/``limit``.

    With ``refresh=True`` (or a ``limit``) it crawls for new/missing chars first.
    With neither, it just reads whatever is cached (offline rebuilds).
    """
    if refresh or limit is not None or not PARSED_CACHE.exists():
        cache = crawl(limit=limit)
    else:
        cache = json.loads(PARSED_CACHE.read_text(encoding="utf-8"))
    return records_from_cache(cache)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    t0 = time.time()
    recs = load(limit=lim)
    chars = {r["char"] for r in recs}
    print(f"dial-pron: {len(recs):,} records over {len(chars):,} chars "
          f"in {time.time()-t0:.1f}s")
    for r in [x for x in recs if x["char"] == "人"][:6]:
        print("  ", r["char"], r["column"], "=", r["reading"])
