# -*- coding: utf-8 -*-
"""Phrase-level Min tone sandhi (hanzihub.appkit) — the ↳ spoken: line.

Within a tone group every non-final syllable takes its sandhi tone and only
the group-final syllable keeps citation; non-Hanzi input characters split
groups. Hokkien local readings are IPA (tone = Chao contour + coda),
Teochew readings are Peng'im (tone = trailing class digit).
"""
import pytest

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


def _patch_mogher(monkeypatch, pairs):
    """Patch mogher's per-character parse (readings + 文/白/训 type). Accepts a
    list of ``reading`` strings (untyped) or ``(reading, type)`` tuples."""
    parsed = [p if isinstance(p, tuple) else (p, "") for p in pairs]
    monkeypatch.setattr(ak, "_mogher_char_parse", lambda ch: parsed)


def test_mogher_reading_for_uses_mogher_primary(monkeypatch):
    # our Peng'im disagrees with mogher's spelling; the character lookup bridges
    # it (single-reading chars just resolve to mogher's spelling)
    readings = {"霜": ["seng1"], "明": ["mêng5"], "望": ["mo7", "bhuang6"]}
    monkeypatch.setattr(ak, "_mogher_char_parse",
                        lambda ch: [(r, "") for r in readings.get(ch, [])])
    assert ak.mogher_reading_for("霜", "sng1") == "seng1"
    assert ak.mogher_reading_for("明", "meng5") == "mêng5"
    # polyphone: take mogher's FIRST-listed reading (primary/most-common),
    # regardless of which one our own seed happens to be
    assert ak.mogher_reading_for("望", "mo7") == "mo7"
    assert ak.mogher_reading_for("望", "bhuang6") == "mo7"
    # character mogher doesn't list → None (caller keeps our own reading)
    assert ak.mogher_reading_for("〇", "ho2") is None


def test_teochew_reading_avoids_sudu_slang(monkeypatch):
    # 一: 俗 ieu1 (slang) + 文 ig4 + 训 zêg8 (the everyday 'one', 一起 = zêg8-ki).
    # Natural keeps the everyday 训读 zêg8 and NEVER the 俗讀; 文讀 mode picks ig4.
    # 俗讀 is demoted below both standard readings either way.
    _patch_mogher(monkeypatch, [("ieu1", "俗"), ("ig4", "文"), ("zêg8", "训")])
    c = ak._teochew_reading_candidates("一", "zek8")
    assert c[0] == "zêg8"
    assert c.index("ieu1") > c.index("ig4")           # 俗讀 sinks below 文
    assert ak._teochew_reading_candidates("一", "zek8", literary=True)[0] == "ig4"


def test_teochew_reading_seed_promotes_only_everyday_match(monkeypatch):
    # 氣: our seed ki3 IS the 文 reading; natural must NOT promote the 白 kui3
    # (shares tone+initial but is a different rime) — take mogher's first, ki3.
    _patch_mogher(monkeypatch, [("ki3", "文"), ("kui3", "白")])
    assert ak._teochew_reading_candidates("氣", "ki3")[0] == "ki3"
    # 一: seed zek8 names the everyday 训 reading, spelled zêg8 by mogher —
    # fuzzy match still promotes it over the literary ig4.
    _patch_mogher(monkeypatch, [("ieu1", "俗"), ("ig4", "文"), ("zêg8", "训")])
    assert ak._teochew_reading_candidates("一", "zek8")[0] == "zêg8"


def test_pengim_norm_matches_romanisation_variants():
    assert ak._pengim_norm("zek8") == ak._pengim_norm("zêg8")   # ê/e + k/g coda
    assert ak._pengim_norm("ki3") != ak._pengim_norm("kui3")    # different rime


