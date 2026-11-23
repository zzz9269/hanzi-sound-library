"""Export the dataset as static JSON for the web app in ``web/``.

    python -m hanzihub.build_web            # → web/data/

The web app is a static PWA (GitHub Pages): no server, so everything the UI
shows per character is PRE-COMPUTED here with the same display logic the
Streamlit app uses at request time — Chao tone letters, ≈ English
approximations, Taiwanese Hokkien and Swatow Teochew selection, fanqie / MC-position breakdowns, the
mogher.com recording file for Teochew readings and the tâi-lô for ithuan.tw
Hokkien audio. The browser only fetches one small shard per lookup.

Layout of ``web/data/``::

    meta.json            columns, sections, labels, shard scheme, build info
    c/<hex>.json         {char: entry} for code points (cp >> 8) == hex
    p/<hex>.json         provenance rows {char: [[col, reading, source, conf]]}
    s/en/<a>.json        English word → [chars]          (first letter a–z)
    s/rd/<a>.json        reading key → [[char, colIdx]]   (first letter)
    s2t.json             simplified → traditional (single chars)
    poems.json, passages.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

from . import appkit as ak
from . import paths
from .sources import unihan_readings, wiktionary_zhpron

OUT = paths.ROOT / "web" / "data"

SINITIC = ["Mandarin", "Cantonese", "Hokkien", "Teochew", "Eastern Min (Fuzhou)",
           "Northern Min (Jian'ou)", "Hainanese (Haikou)", "Hakka", "Wu",
           "Hui (Shexian)", "Gan", "Xiang", "Jin"]
HIST = ["Old Chinese", "Old Chinese (Zhengzhang)", "Proto-Min", "Middle Chinese",
        "Middle Chinese (Baxter)", "Middle Chinese (position)", "Fanqie", "Tang"]
SINO = ["Japanese", "Japanese On", "Japanese Kun", "Okinawan", "Korean (Hangul)",
        "Korean (romanized)", "Vietnamese", "Zhuang"]

# label, native name, romanisation scheme shown under the label, audio kind
COLUMN_INFO = {
    "Mandarin": ("Mandarin", "普通話", "Pinyin", "tts:zh-CN"),
    "Cantonese": ("Cantonese", "粵語", "Jyutping", "tts:zh-HK"),
    "Hokkien": ("Taiwanese Hokkien", "臺語", "Pe̍h-ōe-jī", "ithuan"),
    "Teochew": ("Teochew (Swatow)", "潮州話 · 汕頭", "Peng'im", "mogher"),
    "Eastern Min (Fuzhou)": ("Fuzhou", "福州話", "Foochow Romanized", ""),
    "Northern Min (Jian'ou)": ("Jian'ou", "建甌話", "Kienning Colloquial", ""),
    "Hainanese (Haikou)": ("Hainanese", "海南話", "IPA · Haikou", ""),
    "Hakka": ("Hakka", "客家話", "Pha̍k-fa-sṳ", ""),
    "Wu": ("Wu", "吳語", "Wugniu · Shanghai", ""),
    "Hui (Shexian)": ("Hui", "徽語", "IPA · Shexian", ""),
    "Gan": ("Gan", "贛語", "Nanchang", ""),
    "Xiang": ("Xiang", "湘語", "Changsha", ""),
    "Jin": ("Jin", "晉語", "Taiyuan", ""),
    "Old Chinese": ("Old Chinese", "上古漢語", "Baxter–Sagart 2014", ""),
    "Old Chinese (Zhengzhang)": ("Old Chinese", "上古漢語", "Zhengzhang Shangfang", ""),
    "Proto-Min": ("Proto-Min", "原始閩語", "comparative reconstruction", ""),
    "Middle Chinese": ("Middle Chinese", "中古漢語", "Baxter transcription", ""),
    "Middle Chinese (Baxter)": ("Middle Chinese", "中古漢語", "IPA", ""),
    "Middle Chinese (position)": ("Rime position", "音韻地位", "initial · grade · rime · tone", ""),
    "Fanqie": ("Fanqie", "反切", "Guangyun spelling", ""),
    "Tang": ("Late Middle Chinese", "唐代", "Tang reading", ""),
    "Japanese": ("Japanese", "日本語", "kana", "tts:ja-JP"),
    "Japanese On": ("On'yomi", "音読み", "romaji", ""),
    "Japanese Kun": ("Kun'yomi", "訓読み", "romaji", ""),
    "Okinawan": ("Okinawan", "沖縄語", "kana", ""),
    "Korean (Hangul)": ("Korean", "한국어", "Hangul", "tts:ko-KR"),
    "Korean (romanized)": ("Korean", "한국어", "Yale", ""),
    "Vietnamese": ("Vietnamese", "Tiếng Việt", "Hán-Việt", "tts:vi-VN"),
    "Zhuang": ("Zhuang", "Vahcuengh", "Sawndip", ""),
}
# romanisation scheme for ≈ English / Chao conversion of Wiktionary readings
ROM_SCHEME = {**ak.ROM_SCHEME, "Cantonese": "jyutping"}
KEEP_NATIVE_TONES = {"Mandarin", "Cantonese"}      # pinyin / jyutping as written
TOKEN_SPLIT_COLS = {"Japanese", "Japanese On", "Japanese Kun", "Korean (Hangul)",
                    "Korean (romanized)", "Vietnamese"}
_HAN_NOTE = re.compile(r"\s*\([^)]*[㐀-鿿][^)]*\)")
_ALT_SPLIT = re.compile(r"\s*[|/]\s*")
_KANA = re.compile(r"[぀-ヿㇰ-ㇿ]")


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").replace("≈", "").strip()


# --- Hokkien POJ → Tâi-lô (the spelling ithuan.tw's synthesiser reads) -----
_POJ_TONE_MARKS = "\u0300\u0301\u0302\u0304\u0306\u030c\u030d"
_POJ_RE = re.compile(r"[A-Za-z\u0300-\u036fⁿ-]+")


def is_poj(s: str) -> bool:
    """A POJ / Tâi-lô spelling (Latin letters, tone marks, ⁿ, o͘), not IPA."""
    return bool(s) and bool(_POJ_RE.fullmatch(unicodedata.normalize("NFD", s)))


def _tailo_syllable(syl: str) -> str:
    nfd = unicodedata.normalize("NFD", syl)
    nfd = re.sub(r"([oO])([\u0300-\u0357\u0359-\u036f]*)\u0358", r"\1\2o", nfd)   # o͘ → oo
    tone = next((c for c in nfd if c in _POJ_TONE_MARKS), "")
    t = "".join(c for c in nfd if not unicodedata.combining(c))
    t = t.replace("ⁿ", "nn")
    for a, b in (("chh", "tsh"), ("Chh", "Tsh"), ("ch", "ts"), ("Ch", "Ts"),
                 ("oa", "ua"), ("oe", "ue"), ("eng", "ing"), ("ek", "ik")):
        t = t.replace(a, b)
    if not tone:
        return unicodedata.normalize("NFC", t)
    # Tâi-lô puts the mark on a, else the first o of oo, else e / o, else
    # the second of iu / ui, else the lone i / u, else syllabic m / n(g)
    low = t.lower()
    vowels = [i for i, c in enumerate(low) if c in "aeiou"]
    if "a" in low:
        at = low.index("a")
    elif "oo" in low:
        at = low.index("oo")
    elif any(c in low for c in "eo"):
        at = min(low.index(c) for c in "eo" if c in low)
    elif vowels:
        at = vowels[-1]
    else:
        at = next((i for i, c in enumerate(low) if c in "mn"), 0)
    return unicodedata.normalize("NFC", t[:at + 1] + tone + t[at + 1:])


def poj_to_tailo(s: str) -> str:
    """POJ (``góa``, ``ngó͘``, ``thiⁿ``, ``chhiū``) → Tâi-lô (``guá``,
    ``ngóo``, ``thinn``, ``tshiū``), tone mark moved to where Tâi-lô puts it."""
    s = unicodedata.normalize("NFC", s or "")
    return "-".join(_tailo_syllable(x) for x in s.split("-"))


_YUE_INITIALS = [("t͡sʰ", "c"), ("t͡s", "z"), ("kʷʰ", "kw"), ("kʷ", "gw"), ("pʰ", "p"),
                 ("tʰ", "t"), ("kʰ", "k"), ("p", "b"), ("t", "d"), ("k", "g"), ("ŋ", "ng"),
                 ("m", "m"), ("n", "n"), ("l", "l"), ("f", "f"), ("h", "h"), ("s", "s"),
                 ("j", "j"), ("w", "w")]
_YUE_RHYME = [("aː", "aa"), ("ɛː", "e"), ("iː", "i"), ("ɔː", "o"), ("uː", "u"), ("œː", "oe"),
              ("yː", "yu"), ("ɐ", "a"), ("ɪ", "i"), ("ʊ", "u"), ("ɵ", "eo"), ("i̯", "i"),
              ("u̯", "u"), ("y̯", "i"), ("ŋ", "ng")]
_YUE_TONE = {"˥": 1, "˥˥": 1, "˥˧": 1, "˧˥": 2, "˧": 3, "˧˧": 3, "˨˩": 4, "˩": 4, "˩˩": 4,
             "˩˧": 5, "˨˧": 5, "˨": 6, "˨˨": 6}


def yue_ipa_to_jyutping(ipa: str) -> str:
    """Guangzhou IPA syllable ('hɔːŋ˨˩', 't͡sʰœːŋ˧˥') -> Jyutping ('hong4',
    'coeng2'); "" when it isn't a clean single syllable."""
    m = re.fullmatch(r"([^˥˦˧˨˩]+)([˥˦˧˨˩]+)", (ipa or "").strip().replace("̚", ""))
    if not m or m.group(2) not in _YUE_TONE:
        return ""
    seg, tone = m.group(1), _YUE_TONE[m.group(2)]
    if seg in ("ŋ̩", "m̩"):
        return ("ng" if seg == "ŋ̩" else "m") + str(tone)
    ini = ""
    for a, b in _YUE_INITIALS:
        if seg.startswith(a) and len(seg) > len(a):
            ini, seg = b, seg[len(a):]
            break
    for a, b in _YUE_RHYME:
        seg = seg.replace(a, b)
    if not re.fullmatch(r"(aa|a|e|i|o|u|oe|eo|yu)(i|u)?(m|n|ng|p|t|k)?", seg):
        return ""
    if seg[-1] in "ptk" and tone not in (1, 3, 6):
        return ""
    return f"{ini}{seg}{tone}"


