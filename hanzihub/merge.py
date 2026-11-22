"""Merge all source loaders into the canonical long table and derive the wide CSV.

* **Long table** (``readings_long.parquet``): one row per
  ``(char, column, reading, source)`` — the fully-provenanced source of truth.
* **Wide table** (``combined_readings.csv``): app-facing superset of the legacy
  columns, with branch columns gap-filled from representative localities and a
  full ``dial:<branch>-<locality>`` layer appended.
"""
from __future__ import annotations

import re
import unicodedata
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
    recs += mcpdict.load()      # 漢字音典 locality tables + Sino-Xenic + 廣韻
    recs += okinawan.load()     # Okinawan (Ryukyuan) kanji readings
    if use_wiktionary:
        recs += wiktionary_dialpron.load(refresh=refresh_wiktionary,
                                         limit=limit_wiktionary)
    harmonize_fallback_tones(recs)
    return apply_fallbacks(recs)


_CHAO_TAIL = re.compile(r"[˥˦˧˨˩]+$")
HARMONIZE_MIN_N = 8        # shared chars needed per tone class
HARMONIZE_MIN_SHARE = 0.6  # majority needed before the contour is adopted


def harmonize_fallback_tones(recs: list[dict], *, verbose: bool = False) -> dict:
    """Render gap-fill readings' tones in the column's own convention.

    A gap-fill table (MCPDict) and the column's primary source (kaikki /
    Wiktionary) can describe the same tone CATEGORY with different citation
    values (Changsha 陰平 ˧˧ vs ˧˧˦, Fuzhou 上聲 ˧˧ vs ˧˩). The category is
    reliable, so per (column, tone class) we look at the characters both
    sources share and, if the primary source clearly agrees on one contour for
    that class (≥ ``HARMONIZE_MIN_N`` chars, ≥ ``HARMONIZE_MIN_SHARE``), the
    gap-fill readings of that class take it — the column then reads
    consistently. Classes without clear evidence keep MCPDict's own value.
    Mutates ``recs`` in place; returns ``{column: {class: contour}}``."""
    from collections import Counter

    primary_tones: dict[tuple[str, str], set[str]] = defaultdict(set)
    fb_classes: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in recs:
        key = (r["column"], r["char"])
        if r.get("fallback"):
            if r.get("tone_class") is not None:
                fb_classes[key].add(r["tone_class"])
        elif r["column"].startswith("dial:"):
            for part in re.split(r"[/|]", normalize_reading(r["reading"], r["column"])):
                m = _CHAO_TAIL.search(part.strip())
                if m:
                    primary_tones[key].add(m.group(0))

    votes: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for key, classes in fb_classes.items():
        pt = primary_tones.get(key)
        if pt and len(pt) == 1 and len(classes) == 1:   # unambiguous pairs only
            votes[key[0]][next(iter(classes))][next(iter(pt))] += 1

    mapping: dict[str, dict[str, str]] = {}
    for col, by_cls in votes.items():
        for cls, cnt in by_cls.items():
            n = sum(cnt.values())
            tone, k = cnt.most_common(1)[0]
            if n >= HARMONIZE_MIN_N and k / n >= HARMONIZE_MIN_SHARE:
                mapping.setdefault(col, {})[cls] = tone

    for r in recs:
        if not r.get("fallback") or r.get("tone_class") is None:
            continue
        tone = mapping.get(r["column"], {}).get(r["tone_class"])
        if tone:
            r["reading"] = _CHAO_TAIL.sub(tone, r["reading"])
    if verbose:
        for col, m in sorted(mapping.items()):
            print(f"[harmonize] {col}: {m}")
    return mapping


def apply_fallbacks(recs: list[dict]) -> list[dict]:
    """Drop gap-fill records (``fallback=True``) for any (char, column) that a
    primary source already covers, so a cell never mixes two transcriptions
    of the same place / reading system."""
    primary = {(r["char"], r["column"]) for r in recs if not r.get("fallback")}
    return [r for r in recs
            if not r.get("fallback") or (r["char"], r["column"]) not in primary]


# --- ingest normalisation -------------------------------------------------
# Sources write the same reading in different Unicode shapes: NFC vs NFD,
# tie bar above (t͡s) vs below (t͜s), and pitch contours as superscript
# digits (kaikki tʰi⁵³) vs Chao letters (wikihan tʰi˥˧). Normalising at ingest
# makes readings comparable, so the wide-cell dedupe actually deduplicates.
# Superscripts on the tone-CATEGORY columns are classes, not pitches — exempt.
_SUP_TO_CHAO = {"¹": "˩", "²": "˨", "³": "˧", "⁴": "˦", "⁵": "˥"}
_SUP_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
# (Definition superscripts are footnote markers, not tones — also exempt.)
_TONE_CATEGORY_COLS = {"Middle Chinese (Baxter)", "Proto-Min", "Definition"}


def _sup_run_to_chao(m: re.Match) -> str:
    run = m.group(0)
    if all(c in _SUP_TO_CHAO for c in run):
        return "".join(_SUP_TO_CHAO[c] for c in run)
    return run  # 0/6–9 present → a tone class, leave alone


def normalize_reading(reading: str, column: str) -> str:
    """Canonical Unicode + tone shape for one source reading."""
    s = unicodedata.normalize("NFC", str(reading)).strip()
    s = s.replace("͜", "͡")        # tie bar below → above
    s = re.sub(r"[ \t]+", " ", s)
    if column not in _TONE_CATEGORY_COLS:
        s = _SUP_RUN.sub(_sup_run_to_chao, s)
    return s


def long_table(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(
        records, columns=["char", "column", "reading", "source", "locality", "conf"])
    df["reading"] = [normalize_reading(r, c)
                     for r, c in zip(df["reading"].astype(str), df["column"])]
    df = df[df["reading"].str.strip().ne("")]
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
