# -*- coding: utf-8 -*-
"""The bundled classical-poetry library (hanzihub.reading.load_poems) that the
🎋 Poems page reads from, plus the recite-mode masking used to hide characters."""
from hanzihub import reading as rd


def test_library_loads_all_anthologies():
    poems = rd.load_poems()
    assert len(poems) > 800                       # ~955: Tang300 + Song300 + 詩經 + 蒙學
    anthologies = {p["anthology"] for p in poems}
    assert {"唐詩三百首", "宋詞三百首", "詩經", "蒙學"} <= anthologies


def test_records_are_well_formed():
    for p in rd.load_poems():
        assert p["title"] and p["author"]
        assert p["lines"] and all(isinstance(ln, str) and ln.strip() for ln in p["lines"])
        assert isinstance(p["id"], str) and p["id"]


def test_song_ci_converted_to_traditional():
    # 宋詞三百首 ships Simplified in the source; the build must convert it. The
    # Simplified-only forms 黄/邁 → Traditional 黃, 与 → 與 must not survive.
    text = "".join(ln for p in rd.load_poems() if p["anthology"] == "宋詞三百首"
                   for ln in p["lines"] + [p["title"], p["author"]])
    assert "黄" not in text and "变" not in text


def test_famous_variant_overridden_to_taught_text():
    # 靜夜思 ships as the older 宋本 (牀前看月光…舉頭望山月); the build overrides it
    # to the version taught in schools.
    jys = next(p for p in rd.load_poems() if p["title"] == "靜夜思")
    joined = "".join(jys["lines"])
    assert "床前明月光" in joined and "舉頭望明月" in joined
    assert "看月光" not in joined and "望山月" not in joined


def test_lines_split_into_readable_sentences():
    # A poem's joined lines must break back into per-line sentences for rendering.
    guanju = next(p for p in rd.load_poems() if p["title"] == "關雎")
    lines = rd.sentences("\n".join(guanju["lines"]))
    assert len(lines) >= 5 and all(rd.has_hanzi(ln) for ln in lines)
