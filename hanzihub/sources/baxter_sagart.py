"""Loader for the Baxter–Sagart 2014 Old/Middle Chinese reconstruction Excel.

Columns of interest: ``zi`` (char), ``OC`` (Old Chinese, e.g. ``*qˤə``),
``MC`` (Middle Chinese, Baxter transcription, e.g. ``'oj``).
"""
from __future__ import annotations

import unicodedata

import pandas as pd

from . import record, is_single_han
from ..paths import BAXTER_SAGART_XLSX
from ..schema import SRC_BAXTER


def load(path=BAXTER_SAGART_XLSX) -> list[dict]:
    df = pd.read_excel(path, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    records: list[dict] = []
    for _, row in df.iterrows():
        ch = row.get("zi")
        if not isinstance(ch, str):
            continue
        ch = unicodedata.normalize("NFC", ch).strip()
        if not is_single_han(ch):
            continue
        oc = row.get("OC")
        mc = row.get("MC")
        if isinstance(oc, str) and oc.strip():
            records.append(record(ch, "Old Chinese", oc, SRC_BAXTER))
        if isinstance(mc, str) and mc.strip():
            # Baxter–Sagart's curated MC transcription is the primary "Middle
            # Chinese" column (legacy app compatibility). qieyun supplies the
            # alternative position-derived reconstruction columns.
            records.append(record(ch, "Middle Chinese", mc, SRC_BAXTER))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"Baxter-Sagart: {len(recs):,} records")
    for r in recs[:8]:
        print("  ", r["char"], r["column"], "=", r["reading"])
