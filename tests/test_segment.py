# -*- coding: utf-8 -*-
"""Segmentation + MC-descriptor parsing (hanzihub.segment) — the slot logic the
ML imputer and the Proto-Min reconstruction both build on."""
from hanzihub import segment


# ---------------------------------------------------------------- MC parse --
def test_parse_mc_simple():
    assert segment.parse_mc_position("端一東平") == {
        "initial": "端", "openness": "", "division": "一",
        "cls": "", "rime": "東", "tone": "平"}


def test_parse_mc_full():
    assert segment.parse_mc_position("云合三B支平") == {
        "initial": "云", "openness": "合", "division": "三",
        "cls": "B", "rime": "支", "tone": "平"}


def test_parse_mc_open_division4():
    p = segment.parse_mc_position("透開四先平")
    assert p["initial"] == "透" and p["openness"] == "開"
    assert p["division"] == "四" and p["rime"] == "先" and p["tone"] == "平"


def test_parse_mc_rejects_garbage():
    assert segment.parse_mc_position("") is None
    assert segment.parse_mc_position(None) is None
    assert segment.parse_mc_position("abc") is None


# ---------------------------------------------------------- split_syllable --
def test_split_digit_tone_romanisation():
    assert segment.split_syllable("jau1") == ("j", "au", "1")
    assert segment.split_syllable("a1") == ("", "a", "1")
    assert segment.split_syllable("tiang1") == ("t", "iang", "1")


def test_split_chao_tone_letters():
    assert segment.split_syllable("kʰi̯ɛn˥˩") == ("kʰ", "i̯ɛn", "˥˩")


def test_split_superscript_tone():
    assert segment.split_syllable("tʰieŋ⁵⁵") == ("tʰ", "ieŋ", "⁵⁵")


def test_split_toneless():
    assert segment.split_syllable("then") == ("th", "en", "")


def test_split_syllabic_nasal():
    # Hokkien pŋ̩ — no vowel, nasal is the nucleus, p stays the onset
    onset, rhyme, tone = segment.split_syllable("pŋ̩˥")
    assert onset == "p" and rhyme.startswith("ŋ") and tone == "˥"
    onset, rhyme, _ = segment.split_syllable("ŋ̩")
    assert onset == "" and rhyme.startswith("ŋ")


def test_split_blank():
    assert segment.split_syllable("") is None
    assert segment.split_syllable(None) is None
    assert segment.split_syllable("   ") is None


# ------------------------------------------------------- nucleus / folding --
def test_nucleus_drops_coda_and_marks():
    assert segment.nucleus("iaŋ") == "ia"
    assert segment.nucleus("i̯ɔ̃k") == "iɔ"
    assert segment.nucleus("i̯ɔ̃k", fold=True) == "io"


def test_fold_vowels():
    assert segment.fold_vowels("ɔ") == "o"
    assert segment.fold_vowels("ɯ") == "u"
    assert segment.fold_vowels("ɛ") == "e"
    assert segment.fold_vowels("k") == "k"  # non-vowels pass through


# -------------------------------------------------------------- iter cells --
def test_iter_readings_splits_variants_and_strips_ml():
    cell = "be˥˩/bɛ˥˩ | siang1[ML]"
    assert list(segment.iter_readings(cell)) == ["be˥˩", "bɛ˥˩", "siang1"]


def test_iter_readings_empty():
    assert list(segment.iter_readings("")) == []
    assert list(segment.iter_readings(None)) == []
