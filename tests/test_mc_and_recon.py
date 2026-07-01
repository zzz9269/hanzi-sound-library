# -*- coding: utf-8 -*-
"""Middle Chinese position decoding (appkit) + Proto-Min comparative helpers
(reconstruct)."""
from hanzihub import appkit as ak
from hanzihub import reconstruct as rc


# --------------------------------------------------- MC position (appkit) --
def test_mc_readable_syllable():
    assert ak.mc_readable_syllable("心合一寒平") == "swan"


def test_mc_breakdown_roles():
    rows = ak.mc_position_breakdown("透開四先平")
    glyphs = [g for g, _ in rows]
    assert glyphs == ["透", "開", "四", "先", "平"]
    assert "initial" in rows[0][1]
    assert "tone" in rows[-1][1]


def test_explain_mc_position_mentions_tone():
    out = ak.explain_mc_position("心合一寒平")
    assert "swan" in out and "level" in out


def test_mc_entering_tone_stops_coda():
    # 入聲 swaps the nasal coda for the matching stop: 東 -ŋ → -k
    p = ak.parse_mc_position("見一東入")
    assert ak._mc_syllable_ipa(p).endswith("k")


# ------------------------------------------------ Proto-Min (reconstruct) --
def test_mc_coda_by_rime_class():
    assert rc._mc_coda({"rime": "東", "tone": "平"}) == "ŋ"
    assert rc._mc_coda({"rime": "東", "tone": "入"}) == "k"
    assert rc._mc_coda({"rime": "寒", "tone": "平"}) == "n"
    assert rc._mc_coda({"rime": "侵", "tone": "入"}) == "p"
    assert rc._mc_coda({"rime": "支", "tone": "平"}) == ""   # 陰聲韻: open


def test_reanchor_rhyme_replaces_coda_and_denasalises():
    assert rc._reanchor_rhyme("iaŋ", "k") == "iak"
    assert rc._reanchor_rhyme("ĩ", "n") == "in"


def test_majority_vote_and_tiebreak():
    assert rc._majority(["a", "a", "b"], ["a", "a", "b"]) == "a"
    # tie → first value in the priority list wins
    assert rc._majority(["x", "y"], ["y", "x"]) == "y"
    assert rc._majority([], []) == ""


# ------------------------------------------------------------ schema sanity --
def test_locality_table_is_39_points():
    from hanzihub import schema
    assert len(schema.LOCALITIES) == 39
    assert schema.locality_col(schema.LOCALITIES[0]) == "dial:Mandarin-Beijing"
