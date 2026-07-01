# -*- coding: utf-8 -*-
"""Unified Chao tone-letter display (hanzihub.appkit) — every notation the data
carries must convert (or deliberately NOT convert) exactly as documented in
Guides/tone_contour_guide.md."""
from hanzihub import appkit as ak


# ------------------------------------------------------------ contour core --
def test_contour_to_chao_valid():
    assert ak.contour_to_chao("55") == "˥˥"
    assert ak.contour_to_chao("213") == "˨˩˧"
    assert ak.contour_to_chao("5") == "˥"


def test_contour_to_chao_rejects_class_digits():
    # 0 / 6–9 are tone classes, not pitch levels — must refuse
    assert ak.contour_to_chao("6") == ""
    assert ak.contour_to_chao("90") == ""
    assert ak.contour_to_chao("") == ""


# ------------------------------------------------- IPA contour conversions --
def test_superscript_contours_convert():
    assert ak.tones_to_chao("tʰieŋ⁵⁵", "Eastern Min (Fuzhou)") == "tʰieŋ˥˥"
    assert ak.tones_to_chao("tʰin²¹³", "dial:Cantonese-Dongguan") == "tʰin˨˩˧"
    assert ak.tones_to_chao("tʰiẽ³²⁴ | tʰiẽ̞³³⁴", "dial:Wu-Hangzhou") == \
        "tʰiẽ˧˨˦ | tʰiẽ̞˧˧˦"


def test_ascii_contours_convert_only_in_ipa_context():
    # Hakka parenthetical tone note is IPA context → converts
    assert ak.tones_to_chao("tʰi̯en˨˦ | tʰien (陰平44)", "Hakka") == \
        "tʰi̯en˨˦ | tʰien (陰平˦˦)"
    # a bare romanisation with an unknown column keeps its digit
    assert ak.tones_to_chao("tiang1", None) == "tiang1"


def test_existing_chao_letters_untouched():
    assert ak.tones_to_chao("tʰĩ˥/tʰi̯ɛn˥", "Hokkien") == "tʰĩ˥/tʰi̯ɛn˥"
    assert ak.tones_to_chao("tiān | tʰi̯ɛn˥", "Mandarin") == "tiān | tʰi̯ɛn˥"


# ------------------------------------------------ tone-class digit schemes --
def test_jyutping_class_to_contour():
    assert ak.tones_to_chao("tin1 | tʰiːn˥", "Cantonese") == "tin˥˥ | tʰiːn˥"
    assert ak.tones_to_chao("sam3", "Cantonese") == "sam˧˧"


def test_teochew_class_to_contour():
    assert ak.tones_to_chao("tiang1", "Teochew") == "tiang˧˧"


def test_haikou_mcpdict_categories():
    assert ak.tones_to_chao("hi1 | hin1", "Hainanese (Haikou)") == "hi˨˦ | hin˨˦"
    # 9 = MCPDict 長入 (long entering) → 55
    assert ak.tones_to_chao("ke9", "dial:Min-Haikou") == "ke˥˥"
    # ML tag must survive
    assert ak.tones_to_chao("hin1[ML]", "dial:Min-Haikou") == "hin˨˦[ML]"


# --------------------------------------- category superscripts stay digits --
def test_proto_min_category_exempt():
    assert ak.tones_to_chao("*tʰin¹", "Proto-Min") == "*tʰin¹"


def test_baxter_mc_category_exempt():
    assert ak.tones_to_chao("tʰen¹", "Middle Chinese (Baxter)") == "tʰen¹"


# --------------------------------------------------- live-Wiktionary chips --
def test_wugniu_leading_digit_moves_to_end():
    assert ak.wikt_rom_to_chao("8laq / 1la", "wugniu") == "laq˩˨ / la˥˧"


def test_trailing_digit_schemes():
    assert ak.wikt_rom_to_chao("tiang1", "teochew") == "tiang˧˧"


def test_diacritic_schemes_pass_through():
    assert ak.wikt_rom_to_chao("thiⁿ / thian", "poj") == "thiⁿ / thian"


def test_no_scheme_pass_through():
    assert ak.wikt_rom_to_chao("tin1", None) == "tin1"


# ------------------------------------------------------------- HTML layer --
def test_chao_html_wraps_and_escapes():
    out = ak.chao_html("a<b˧˥")
    assert "&lt;" in out                      # escaped
    assert "˧˥" in out and "font-family" in out  # wrapped run


def test_render_readings_html_converts_and_tags_ml():
    out = ak.render_readings_html("tin1 | tʰiːn˥", "Cantonese")
    assert "tin" in out and "˥˥" in out
    out_ml = ak.render_readings_html("hin1[ML]", "dial:Min-Haikou")
    assert "˨˦" in out_ml and "ML" in out_ml


def test_has_ipa():
    assert ak.has_ipa("tʰĩ˥")
    assert not ak.has_ipa("tiang1")
    assert not ak.has_ipa("")
