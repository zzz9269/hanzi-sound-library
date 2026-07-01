"""Approximate Proto-Min reconstruction by the comparative method.

There is **no** published machine-readable Proto-Min dataset (Norman's
reconstruction lives in print tables; Wiktionary/kaikki have no Proto-Min
lemmas), so the proto-Min node can't be *sourced* — it has to be *reconstructed*
from the attested Min daughters we already carry. This module does a transparent,
first-order comparative reconstruction and flags every output as approximate
(leading ``*``, ``source="recon"``). It is **not** Norman's system and carries no
precision guarantee — unlike the dialect predictions in :mod:`hanzihub.impute`,
there is no ground truth to validate against.

Method
------
For each character attested in ≥2 of the **five** Min daughters that carry an
**IPA** transcription — Hokkien, Eastern Min (Fuzhou), Northern Min (Jian'ou),
and (added 2026-06-26) Teochew via its IPA Shantou locality ``dial:Min-Shantou``
and Hainanese via ``dial:Min-Haikou`` — we:

* segment each reflex into ``(onset, rhyme, tone)`` (:mod:`hanzihub.segment`);
* reconstruct the **onset** and **rhyme** by majority vote across the daughters
  (a shared form is treated as a retention from the proto-language), breaking ties
  toward the more conservative daughter — Northern Min for initials, coastal Min
  for rhymes; the two added coastal Southern Min daughters sit at LOWER tie-break
  priority (Hainanese last — its implosives/vowel shifts are the most divergent);
* reconstruct the **tone** as a *category* (陰/陽 × 平上去入, the standard 8-way
  Min numbering) from the Middle Chinese 聲 + initial voicing, which is regular and
  well-founded — not from the daughters' divergent Chao pitch values.

The result is ``*<onset><rhyme><tone-category-digit>``, e.g. ``*kʰeiŋ⁷``. Each record's
``conf`` is the **nucleus vote-margin**: the fraction of contributing daughters that
share the (vowel-class folded) nucleus — 1.0 = unanimous, ~0.5 = split. This is an
*honest* confidence for the one slot the daughters (not MC) decide and the weak one;
onset/coda/tone are MC-anchored and not reflected in it. The app shows it as a chip.

Note: Teochew/Hainanese are folded in through their **IPA locality** columns
(``dial:Min-Shantou`` / ``dial:Min-Haikou``), which are slot-alignable; the
Peng'im *Teochew* branch column (``cing5``-style) stays excluded — its notation
is not segmentally comparable. Adding daughters mainly strengthens the nucleus
vote and raises coverage (the ≥2 threshold is now over five varieties).
"""
from __future__ import annotations

import unicodedata

import pandas as pd

from . import segment
from .schema import SRC_RECON

# Min daughters that share an IPA transcription (alignable slot-by-slot). The two
# coastal Southern Min additions are their IPA *locality* columns (Teochew=Shantou,
# Hainanese=Haikou), NOT the Peng'im Teochew branch column.
# Order = conservativeness priority used to break majority-vote ties: Northern Min
# is most conservative for initials, coastal Min for rhymes; Hainanese is ranked
# last on both (most divergent initials and vowels).
_TEOCHEW = "dial:Min-Shantou"
_HAINANESE = "dial:Min-Haikou"
_ONSET_PRIORITY = ["Northern Min (Jian'ou)", "Eastern Min (Fuzhou)", "Hokkien",
                   _TEOCHEW, _HAINANESE]
_RHYME_PRIORITY = ["Hokkien", _TEOCHEW, "Eastern Min (Fuzhou)",
                   "Northern Min (Jian'ou)", _HAINANESE]
_IPA_DAUGHTERS = set(_ONSET_PRIORITY)

MC_POS_COL = "Middle Chinese (position)"
PROTO_COL = "Proto-Min"
MIN_DAUGHTERS_REQUIRED = 2

# Middle Chinese voiced (濁) initials → 陽 tone register; everything else → 陰.
# 全濁 + 次濁 (sonorants), spanning the historical 母 inventory + variants.
# qieyun-data uses 常 (not 禪) and 孃 (not 娘); keep traditional aliases too.
_VOICED_INITIALS = set("並奉定澄羣群從邪崇床俟船常禪匣云以喻明微泥孃娘疑來日")
_SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹"  # superscript digits for the tone-category marker

