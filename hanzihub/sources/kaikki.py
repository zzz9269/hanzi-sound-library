"""Loader for kaikki.org (machine-readable Wiktionary) — the locality IPA lever.

kaikki.org publishes a pre-parsed JSON-Lines extract of the entire English
Wiktionary Chinese section. Each entry has a ``sounds`` array whose items carry
an ``ipa`` string plus ``tags`` naming the variety/locality, e.g.::

    {"ipa": "/kʰɛiŋ³³/", "tags": ["Min-Dong", "Fuzhou", "Sinological-IPA"]}
    {"ipa": "/tsʰuan¹/",  "tags": ["Hokkien", "Quanzhou"]}

This is exactly the per-character locality IPA the legacy pipeline lacked (the
``dial-pron`` module only covers ~1k chars). We stream the big ``.jsonl`` once,
keep single-Han-character entries, and from each tagged IPA derive a
``dial:<branch>-<locality>`` column: the **branch** comes from the family tag
(Wu / Hokkien / Min-Dong / Hakka / …) and the **locality** from the place tag
(Shanghai / Quanzhou / Fuzhou / Meixian / …). This captures ~50 dialect points,
far beyond the canonical 39, and the branch columns then gap-fill from their
representative locality in :mod:`hanzihub.merge`.

NB kaikki/Wiktionary has **no** systematic Haikou-Hainanese or Shexian-Hui IPA
(its nearest tags, ``Leizhou`` and ``Hui'an``, are *different* lects), so those
two columns can't be filled from this source.

Workflow::

    # one-off, from the 1.1 GB download (kept out of the synced project tree):
    python -m hanzihub.sources.kaikki  C:\\path\\to\\kaikki-Chinese.jsonl
    # then normal builds read the small cache under data/raw/kaikki/.
"""
from __future__ import annotations

import json
import re

from . import is_single_han, record
from ..paths import RAW_DIR
from ..schema import LOCALITIES, SRC_KAIKKI

KAIKKI_DIR = RAW_DIR / "kaikki"
PARSED_CACHE = KAIKKI_DIR / "kaikki_readings.json"

# Family/group tag → wide-CSV branch label (matches schema dial: prefixes).
_GROUP_TO_BRANCH = {
    "Mandarin": "Mandarin", "Dungan": "Mandarin",
    "Cantonese": "Cantonese",
    "Wu": "Wu", "Hakka": "Hakka", "Gan": "Gan", "Jin": "Jin", "Xiang": "Xiang",
    "Hokkien": "Min", "Min-Nan": "Min", "Teochew": "Min", "Min-Dong": "Min",
    "Min-Bei": "Min", "Puxian-Min": "Min", "Leizhou": "Min",
    "Southern-Pinghua": "Pinghua",
}

# Group tags that *are* a single locality when no city tag accompanies them.
_GROUP_DEFAULT_CITY = {
    "Min-Dong": "Fuzhou", "Min-Bei": "Jian'ou", "Puxian-Min": "Putian",
    "Leizhou": "Leizhou", "Teochew": "Shantou", "Southern-Pinghua": "Nanning",
}

# Normalise kaikki place tags to a single canonical city name.
_CITY_NORMALIZE = {"Taishanese": "Taishan", "Taicheng": "Taishan",
                  "Teochew": "Shantou"}

# Group tags → the niche Min *branch* columns (filled directly).
_NICHE_BRANCH = {"Min-Dong": "Eastern Min (Fuzhou)",
                 "Min-Bei": "Northern Min (Jian'ou)"}

# Recognised place tags: the canonical 39 + the extra points kaikki carries.
_PLACES = {loc.name for loc in LOCALITIES} | {
    # Wu
    "Ningbo", "Chongming", "Fuyang", "Jinhua",
    # Min (Hokkien & friends)
    "Quanzhou", "Zhangzhou", "Taipei", "Kaohsiung", "Tainan", "Taichung",
    "Lukang", "Yilan", "Kinmen", "Penang", "Klang", "Zhangpu", "Changtai",
    "Nan'an", "Tong'an", "Hui'an", "Jinjiang", "Leizhou", "Putian", "Shantou",
    # Hakka
    "Sixian", "Hailu", "Neipu", "Miaoli", "Zhudong", "Changting", "Dongguan",
    # Cantonese
    "Taishan", "Taishanese", "Taicheng",
    # Xiang / Mandarin extras
    "Loudi", "Yangzhou",
}

