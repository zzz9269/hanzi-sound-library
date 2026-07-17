# -*- coding: utf-8 -*-
"""Phrase-level Min tone sandhi (hanzihub.appkit) — the ↳ spoken: line.

Within a tone group every non-final syllable takes its sandhi tone and only
the group-final syllable keeps citation; non-Hanzi input characters split
groups. Hokkien local readings are IPA (tone = Chao contour + coda),
Teochew readings are Peng'im (tone = trailing class digit).
"""
from hanzihub import appkit as ak


# ------------------------------------------ Hokkien IPA contour → class --
def test_hokkien_class_open_syllables():
    assert ak._hokkien_ipa_class("ki", "˥") == "1"        # 陰平 55
    assert ak._hokkien_ipa_class("ŋ̩", "˥˩") == "2"        # 陰上 51
    assert ak._hokkien_ipa_class("sĩ", "˧˩") == "3"        # 陰去 31/21
    assert ak._hokkien_ipa_class("lam", "˨˦") == "5"       # 陽平 24
    assert ak._hokkien_ipa_class("tʰe", "˧") == "7"        # 陽去 33 (TW)
    assert ak._hokkien_ipa_class("ha", "˨") == "7"         # 陽去 22 (Amoy)


def test_hokkien_class_checked_split_by_pitch():
    assert ak._hokkien_ipa_class("t͡sʰat", "˧") == "4"     # 陰入, low
    assert ak._hokkien_ipa_class("t͡ɕit", "˥") == "8"      # 陽入, high
    assert ak._hokkien_ipa_class("baʔ", "˧") == "4"        # glottal coda too


# ---------------------------------------- coda-sensitive checked sandhi --
def test_poj_checked_sandhi_ptk_swaps_4_and_8():
    assert ak._sandhi_contour_of("4", "sit", "poj") == "44"   # 4 → 8
    assert ak._sandhi_contour_of("8", "t͡ɕit", "poj") == "32"  # 8 → 4


def test_poj_checked_sandhi_glottal_joins_open_circle():
    assert ak._sandhi_contour_of("4", "baʔ", "poj") == "51"   # 4-h → 2
    assert ak._sandhi_contour_of("8", "baʔ", "poj") == "21"   # 8-h → 3
    assert ak._sandhi_contour_of("4", "bah", "poj") == "51"   # POJ -h form


# ------------------------------------------------- token tone recovery --
def test_syllable_tone_hokkien_ipa():
    base, cls, cit = ak._syllable_tone("t͡ɕit˥", "poj")
    assert (base, cls, cit) == ("t͡ɕit", "8", "˥")


def test_syllable_tone_teochew_digit_and_ml_suffix():
    base, cls, cit = ak._syllable_tone("suang2[ML]", "teochew")
    assert (base, cls) == ("suang", "2")
    assert cit == ak.contour_to_chao(ak._TONE_CONTOUR["teochew"]["2"])


def test_syllable_tone_poj_diacritic():
    base, cls, cit = ak._syllable_tone("lâm", "poj")
    assert cls == "5" and cit == ak.contour_to_chao("24")


def test_syllable_tone_unknown_returns_none():
    assert ak._syllable_tone("", "poj") is None
    assert ak._syllable_tone("ki˩˩˩", "poj") is None   # contour not in inventory


# ---------------------------------------------------- phrase surfacing --
def test_phrase_nonfinal_sandhi_final_citation():
    pairs = [("豬", "ti˥"), ("肉", "baʔ˧")]
    (group,) = ak.phrase_surface_tones(pairs, "poj")
    first, last = group
    assert first["surface"] == ak.contour_to_chao("33")   # 1 → 7 non-final
    assert first["changed"]
    assert last["final"] and last["surface"] == "˧"        # citation kept


def test_punctuation_splits_tone_groups():
    pairs = [("天", "tʰĩ˥"), ("，", None), ("光", "kŋ̩˥"), ("明", "biŋ˨˦")]
    g1, g2 = ak.phrase_surface_tones(pairs, "poj")
    # 天 is alone in its group → group-final → citation, no sandhi
    assert g1[0]["final"] and g1[0]["surface"] == "˥"
    # 光 is non-final in the second group → sandhi 55→33
    assert not g2[0]["final"] and g2[0]["surface"] == ak.contour_to_chao("33")


