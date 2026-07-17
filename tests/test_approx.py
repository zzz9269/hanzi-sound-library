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


def test_ipa_to_english_coda_labial_reordered():
    # syllable-final /Cʷ/ is the rime's off-glide: read "ghawk" not "ghakw"
    # (學 = haewk = ɣæwk). ONSET /kʷa/ keeps its real "kw-".
    assert ak.ipa_to_english("ɣækʷ⁴") == "ghawk⁴"
    assert ak.ipa_to_english("ɣækʷ") == "ghawk"
    assert ak.ipa_to_english("kʷɑ") == "kwah"      # onset untouched


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


# ------------------------------------------------------- sandhi hints ------
def test_sandhi_hint_poj_tone_circle():
    out = ak.sandhi_hint_html("thiⁿ / thian", "poj")
    assert "˥˥" in out and "˧˧" in out       # citation 55 → sandhi 33 (1→7)


def test_sandhi_hint_teochew():
    assert "˧˦" in ak.sandhi_hint_html("tiang1", "teochew")


def test_sandhi_hint_inapplicable():
    assert ak.sandhi_hint_html("tin1", None) == ""
    assert ak.sandhi_hint_html("", "poj") == ""


# ------------------------------------------------- MC division medials -----
def test_mc_division_medials():
    assert ak.mc_readable_syllable("見三東平") == "kyung"   # 三等 -j-
    assert ak.mc_readable_syllable("心開四先平") == "sien"  # 四等 -i-
    assert ak.mc_readable_syllable("心合一寒平") == "swan"  # 一等 unchanged
