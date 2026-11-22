"""Web exporter helpers: IPA→Jyutping, POJ→Tâi-lô, Unihan and zh-pron parsing."""
import pytest

from hanzihub.build_web import poj_to_tailo, yue_ipa_to_jyutping
from hanzihub.scrapers import _extract_template
from hanzihub.sources.unihan_readings import _readings_after_colon
from hanzihub.sources.wiktionary_zhpron import parse_zhpron


@pytest.mark.parametrize("ipa, jp", [
    ("hɔːŋ˨˩", "hong4"), ("haːŋ˨˩", "haang4"), ("hɐŋ˨", "hang6"),
    ("t͡sʰœːŋ˧˥", "coeng2"), ("t͡sœːŋ˥", "zoeng1"), ("kʷʰɐn˨˩", "kwan4"),
    ("kʷɐi̯˧", "gwai3"), ("jyːt˨", "jyut6"), ("sɵy̯˧", "seoi3"), ("wuːy̯˨˩", "wui4"),
    ("kʰɔːk˧", "kok3"), ("ŋ̩˩˧", "ng5"), ("ŋaːu̯˨", "ngaau6"), ("lɵn˨", "leon6"),
    ("faːt̚˥", "faat1"), ("jiːp˨", "jip6"), ("ɔːi̯˧", "oi3"), ("sɛː˥", "se1"),
])
def test_yue_ipa_to_jyutping(ipa, jp):
    assert yue_ipa_to_jyutping(ipa) == jp


@pytest.mark.parametrize("bad", ["", "hɔːŋ", "kɔːk˧˥", "xyz˥", "hɔːŋ˧˧˧"])
def test_yue_ipa_to_jyutping_rejects_unclean(bad):
    assert yue_ipa_to_jyutping(bad) == ""


@pytest.mark.parametrize("poj, tl", [
    ("kiâⁿ", "kiânn"), ("chhiū", "tshiū"), ("chiá", "tsiá"), ("hoa", "hua"),
    ("hêng", "hîng"), ("e̍k", "i̍k"), ("o͘", "oo"),
])
def test_poj_to_tailo(poj, tl):
    assert poj_to_tailo(poj) == tl


def test_unihan_readings_after_colon():
    assert _readings_after_colon("0436.020:háng 1285.050:xíng,xìng") == ["háng", "xíng", "xìng"]
    assert _readings_after_colon("") == []


def test_zhpron_comments_are_dropped_before_splitting_params():
    wt = "{{zh-pron\n|m=zhě<!--, zhe-->\n|c=ze2\n|mn=<!--chiá-->chiá\n|cat=pron}}"
    assert "<!--" not in _extract_template(wt, "zh-pron")
    out = parse_zhpron(wt)
    assert out["Mandarin"] == "zhě"
    assert out["Cantonese"] == "ze2"