def test_unknown_reading_still_counts_as_following_syllable():
    pairs = [("天", "tʰĩ˥"), ("骉", None)]
    (group,) = ak.phrase_surface_tones(pairs, "poj")
    assert not group[0]["final"]                     # 骉 still follows it
    assert group[0]["surface"] == ak.contour_to_chao("33")
    assert group[1]["surface"] == ""                 # unreadable, no claim


def test_single_syllable_input_yields_nothing():
    assert ak.phrase_surface_tones([("天", "tʰĩ˥")], "poj") == []


def test_teochew_phrase_uses_class_table():
    pairs = [("好", "ho2"), ("人", "nang5")]
    (group,) = ak.phrase_surface_tones(pairs, "teochew")
    assert group[0]["surface"] == ak.contour_to_chao(
        ak._SANDHI_CONTOUR["teochew"]["2"])
    assert group[1]["surface"] == ak.contour_to_chao(
        ak._TONE_CONTOUR["teochew"]["5"])


# ------------------------------------------------------------ html line --
def test_phrase_sandhi_html_smoke():
    pairs = [("豬", "ti˥"), ("肉", "baʔ˧")]
    html = ak.phrase_sandhi_html(pairs, "Hokkien")
    assert "spoken:" in html and "ti" in html
    assert ak.phrase_sandhi_html(pairs, "Wu") == ""       # no sandhi table
    assert ak.phrase_sandhi_html([("豬", "ti˥")], "Hokkien") == ""


# ------------------------------- tâi-lô referee (reading disambiguation) --
def test_tailo_units_parses_kip_with_glued_punctuation():
    units = ak._tailo_units("Kin-á-ji̍t thinn-khì tsin-hó,guá siūnn-beh.")
    assert [c for _, c in units] == ["1", "2", "8", "1", "3", "1", "2",
                                     "2", "7", "4"]


def test_tailo_units_keeps_echoed_hanzi_in_order():
    units = ak._tailo_units("Tse-sī㗊jī")          # ithuan couldn't read 㗊
    assert [u for u, _ in units] == ["Tse", "sī", "㗊", "jī"]
    assert units[2][1] == ""


def test_tailo_nasal():
    assert ak._tailo_nasal("siūnn") and ak._tailo_nasal("mn̄gh") is False
    assert ak._tailo_nasal("thinn") and not ak._tailo_nasal("hó")
    assert ak._tailo_nasal("sannh")                # nasal + glottal coda


_FAKE = {
    "台": {"Hokkien": "i˨˦"},
    "灣": {"Hokkien": "u̯an˥/u̯an˨˦"},
    "好": {"Hokkien": "hɔ̃˧˩ | hɤ˥˩/hɔ̃˥˩/hɔ˥˩"},
}


def test_tailo_matched_tokens_picks_tone_matching_alternate():
    pairs = ak.tailo_matched_tokens(_FAKE, "Hokkien", "台灣", None, "Tâi-uân")
    assert pairs == [("台", "i˨˦"), ("灣", "u̯an˨˦")]   # 灣 → tone 5 variant


def test_tailo_matched_tokens_prefers_nasality_agreement():
    (pair,) = ak.tailo_matched_tokens(_FAKE, "Hokkien", "好", None, "hó")
    assert pair == ("好", "hɤ˥˩")                  # tone 2 AND non-nasal


def test_tailo_matched_tokens_falls_back_on_misalignment():
    before = ak.per_char_tokens(_FAKE, "Hokkien", "台灣", None)
    assert ak.tailo_matched_tokens(_FAKE, "Hokkien", "台灣", None,
                                   "Tâi-uân-lâng") == before
    assert ak.tailo_matched_tokens(_FAKE, "Hokkien", "台灣", None,
                                   "") == before


