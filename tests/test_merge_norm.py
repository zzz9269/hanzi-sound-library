# -*- coding: utf-8 -*-
"""Ingest normalisation (hanzihub.merge.normalize_reading)."""
from hanzihub import merge


def test_superscript_contour_to_chao():
    assert merge.normalize_reading("tʰi⁵³", "dial:Wu-Shanghai") == "tʰi˥˧"
    assert merge.normalize_reading("tʰieŋ⁵⁵", "Eastern Min (Fuzhou)") == "tʰieŋ˥˥"


def test_category_columns_exempt():
    assert merge.normalize_reading("tʰen¹", "Middle Chinese (Baxter)") == "tʰen¹"
    assert merge.normalize_reading("*tʰin¹", "Proto-Min") == "*tʰin¹"


def test_class_digit_superscripts_left_alone():
    # a run containing 6-9 is a class label, not a contour
    assert merge.normalize_reading("a⁶", "Wu") == "a⁶"


def test_tie_bar_and_whitespace_unified():
    assert merge.normalize_reading("t͜sʰuan¹", "Hokkien") == "t͡sʰuan˩"
    assert merge.normalize_reading("  a   b ", "Wu") == "a b"


def test_long_table_dedupes_across_notations():
    recs = [
        {"char": "天", "column": "Wu", "reading": "tʰi⁵³", "source": "kaikki",
         "locality": "", "conf": None},
        {"char": "天", "column": "Wu", "reading": "tʰi˥˧", "source": "kaikki",
         "locality": "", "conf": None},
    ]
    df = merge.long_table(recs)
    assert len(df) == 1 and df.iloc[0]["reading"] == "tʰi˥˧"