# --- Min: Taiwanese Hokkien and Swatow (Shantou) Teochew --------------------
# Wiktionary's zh-pron tags Min readings by place: Hokkien ``mn=`` groups are
# ``codes:reading`` (tw = Taiwan general, tp Taipei, kh Kaohsiung …; xm Xiamen,
# qz Quanzhou, zz Zhangzhou …), and the Teochew ``mn-t_note`` says which
# readings are Chaozhou-city-only, Chaoyang-only and so on. Both notes also say
# which readings are vernacular (白) and which literary (文).
TW_CODES = {"tp", "kh", "tn", "tc", "yl", "hc"}          # major Taiwanese cities
TW_PLACES = ("taiwan", "taipei", "kaohsiung", "tainan", "taichung", "yilan", "hsinchu")
TEO_PLACES = ("chaozhou", "shantou", "swatow", "jieyang", "chenghai", "chaoyang", "puning",
              "huilai", "raoping", "chao'an", "chaoan", "nan'ao", "nanao", "haimen", "dahao",
              "pontianak", "bangkok", "singapore", "malaysia", "thailand", "kuching")
HOK_PLACES = ("xiamen", "amoy", "quanzhou", "zhangzhou", "jinjiang", "penang", "manila",
              "philippines", "medan", "lukang", "sanxia", "kinmen", "magong", "zhangpu")
SWATOW = ("shantou", "swatow")
_DASH = r"\s[-–—]\s"


def _split_top(s: str, sep: str = ";") -> list[str]:
    parts, depth, cur = [], 0, []
    for c in s:
        depth += c in "([{"
        depth -= c in ")]}" and depth > 0
        if c == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def min_note_info(note: str, home: tuple[str, ...]) -> dict[str, dict]:
    """``{reading: {"k": "v"|"l"|"", "places": set, "rare": bool}}`` from a
    zh-pron Min note such as ``"tin1 - vernacular; tiêng1/tiang1 - literary
    (tiêng1 - Chaozhou)"``. ``home`` are the place names this app reads for:
    a line scoped to other places (``"Xiamen, Quanzhou: koe - vernacular; ke
    - literary"``) doesn't label readings. ``rare`` marks readings the note
    limits to one word (地 ``tī - … only used in 土地公``)."""
    info: dict[str, dict] = {}
    if not note:
        return info

    def places(text: str) -> set:
        low = text.lower()
        return {p for p in TEO_PLACES + TW_PLACES + HOK_PLACES if p in low}

    note = unicodedata.normalize("NFC", note)
    for line in re.split(r"\n|<br\s*/?>", note):
        rare_line = bool(re.search(r"\bonly (?:used )?in\b", line))
        line = re.sub(r"\{\{[^{}]*\}\}", "", line)
        # a leading "Place, Place:" scopes the line to those places
        scope = re.match(r"^\s*([A-Z][A-Za-z' ]*(?:,\s*[A-Z][A-Za-z' ]*)*):", line)
        use_labels = True
        if scope:
            if places(scope.group(1)):
                use_labels = any(h in scope.group(1).lower() for h in home)
            line = line[scope.end():]                 # ("Other readings:" scopes nothing)
        _note_clauses(line, home, use_labels, rare_line, places, info)
    return info