# Cap distinct readings per (char, column): Wiktionary aggregates many minor
# transcription variants (e.g. ~12 for one Suzhou syllable) — a few is plenty.
_MAX_PER_COL = 4

_IPA_STRIP = re.compile(r"^[\[/]+|[\]/]+$")


def _norm_tag(t: str) -> str:
    return t.replace("’", "'").strip()


def _clean_ipa(s: str) -> str:
    return _IPA_STRIP.sub("", (s or "").strip()).strip()


def _columns_for_sound(tags: list[str]) -> list[str]:
    """Wide-CSV columns a tagged IPA belongs to (a dial: locality + niche branch)."""
    cols: list[str] = []
    branch = next((_GROUP_TO_BRANCH[t] for t in tags if t in _GROUP_TO_BRANCH), None)
    city = None
    for t in tags:
        if t in _CITY_NORMALIZE:
            city = _CITY_NORMALIZE[t]; break
        if t in _PLACES:
            city = t; break
    if city is None and branch:
        city = next((_GROUP_DEFAULT_CITY[t] for t in tags if t in _GROUP_DEFAULT_CITY), None)
    if branch and city:
        cols.append(f"dial:{branch}-{city}")
    for t in tags:
        if t in _NICHE_BRANCH:
            cols.append(_NICHE_BRANCH[t])
    return cols


def build_cache(raw_path: str, *, verbose: bool = True) -> dict[str, list[list[str]]]:
    """Stream the kaikki ``.jsonl`` and write the compact per-char cache.

    Cache shape: ``{char: [[column, reading], ...]}`` (deduplicated, capped)."""
    KAIKKI_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, set[tuple[str, str]]] = {}
    lines = 0
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            lines += 1
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            word = obj.get("word", "")
            if not is_single_han(word):
                continue
            pairs = out.setdefault(word, set())
            for s in obj.get("sounds", []):
                ipa = _clean_ipa(s.get("ipa", ""))
                if not ipa:
                    continue
                tags = [_norm_tag(t) for t in s.get("tags", [])]
                for col in _columns_for_sound(tags):
                    pairs.add((col, ipa))
            if verbose and lines % 100000 == 0:
                print(f"[kaikki]   {lines:,} lines processed")

    cache: dict[str, list[list[str]]] = {}
    for ch, pairs in out.items():
        if not pairs:
            continue
        by_col: dict[str, list[str]] = {}
        for col, reading in sorted(pairs):
            kept = by_col.setdefault(col, [])
            if len(kept) < _MAX_PER_COL:
                kept.append(reading)
        cache[ch] = [[col, r] for col, rs in by_col.items() for r in rs]
    PARSED_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    if verbose:
        total = sum(len(v) for v in cache.values())
        ncols = len({c for v in cache.values() for c, _ in v})
        print(f"[kaikki] cached {len(cache):,} chars, {total:,} (column,reading) pairs, "
              f"{ncols} distinct columns from {lines:,} lines → {PARSED_CACHE}")
    return cache


def records_from_cache(cache: dict[str, list[list[str]]]) -> list[dict]:
    records: list[dict] = []
    for char, pairs in cache.items():
        if not is_single_han(char):
            continue
        for column, reading in pairs:
            loc = column.split("-", 1)[1] if column.startswith("dial:") else ""
            records.append(record(char, column, reading, SRC_KAIKKI, locality=loc))
    return records


def load() -> list[dict]:
    """Return kaikki records from the cache, or ``[]`` if it hasn't been built."""
    if not PARSED_CACHE.exists():
        return []
    cache = json.loads(PARSED_CACHE.read_text(encoding="utf-8"))
    return records_from_cache(cache)


if __name__ == "__main__":
    import sys
    import time
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m hanzihub.sources.kaikki <kaikki-Chinese.jsonl>")
    t0 = time.time()
    build_cache(sys.argv[1])
    print(f"[kaikki] done in {time.time() - t0:.0f}s")
