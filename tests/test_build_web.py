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
    ("góa", "guá"), ("ngó͘", "ngóo"), ("thiⁿ", "thinn"), ("chúi", "tsuí"), ("n̄g", "n̄g"),
    ("m̄", "m̄"), ("hòⁿ", "hònn"), ("koaiⁿ", "kuainn"), ("khìr", "khìr"), ("ke-á", "ke-á"),
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


# ---------------------------------------------- Min: Taiwan / Swatow picks --
import hanzihub.build_web as bw

# raw zh-pron Min parameters as the snapshot stores them (trimmed)
EAT = [{"mn": "ml,jj,ly,tw:si̍t/xm,zz:se̍k", "mn-t": "sig8",
        "mn_note": "si̍t - vernacular (Xiamen, Zhangzhou), literary (Quanzhou, Jinjiang, Taiwan); se̍k - literary"},
       {"mn": "xm:sū", "mn-t": "se6"},
       {"mn": "ml,jj,dh,tp,kh,tn,tc,hc,lk,km,mg,pn,sg,ph:chia̍h/sx,yl:chiā/ly:chǎ", "mn-t": "ziah8"}]
SKY = [{"mn": "ml,jj,tw,sg:thiⁿ/ml,jj,tw,sg:thian/ha:then", "mn-t": "tin1/tiêng1/tiang1",
        "mn-t_note": "tin1 - vernacular; tiêng1/tiang1 - literary (tiêng1 - Chaozhou)",
        "mn_note": "thiⁿ - vernacular; thian/then - literary"}]
YOU = [{"mn": "xm,zz,kh,tn,tc,yl,hc,ph,sg:lí/qz,dh,lk,sx,km,hc,sg:lír/tp,mg,sg,pn:lú/ní", "mn-t": "le2",
        "mn_note": "lí/lír/lú - vernacular; ní - literary"}]
CHICKEN = [{"mn": "xm,qz,jj,tp,lk,km,mg,hc,sg,ph:koe/ml,jj,zp,yl,tn,kh,tc,pn:ke/sx:kere", "mn-t": "goi1",
            "mn_note": "Xiamen, Quanzhou: koe - vernacular; ke - literary"}]
GO = [{"mn": "xm,zz,jj,kh,tn,yl,hc,tc,ph:khì/qz,lk,sx,km,hc:khìr/xm,tp,mg:khù", "mn-t": "ke3/ku3",
       "mn-t_note": "ke3 - Chaozhou, Chenghai, Shantou, Jieyang, Pontianak; ku3 - Chaoyang, Puning, Huilai"}]


def test_note_label_per_place():
    # si̍t is vernacular in Xiamen but literary in Taiwan
    assert bw.min_note_info(EAT[0]["mn_note"], bw.TW_PLACES)["si̍t"]["k"] == "l"


def test_note_scoped_to_other_places_drops_labels():
    info = bw.min_note_info(CHICKEN[0]["mn_note"], bw.TW_PLACES)
    assert info["koe"]["k"] == "" and info["ke"]["k"] == ""


def test_taiwanese_everyday_reading_leads():
    assert bw.taiwanese_readings(EAT)[:2] == [("chia̍h", ""), ("si̍t", "l")]
    assert bw.taiwanese_readings(SKY) == [("thiⁿ", "v"), ("thian", "l")]   # no Hainan then


def test_taiwanese_city_only_variants_last():
    assert [r for r, _ in bw.taiwanese_readings(YOU)] == ["lí", "ní", "lír", "lú"]
    assert [r for r, _ in bw.taiwanese_readings(CHICKEN)][0] == "ke"


def test_swatow_drops_other_places():
    assert bw.swatow_readings(SKY) == [("tin1", "v"), ("tiang1", "l")]     # not Chaozhou tiêng1
    assert bw.swatow_readings(GO) == [("ke3", "")]                         # not Chaoyang ku3