def _note_clauses(note, home, use_labels, rare_line, places, info):
    for clause in _split_top(note, ";"):
        m = re.match(rf"(.+?){_DASH}(.*)$", clause, re.S)
        if not m:
            continue
        left, right = m.group(1).rsplit(":", 1)[-1], m.group(2)
        subs = re.findall(rf"\(([^()]*?){_DASH}([^()]*)\)", right)
        top = re.sub(rf"\([^()]*?{_DASH}[^()]*\)", "", right)
        # "vernacular (Xiamen, Zhangzhou), literary (Quanzhou, Taiwan)": the
        # stratum differs by place, so take the one naming a home place
        segs = [("l" if s.lower() == "literary" else "v", places(p or ""))
                for s, p in re.findall(r"(vernacular|colloquial|literary)\s*(?:\(([^()]*)\))?",
                                       top, re.I)]
        k = ""
        if len(segs) == 1:
            k = segs[0][0]
        elif segs:
            k = next((s for s, ps in segs if ps & set(home)),
                     next((s for s, ps in segs if not ps), ""))
        rare = rare_line and bool(re.search(r"\bonly (?:used )?in\b", clause))
        for r in (x.strip() for x in re.split(r"[/,]", left)):
            if r:
                d = info.setdefault(r, {"k": "", "places": set(), "rare": False})
                if use_labels and k:
                    d["k"] = k
                d["places"] |= places(top)
                d["rare"] |= rare
        for sub_left, sub_right in subs:
            for r in (x.strip() for x in re.split(r"[/,]", sub_left)):
                if r:
                    info.setdefault(r, {"k": "", "places": set(), "rare": False})["places"] |= places(sub_right)


def _min_groups(val: str):
    """``[(codes, reading)]`` from a zh-pron Min value (``tw,kh:kiâⁿ/hêng``)."""
    out = []
    for g in (val or "").split("/"):
        g = g.strip()
        if not g:
            continue
        codes, rd = (g.split(":", 1) if ":" in g else ("", g))
        codes = {c.strip() for c in codes.split(",") if c.strip()}
        for r in ([rd] if codes else rd.split(",")):
            r = unicodedata.normalize("NFC", r.split(">")[0].strip())
            if r and "=" not in r and not _HAN_CHAR.search(r):
                out.append((codes, r))
    return out


def taiwanese_readings(min_raw: list[dict]) -> list[tuple[str, str]]:
    """Taiwanese Hokkien readings ``[(poj, "v"|"l"|"")]`` from the raw Min
    parameters of every zh-pron on a page: readings tagged for Taiwan (or
    untagged, i.e. general), most widely used first, vernacular before
    literary as Wiktionary orders them. ``[]`` when none apply to Taiwan."""
    found = []                           # (reading, label, score, order, wide)
    for ti, t in enumerate(min_raw or []):
        info = min_note_info(t.get("mn_note", ""), TW_PLACES)
        groups = _min_groups(t.get("mn", ""))
        mixed = any(codes for codes, _ in groups)
        for codes, r in groups:
            # untagged = general; but an untagged reading listed beside
            # place-tagged ones (你 …/lú/ní) is not the main one, and one in
            # a later etymology (王 ōng "to rule", 樂 ngāu) yields to the main
            # etymology's Taiwanese reading
            score = ((3 if mixed else 6 if ti == 0 else 4) if not codes
                     else (5 if "tw" in codes else 0) + len(codes & TW_CODES))
            if info.get(r, {}).get("rare"):
                score = min(score, 1)
            # heard across Taiwan by name: untagged alone, or 3+ cities listed
            wide = (not codes and not mixed) or len(codes & TW_CODES) >= 3
            if score > 0 and r not in (x[0] for x in found):
                found.append((r, info.get(r, {}).get("k", ""), score, len(found), wide))
    # Wiktionary's order, grouped by label; readings heard in only one or two
    # Taiwanese cities (你 Taipei lú, Hsinchu lír) come last. When the main
    # etymology is literary in Taiwan, an everyday reading Wiktionary lists
    # for city after city leads instead (食 chia̍h before si̍t), but not a
    # Min-only word merely tagged "Taiwan" (地 tè, an alternative form of 塊).
    groups = list(dict.fromkeys([x[1] for x in found if x[2] >= 3]
                                + [x[1] for x in found]))
    if len(groups) > 1 and groups[0] == "l":
        nxt = next((x for x in found if x[1] == groups[1] and x[2] >= 3), None)
        if nxt and nxt[4]:
            groups[0], groups[1] = groups[1], groups[0]
    found.sort(key=lambda x: (x[2] < 3, groups.index(x[1]), -x[2], x[3]))
    return [(x[0], x[1]) for x in found]


def swatow_readings(min_raw: list[dict]) -> list[tuple[str, str]]:
    """Swatow (Shantou) Teochew readings ``[(pengim, "v"|"l"|"")]``: drops the
    readings Wiktionary's note limits to other places (Chaozhou city's
    -iêng/-uêng, Chaoyang's -u for -e …). Falls back to every reading when
    the note would leave none.

    Teochew readings are rarely labelled, so the zh-pron holding the leading
    Taiwanese reading goes first: each zh-pron is one etymology or stratum
    across Min, so 食's chia̍h sits with ziah8 and 人's lâng with nang5, and
    the everyday reading leads in Teochew too."""
    raw = list(min_raw or [])
    tw = taiwanese_readings(raw)
    if tw:
        lead = next((i for i, t in enumerate(raw)
                     if any(r == tw[0][0] for _, r in _min_groups(t.get("mn", "")))), 0)
        raw.insert(0, raw.pop(lead))
    every, kept = [], []
    for t in raw:
        info = min_note_info(t.get("mn-t_note", ""), SWATOW)
        for _, r in _min_groups(t.get("mn-t", "")):
            if r in (x[0] for x in every):
                continue
            d = info.get(r, {"k": "", "places": set(), "rare": False})
            every.append((r, d["k"]))
            if not d["places"] or any(p in d["places"] for p in SWATOW):
                kept.append((r, d["k"]))
    return kept or every


