"""Deterministic romanisation converters for the Sino-Xenic sources.

MCPDict ships its Vietnamese table in **Telex** ASCII (``truwowngj`` = trượng)
and its Korean table in Naver's **Revised Romanization** (``ryeok(yeok)``);
the dataset stores Vietnamese in Quốc Ngữ and Korean as Hangul + Yale (the
Unihan ``kKorean`` convention the app already pairs against). These
converters are pure, syllable-level and validated against the Unihan columns
(see ``tests/test_sinoxenic.py``) — anything they cannot parse cleanly returns
``""`` so the loader drops it rather than storing a guess.
"""
from __future__ import annotations

import re
import unicodedata

# ============================================================== Vietnamese ==
_TELEX_TONE = {"s": "́", "f": "̀", "r": "̉", "x": "̃",
               "j": "̣", "z": ""}
# order matters: longest / most specific first
_TELEX_VOWEL = [("uwow", "ươ"), ("uow", "ươ"), ("uwo", "ươ"), ("aa", "â"), ("aw", "ă"),
                ("ee", "ê"), ("oo", "ô"), ("ow", "ơ"), ("uw", "ư"),
                ("w", "ư")]
_VN_ONSETS = ["ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "th", "tr", "qu",
              "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r",
              "s", "t", "v", "x"]
_VN_CODAS = ["ch", "nh", "ng", "c", "m", "n", "p", "t"]
_VN_VOWELS = set("aăâeêioôơuưy")
_VN_MARKED = set("ăâêôơư")
_VN_RE = re.compile(r"^[a-zđăâêôơư]+$")


def _vn_place_tone(syl: str, mark: str) -> str:
    """Put the tone diacritic on the right vowel (traditional placement, the
    style Unihan ``kVietnamese`` uses: hòa, thủy, của, ngoài)."""
    if not mark:
        return syl
    onset = next((o for o in _VN_ONSETS if syl.startswith(o)), "")
    rest = syl[len(onset):]
    if onset == "gi" and not any(c in _VN_VOWELS for c in rest):
        onset, rest = "g", syl[1:]          # gìn: the i IS the vowel
    coda = next((c for c in _VN_CODAS if rest.endswith(c) and len(rest) > len(c)), "")
    nucleus = rest[:len(rest) - len(coda)] if coda else rest
    if not nucleus or any(c not in _VN_VOWELS for c in nucleus):
        return ""
    marked = [i for i, c in enumerate(nucleus) if c in _VN_MARKED]
    if marked:
        pos = marked[-1]                     # ươ → ơ, uyê → ê, ưu → ư
    elif coda:
        pos = len(nucleus) - 1               # hoàn, huỳnh
    elif len(nucleus) == 1:
        pos = 0
    elif len(nucleus) == 2:
        pos = 0                              # hòa, của, mía, hài
    else:
        pos = 1                              # ngoài, khuya
    base = onset + nucleus[:pos] + nucleus[pos] + mark + nucleus[pos + 1:] + coda
    return unicodedata.normalize("NFC", base)


def telex_to_vietnamese(tok: str) -> str:
    """``nhaats`` → ``nhất``; ``truwowngj`` → ``trượng``; ``ddinh`` → ``đinh``.
    Returns ``""`` for anything that is not one well-formed syllable."""
    s = (tok or "").strip().lower()
    if not s or not s.isascii():
        return ""
    mark = ""
    if s[-1] in _TELEX_TONE and len(s) > 1:
        mark, s = _TELEX_TONE[s[-1]], s[:-1]
    s = s.replace("dd", "đ")
    for k, v in _TELEX_VOWEL:
        s = s.replace(k, v)
    if not _VN_RE.match(s):
        return ""
    return _vn_place_tone(s, mark) if mark else unicodedata.normalize("NFC", s)


# ================================================================== Korean ==
_L = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj",
      "ch", "k", "t", "p", "h"]
_V = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe",
      "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
# Sino-Korean syllables only ever close in ㄱ ㄴ ㄹ ㅁ ㅂ ㅇ
_T = {"": 0, "k": 1, "n": 4, "l": 8, "m": 16, "p": 17, "ng": 21}
_RR_ONSETS = sorted(((o, i) for i, o in enumerate(_L) if o), key=lambda x: -len(x[0]))
_RR_VOWELS = sorted(((v, i) for i, v in enumerate(_V)), key=lambda x: -len(x[0]))


def rr_to_hangul(tok: str) -> str:
    """Revised Romanization of ONE Sino-Korean syllable → Hangul
    (``ryeok`` → 력, ``guk`` → 국). ``""`` if it doesn't parse as
    onset + vowel + a legal Sino-Korean coda."""
    s = (tok or "").strip().lower()
    if not s or not s.isascii() or not s.isalpha():
        return ""
    cands = [(o, i) for o, i in _RR_ONSETS if s.startswith(o)]
    if s[0] == "l":                       # occasional initial ㄹ written l
        cands.insert(0, ("l", _L.index("r")))
    cands.append(("", _L.index("")))
    for o, li in cands:                   # longest onset first
        rest = s[len(o):]
        for v, vi in _RR_VOWELS:          # longest vowel first
            if rest.startswith(v) and rest[len(v):] in _T:
                return chr(0xAC00 + (li * 21 + vi) * 28 + _T[rest[len(v):]])
    return ""


def naver_korean(val: str) -> list[str]:
    """Naver cell → Hangul list. ``ryeok(yeok)`` = the etymological reading
    plus its 두음법칙 word-initial form → ``['력', '역']``."""
    out: list[str] = []
    for part in re.split(r"[()\s/,]+", val or ""):
        h = rr_to_hangul(part)
        if h and h not in out:
            out.append(h)
    return out


# Yale, in the Unihan kKorean spelling (uppercase; ㅜ = WU even after labials:
# 不 PWU, 國 KWUK; ㅐ = AY, ㅢ = UY → 희 HUY).
_YALE_L = ["K", "KK", "N", "T", "TT", "L", "M", "P", "PP", "S", "SS", "", "C",
           "CC", "CH", "KH", "TH", "PH", "H"]
_YALE_V = ["A", "AY", "YA", "YAY", "E", "EY", "YE", "YEY", "O", "WA", "WAY",
           "OY", "YO", "WU", "WE", "WEY", "WI", "YU", "U", "UY", "I"]
_YALE_T = {0: "", 1: "K", 4: "N", 8: "L", 16: "M", 17: "P", 21: "NG"}


def hangul_to_yale(h: str) -> str:
    """One precomposed Hangul syllable → Unihan-style Yale (천 → CHEN)."""
    if len(h or "") != 1 or not (0xAC00 <= ord(h) <= 0xD7A3):
        return ""
    n = ord(h) - 0xAC00
    li, vi, ti = n // (21 * 28), (n // 28) % 21, n % 28
    if ti not in _YALE_T:
        return ""
    return _YALE_L[li] + _YALE_V[vi] + _YALE_T[ti]