def test_swatow_follows_the_taiwanese_etymology():
    # the zh-pron holding chia̍h holds ziah8: the everyday reading leads
    assert [r for r, _ in bw.swatow_readings(EAT)] == ["ziah8", "sig8", "se6"]


@pytest.mark.parametrize("ipa, pengim", [
    ("kʰɯ˨˩˧", "ke3"), ("tʰĩ˧˧", "tin1"), ("poiʔ˨", "boih4"), ("kuaŋ˧˧", "guang1"),
    ("t͡siaʔ˦", "ziah8"), ("ŋo˥˨", "ngo2"), ("sik˦", "sig8"), ("ᵐbue˥˥", "bhuê5"),
])
def test_shantou_ipa_to_pengim(ipa, pengim):
    assert bw.shantou_ipa_to_pengim(ipa) == pengim


@pytest.mark.parametrize("ipa, pengim", [
    ("tʰieŋ˧˧˨", "tiêng1"), ("tsə˧˧˨", "ze1"), ("tɛŋ˧˧˨", "dêng1"), ("siaŋ˧˧˨", "siang1"),
    ("kʰək˨", "keg4"), ("hiɜp˥˦", "hiêb8"),
])
def test_chaozhou_pengim(ipa, pengim):
    assert bw.chaozhou_pengim(ipa) == pengim


def test_xlsx_to_pengim():
    assert bw.xlsx_to_pengim("heng5") == "hêng5"
    assert bw.xlsx_to_pengim("hau2") == "hao2"
    assert bw.xlsx_to_pengim("ho2?") == ""


def test_teochew_audio_only_for_chaozhou_syllables(monkeypatch):
    monkeypatch.setattr(bw, "CZ_SYLLABLES", {"tiêng1", "siang1", "ke3"})
    assert bw._audio_key("Teochew", "tiang1") == ""          # Swatow-only: no recording
    assert bw._audio_key("Teochew", "siang1").startswith("m:")
    assert bw._audio_key("Teochew", "ke3").startswith("m:")
    assert bw._audio_key("Teochew", "tin1").startswith("m:")   # filter is for -iang/-uang only


@pytest.mark.parametrize("rom, ok", [("thiⁿ", True), ("ngó͘", True), ("chia̍h", True),
                                     ("tʰĩ˥", False), ("", False), ("ka˥", False)])
def test_is_poj(rom, ok):
    assert bw.is_poj(rom) is ok


def test_hokkien_nasal_readings_get_audio():
    assert bw._audio_key("Hokkien", "thiⁿ") == "h:thinn"
    assert bw._audio_key("Hokkien", "góa") == "h:guá"


EARTH = [{"mn": "xm,qz,jj,tp,lk,km,mg,hc,tc,ph:tōe/ml,jj,kh,tn,yl,ph:tē/lk:tǒe/sx:tēre/tī", "mn-t": "di7",
          "mn_note": "Xiamen, Quanzhou, Jinjiang, Philippines: tōe - vernacular; tē - literary\n"
                     "Zhangzhou, Taiwan: tē/tōe/tǒe/tēre - literary\n"
                     "Other readings: tī - vernacular (may be considered literary, only used in {{zh-l|*土地公}})"},
         {"mn": "ml:tē", "mn-t": "di7"},
         {"mn": "xm,zz,tw:tè/qz:tèr", "mn-t": "do3"}]


def test_note_scopes_each_line():
    info = bw.min_note_info(EARTH[0]["mn_note"], bw.TW_PLACES)
    assert info["tē"]["k"] == "l" and info["tōe"]["k"] == "l"     # the Taiwan line
    assert info["tī"]["k"] == "v" and info["tī"]["rare"]           # "Other readings:"


def test_min_only_word_does_not_lead():
    # 地 tè is 塊 "place" written 地: the main etymology's tōe / tē lead
    tw = bw.taiwanese_readings(EARTH)
    assert [r for r, _ in tw[:2]] == ["tōe", "tē"] and tw[-1][0] == "tī"