# Shantou dialect-survey IPA → Peng'im, for characters Wiktionary lacks
_TEO_INITIALS = [("t͡ɕʰ", "c"), ("tɕʰ", "c"), ("t͡ɕ", "z"), ("tɕ", "z"), ("d͡ʑ", "r"), ("dʑ", "r"),
                 ("ɕ", "s"), ("ᵐb", "bh"), ("ᵑg", "gh"),
                 ("t͡sʰ", "c"), ("tsʰ", "c"), ("t͡s", "z"), ("ts", "z"), ("d͡z", "r"),
                 ("dz", "r"), ("pʰ", "p"), ("tʰ", "t"), ("kʰ", "k"), ("p", "b"), ("t", "d"),
                 ("k", "g"), ("b", "bh"), ("g", "gh"), ("ŋ", "ng"), ("m", "m"), ("n", "n"),
                 ("l", "l"), ("s", "s"), ("z", "r"), ("h", "h")]
_TEO_TONES_OPEN = {"˧": 1, "˧˧": 1, "˥˨": 2, "˥˧": 2, "˥˧˨": 2, "˨˩˧": 3, "˨˩˨": 3, "˨˩˧˨": 3,
                   "˥": 5, "˥˥": 5, "˧˥": 6, "˨˥": 6, "˩": 7, "˩˩": 7, "˨˩": 7, "˨˨": 7, "˨": 7}
_TEO_TONES_CHECKED = {"˨": 4, "˧˨": 4, "˨˩": 4, "˩": 4, "˧": 4,
                      "˦": 8, "˥": 8, "˥˦": 8, "˦˥": 8}


def shantou_ipa_to_pengim(ipa: str) -> str:
    """Shantou IPA syllable (``kʰɯ˨˩˧``, ``tʰĩ˧˧``, ``poiʔ˨``) → Peng'im
    (``ke3``, ``tin1``, ``boih4``); ``""`` if it doesn't parse cleanly."""
    m = re.fullmatch(r"([^˥˦˧˨˩]+)([˥˦˧˨˩]+)", unicodedata.normalize("NFD", (ipa or "").strip())
                     .replace("̚", "").replace("͡", "͡"))
    if not m:
        return ""
    seg, contour = unicodedata.normalize("NFC", m.group(1)).replace("ɡ", "g"), m.group(2)
    nasal = "̃" in unicodedata.normalize("NFD", seg)
    seg = unicodedata.normalize("NFC", unicodedata.normalize("NFD", seg).replace("̃", ""))
    seg = seg.replace("̩", "").replace("̍", "")        # syllabic marks
    if seg in ("m", "ŋ"):
        ini, rime = "", seg
    else:
        ini = ""
        for a, b in _TEO_INITIALS:
            if seg.startswith(a) and len(seg) > len(a):
                ini, seg = b, seg[len(a):]
                break
        rime = seg
    coda = ""
    for a, b in (("ŋ", "ng"), ("m", "m"), ("p", "b"), ("k", "g"), ("ʔ", "h")):
        if rime.endswith(a) and len(rime) > len(a):
            rime, coda = rime[:-len(a)], b
            break
    rime = rime.replace("ɯ", "E").replace("e", "ê").replace("E", "e").replace("au", "ao")
    if rime in ("m", "ŋ"):
        rime = "ng" if rime == "ŋ" else "m"
    if not re.fullmatch(r"(i|u)?(a|o|ê|e|i|u)(i|o|u)?", rime) and rime not in ("m", "ng"):
        return ""
    checked = coda in ("b", "g", "h")
    tone = (_TEO_TONES_CHECKED if checked else _TEO_TONES_OPEN).get(contour)
    if not tone:
        return ""
    return f"{ini}{rime}{'n' if nasal and not coda else ''}{coda}{tone}"


def xlsx_to_pengim(r: str) -> str:
    """The Teochew spreadsheet's spelling → Peng'im where it is unambiguous:
    it writes ``e`` for ê and ``au`` for ao (it also writes ``u`` for the ɯ
    vowel, which can't be told apart from u, so that stays)."""
    r = (r or "").strip()
    if not re.fullmatch(r"[a-z]+[1-8]", r):
        return ""
    return r.replace("e", "ê").replace("au", "ao")


def _drop_chaozhou_doublets(xs: list[str], pat: str, repl: str) -> list[str]:
    """Drop Chaozhou-city -iêng/-uêng (IPA -ieŋ/-ueŋ) forms when the Swatow
    -iang/-uang counterpart is also listed (the survey data mixes both)."""
    return [x for x in xs if not (re.search(pat, x) and re.sub(pat, repl, x) in xs)]


def min_column(col, zh, bucket, ds_roms, wikt_roms):
    """Readings for Hokkien (Taiwanese) or Teochew (Swatow):
    ``(picked, local_ipa, unverified)`` where ``picked`` is
    ``[(reading, ml, "v"|"l"|"")]`` or ``None`` to keep the generic readings,
    and ``local_ipa`` the Taipei / Shantou survey IPA for the IPA line."""
    raw = (zh or {}).get("_min") or []
    if col == "Hokkien":
        loc = [a for a in _alts(bucket.get("dial:Min-Taipei", "")) if ak.has_ipa(a)]
        picked = taiwanese_readings(raw)
        return ([(r, False, k) for r, k in picked] if picked else None,
                list(dict.fromkeys(loc)), False)
    loc = [a for a in _alts(bucket.get("dial:Min-Shantou", "")) if ak.has_ipa(a)]
    loc = _drop_chaozhou_doublets(list(dict.fromkeys(loc)), r"([iu])e(ŋ|k)", r"\1a\2")
    picked = swatow_readings(raw)
    if picked:
        return [(r, False, k) for r, k in picked], loc, False
    conv = [c for c in dict.fromkeys(shantou_ipa_to_pengim(a) for a in loc) if c]
    conv = _drop_chaozhou_doublets(conv, r"([iu])ê(ng|g)", r"\1a\2")
    if conv:
        return [(c, False, "") for c in conv], loc, False
    xl = [(xlsx_to_pengim(r), ml, "") for r, ml in ds_roms if xlsx_to_pengim(r)]
    return (xl, loc, True) if xl else ([], loc, False)


# Teochew syllables that exist in Chaozhou city, where mogher.com's recordings
# come from. Swatow -iang/-uang/-iag/-uag often stand where Chaozhou says
# -iêng/-uêng/-iêg/-uêg (天 tiang1 ~ tiêng1, 關 guang1 ~ guêng1), and mogher
# has no file for those, so such readings get no play button rather than a
# silent one. ``None`` = unknown, don't filter.
CZ_SYLLABLES: set | None = None
# Chaozhou dialect-survey tone contours → the Shantou ones shantou_ipa_to_pengim
# reads (checked against Wiktionary's Peng'im: 97-99% per tone)
_CZ_TONE = {"˧˧˨": "˧", "˥˨": "˥˨", "˨˩˧": "˨˩˧", "˨": "˨", "˥˥˦": "˥", "˨˥": "˧˥",
            "˨˩": "˩", "˥˦": "˦"}
