# -*- coding: utf-8 -*-
"""English sounds-like approximations + romanisation tone recovery
(hanzihub.appkit) — the green ≈ line."""
from hanzihub import appkit as ak


# ------------------------------------------------- romanisation → English --
def test_teochew_trailing_digit():
    assert ak.romanization_to_english("tiang1", "teochew") == "tyahng˧˧"


def test_wugniu_leading_digit():
    assert ak.romanization_to_english("8laq", "wugniu") == "lah˩˨"


def test_poj_diacritic_tone_recovered():
    # unmarked open POJ syllable = tone 1 (陰平 55 in the Taipei table)
    assert ak.romanization_to_english("thi", "poj") == "tee˥˥"


def test_unknown_scheme_keeps_class_digit_superscript():
    # no scheme → the class digit must NOT be dressed up as a pitch trace
    assert ak.romanization_to_english("sam3", None) == "sahm³"


def test_poj_checked_final_unmarked_is_tone4():
    out = ak.romanization_to_english("sit", "poj")
    assert out.endswith("˧˨")  # POJ tone 4 → 32 checked


# -------------------------------------------------- diacritic tone tables --
def test_diacritic_tone_poj():
    assert ak._diacritic_tone("lím", "poj") == "2"
    assert ak._diacritic_tone("lâm", "poj") == "5"
    assert ak._diacritic_tone("sim", "poj") == "1"   # unmarked, open
    assert ak._diacritic_tone("sit", "poj") == "4"   # unmarked, checked


def test_diacritic_tone_buc_checked_shift():
    # acute = 上去(3), but with a stop final it means 上入(4)
    assert ak._diacritic_tone("áik", "buc") == "4"


# --------------------------------------------------------- IPA → English --
def test_ipa_to_english_keeps_chao_letters():
    assert ak.ipa_to_english("tʰieŋ˥˥") == "tyehng˥˥"
    assert ak.ipa_to_english("tʰĩ˥") == "teeⁿ˥"


def test_ipa_to_english_never_leaks_cjk():
    out = ak.ipa_to_english("tʰien (陰平˦˦)")
    assert "陰" not in out and "平" not in out


def test_ipa_to_english_one_syllable_per_syllable():
    # vowel-run folding: a diphthong must not become two syllables
    assert ak.ipa_to_english("kʰau") == "kow"


# ----------------------------------------------------- Baxter–Sagart gloss --
def test_baxter_sagart_markup_stripped():
    assert ak.baxter_sagart_approx("*[k]ʷʰˤret-s") == "khwret-s"
    assert ak.baxter_sagart_approx("") == ""


# ---------------------------------------------------------- approx_html ----
def test_approx_html_ipa_column():
    out = ak.approx_html("Hokkien", "tʰĩ˥/tʰi̯ɛn˥")
    assert out.startswith("<span") and "≈" in out and "˥" in out


def test_approx_html_proto_min_keeps_category():
    out = ak.approx_html("Proto-Min", "*tʰin¹")
    assert "¹" in out and "˩" not in out


def test_approx_html_non_phonetic_column_empty():
    assert ak.approx_html("Definition", "sky, heaven") == ""