# (聲, register) → 8-way Min tone-category number: 陰平1 陽平2 陰上3 陽上4
#                                                  陰去5 陽去6 陰入7 陽入8
_TONE_CATEGORY = {
    ("平", "陰"): 1, ("平", "陽"): 2, ("上", "陰"): 3, ("上", "陽"): 4,
    ("去", "陰"): 5, ("去", "陽"): 6, ("入", "陰"): 7, ("入", "陽"): 8,
}

# --- MC anchoring: reconstruct onset from 母, coda from 韻 -----------------
# Middle Chinese initial 母 → Proto-Min onset (the regular, *non-softened*
# correspondence — Norman's baseline series). qieyun-data already uses the
# heavy-lip 幫組 for light-lip words (Min split before 輕脣化), so no 非敷奉微 row
# is needed. Voicing is baked in here (並→b, 從→d͡z…), so daughters' devoicing is
# overridden. The retroflex 知/莊 series merge to dentals in Min; 章 series → palatal.
_INITIAL_TO_MIN = {
    "幫": "p", "滂": "pʰ", "並": "b", "明": "m",
    "端": "t", "透": "tʰ", "定": "d", "泥": "n",
    "知": "t", "徹": "tʰ", "澄": "d", "孃": "n", "娘": "n",
    "見": "k", "溪": "kʰ", "羣": "ɡ", "群": "ɡ", "疑": "ŋ",
    "精": "t͡s", "清": "t͡sʰ", "從": "d͡z", "心": "s", "邪": "z",
    "莊": "t͡s", "初": "t͡sʰ", "崇": "d͡z", "床": "d͡z", "生": "s", "俟": "z",
    "章": "t͡ɕ", "昌": "t͡ɕʰ", "常": "d͡ʑ", "禪": "d͡ʑ", "書": "ɕ", "船": "ʑ",
    "日": "ȵ", "來": "l",
    "影": "", "云": "", "以": "", "喻": "", "曉": "h", "匣": "ɦ",
}

# Rime-class (韻) → coda place, grouped by 攝. Unlisted rimes are 陰聲 (open, no
# coda). Nasal coda for 平/上/去; the matching stop for 入聲.
_RIME_LABIAL = set("侵覃談鹽添咸銜嚴凡")                 # 深·咸 → -m / -p
_RIME_CORONAL = set("真諄臻文殷魂痕寒桓刪山先仙元")        # 臻·山 → -n / -t
_RIME_VELAR = set("東冬鍾江陽唐庚耕清青蒸登")             # 通江宕梗曾 → -ŋ / -k
_NASAL_CODA = {"labial": "m", "coronal": "n", "velar": "ŋ"}
_STOP_CODA = {"labial": "p", "coronal": "t", "velar": "k"}

_CODA_CHARS = set("mnŋptkʔ")


def _mc_coda(parsed: dict) -> str:
    """Coda restored from the MC rime-class + tone (``""`` for 陰聲韻)."""
    rime, tone = parsed["rime"], parsed["tone"]
    place = ("labial" if rime in _RIME_LABIAL else
             "coronal" if rime in _RIME_CORONAL else
             "velar" if rime in _RIME_VELAR else None)
    if place is None:
        return ""
    return (_STOP_CODA if tone == "入" else _NASAL_CODA)[place]


def _reanchor_rhyme(rhyme: str, coda: str) -> str:
    """Drop the daughter's (merged) coda + nasalisation, append the MC coda."""
    r = unicodedata.normalize("NFD", rhyme).replace("̃", "")  # denasalise
    r = unicodedata.normalize("NFC", r)
    while r and r[-1] in _CODA_CHARS:
        r = r[:-1]
    return r + coda


def _first_ipa(cell_readings: list[str]) -> str:
    """First usable surface reading from a daughter's long-table values."""
    for r in cell_readings:
        for part in segment.iter_readings(r):
            return part
    return ""


