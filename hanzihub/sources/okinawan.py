"""Loader for Okinawan (Ryukyuan) kanji readings, from kaikki.org.

kaikki publishes a small (~1.7 MB) Okinawan extract. For a kanji headword the
lemma entry carries the reading in its ``forms`` — a ``hiragana`` form plus a
``romanization`` form, e.g. for 血: ``ちー`` / ``chī``. We pair them into one
``Okinawan`` reading column (``ちー (chī)``). Entries without a hiragana form
(e.g. the bare "Nth grade kyōiku kanji" note) are skipped.

Download once with :func:`download`; the loader reads the cached ``.jsonl``.
"""
from __future__ import annotations

import json

from . import is_single_han, record
from ..paths import RAW_DIR
from ..schema import SRC_OKINAWAN

OKINAWAN_DIR = RAW_DIR / "okinawan"
JSONL = OKINAWAN_DIR / "okinawan.jsonl"
_URL = "https://kaikki.org/dictionary/Okinawan/kaikki.org-dictionary-Okinawan.jsonl"


def download(*, force: bool = False) -> None:
    import requests
    OKINAWAN_DIR.mkdir(parents=True, exist_ok=True)
    if JSONL.exists() and not force:
        return
    r = requests.get(_URL, timeout=60)
    r.raise_for_status()
    JSONL.write_text(r.text, encoding="utf-8")


def load() -> list[dict]:
    """Return ``Okinawan`` reading records from the cached jsonl (``[]`` if absent)."""
    if not JSONL.exists():
        return []
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        word = obj.get("word", "")
        if not is_single_han(word):
            continue
        hira = rom = ""
        for f in obj.get("forms", []):
            tags = f.get("tags", [])
            form = f.get("form", "").strip()
            if "hiragana" in tags and not hira:
                hira = form
            elif "romanization" in tags and form and " " not in form and len(form) < 12:
                rom = form
        if not hira:
            continue
        reading = hira + (f" ({rom})" if rom and rom != hira else "")
        key = (word, reading)
        if key in seen:
            continue
        seen.add(key)
        records.append(record(word, "Okinawan", reading, SRC_OKINAWAN))
    return records


if __name__ == "__main__":
    download()
    recs = load()
    print(f"[okinawan] {len(recs):,} kanji readings")
    print("  sample:", [(r["char"], r["reading"]) for r in recs[:6]])
