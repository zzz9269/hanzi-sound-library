"""Loader for the two points kaikki/Wiktionary lacks: Haikou (Hainanese) and
Shexian (Hui), sourced from 漢字音典 / MCPDict (github.com/osfans/MCPDict).

MCPDict ships ~2,800 per-dialect 字表 as TSVs under ``tools/tables/data/``.
Two of them fill the last gaps in this dataset:

* ``海口2025-12-23.tsv`` — Hainanese (Haikou), columns ``漢字 / 音標 / 註釋``
  (ready-made IPA, e.g. ``邊 ɓi1``).
* ``歙县岩寺YB_21J03.tsv`` — Hui (Shexian), columns
  ``cid / character / initial / final / tone`` which we recombine into IPA
  (``多 t əɤ 53`` → ``təɤ˥˧``).

Each fills a ``dial:`` locality column; the ``Hainanese (Haikou)`` and
``Hui (Shexian)`` branch columns then gap-fill from their representative
locality in :mod:`hanzihub.merge`.
"""
from __future__ import annotations

import csv
import urllib.parse

from . import is_single_han, record
from ..paths import RAW_DIR
from ..schema import SRC_MCPDICT

MCPDICT_DIR = RAW_DIR / "mcpdict"
_RAW_BASE = "https://raw.githubusercontent.com/osfans/MCPDict/master/tools/tables/data/"

# (local cache name, upstream filename, format, dial: column, locality)
_POINTS = [
    ("haikou.tsv", "海口2025-12-23.tsv", "ipa", "dial:Min-Haikou", "Haikou"),
    ("shexian.tsv", "歙县岩寺YB_21J03.tsv", "ife", "dial:Hui-Shexian", "Shexian"),
]

# initial-aspiration digraphs → IPA; zero-initial markers → ""
_ASP = {"th": "tʰ", "ph": "pʰ", "kh": "kʰ", "tsh": "tsʰ", "tʃh": "tʃʰ",
        "tɕh": "tɕʰ", "tʂh": "tʂʰ", "ch": "tɕʰ"}
_ZERO = {"∅", "0", "Ø", "ø", "", "-"}
_CHAO = {"1": "˩", "2": "˨", "3": "˧", "4": "˦", "5": "˥"}


def download(*, force: bool = False) -> None:
    """Fetch the needed TSVs into the cache (small; skips existing unless force)."""
    import requests
    MCPDICT_DIR.mkdir(parents=True, exist_ok=True)
    for cache_name, upstream, *_ in _POINTS:
        dest = MCPDICT_DIR / cache_name
        if dest.exists() and not force:
            continue
        url = _RAW_BASE + urllib.parse.quote(upstream)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        dest.write_text(r.text, encoding="utf-8")


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t"))


def _parse_ipa(rows):
    out = []
    for r in rows[1:]:
        if len(r) >= 2 and is_single_han(r[0].strip()) and r[1].strip():
            out.append((r[0].strip(), r[1].strip()))
    return out


def _parse_ife(rows):
    out = []
    for r in rows[1:]:
        if len(r) < 5 or not is_single_han(r[1].strip()):
            continue
        ini, fin, tone = r[2].strip(), r[3].strip(), r[4].strip()
        ini = _ASP.get(ini, ini)
        if ini in _ZERO:
            ini = ""
        chao = "".join(_CHAO.get(c, "") for c in tone)
        ipa = (ini + fin + chao).strip()
        if ipa:
            out.append((r[1].strip(), ipa))
    return out


def load() -> list[dict]:
    """Return Haikou + Shexian records from the cached TSVs (``[]`` if absent)."""
    records: list[dict] = []
    for cache_name, _upstream, fmt, column, locality in _POINTS:
        path = MCPDICT_DIR / cache_name
        if not path.exists():
            continue
        rows = _rows(path)
        pairs = _parse_ipa(rows) if fmt == "ipa" else _parse_ife(rows)
        seen: set[tuple[str, str]] = set()
        for char, reading in pairs:
            if (char, reading) in seen:
                continue
            seen.add((char, reading))
            records.append(record(char, column, reading, SRC_MCPDICT, locality=locality))
    return records


if __name__ == "__main__":
    download()
    recs = load()
    from collections import Counter
    by_col = Counter(r["column"] for r in recs)
    print(f"[mcpdict] {len(recs):,} records: {dict(by_col)}")
    print("  sample:", [(r["char"], r["reading"]) for r in recs[:4]])
