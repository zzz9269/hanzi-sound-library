"""Loader for ``wikihan-ipa.tsv`` (Wiktionary-derived IPA per branch).

Columns: Character, Middle Chinese (Baxter and Sagart 2014), Cantonese, Gan,
Hakka, Jin, Mandarin, Hokkien, Wu, Xiang. A character cell may be a literal
Han char or a ``U+XXXX`` code point.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from . import record, is_single_han
from ..paths import WIKIHAN_TSV
from ..schema import SRC_WIKIHAN

# tsv column -> wide-CSV column
COLMAP = {
    "Cantonese": "Cantonese",
    "Gan": "Gan",
    "Hakka": "Hakka",
    "Jin": "Jin",
    "Mandarin": "Mandarin",
    "Hokkien": "Hokkien",
    "Wu": "Wu",
    "Xiang": "Xiang",
    "Middle Chinese (Baxter and Sagart 2014)": "Middle Chinese (Baxter)",
}

_HEX = re.compile(r"([0-9A-Fa-f]{4,6})")
_EMPTY = {"", "-", "—", "–", "nan"}


def _norm_char(val: str):
    s = unicodedata.normalize("NFC", str(val or "")).strip()
    if is_single_han(s):
        return s
    m = _HEX.search(s.upper())
    if m:
        try:
            c = chr(int(m.group(1), 16))
            return c if is_single_han(c) else None
        except ValueError:
            return None
    return None


def load(path=WIKIHAN_TSV) -> list[dict]:
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    char_col = df.columns[0]
    records: list[dict] = []
    for _, row in df.iterrows():
        ch = _norm_char(row[char_col])
        if not ch:
            continue
        for src_col, dst_col in COLMAP.items():
            if src_col not in df.columns:
                continue
            val = str(row[src_col]).strip()
            if val.lower() in _EMPTY:
                continue
            records.append(record(ch, dst_col, val, SRC_WIKIHAN))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"wikihan: {len(recs):,} records")
    for r in recs[:8]:
        print("  ", r["char"], r["column"], "=", r["reading"])
