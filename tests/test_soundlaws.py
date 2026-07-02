# -*- coding: utf-8 -*-
"""Sound-law edge notes derived from the MC 音韻地位 (hanzihub.soundlaws)."""
from hanzihub import soundlaws


def test_voiceless_level_tone_minimal():
    n = soundlaws.edge_notes("透開四先平")
    assert "tone 1" in n["man"][0]
    assert "wu" not in n            # nothing notable for Wu here


def test_voiced_entering_full_story():
    n = soundlaws.edge_notes("並開二庚入")
    assert any("入聲 lost" in x for x in n["man"])
    assert any("plain" in x for x in n["man"])       # 仄聲 devoicing → plain
    assert any("VOICED" in x for x in n["wu"])       # Wu keeps voice
    assert any("-p/-t/-k" in x for x in n["yue"])    # Cantonese keeps stops
    assert any("ASPIRATED" in x for x in n["hak"])   # Hakka signature
    # entering tone: the -ŋ note must NOT fire (coda is -k here)
    assert not any("ŋ" in x for x in n["sj"])


def test_min_pre_split_notes():
    assert any("DENTAL" in x
               for x in soundlaws.edge_notes("知三東平")["pmin"])
    assert any("輕脣" in x
               for x in soundlaws.edge_notes("幫三東平")["pmin"])


def test_korean_t_to_l():
    n = soundlaws.edge_notes("端開一寒入")
    assert any("-l" in x for x in n["sk"])


def test_unparsable_returns_empty():
    assert soundlaws.edge_notes("") == {}
    assert soundlaws.edge_notes("garbage") == {}
