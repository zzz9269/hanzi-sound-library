"""Loader for nk2028 qieyun-data — the 廣韻 (Guangyun) rime dictionary.

Source: ``韻書/廣韻.csv`` (nk2028/qieyun-data, GitHub). One row per character
entry with columns including ``音韻地位`` (phonological position descriptor,
e.g. ``端一東平``), ``反切`` (fanqie, e.g. ``德紅``) and ``字頭`` (the character).

We emit two honest, fully-sourced columns (no fabricated IPA reconstruction):
  * ``Fanqie``                  — 反切 spelling (big coverage boost over Unihan)
  * ``Middle Chinese (position)`` — the Qieyun rime-table position descriptor
"""
from __future__ import annotations

from . import record, is_single_han
from .._http import fetch_text
from ..paths import QIEYUN_CACHE
from ..schema import SRC_QIEYUN

import csv
import io

URL = ("https://raw.githubusercontent.com/nk2028/qieyun-data/main/"
       "%E9%9F%BB%E6%9B%B8/%E5%BB%A3%E9%9F%BB.csv")  # 韻書/廣韻.csv


def load(*, force: bool = False) -> list[dict]:
    text = fetch_text(URL, QIEYUN_CACHE / "廣韻.csv", force=force)
    reader = csv.DictReader(io.StringIO(text))
    fanqie_seen: set[tuple[str, str]] = set()
    pos_seen: set[tuple[str, str]] = set()
    records: list[dict] = []
    for row in reader:
        ch = (row.get("字頭") or "").strip()
        if not is_single_han(ch):
            continue
        fanqie = (row.get("反切") or "").strip()
        position = (row.get("音韻地位") or "").strip()
        if fanqie and (ch, fanqie) not in fanqie_seen:
            fanqie_seen.add((ch, fanqie))
            records.append(record(ch, "Fanqie", fanqie, SRC_QIEYUN))
        if position and (ch, position) not in pos_seen:
            pos_seen.add((ch, position))
            records.append(
                record(ch, "Middle Chinese (position)", position, SRC_QIEYUN))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"qieyun 廣韻: {len(recs):,} records")
    for r in recs[:10]:
        print("  ", r["char"], r["column"], "=", r["reading"])