def test_teochew_reading_everyday_vs_literary(monkeypatch):
    # 食: ziah8 白 (eat, everyday) vs sig8 文 (literary). And 二: no6 训 (everyday
    # 'two things') vs ri6/ri7 文. Natural → the everyday {白,训}; 文讀 → 文.
    _patch_mogher(monkeypatch, [("ziah8", "白"), ("sig8", "文")])
    assert ak._teochew_reading_candidates("食", "ziah8")[0] == "ziah8"
    assert ak._teochew_reading_candidates("食", "ziah8", literary=True)[0] == "sig8"
    _patch_mogher(monkeypatch, [("no6", "训"), ("ri6", "文"), ("ri7", "文")])
    assert ak._teochew_reading_candidates("二", "no6")[0] == "no6"
    assert ak._teochew_reading_candidates("二", "no6", literary=True)[0] in ("ri6", "ri7")


def test_teochew_unit_mp3_uses_mogher_own_spelling(monkeypatch):
    _patch_mogher(monkeypatch, ["seng1"])
    fetched = {}
    monkeypatch.setattr(ak, "_mogher_fetch",
                        lambda syl: fetched.setdefault(syl, b"\xff\xfbX"))
    # citation 霜: our sng1 is never requested — mogher's seng1 is
    ak._teochew_unit_mp3("霜", "sng1", sandhi=False)
    assert "seng1" in fetched and "sng1" not in fetched


def test_teochew_unit_mp3_sandhi_falls_back_to_citation(monkeypatch):
    _patch_mogher(monkeypatch, ["ho2"])
    # mogher has citation ho2 but not the sandhi-tone ho6 → speak ho2, same
    # syllable, never a different one
    monkeypatch.setattr(ak, "_mogher_fetch",
                        lambda syl: b"\xff\xfbHO2" if syl == "ho2" else None)
    assert ak._teochew_unit_mp3("好", "ho2", sandhi=True) == b"\xff\xfbHO2"


def test_teochew_unit_mp3_walks_to_a_recorded_reading(monkeypatch):
    # 思: mogher lists se1 first (matches our su1) but only RECORDED si1;
    # must fall through mogher's other readings rather than go silent
    _patch_mogher(monkeypatch, ["se1", "se3", "si1", "sai1"])
    monkeypatch.setattr(ak, "_mogher_fetch",
                        lambda syl: b"\xff\xfbSI1" if syl == "si1" else None)
    assert ak._teochew_unit_mp3("思", "su1", sandhi=False) == b"\xff\xfbSI1"


def test_teochew_unit_mp3_falls_back_to_our_own_reading(monkeypatch):
    # mogher lists a reading but records NONE of them; our own reading is the
    # last-resort candidate so audio still plays when it happens to be recorded
    _patch_mogher(monkeypatch, ["se1"])
    monkeypatch.setattr(ak, "_mogher_fetch",
                        lambda syl: b"\xff\xfbSU1" if syl == "su1" else None)
    assert ak._teochew_unit_mp3("思", "su1", sandhi=False) == b"\xff\xfbSU1"


def test_teochew_unit_mp3_raises_when_nothing_recorded(monkeypatch):
    _patch_mogher(monkeypatch, ["se1"])
    monkeypatch.setattr(ak, "_mogher_fetch", lambda syl: None)
    with pytest.raises(RuntimeError):
        ak._teochew_unit_mp3("思", "su1", sandhi=False)


def test_teochew_voiced_reading_shows_what_it_plays(monkeypatch):
    _patch_mogher(monkeypatch, ["se1", "si1", "sai1"])
    monkeypatch.setattr(ak, "_mogher_fetch",
                        lambda syl: b"\xff\xfbX" if syl == "si1" else None)
    # top pick se1 is unrecorded → show the recorded si1 (what audio plays),
    # never one thing read and another heard
    assert ak.teochew_voiced_reading("思", "su1") == "si1"


def test_teochew_voiced_reading_rescues_ipa_entry(monkeypatch):
    # 床's stored reading is IPA, not Peng'im; mogher's ceng5 is shown+voiced
    _patch_mogher(monkeypatch, ["ceng5"])
    monkeypatch.setattr(ak, "_mogher_fetch",
                        lambda syl: b"\xff\xfbX" if syl == "ceng5" else None)
    assert ak.teochew_voiced_reading("床", "t͡sʰɯŋ55") == "ceng5"


