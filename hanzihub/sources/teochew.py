"""Loader for the Teochew Excel (``潮州話.xlsx``).

First two columns are Character(s) and Pronunciation. Refactor of
``load_teochew_from_excel`` from ``漢字音庫.py`` (first reading wins per char).
"""
from __future__ import annotations

import pandas as pd

from . import record, is_single_han
from ..paths import TEOCHEW_XLSX
from ..schema import SRC_TEOCHEW


def load(path=TEOCHEW_XLSX) -> list[dict]:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    char_col, pron_col = df.columns[:2]
    seen: set[str] = set()
    records: list[dict] = []
    for _, row in df.iterrows():
        chars = str(row[char_col]).strip()
        pron = str(row[pron_col]).strip()
        if chars.lower() == "nan" or pron.lower() == "nan" or not pron:
            continue
        for ch in chars:
            if is_single_han(ch) and ch not in seen:
                seen.add(ch)
                records.append(record(ch, "Teochew", pron, SRC_TEOCHEW))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"Teochew: {len(recs):,} records")
    for r in recs[:8]:
        print("  ", r["char"], "=", r["reading"])
