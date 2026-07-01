"""Loader for the Hakka Excel (``客家話.xlsx``).

Columns: Phonetic, Tone, Characters (a run of Han chars sharing the reading).
Each character maps to ``"<phonetic> (<tone>)"``. Refactor of
``load_hakka_from_excel`` from ``漢字音庫.py`` (first reading wins per char).
"""
from __future__ import annotations

import re

import pandas as pd

from . import record, is_single_han
from ..paths import HAKKA_XLSX
from ..schema import SRC_HAKKA


def load(path=HAKKA_XLSX) -> list[dict]:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    seen: set[str] = set()
    records: list[dict] = []
    for _, row in df.iterrows():
        phon = str(row.get("Phonetic", "")).strip()
        tone = str(row.get("Tone", "")).strip()
        chars = str(row.get("Characters", "")).strip()
        if not chars or chars.lower() == "nan":
            continue
        reading = f"{phon} ({tone})".strip()
        for part in re.split(r"[,\s;|]+", chars):
            for ch in part:
                if is_single_han(ch) and ch not in seen:
                    seen.add(ch)
                    records.append(record(ch, "Hakka", reading, SRC_HAKKA))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"Hakka: {len(recs):,} records")
    for r in recs[:8]:
        print("  ", r["char"], "=", r["reading"])
