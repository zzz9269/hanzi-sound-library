# -*- coding: utf-8 -*-
"""Sino-Xenic converters + MCPDict normalised tables + merge gap-fill rule."""
from hanzihub import sinoxenic as sx
from hanzihub.merge import apply_fallbacks
from hanzihub.sources import mcpdict as m
from hanzihub.sources.wiktionary_dialpron import normalize_dialpron


# ------------------------------------------------------------- Vietnamese --
def test_telex_basic_and_tone_marks():
    assert sx.telex_to_vietnamese("nhaats") == "nhất"
    assert sx.telex_to_vietnamese("ddinh") == "đinh"
    assert sx.telex_to_vietnamese("tam") == "tam"
    assert sx.telex_to_vietnamese("mawcj") == "mặc"


def test_telex_uow_cluster():
    assert sx.telex_to_vietnamese("truwowngj") == "trượng"
    assert sx.telex_to_vietnamese("thuwowng") == "thương"
    assert sx.telex_to_vietnamese("duwx") == "dữ"


def test_telex_traditional_tone_placement():
    # open 2-vowel nucleus → first vowel (Unihan style); coda → last vowel
    assert sx.telex_to_vietnamese("hoaf") == "hòa"
    assert sx.telex_to_vietnamese("cuar") == "của"
    assert sx.telex_to_vietnamese("hoanf") == "hoàn"
    assert sx.telex_to_vietnamese("ngoaif") == "ngoài"
    assert sx.telex_to_vietnamese("quys") == "quý"
    assert sx.telex_to_vietnamese("gias") == "giá"


def test_telex_rejects_garbage():
    assert sx.telex_to_vietnamese("") == ""
    assert sx.telex_to_vietnamese("ab1") == ""


# ----------------------------------------------------------------- Korean --
def test_rr_to_hangul():
    assert sx.rr_to_hangul("guk") == "국"
    assert sx.rr_to_hangul("ryeok") == "력"
    assert sx.rr_to_hangul("cheon") == "천"
    assert sx.rr_to_hangul("in") == "인"
    assert sx.rr_to_hangul("chi") == "치"
    assert sx.rr_to_hangul("ui") == "의"
    assert sx.rr_to_hangul("baek") == "백"
    assert sx.rr_to_hangul("x1") == ""


def test_naver_initial_law_pair():
    assert sx.naver_korean("ryeok(yeok)") == ["력", "역"]
    assert sx.naver_korean("ri(i)") == ["리", "이"]


def test_hangul_to_yale_matches_unihan_convention():
    assert sx.hangul_to_yale("천") == "CHEN"
    assert sx.hangul_to_yale("국") == "KWUK"
    assert sx.hangul_to_yale("희") == "HUY"
    assert sx.hangul_to_yale("랭") == "LAYNG"
    assert sx.hangul_to_yale("치") == "CHI"
    assert sx.hangul_to_yale("a") == ""


# ------------------------------------------------- MCPDict normalised table --
def test_tone_table_skips_empty_contours():
    t = m.tone_table({"1": ["11", "1", "1", "平"], "0": ["", "0", "0", "輕聲"],
                      "7a": ["5", "7a", "4a", "上陰入"]})
    assert t == {"1": "˩˩", "7a": "˥"}


def test_parse_out_maps_class_and_drops_doubtful():
    tones = {"1": "˩˩", "3": "˥˧", "7a": "˥"}
    lines = ["#漢字\t音標\t解釋",
             "天\ttʰie1\t",
             "□\tma1\t~虎",             # no character → skipped
             "上\tsɒ̃3-\t白",           # colloquial tag stripped
             "七\ttsʰiəʔ7a\t",          # a/b sub-class
             "疑\tni3?\t",               # 存疑 → dropped
             "怪\tkuai9\t"]              # unmapped class → dropped, never guessed
    assert m.parse_out(lines, tones) == [
        ("天", "tʰie˩˩"), ("上", "sɒ̃˥˧"), ("七", "tsʰiəʔ˥")]


# ------------------------------------------------------- merge gap-fill rule --
def _r(ch, col, rd, src, fb=False):
    return {"char": ch, "column": col, "reading": rd, "source": src,
            "locality": "", "conf": 1.0, "fallback": fb}


def test_apply_fallbacks_only_fills_gaps():
    recs = [_r("天", "dial:Jin-Taiyuan", "tʰie˩˩", "kaikki"),
            _r("天", "dial:Jin-Taiyuan", "tʰiɛ˩˩", "mcpdict", True),
            _r("地", "dial:Jin-Taiyuan", "ti˦˥", "mcpdict", True)]
    kept = apply_fallbacks(recs)
    assert [(r["char"], r["source"]) for r in kept] == [("天", "kaikki"), ("地", "mcpdict")]


# ------------------------------------------------- Wiktionary dial-pron slot --
def test_normalize_dialpron_splits_and_converts():
    assert normalize_dialpron("zin31|naŋ31訓儂") == ["zin˧˩", "naŋ˧˩"]
    assert normalize_dialpron("ʐən35") == ["ʐən˧˥"]
    assert normalize_dialpron("tɛ̃55") == ["tɛ̃˥˥"]
    assert normalize_dialpron("tə0") == ["tə0"]      # neutral tone left alone
    assert normalize_dialpron("") == []
