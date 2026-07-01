"""Merge all source loaders into the canonical long table and derive the wide CSV.

* **Long table** (``readings_long.parquet``): one row per
  ``(char, column, reading, source)`` — the fully-provenanced source of truth.
* **Wide table** (``combined_readings.csv``): app-facing superset of the legacy
  columns, with branch columns gap-filled from representative localities and a
  full ``dial:<branch>-<locality>`` layer appended.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from . import schema
from .schema import (BRANCH_REPRESENTATIVE, LOCALITIES, PREFERRED_ORDER,
                     SRC_ML, locality_col)
from .sources import (baxter_sagart, hakka, kaikki, mcpdict, okinawan, qieyun_mc,
                      teochew, unihan, wikihan, wiktionary_dialpron, ytenx_oc)

# Order in which a reading's source determines its position within a wide cell.
SOURCE_PRIORITY = {
    schema.SRC_UNIHAN: 0,
    schema.SRC_BAXTER: 1,
    schema.SRC_YTENX: 2,
    schema.SRC_QIEYUN: 3,
    schema.SRC_WIKIHAN: 4,
    schema.SRC_HAKKA: 5,
    schema.SRC_TEOCHEW: 6,
    schema.SRC_WIKTIONARY: 7,
    schema.SRC_KAIKKI: 8,
    schema.SRC_MCPDICT: 9,
    schema.SRC_RECON: 10,  # comparative reconstruction (Proto-Min)
    SRC_ML: 99,            # predictions always sort last
}


def collect_records(*, use_wiktionary: bool = True,
                     refresh_wiktionary: bool = False,
                     limit_wiktionary: int | None = None) -> list[dict]:
    """Load and concatenate records from every source."""
    recs: list[dict] = []
    recs += unihan.load()
    recs += baxter_sagart.load()
    recs += wikihan.load()
    recs += hakka.load()
    recs += teochew.load()
    recs += ytenx_oc.load()
    recs += qieyun_mc.load()
    recs += kaikki.load()       # locality IPA (no-op until the cache is built)
    recs += mcpdict.load()      # Haikou (Hainanese) + Shexian (Hui)
    recs += okinawan.load()     # Okinawan (Ryukyuan) kanji readings
    if use_wiktionary:
        recs += wiktionary_dialpron.load(refresh=refresh_wiktionary,
                                         limit=limit_wiktionary)
    return recs


def long_table(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(
        records, columns=["char", "column", "reading", "source", "locality", "conf"])
    df = df[df["reading"].astype(str).str.strip().ne("")]
    df = df.drop_duplicates(subset=["char", "column", "reading", "source"])
    return df.reset_index(drop=True)


def _render_cell(reading_sources: dict[str, set[str]]) -> str:
    """Render distinct readings for one cell, ``[ML]``-tagging ML-only readings."""
    items = sorted(
        reading_sources.items(),
        key=lambda kv: (min(SOURCE_PRIORITY.get(s, 50) for s in kv[1]), kv[0]),
    )
    parts = []
    for reading, sources in items:
        if sources == {SRC_ML}:
            parts.append(f"{reading}[ML]")
        else:
            parts.append(reading)
    return " | ".join(parts)


def wide_table(long_df: pd.DataFrame) -> pd.DataFrame:
    # char -> column -> {reading: set(sources)}
    cells: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set)))
    for char, column, reading, source in long_df[
            ["char", "column", "reading", "source"]].itertuples(index=False):
        cells[char][column][reading].add(source)

    # Render every (char, column) cell
    rows: dict[str, dict[str, str]] = {}
    all_cols: set[str] = set()
    for char, colmap in cells.items():
        row: dict[str, str] = {}
        for column, rs in colmap.items():
            row[column] = _render_cell(rs)
            all_cols.add(column)
        rows[char] = row

    # Gap-fill branch columns from their representative locality (empties only)
    for char, row in rows.items():
        for branch_col, loc_idx in BRANCH_REPRESENTATIVE.items():
            if row.get(branch_col):
                continue
            loc_col = locality_col(LOCALITIES[loc_idx])
            val = row.get(loc_col)
            if val:
                row[branch_col] = val
                all_cols.add(branch_col)

    df = pd.DataFrame.from_dict(rows, orient="index").fillna("")
    df.index.name = "char"
    df = df.reset_index()
    return df[_ordered_columns(df.columns)]


def _ordered_columns(cols) -> list[str]:
    cols = list(cols)
    dial_cols = [c for c in cols if c.startswith("dial:")]
    # dial: columns: canonical 39 first (in locality order), then the rest
    # (extra kaikki points beyond the 39) grouped by branch, alphabetically.
    dial_order = [locality_col(loc) for loc in LOCALITIES]
    dial_sorted = [c for c in dial_order if c in dial_cols]
    dial_extra = sorted(c for c in dial_cols if c not in dial_sorted)
    non_dial = [c for c in cols if c != "char" and not c.startswith("dial:")]
    preferred = [c for c in PREFERRED_ORDER if c in non_dial]
    rest = sorted(c for c in non_dial if c not in PREFERRED_ORDER)
    return ["char"] + preferred + rest + dial_sorted + dial_extra


def build(*, use_wiktionary: bool = True, refresh_wiktionary: bool = False,
          limit_wiktionary: int | None = None,
          verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    recs = collect_records(use_wiktionary=use_wiktionary,
                           refresh_wiktionary=refresh_wiktionary,
                           limit_wiktionary=limit_wiktionary)
    long_df = long_table(recs)
    wide_df = wide_table(long_df)
    if verbose:
        print(f"[merge] long: {len(long_df):,} rows | "
              f"wide: {wide_df.shape[0]:,} chars × {wide_df.shape[1]} cols")
    return long_df, wide_df