def test_teochew_voiced_reading_falls_back_when_nothing_recorded(monkeypatch):
    _patch_mogher(monkeypatch, ["ceng5"])
    monkeypatch.setattr(ak, "_mogher_fetch", lambda syl: None)
    # nothing recorded → still return mogher's top reading (display), audio
    # branch will just report unavailable
    assert ak.teochew_voiced_reading("床", "t͡sʰɯŋ55") == "ceng5"


def test_teochew_node_reading_is_mogher_primary(monkeypatch):
    # the evolution-tree Teochew node must read from mogher (like the panel row
    # + phrase sandhi), NOT Wiktionary — EVERY reading mogher lists, incl. 俗讀,
    # each as Chao Peng'im. 俗讀 (ka7) is kept but demoted below 文/白, even
    # though mogher lists it FIRST.
    _patch_mogher(monkeypatch, [("ka7", "俗"), ("gieh4", "白"),
                                ("gag4", "文"), ("giog4", "白")])
    got = ak.teochew_node_reading("腳")
    assert got == " ".join(ak.wikt_rom_to_chao(r, "teochew")
                           for r in ("gieh4", "gag4", "giog4", "ka7"))


def test_teochew_node_reading_empty_when_mogher_silent(monkeypatch):
    # mogher lists nothing → '' so the tree falls back to Wiktionary / dataset
    _patch_mogher(monkeypatch, [])
    assert ak.teochew_node_reading("〇") == ""


def test_teochew_phrase_mp3_skips_uncovered_chars(monkeypatch):
    # 蕭 isn't in mogher's dictionary at all → skip it and voice the rest,
    # rather than silencing the whole line; report it in `missing`
    def fake_unit(ch, tok, sandhi):
        if ch == "蕭":
            raise RuntimeError("no recording")
        return b"\xff\xfb" + ch.encode()
    monkeypatch.setattr(ak, "_teochew_unit_mp3", fake_unit)
    monkeypatch.setattr(ak, "_mp3_frames", lambda b: b)
    pairs = [("雨", "u2"), ("蕭", "siau1"), ("歇", "hiah4")]
    mp3, missing = ak.teochew_phrase_mp3(pairs, spoken=False)
    assert missing == ["蕭"]
    assert mp3 == b"\xff\xfb" + "雨".encode() + b"\xff\xfb" + "歇".encode()


def test_teochew_phrase_mp3_none_when_nothing_voiced(monkeypatch):
    monkeypatch.setattr(ak, "_teochew_unit_mp3",
                        lambda *a: (_ for _ in ()).throw(RuntimeError()))
    mp3, missing = ak.teochew_phrase_mp3([("蕭", "siau1")], spoken=False)
    assert mp3 is None and missing == ["蕭"]


def test_t2s_text_maps_traditional_to_simplified_for_mogher():
    # mogher is indexed by simplified hanzi; the query form must be simplified
    assert ak.t2s_text("髮") == "发"
    assert ak.t2s_text("蕭") == "萧"
    assert ak.t2s_text("发") == "发"   # already simplified → unchanged


def test_mogher_char_readings_queries_simplified(monkeypatch):
    seen = {}
    class R:
        ok = True
        text = ('<a href="/dic/czpy/huêg4"> huêg4 '
                '<label class="label label-primary wendu-label">文</label></a>')
    def fake_get(url, timeout=0):
        seen["url"] = url
        return R()
    monkeypatch.setattr(ak, "_tts_cache_path",
                        lambda *a: __import__("pathlib").Path(
                            __import__("tempfile").mkdtemp()) / "x")
    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    assert ak.mogher_char_readings("髮") == ["huêg4"]
    assert seen["url"].endswith("/发")   # queried the simplified form


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


# ------------------- Teochew doublet referee (Hokkien cognate tâi-lô) --
def test_teochew_cognate_score_separates_doublets():
    inits = ak._pengim_initials_for_tailo("lo̍k")     # l- → Peng'im l/n
    assert ak._teochew_cognate_score("lag8", "8", inits) == 3
    assert ak._teochew_cognate_score("ghauh8", "8", inits) == 1
    assert ak._pengim_initials_for_tailo("ê") == ("",)   # zero initial