def test_tailo_matched_tokens_keeps_first_when_no_class_matches():
    (pair,) = ak.tailo_matched_tokens(_FAKE, "Hokkien", "台", None, "tāi")
    assert pair == ("台", "i˨˦")                   # no tone-7 variant stored


def test_tailo_matched_tokens_ignores_non_poj_dialects():
    data = {"好": {"Teochew": "ho2/hao3"}, "人": {"Teochew": "nang5"}}
    pairs = ak.tailo_matched_tokens(data, "Teochew", "好人", None, "hó-lâng")
    assert pairs == ak.per_char_tokens(data, "Teochew", "好人", None)


# ----------------------- Teochew stitched audio (mogher.com) — offline --
def test_teochew_audio_plan_citation_keeps_tones():
    pairs = [("好", "ho2"), ("人", "nang5")]
    assert ak.teochew_audio_plan(pairs, spoken=False) == ["ho2", "nang5"]


def test_teochew_audio_plan_spoken_substitutes_sandhi_tone():
    pairs = [("好", "ho2"), ("人", "nang5")]
    # non-final tone 2 → its sandhi (35) is exactly citation tone 6
    assert ak.teochew_audio_plan(pairs, spoken=True) == ["ho6", "nang5"]


def test_teochew_audio_plan_checked_swap_and_groups():
    pairs = [("八", "boih4"), ("，", None), ("人", "nang5")]
    # 八 is group-final (punctuation splits) → keeps tone 4 even when spoken
    assert ak.teochew_audio_plan(pairs, spoken=True) == ["boih4", "nang5"]
    pairs = [("八", "boih4"), ("個", "gai7")]
    assert ak.teochew_audio_plan(pairs, spoken=True) == ["boih8", "gai7"]


def test_teochew_audio_plan_none_when_reading_missing():
    assert ak.teochew_audio_plan([("好", "ho2"), ("骉", None)], False) is None
    assert ak.teochew_audio_plan([("！", None)], False) is None


def test_teochew_sandhi_audio_map_is_total_and_valid():
    assert set(ak._TEOCHEW_SANDHI_AUDIO) == set("12345678")
    assert set(ak._TEOCHEW_SANDHI_AUDIO.values()) <= set("12345678")


def test_mogher_variants_cover_chaozhou_shantou_vowels():
    assert "die5" in ak._mogher_variants("dio5")
    assert "dio5" in ak._mogher_variants("die5")
    assert ak._mogher_variants("ho2") == ["ho2"]


def test_mp3_frames_strips_id3v2_and_v1():
    body = b"\xff\xfbAUDIOFRAMES"
    v2 = b"ID3\x04\x00\x00\x00\x00\x00\x0a" + b"x" * 10
    v1 = b"TAG" + b"\x00" * 125
    assert ak._mp3_frames(v2 + body + v1) == body
    assert ak._mp3_frames(body) == body


def test_phrase_sandhi_html_custom_label():
    pairs = [("豬", "ti˥"), ("肉", "baʔ˧")]
    html = ak.phrase_sandhi_html(pairs, "Hokkien", label="↳ colloquial spoken:")
    assert "colloquial spoken:" in html and "↳ spoken:" not in html


def test_teochew_colloquial_source_swaps_taiwan_words():
    assert ak.teochew_colloquial_source("今仔日我真爽快") == "今日我真爽快"
    assert ak.teochew_colloquial_source("明仔載去佗位") == "明日去底塊"
    assert ak.teochew_colloquial_source("阮食飯") == "阮食飯"   # shared stays
    assert ak.teochew_colloquial_source("") == ""


def test_hanzi_only_strips_punctuation():
    assert ak.hanzi_only("你敢食飽矣？") == "你敢食飽矣"
    assert ak.hanzi_only("a-b?!") == ""


def test_mogher_variants_cover_coda_letter_swaps():
    assert "rig8" in ak._mogher_variants("rik8")
    assert "sik4" in ak._mogher_variants("sig4")
    assert "liou2" in ak._mogher_variants("liau2")
    # the swap only touches the coda, never the initial
    assert ak._mogher_variants("kim1") == ["kim1"]
    assert ak._mogher_variants("pim1") == ["pim1"]
