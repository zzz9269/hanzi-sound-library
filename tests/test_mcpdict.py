# -*- coding: utf-8 -*-
"""MCPDict table parsers (hanzihub.sources.mcpdict) — one test per format."""
from hanzihub.sources import mcpdict as m


def test_parse_cols_structured_suzhou_style():
    rows = [["ID", "漢字", "聲", "韻", "調"],
            ["1", "㒼", "m", "ɵ", "2"],
            ["2", "天", "tʰ", "i", "1"],
            ["3", "缺", "tɕʰ", "iɪ", "9"]]      # unmappable class → skipped
    opts = {"char": 1, "onset": 2, "rime": 3, "tone": 4,
            "tone_map": {"1": "44", "2": "223"}}
    assert m._parse_cols(rows, opts) == [("㒼", "mɵ˨˨˧"), ("天", "tʰi˦˦")]


def test_parse_cols_tone_name_map():
    rows = [["ID", "繁", "简", "聲韻", "声", "韵", "調"],
            ["1", "便", "便", "", "b", "ei", "阳平"]]
    opts = {"char": 1, "onset": 4, "rime": 5, "tone": 6,
            "tone_map": {"阳平": "31"}}
    assert m._parse_cols(rows, opts) == [("便", "bei˧˩")]


def test_parse_cols_inline_contour_and_zero_initial():
    rows = [["h"], ["1", "又", "又", "∅ɐ22"], ["2", "天", "天", "tʰin55"]]
    opts = {"char": 1, "ipa": 3, "inline_contour": True}
    assert m._parse_cols(rows, opts) == [("又", "ɐ˨˨"), ("天", "tʰin˥˥")]


def test_parse_cols_contour_column_multichar():
    rows = [["IPA", "調值", "調類", "漢字"],
            ["tse", "24", "7", "卒失"]]
    opts = {"char": 3, "ipa": 0, "tone": 1, "tone_is_contour": True}
    assert m._parse_cols(rows, opts) == [("卒", "tse˨˦"), ("失", "tse˨˦")]


def test_parse_tongyin_with_embedded_tone_values():
    rows = [["#符号说明：-白=文*俗?待考", ""],
            ["#调值", "［1］22［3］512"],
            ["#ɑ", ""],
            ["p", "［1］芭巴{～黎}疤［3］把靶"]]
    out = m._parse_tongyin(rows, {})
    assert ("芭", "pɑ˨˨") in out and ("巴", "pɑ˨˨") in out
    assert ("把", "pɑ˥˩˨") in out
    assert all(ch != "黎" for ch, _ in out)     # brace note stripped


def test_parse_tongyin_without_tone_values_keeps_class():
    rows = [["#ɿ", ""], ["ts", "[1]资姿[3]紫"]]
    out = m._parse_tongyin(rows, {})
    assert ("资", "tsɿ1") in out and ("紫", "tsɿ3") in out


def test_chao_helper():
    assert m._chao("223") == "˨˨˧"
    assert m._chao("9") == ""
