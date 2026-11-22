"""Loader for the Unicode Unihan ``Unihan_Readings.txt`` database.

Refactor of ``load_unihan_pronunciations`` from ``漢字音庫.py``, with two fixes:
  * ``kTang`` now maps to the **Tang** column (it is Tang-dynasty pronunciation,
    not Middle Chinese — the original conflated them);
  * ``kHangul`` source-tags (``:0E`` etc.) are stripped per syllable, and
    ``kFanqie`` / ``kZhuang`` are captured.
"""
from __future__ import annotations

import re

from . import record
from ..paths import UNIHAN_TXT
from ..schema import SRC_UNIHAN

# Unihan field -> wide-CSV column
FIELDS_MAP = {
    "kDefinition": "Definition",
    "kMandarin": "Mandarin",
    "kCantonese": "Cantonese",
    "kTang": "Tang",
    "kJapanese": "Japanese",
    "kJapaneseOn": "Japanese On",
    "kJapaneseKun": "Japanese Kun",
    "kHangul": "Korean (Hangul)",
    "kKorean": "Korean (romanized)",
    "kVietnamese": "Vietnamese",
    "kFanqie": "Fanqie",
    "kZhuang": "Zhuang",
}

_CTRL_TAIL = re.compile(r"[\x00-\x1F\x7F]+$")
_HANGUL_SRC = re.compile(r":[0-9A-Za-z]+")  # strips ":0E" provenance markers


def _clean(field: str, value: str) -> str:
    value = value.strip()
    if field == "kHangul":
        value = _HANGUL_SRC.sub("", value)
    return _CTRL_TAIL.sub("", value)


def load(path=UNIHAN_TXT) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            ucode, field, value = parts
            col = FIELDS_MAP.get(field)
            if not col:
                continue
            try:
                char = chr(int(ucode[2:], 16))
            except ValueError:
                continue
            cleaned = _clean(field, value)
            if not cleaned:
                continue
            if field == "kVietnamese":
                # one record per reading, so other Hán-Việt sources dedupe
                # against each word instead of the space-joined string
                for tok in dict.fromkeys(cleaned.split()):
                    records.append(record(char, col, tok, SRC_UNIHAN))
            else:
                records.append(record(char, col, cleaned, SRC_UNIHAN))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"Unihan: {len(recs):,} records")
    for r in recs[:8]:
        print("  ", r["char"], r["column"], "=", r["reading"][:40])
