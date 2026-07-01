"""Loader for ytenx (韻典網) Zhengzhang Shangfang Old Chinese reconstructions.

Source file: ``ytenx/sync/dciangx/DrienghTriang.txt`` (BYVoid/ytenx, GitHub).
Space-delimited with empty fields preserved (so split on a single space keeps
column alignment). Header:

    字 廣韻聲 廣韻韻 聲調 等 重紐 開合 上字 下字 聲符 韻部 韻部細分 擬音 擬音2 ...

We take column 0 (字) and column 12 (擬音 = Zhengzhang OC IPA, e.g. ``qɯːds``).
A character may have several lines (multiple readings); all distinct ones kept.
"""
from __future__ import annotations

from . import record, is_single_han
from .._http import fetch_text
from ..paths import YTENX_CACHE
from ..schema import SRC_YTENX

URL = ("https://raw.githubusercontent.com/BYVoid/ytenx/master/"
       "ytenx/sync/dciangx/DrienghTriang.txt")

_OC_IDX = 12


def load(*, force: bool = False) -> list[dict]:
    text = fetch_text(URL, YTENX_CACHE / "DrienghTriang.txt", force=force)
    seen: set[tuple[str, str]] = set()
    records: list[dict] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split(" ")
        if len(cols) <= _OC_IDX:
            continue
        ch = cols[0].strip()
        oc = cols[_OC_IDX].strip()
        if not is_single_han(ch) or not oc:
            continue
        key = (ch, oc)
        if key in seen:
            continue
        seen.add(key)
        records.append(record(ch, "Old Chinese (Zhengzhang)", oc, SRC_YTENX))
    return records


if __name__ == "__main__":
    recs = load()
    print(f"ytenx OC (Zhengzhang): {len(recs):,} records")
    for r in recs[:8]:
        print("  ", r["char"], "=", r["reading"])