def _majority(values: list[str], priority_owner: list[str]) -> str:
    """Most common non-empty value; ties broken by the priority order of the
    (value, owner) pairs supplied via ``priority_owner`` (a parallel list)."""
    counts: dict[str, int] = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return ""
    best = max(counts.values())
    tied = {v for v, c in counts.items() if c == best}
    if len(tied) == 1:
        return next(iter(tied))
    for v in priority_owner:           # first tied value in priority order
        if v in tied:
            return v
    return next(iter(tied))


def proto_min(long_df: pd.DataFrame, *, verbose: bool = True) -> list[dict]:
    """Reconstruct a Proto-Min reading per eligible char; return record dicts."""
    sub = long_df[long_df["column"].isin(_IPA_DAUGHTERS | {MC_POS_COL})]
    # char -> column -> [readings]
    by_char: dict[str, dict[str, list[str]]] = {}
    for char, column, reading in sub[["char", "column", "reading"]].itertuples(index=False):
        by_char.setdefault(char, {}).setdefault(column, []).append(reading)

    records: list[dict] = []
    for char, cols in by_char.items():
        # Segment each available IPA daughter's primary reflex.
        seg: dict[str, tuple[str, str, str]] = {}
        for col in _IPA_DAUGHTERS:
            if col in cols:
                s = segment.split_syllable(_first_ipa(cols[col]))
                if s is not None:
                    seg[col] = s
        if len(seg) < MIN_DAUGHTERS_REQUIRED:
            continue

        onsets = [seg[c][0] for c in _ONSET_PRIORITY if c in seg]
        rhymes = [seg[c][1] for c in _RHYME_PRIORITY if c in seg]
        # Prefer a rhyme with a real vowel nucleus over a vowel-less syllabic
        # nasal (e.g. Hokkien pŋ̩), which would otherwise win the vote and then
        # collide with the MC-restored coda.
        voweled = [r for r in rhymes if any(c in segment._VOWELS for c in r)]
        onset = _majority(onsets, onsets)
        rhyme = _majority(voweled or rhymes, voweled or rhymes)
        if not rhyme:                  # need at least a rhyme to be meaningful
            continue

        # Nucleus confidence: the one slot the daughters (not MC) determine, and the
        # weak one — measured here as how much they AGREE on the (vowel-class folded)
        # nucleus. 1.0 = unanimous; ~0.5 = split vote. A single witness is treated as
        # uncertain (0.5), not falsely confident. This becomes the record's `conf`.
        nuclei = [segment.nucleus(r, fold=True) for r in (voweled or rhymes)]
        nuclei = [n for n in nuclei if n]
        if len(nuclei) >= 2:
            top = max(nuclei.count(n) for n in set(nuclei))
            nucleus_conf = top / len(nuclei)
        else:
            nucleus_conf = 0.5

        # Anchor on Middle Chinese: onset from 母 (regular MC→Min correspondence,
        # overriding the daughters' divergent/devoiced reflexes), coda from 韻,
        # tone category from 聲 + voicing register. Daughters supply the nucleus.
        mc_pos = _first_ipa(cols.get(MC_POS_COL, []))
        parsed = segment.parse_mc_position(mc_pos)
        tone = ""
        if parsed:
            init = parsed["initial"]
            if init in _INITIAL_TO_MIN:
                onset = _INITIAL_TO_MIN[init]
            rhyme = _reanchor_rhyme(rhyme, _mc_coda(parsed))
            register = "陽" if init in _VOICED_INITIALS else "陰"
            num = _TONE_CATEGORY.get((parsed["tone"], register))
            tone = _SUPER[num] if num else ""

        reading = f"*{onset}{rhyme}{tone}"
        records.append({
            "char": char, "column": PROTO_COL, "reading": reading,
            "source": SRC_RECON, "locality": "", "conf": round(nucleus_conf, 3),
        })

    if verbose:
        print(f"[recon] Proto-Min reconstructed for {len(records):,} chars "
              f"(≥{MIN_DAUGHTERS_REQUIRED} IPA Min daughters)")
    return records


def run(long_df: pd.DataFrame, *, verbose: bool = True) -> pd.DataFrame:
    """Append Proto-Min reconstruction rows to the long table."""
    recs = proto_min(long_df, verbose=verbose)
    if not recs:
        return long_df
    return pd.concat([long_df, pd.DataFrame.from_records(recs)],
                     ignore_index=True)