_CZ_VOWEL = str.maketrans({"ə": "ɯ", "ɛ": "e", "ɜ": "e"})


def chaozhou_pengim(ipa: str) -> str:
    """Chaozhou survey IPA (``tʰieŋ˧˧˨``, ``tsə˧˧˨``) → Peng'im (``tiêng1``,
    ``ze1``); ``""`` if it doesn't parse."""
    m = re.fullmatch(r"(.+?)([˥˦˧˨˩]+)", (ipa or "").strip())
    if not m or m.group(2) not in _CZ_TONE:
        return ""
    return shantou_ipa_to_pengim(m.group(1).translate(_CZ_VOWEL) + _CZ_TONE[m.group(2)])


def chaozhou_syllables(data: dict) -> set:
    return {p for bucket in data.values()
            for a in _alts(bucket.get("dial:Min-Chaozhou", ""))
            if (p := chaozhou_pengim(a))}


# Per-syllable recordings hosted with the app (web/audio/):
#   cmn/  Mandarin, hugolpz/audio-cmn "syllabs v.2" (speaker Chen Wang, CC BY-SA)
#   vie/  Vietnamese, Lingua Libre recordings by a Hanoi speaker
#         ("Penn Zero MSSJ", CC0, via Wikimedia Commons).
#         Southern-speaker recordings are left out: the readings are Northern.
# See web/audio/CREDITS.md. A syllable with no recording gets no key.
AUDIO_DIR = Path(__file__).resolve().parent.parent / "web" / "audio"
_TONE_MARK = {"\u0304": "1", "\u0301": "2", "\u030C": "3", "\u0300": "4"}


def _audio_files(sub: str) -> set:
    d = AUDIO_DIR / sub
    return {f.name for f in d.iterdir()} if d.is_dir() else set()


CMN_FILES = _audio_files("cmn")
VIE_FILES = _audio_files("vie")


def pinyin_numbered(py: str) -> str:
    """xíng → xing2, lǜ → lv4. "" for the neutral tone (no recording exists)
    or anything that is not one plain pinyin syllable."""
    s = unicodedata.normalize("NFD", py.strip().lower())
    tone = ""
    for m, t in _TONE_MARK.items():
        if m in s:
            tone = t
            s = s.replace(m, "")
    s = s.replace("u\u0308", "v").replace("\u0308", "")
    s = unicodedata.normalize("NFC", s).replace("ê", "e")
    return s + tone if tone and re.fullmatch(r"[a-z]+", s) else ""


def vie_file(syl: str) -> str:
    """The recording's file name for one Vietnamese syllable."""
    s = unicodedata.normalize("NFC", syl.strip().lower())
    return f"{s}.mp3" if re.fullmatch(r"[a-zà-ỹđ]+", s) else ""


def _audio_key(col: str, rom: str) -> str:
    if col == "Mandarin":
        n = pinyin_numbered(rom)
        return f"c:{n}" if n and f"cmn-{n}.mp3" in CMN_FILES else ""
    if col == "Vietnamese":
        f = vie_file(rom)
        return f"v:{f}" if f and f in VIE_FILES else ""
    if col == "Teochew" and re.fullmatch(r"[a-zê]+\d", rom):
        if CZ_SYLLABLES and re.search(r"[iu]a(ng|g)\d$", rom) and rom not in CZ_SYLLABLES:
            return ""
        f = ak.pengim_to_mogher_file(rom)
        return f"m:{f}" if f else ""
    if col == "Hokkien" and is_poj(rom):          # (ak.has_ipa counts ⁿ as IPA)
        return "h:" + poj_to_tailo(rom)
    return ""


def _reading(t, e="", ml=False, a="", k="", q=False):
    """One reading for the app: t display text, e ≈English, m machine-
    predicted, a audio key, k "v" vernacular / "l" literary, q unverified."""
    r = {"t": t}
    if e:
        r["e"] = e
    if ml:
        r["m"] = 1
    if a:
        r["a"] = a
    if k:
        r["k"] = k
    if q:
        r["q"] = 1
    return r


def _ipa_en(col, alt):
    if col == "Old Chinese":
        return ak.baxter_sagart_approx(alt)
    if col in ak.IPA_APPROX_COLS or col.startswith("dial:") or ak.has_ipa(alt):
        return ak.ipa_to_english(ak.tones_to_chao(alt, None if col.startswith("dial:") else col))
    return ""


def _alts(val):
    return [a.strip() for a in _ALT_SPLIT.split((val or "").strip()) if a.strip()]


MAX_ROMS = 6
CHANGED_TONE = re.compile(r"[a-z]+\d-\d")   # Jyutping 變音: jip6-2


