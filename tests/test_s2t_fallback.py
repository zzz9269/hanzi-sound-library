# -*- coding: utf-8 -*-
"""Simplified→traditional fallback (hanzihub.appkit) — the dataset is keyed by
traditional characters, so simplified input must fall back to the traditional
form's readings instead of a starved row."""
from hanzihub import appkit as ak

# minimal synthetic dataset: 葉 (trad of 叶) is rich, 叶 itself is sparse,
# 柔 has no variant pair, 発 has no traditional entry at all.
DATA = {
    "叶": {"Mandarin": "xié", "Hokkien": ""},
    "葉": {"Mandarin": "yè", "Hokkien": "ia̍p", "Wu": "jiq"},
    "柔": {"Mandarin": "róu", "Hokkien": "jiû"},
}


# ------------------------------------------------------------- s2t_text ----
def test_s2t_text_phrase_aware():
    # STPhrases must disambiguate one-to-many chars by context
    assert ak.s2t_text("头发") == "頭髮"
    assert ak.s2t_text("干燥") == "乾燥"
    assert ak.s2t_text("叶淑柔") == "葉淑柔"


def test_s2t_text_traditional_passthrough():
    assert ak.s2t_text("葉淑柔") == "葉淑柔"
    assert ak.s2t_text("") == ""


# ------------------------------------------------------- per_char_tokens ---
def test_per_char_tokens_fallback_fills_gap():
    toks = ak.per_char_tokens(DATA, "Hokkien", "叶柔", "葉柔")
    assert toks == [("叶", "ia̍p"), ("柔", "jiû")]


def test_per_char_tokens_own_reading_wins():
    # 叶 has its own Mandarin cell — must NOT be overridden by 葉's
    toks = ak.per_char_tokens(DATA, "Mandarin", "叶", "葉")
    assert toks == [("叶", "xié")]


def test_per_char_tokens_none_when_both_empty():
    toks = ak.per_char_tokens(DATA, "Wu", "叶柔", "葉柔")
    assert toks == [("叶", "jiq"), ("柔", None)]


def test_per_char_tokens_misaligned_alt_ignored():
    toks = ak.per_char_tokens(DATA, "Hokkien", "叶柔", "葉")
    assert toks == [("叶", None), ("柔", "jiû")]


# ------------------------------------------------------- concat_per_char ---
def test_concat_per_char_with_alt():
    assert ak.concat_per_char(DATA, "Hokkien", "叶柔", "葉柔") == "ia̍p jiû"


def test_concat_per_char_without_alt_keeps_raw_char():
    assert ak.concat_per_char(DATA, "Hokkien", "叶柔") == "叶 jiû"


# ---------------------------------------------------- with_trad_fallback ---
def test_with_trad_fallback_backfills_empty_columns():
    bucket, trad = ak.with_trad_fallback(DATA, "叶")
    assert trad == "葉"
    assert bucket["Mandarin"] == "xié"      # own reading kept
    assert bucket["Hokkien"] == "ia̍p"       # empty cell backfilled
    assert bucket["Wu"] == "jiq"            # absent column backfilled


def test_with_trad_fallback_noop_for_traditional():
    bucket, trad = ak.with_trad_fallback(DATA, "柔")
    assert trad is None
    assert bucket == DATA["柔"]


def test_with_trad_fallback_unknown_char():
    bucket, trad = ak.with_trad_fallback(DATA, "発")
    assert bucket == {} and trad is None