def test_teochew_cognate_referee_picks_matching_doublet():
    data = {"快": {"Teochew": "kuai3"}, "樂": {"Teochew": "ghauh8 | lag8"}}
    pairs = ak.teochew_tailo_matched_tokens(data, "Teochew", "快樂", None,
                                            "khuài-lo̍k")
    assert pairs == [("快", "kuai3"), ("樂", "lag8")]


def test_teochew_cognate_referee_consults_mogher(monkeypatch):
    monkeypatch.setattr(ak, "mogher_char_readings",
                        lambda ch: ["lag8", "ghaoh8"])
    data = {"快": {"Teochew": "kuai3"}, "樂": {"Teochew": "ghauh8"}}
    pairs = ak.teochew_tailo_matched_tokens(data, "Teochew", "快樂", None,
                                            "khuài-lo̍k")
    assert pairs[1] == ("樂", "lag8")


def test_teochew_cognate_referee_falls_back_on_misalignment(monkeypatch):
    monkeypatch.setattr(ak, "mogher_char_readings",
                        lambda ch: (_ for _ in ()).throw(AssertionError))
    data = {"樂": {"Teochew": "ghauh8"}}
    before = ak.per_char_tokens(data, "Teochew", "樂", None)
    assert ak.teochew_tailo_matched_tokens(data, "Teochew", "樂", None,
                                           "") == before
    assert ak.teochew_tailo_matched_tokens(data, "Teochew", "樂", None,
                                           "khuài-lo̍k") == before


# ------------------------------------ round-trip accuracy gate (offline) --
def test_roundtrip_score_ranges():
    assert ak.roundtrip_score("我今天很快樂", "我今天很快樂") == 1.0
    # legitimate paraphrase stays above the display threshold
    assert ak.roundtrip_score("你吃飽了嗎？", "你是否吃飽了？") \
        >= ak.LOHANKHA_MIN_ROUNDTRIP
    # an unrelated sentence falls far below it
    assert ak.roundtrip_score("我今天很快樂", "股票市場大跌") < 0.3
    assert ak.roundtrip_score("我今天很快樂", "") == 0.0
    assert ak.roundtrip_score("", "我今天很快樂") == 0.0


def test_roundtrip_threshold_is_sane():
    assert 0.5 <= ak.LOHANKHA_MIN_ROUNDTRIP <= 0.9


def test_colloquial_verified_gates_on_score(monkeypatch, tmp_path):
    monkeypatch.setattr(ak, "hokkien_colloquial",
                        lambda t: ("今仔日我真爽快", "kin-á-ji̍t"))
    monkeypatch.setattr(ak, "_tts_cache_path",
                        lambda *a: tmp_path / "rt.mp3")
    monkeypatch.setattr(ak, "_lohankha_mt",
                        lambda t, i, o: ("今天我很開心", ""))
    got = ak.hokkien_colloquial_verified("今天我很開心")
    assert got == ("今仔日我真爽快", "kin-á-ji̍t", 1.0)
    # a back-translation that disagrees → hidden (None), and the cached
    # score keeps it hidden without re-asking the service
    (tmp_path / "rt.txt").unlink()
    monkeypatch.setattr(ak, "_lohankha_mt",
                        lambda t, i, o: ("股票市場大跌", ""))
    assert ak.hokkien_colloquial_verified("今天我很開心") is None
    monkeypatch.setattr(ak, "_lohankha_mt",
                        lambda t, i, o: (_ for _ in ()).throw(AssertionError))
    assert ak.hokkien_colloquial_verified("今天我很開心") is None


def test_roundtrip_score_normalizes_script_variants():
    # the input is traditionalized (吃→喫) but the back-translation may use
    # the other variant — must not count as a semantic mismatch
    assert ak.roundtrip_score("你喫飽了嗎？", "你是否吃飽了？") == \
        ak.roundtrip_score("你吃飽了嗎？", "你是否吃飽了？")
    assert ak.roundtrip_score("你喫飽了嗎？", "你吃飽了嗎？") == 1.0