def build_entry(ch, bucket, zh, meta, rank, data, colidx, prov_conf, uh=None):
    e = {}
    if bucket.get("Definition"):
        e["d"] = bucket["Definition"]
    m = meta.get(ch, {})
    k = [m.get("strokes") or 0, m.get("radical") or 0, rank or 0]
    if any(k):
        e["k"] = k
    v, ipa, notes, wik = {}, {}, {}, {}
    for col in SINITIC:
        val, rom_w = bucket.get(col, ""), (zh or {}).get(col, "")
        roms, ipas, ipa_raw = [], [], []
        for alt in _alts(val):
            ml = alt.endswith("[ML]")
            a = _HAN_NOTE.sub("", alt.removesuffix("[ML]")).strip()
            if not a:
                continue
            if ak.has_ipa(a):
                ipas.append(_reading(ak.tones_to_chao(a, col), _ipa_en(col, a), ml))
                ipa_raw.append((a, ml))
            else:
                roms.append((a, ml))
        scheme = ROM_SCHEME.get(col)
        ds_roms = list(roms)                     # the dataset's own (pre-Wiktionary)
        if rom_w:
            roms = [(r.strip(), False) for r in rom_w.split(" / ") if r.strip()]
            # Cantonese changed tones (變音, "jip6-2") are word-bound: Wiktionary's
            # zh-pron lists them without saying which words, so a bare
            # "jip6-2" chip reads like a second pronunciation. Leave them out.
            roms = [(r, ml) for r, ml in roms if not CHANGED_TONE.fullmatch(r)] or roms
            wik[colidx[col]] = 1
        # every reading, not just the main one: the dataset keeps a single
        # pinyin/jyutping per character (長 had zhǎng but not cháng)
        extra = []
        if col == "Mandarin" and uh:
            extra = [(r, False) for r in uh[0]]
        elif col == "Cantonese":
            extra = [(yue_ipa_to_jyutping(a), ml) for a, ml in ipa_raw]
            extra += [(r, False) for r in (uh[1] if uh else [])]
        have = {r for r, _ in roms}
        for r, ml in extra:
            if r and r not in have and len(roms) < MAX_ROMS:
                roms.append((r, ml))
                have.add(r)
        if col == "Mandarin" and uh and uh[0] and uh[0][0] in have:
            # kMandarin is Unihan's "most customary" reading: lead with it
            # (Wiktionary lists 的 as dì, dí, de, dī)
            roms.sort(key=lambda x: x[0] != uh[0][0])
        labels, unverified = {}, False
        if col in ("Hokkien", "Teochew"):
            picked, loc_ipa, unverified = min_column(col, zh, bucket, ds_roms, roms)
            if picked is not None:
                roms = [(r, ml) for r, ml, _ in picked]
                labels = {r: k for r, _, k in picked if k}
            if loc_ipa:
                ipas = [_reading(ak.tones_to_chao(a, col), _ipa_en(col, a)) for a in loc_ipa]
        roms = [(part, ml) for r, ml in roms
                for part in (r.split("/") if "/" in r and " " not in r else [r]) if part]
        out = []
        for r, ml in roms:
            disp = r if col in KEEP_NATIVE_TONES else ak.wikt_rom_to_chao(r, scheme)
            if col == "Teochew" and disp == r:
                disp = ak.tones_to_chao(r, col)
            en = ak.romanization_to_english(r, scheme) if scheme else ""
            audio = "" if unverified else _audio_key(col, r)
            out.append(_reading(disp, en, ml, audio, labels.get(r, ""), unverified))
        out = list({r["t"]: r for r in out}.values())
        ipas = list({r["t"]: r for r in ipas}.values())
        if out:
            v[colidx[col]] = out
        if ipas:
            ipa[colidx[col]] = ipas
        # (no tone-sandhi hints: the app reads Min syllable by syllable in
        # citation tones; positional sandhi was not reliable enough to show)
    for col in HIST + SINO + ["Definition"]:
        if col == "Definition" or not bucket.get(col):
            continue
        val = bucket[col]
        if col in TOKEN_SPLIT_COLS:
            alts = ak.split_opts(val)
        elif col in ("Middle Chinese (position)", "Fanqie"):
            alts = _alts(val) if col != "Fanqie" else ak.split_opts(val)
        else:
            alts = _alts(val)
        out = []
        for alt in alts:
            ml = alt.endswith("[ML]")
            a = alt.removesuffix("[ML]").strip()
            if col in ("Japanese On", "Japanese Kun", "Korean (romanized)"):
                a = a.lower()
            if col == "Old Chinese (Zhengzhang)":
                # ytenx spells Zhengzhang's aspirated s (清母 *sʰ-) "sh": 雎 *sʰa,
                # not an English "sh". He has no ʃ in Old Chinese.
                a = a.replace("sh", "sʰ")
            disp = ak.tones_to_chao(a, col)
            en = _ipa_en(col, a) if col not in SINO else ""
            out.append(_reading(disp, en, ml, _audio_key(col, a) if col == "Vietnamese" else ""))
        out = list({r["t"]: r for r in out}.values())
        if out:
            v[colidx[col]] = out
        if col == "Fanqie":
            lines = []
            target_mc = bucket.get("Middle Chinese", "")
            for pair in ak.parse_fanqie_pairs(val)[:3]:
                info = ak.fanqie_explain(pair, data.get(pair[0], {}).get("Middle Chinese", ""),
                                         data.get(pair[1], {}).get("Middle Chinese", ""),
                                         target_mc)
                if info:
                    lines.append({"u": info["upper"], "l": info["lower"],
                                  "i": info["initial"], "f": info["final"],
                                  "tone": info["tone"], "c": info["composed"],
                                  "ok": 1 if info["matches"] else 0})
            if lines:
                notes[colidx[col]] = lines
        if col == "Middle Chinese (position)":
            codes = _alts(val)
            mc_ipas = _alts(bucket.get("Middle Chinese (Baxter)", ""))
            lines = []
            for i, code in enumerate(codes):
                mc_ipa = (mc_ipas[i] if len(mc_ipas) == len(codes)
                          else mc_ipas[0] if len(mc_ipas) == 1 else "")
                parts = ak.mc_position_breakdown(code, mc_ipa)
                if parts:
                    lines.append({"code": code, "syl": ak.mc_readable_syllable(code, mc_ipa),
                                  "parts": [[g, x] for g, x in parts]})
            if lines:
                notes[colidx[col]] = lines
    if ch in prov_conf:
        notes[colidx["Proto-Min"]] = [{"conf": round(prov_conf[ch], 2)}]
    loc = {}
    for col, val in bucket.items():
        if col.startswith("dial:") and val:
            loc[colidx[col]] = [_reading(ak.tones_to_chao(a), ak.ipa_to_english(ak.tones_to_chao(a)))
                                for a in _alts(val)]
    for key, d in (("v", v), ("i", ipa), ("n", notes), ("w", wik), ("l", loc)):
        if d:
            e[key] = d
    return e


_HAN_CHAR = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0003134f]")


def word_pinyin(entries: dict, man_idx: int) -> dict[str, dict[str, str]]:
    """Context readings for Mandarin: ``{first_char: {word: "cháng chéng"}}``
    for every CC-CEDICT word (traditional and simplified) whose pinyin in
    pypinyin's phrase dictionary differs from its characters' default
    readings. 長城 is cháng chéng, not zhǎng chéng; 銀行 is yín háng. Only the
    differences are kept, so the reader can fall back to per-character
    readings everywhere else."""
    from pypinyin import Style, lazy_pinyin
    from pypinyin.constants import PHRASES_DICT

    from .reading import _cedict

    key = str(man_idx)

    def default(c):
        e = entries.get(c) or entries.get(ak.s2t_text(c)) or {}
        r = e.get("v", {}).get(man_idx) or e.get("v", {}).get(key)
        return r[0]["t"] if r else None

    out: dict[str, dict[str, str]] = defaultdict(dict)
    for w in _cedict():
        if not 2 <= len(w) <= 8 or not all(_HAN_CHAR.fullmatch(c) for c in w):
            continue
        s = ak.t2s_text(w)
        if len(s) != len(w) or s not in PHRASES_DICT:
            continue
        py = [unicodedata.normalize("NFC", p) for p in lazy_pinyin(s, style=Style.TONE)]
        if len(py) != len(w) or py == [default(c) for c in w]:
            continue
        out[w[0]][w] = " ".join(py)
    return out


# Wiktionary word readings (kaikki.org extract, data/raw/kaikki/zh_words.json):
# Cantonese Jyutping and Hokkien POJ for multi-character words, with whether
# each POJ form is tagged for a Taiwanese location ("tw"), for no location
# (""), or only for places outside Taiwan ("x").
ZH_WORDS = paths.RAW_DIR / "kaikki" / "zh_words.json"
# Japanese reading types from Wiktionary's kanji categories (呉音, 漢音, 訓…)
JA_KANJI = paths.RAW_DIR / "kaikki" / "ja_kanji.json"
_JA_TYPES = ("goon", "kan'on", "tōon", "kan'yōon", "soon", "on")


def _kata(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def ja_reading_types() -> dict[str, dict]:
    """``{kanji: {"o": {katakana: "type[,type]"}, "k": [kun…], "j": 1}}``: which on'yomi
    Wiktionary attests and of what type, its kun'yomi (okurigana dot
    dropped, as in the Japanese column), and whether the kanji is jōyō."""
    if not JA_KANJI.exists():
        return {}
    out = {}
    for c, d in json.loads(JA_KANJI.read_text("utf-8")).items():
        o = {}
        for t in _JA_TYPES:
            for r in d.get(t, []):
                ts = o.setdefault(_kata(r.replace("・", "")), [])
                if t not in ts:
                    ts.append(t)
        k = list(dict.fromkeys(r.replace("・", "").replace("-", "") for r in d.get("kun", [])))
        e = {}
        if o:   # a reading can be several types: 水 スイ is go-on and kan-on
            e["o"] = {r: ",".join(ts) for r, ts in o.items()}
        if k:
            e["k"] = k
        if e:
            if d.get("joyo"):
                e["j"] = 1
            out[c] = e
    return out


def word_readings_yue_nan(entries: dict, colidx: dict) -> dict[str, dict]:
    """Context readings for Cantonese and Taiwanese Hokkien, like
    ``word_pinyin``: ``{"xy": {first: {word: "hong4 zoeng2"}}, "xh": {...}}``,
    kept only where a word's reading differs from its characters' first
    readings (行長 hong4 zoeng2, not haang4 zoeng2). Simplified spellings of
    each word are added too, so simplified text is read the same way."""
    if not ZH_WORDS.exists():
        return {"xy": {}, "xh": {}}
    words = json.loads(ZH_WORDS.read_text("utf-8"))
    yi, hi = str(colidx["Cantonese"]), str(colidx["Hokkien"])

    def reads(c, k):
        e = entries.get(c) or entries.get(ak.s2t_text(c)) or {}
        v = e.get("v", {})
        return [r["t"] for r in (v.get(int(k)) or v.get(k) or [])]

    def syl_yue(form):
        sy = form.split()
        ok = all(re.fullmatch(r"[a-z]+[1-6]", x) for x in sy)   # no 變音 (hong4-2)
        return sy if ok else None

    def syl_nan(form):
        sy = [unicodedata.normalize("NFC", x).lower() for x in re.split(r"[-\s]+", form) if x]
        return sy if sy and not any(re.search(r"[\d.,;()]", x) for x in sy) else None

    out = {"xy": defaultdict(dict), "xh": defaultdict(dict)}

    def store(key, w, sy, k):
        cs = list(w)
        if len(sy) != len(cs):
            return
        firsts = [(reads(c, k) or [None])[0] for c in cs]
        if [unicodedata.normalize("NFC", f or "").lower() for f in firsts] == sy:
            return
        for spelled in {w, ak.t2s_text(w)}:
            if len(spelled) == len(cs):
                out[key][spelled[0]][spelled] = " ".join(sy)

    for w, d in words.items():
        if not 2 <= len(w) <= 8 or not all(_HAN_CHAR.fullmatch(c) for c in w):
            continue
        for f in d.get("y", []):
            sy = syl_yue(f)
            if sy:
                store("xy", w, sy, yi)
                break
        forms = d.get("h", [])
        tw = [f for f, t in forms if t == "tw"]
        pool = tw or ([f for f, _ in forms] if forms and all(t == "" for _, t in forms) else [])
        best, score = None, -1
        for f in pool:
            sy = syl_nan(f)
            if not sy or len(sy) != len(w):
                continue
            # the form sharing most syllables with the characters' own readings
            sc = sum(x in {unicodedata.normalize("NFC", r).lower() for r in reads(c, hi)}
                     for x, c in zip(sy, w))
            if sc > score:
                best, score = sy, sc
        if best:
            store("xh", w, best, hi)
    return out


# definitions that only point at another character ("(same as 嘛)")
_XREF = re.compile(r"\W*(same as|variant of|ancient form of|old form of|non-classical form|"
                   r"simplified form of|abbreviated form of|interchangeable with|corrupted form)", re.I)

_STOP = set("a an the of to in on and or for with by as at is be it its into from "
            "used also etc one two kind type sort name surname variant same character "
            "radical number kangxi".split())


def _en_words(defn):
    words = re.findall(r"[a-z][a-z'\-]+", (defn or "").lower())
    return [w.strip("'-") for w in words if w.strip("'-") not in _STOP and len(w) > 1]


def _fold(s):
    s = unicodedata.normalize("NFD", (s or "").replace("ⁿ", "n"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), "utf-8")


def build(out: Path = OUT, verbose=True):
    t0 = time.time()
    data, cols = ak.load_combined(str(paths.COMBINED_PARQUET.with_suffix(".csv")))
    global CZ_SYLLABLES
    CZ_SYLLABLES = chaozhou_syllables(data) or None
    meta = ak.char_meta()
    zh = wiktionary_zhpron.load()
    uh = unihan_readings.load()
    try:
        tgh = json.loads((paths.RAW_DIR / "unihan" / "tgh.json").read_text("utf-8"))
    except Exception:
        tgh = {}
    # Proto-Min nucleus confidence from provenance
    prov_rows = defaultdict(list)
    prov_conf = {}
    lp = paths.ROOT / "data" / "out" / "readings_long.parquet"
    if lp.exists():
        ldf = pd.read_parquet(lp, columns=["char", "column", "reading", "source", "conf"])
        for r in ldf.itertuples(index=False):
            if len(r.char) != 1:
                continue
            conf = None if r.conf is None or r.conf != r.conf else round(float(r.conf), 2)
            prov_rows[r.char].append([r.column, r.reading, r.source, conf])
            if r.column == "Proto-Min" and r.source == "recon" and conf is not None:
                prov_conf[r.char] = conf

    dial_cols = sorted([c for c in cols if c.startswith("dial:")],
                       key=lambda c: (c.split(":")[1].split("-")[0], c))
    all_cols = SINITIC + HIST + SINO + dial_cols
    colidx = {c: i for i, c in enumerate(all_cols)}
    columns = []
    for c in all_cols:
        if c.startswith("dial:"):
            m = re.match(r"^dial:([^-]+)-(.+)$", c)
            columns.append({"id": c, "label": m.group(2), "branch": m.group(1),
                            "section": "local"})
            continue
        label, native, scheme, audio = COLUMN_INFO.get(c, (c, "", "", ""))
        sec = "sinitic" if c in SINITIC else "hist" if c in HIST else "sino"
        columns.append({"id": c, "label": label, "native": native, "scheme": scheme,
                        "audio": audio, "section": sec})

    if out.exists():
        # delete files but keep the folders: OneDrive often refuses rmdir on
        # a synced folder (WinError 5) even when it is empty
        for f in out.rglob("*"):
            if f.is_file():
                f.unlink()
    shards = defaultdict(dict)
    pshards = defaultdict(dict)
    en_idx = defaultdict(dict)       # word -> {char: score}
    rd_idx = defaultdict(dict)       # key -> {char: colIdx}
    def rank_of(c):
        r = tgh.get(c)
        if r is None:
            s = ak.t2s_text(c)
            r = tgh.get(s) if len(s) == 1 else None
        return r or 99999
    for ch, bucket in data.items():
        entry = build_entry(ch, bucket, zh.get(ch), meta, rank_of(ch) if rank_of(ch) < 99999 else 0,
                            data, colidx, prov_conf, uh.get(ch))
        if not entry:
            continue
        key = f"{ord(ch) >> 8:x}"
        shards[key][ch] = entry
        if prov_rows.get(ch):
            pshards[key][ch] = prov_rows[ch]
        xref = 100000 if _XREF.match(entry.get("d", "")) else 0
        for pos, w in enumerate(_en_words(entry.get("d", ""))):
            s = rank_of(ch) + (0 if pos == 0 else 20000 + pos) + xref
            if s < en_idx[w].get(ch, 10**9):
                en_idx[w][ch] = s
        for ci, reads in entry.get("v", {}).items():
            col = all_cols[ci]
            if col in ("Middle Chinese (position)", "Fanqie", "Old Chinese",
                       "Japanese", "Korean (Hangul)", "Okinawan"):
                continue
            for r in reads:
                for tok in re.split(r"[\s|/,;·()\[\]]+", r["t"]):
                    f = _fold(tok.strip("*"))
                    f = re.sub(r"[˥˦˧˨˩]+$", "", f)
                    if not re.fullmatch(r"[a-z][a-z0-9'\-]{0,11}", f):
                        continue
                    for k in sorted({f, f.rstrip("0123456789")}):  # sorted: stable across hash seeds
                        if len(k) > 1:
                            rd_idx[k].setdefault(ch, ci)
    # word-level Mandarin readings, stored on each word's first character
    # (simplified-only characters get a stub entry holding just their words)
    all_entries = {c: e for d in shards.values() for c, e in d.items()}
    n_words = 0
    for first, words in word_pinyin(all_entries, colidx["Mandarin"]).items():
        key = f"{ord(first) >> 8:x}"
        shards[key].setdefault(first, {})["x"] = dict(sorted(words.items()))
        n_words += len(words)
    if verbose:
        print(f"[web] {n_words:,} word readings (Mandarin, in context)")
    jt = ja_reading_types()
    for c, t in jt.items():
        key = f"{ord(c) >> 8:x}"
        if c in shards[key]:
            shards[key][c]["jt"] = t
    if verbose and jt:
        print(f"[web] {len(jt):,} kanji with Wiktionary reading types (jt)")
    yn = word_readings_yue_nan(all_entries, colidx)
    for mk, by_first in yn.items():
        for first, words in by_first.items():
            key = f"{ord(first) >> 8:x}"
            shards[key].setdefault(first, {})[mk] = dict(sorted(words.items()))
        if verbose:
            print(f"[web] {sum(len(w) for w in by_first.values()):,} word readings ({mk}: "
                  f"{'Cantonese' if mk == 'xy' else 'Taiwanese Hokkien'}, in context)")
    for key, d in shards.items():
        _dump(out / "c" / f"{key}.json", d)
    for key, d in pshards.items():
        _dump(out / "p" / f"{key}.json", d)
    by_letter = defaultdict(dict)
    for w, chs in en_idx.items():
        by_letter[w[0]][w] = [c for c, _ in sorted(chs.items(), key=lambda x: x[1])[:200]]
    for letter, d in by_letter.items():
        _dump(out / "s" / "en" / f"{letter}.json", d)
    by_letter = defaultdict(dict)
    for k, chs in rd_idx.items():
        if not k or not k[0].isalpha():
            continue
        # Mandarin matches first, then Cantonese, Hokkien… (column order),
        # most common characters first within each
        top = sorted(chs.items(), key=lambda x: (x[1], rank_of(x[0])))[:80]
        by_letter[k[0]][k] = [[c, ci] for c, ci in top]
    for letter, d in by_letter.items():
        _dump(out / "s" / "rd" / f"{letter}.json", d)
    s2t = {}
    for ch in sorted(set(data) | set(tgh)):
        t = ak.s2t_text(ch)
        if t != ch and len(t) == 1 and t in data:
            s2t[ch] = t
    _dump(out / "s2t.json", s2t)
    # poems + sample passages (already bundled with the package)
    pz = paths.ROOT / "hanzihub" / "data" / "poems.json.gz"
    if pz.exists():
        _dump(out / "poems.json", json.loads(gzip.decompress(pz.read_bytes())))
    sp = paths.ROOT / "hanzihub" / "data" / "sample_passages.json"
    if sp.exists():
        _dump(out / "passages.json", json.loads(sp.read_text("utf-8")))
    common = sorted(tgh, key=tgh.get)[:3500]
    # content hash: the app appends ?v=<hash> to every data request, so the
    # service worker never serves a shard from one build with meta from another
    h = hashlib.sha1()
    offline = []                                  # files "Use offline" downloads
    size = 0
    for f in sorted(out.rglob("*.json")):
        b = f.read_bytes()
        h.update(f.relative_to(out).as_posix().encode() + b)
        rel = f.relative_to(out).as_posix()
        if not rel.startswith("p/"):
            offline.append(rel)
            size += len(b)
    columns_json = json.dumps(columns, ensure_ascii=False, sort_keys=True).encode()
    h.update(columns_json)
    _dump(out / "meta.json", {
        "built": time.strftime("%Y-%m-%d"), "v": h.hexdigest()[:10], "chars": len(data),
        "columns": columns, "shardShift": 8, "common": "".join(common),
        "offline": offline, "offlineBytes": size,
    })
    if verbose:
        size = sum(f.stat().st_size for f in out.rglob("*.json"))
        print(f"[web] {len(data):,} chars → {len(shards)} shards, "
              f"{size / 1e6:.1f} MB raw JSON in {time.time() - t0:.0f}s → {out}")


if __name__ == "__main__":
    build()
