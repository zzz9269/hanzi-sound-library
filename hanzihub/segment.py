"""Phonological segmentation for the structured reflex predictor.

Two pure, testable pieces of domain knowledge that the ML engine
(:mod:`hanzihub.impute`) builds on:

1. :func:`parse_mc_position` — split a Middle Chinese 音韻地位 descriptor
   (qieyun-data format, e.g. ``端一東平`` / ``見三C東平`` / ``云合三B支平``) into its
   categorical fields *母 / 開合 / 等 / 類(重紐) / 韻 / 聲*. These categories are the
   linguistically correct predictor of a modern reflex: sound change is regular,
   so a living-dialect reading is (almost) a function of the MC category plus the
   dialect's own sound laws.

2. :func:`split_syllable` — split a surface reading into ``(onset, rhyme, tone)``
   slots. Works across the romanisation systems we target:

   * **digit-tone romanisations** — Jyutping ``jau1``, Teochew Peng'im ``a1``
     (tone = trailing digits);
   * **IPA with Chao tone letters / superscripts** — Hokkien ``kʰi̯ɛn˥˩``, Wu,
     Min, etc. (tone = trailing tone-letter run).

   The segmental part is split at the first vowel: everything before it is the
   onset (initial consonant cluster, including aspiration/tie-bar modifiers),
   the rest is the rhyme (medial + nucleus + coda). This (C)(G)V(C) split is
   system-agnostic and is what lets the model *recompose* syllables it has never
   seen, instead of copying whole strings.
"""
from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------
# Middle Chinese 音韻地位 (qieyun-data descriptor)
# --------------------------------------------------------------------------
# 母 + (開|合)? + 等(一二三四) + 類(A|B|C)? + 韻 + 聲(平上去入)
_MC_RE = re.compile(
    r"^(?P<initial>.)"
    r"(?P<openness>[開合]?)"
    r"(?P<division>[一二三四])"
    r"(?P<cls>[ABC]?)"
    r"(?P<rime>.+?)"
    r"(?P<tone>[平上去入])$"
)

MC_FIELDS = ("initial", "openness", "division", "cls", "rime", "tone")


def parse_mc_position(s: str) -> dict[str, str] | None:
    """Parse a 音韻地位 string into its six categorical fields.

    Returns ``None`` if the string is empty or not a well-formed descriptor.
    Missing optional fields (開合, 重紐類) come back as ``""``.
    """
    if not s:
        return None
    m = _MC_RE.match(s.strip())
    if not m:
        return None
    return {f: m.group(f) for f in MC_FIELDS}


# --------------------------------------------------------------------------
# Surface reading → (onset, rhyme, tone)
# --------------------------------------------------------------------------
# Chao tone letters (U+02E5..U+02E9) and the staff variants, plus IPA tone
# superscript digits used by some Wiktionary transcriptions.
_TONE_LETTERS = "˥˦˧˨˩꜔꜕꜖ꜗꜘꜙꜚ"
_TONE_SUPERS = "¹²³⁴⁵⁶⁷⁸⁹⁰"
_TONE_IPA_RE = re.compile(rf"[{_TONE_LETTERS}{_TONE_SUPERS}]+$")
_TONE_DIGIT_RE = re.compile(r"[0-9]+$")

# Vowel nuclei across the romanisations + IPA we touch. The first vowel marks
# the onset/rhyme boundary; glides (i̯ u̯ / w j) fall naturally on either side.
_VOWELS = set("aeiouyAEIOUY"
              "ɛɔəɤɪʊɨʉɯøœɵæɑɒʌɐɘɞɜɚɝ"   # IPA vowels
              "üöäáàâãéèêíìîóòôúùû"           # accented latin
              "ãẽĩõũỹ")                       # precomposed nasal vowels (Min)
_SYLLABIC_NASALS = set("mnŋ")  # can be the nucleus when no vowel is present

# --------------------------------------------------------------------------
# Nucleus extraction + vowel-class folding (shared by reconstruct + eval)
# --------------------------------------------------------------------------
# Fold near-identical vowels to one representative so a sub-phonemic difference
# (o vs ɔ, e vs ɛ, ɯ vs u) is not treated as a distinct nucleus.
_VOWEL_FOLD = {**{c: "a" for c in "aɑæɒ"}, **{c: "e" for c in "eɛ"},
               **{c: "o" for c in "oɔ"}, **{c: "ə" for c in "əɤʌɐ"},
               **{c: "u" for c in "uɯʊʉ"}, **{c: "i" for c in "iɪɨ"},
               **{c: "y" for c in "yøœɵ"}}
_NUCLEUS_VOWELS = set("aeiouyɛɔəɤɪʊɨɯøœɵæɑɒʌɐ")


def fold_vowels(s: str) -> str:
    """Collapse each vowel to its class representative (o/ɔ→o, ɯ/u→u, …)."""
    return "".join(_VOWEL_FOLD.get(c, c) for c in s)


def nucleus(rhyme: str, *, fold: bool = False) -> str:
    """Bare vowel skeleton of a rhyme — drop combining marks (glide tie-bars,
    nasalisation) and all non-vowels (medial-less coda consonants), optionally
    folded to vowel classes. ``"iaŋ"`` → ``"ia"``; ``"i̯ɔ̃k"`` → ``"iɔ"`` (``"io"`` folded)."""
    r = unicodedata.normalize("NFD", rhyme or "")
    r = "".join(c for c in r if not unicodedata.combining(c))
    r = "".join(c for c in r if c in _NUCLEUS_VOWELS)
    return fold_vowels(r) if fold else r


def _strip_tone(seg: str) -> tuple[str, str]:
    """Return ``(segmental, tone)`` splitting off a trailing tone marker.

    Tries IPA tone letters/superscripts first, then a trailing digit run.
    """
    m = _TONE_IPA_RE.search(seg)
    if m:
        return seg[: m.start()], seg[m.start():]
    m = _TONE_DIGIT_RE.search(seg)
    if m:
        return seg[: m.start()], seg[m.start():]
    return seg, ""


def split_syllable(reading: str) -> tuple[str, str, str] | None:
    """Split one surface syllable into ``(onset, rhyme, tone)``.

    ``onset`` may be empty (vowel-initial or syllabic nasal), ``tone`` may be
    empty (toneless transcription). Returns ``None`` for blank input.
    """
    if reading is None:
        return None
    s = reading.strip()
    if not s:
        return None

    segmental, tone = _strip_tone(s)
    segmental = segmental.strip()

    # onset = leading run up to (but excluding) the first vowel.
    i = 0
    while i < len(segmental) and segmental[i] not in _VOWELS:
        i += 1
    if i >= len(segmental):
        # no vowel: a syllabic nasal is the nucleus — keep any preceding
        # consonants as the onset (e.g. Hokkien pŋ̩ → p + ŋ̩; bare ŋ̩ → ∅ + ŋ̩).
        nas = [j for j, ch in enumerate(segmental) if ch in _SYLLABIC_NASALS]
        if nas and nas[-1] > 0:
            k = nas[-1]
            return segmental[:k], segmental[k:], tone
        return "", segmental, tone
    return segmental[:i], segmental[i:], tone


def iter_readings(cell: str):
    """Yield individual surface readings from a wide-table cell.

    A cell may hold several distinct sourced readings joined by `` | `` and a
    single reading may list variants with ``/`` (e.g. Hokkien literary/colloquial
    ``be˥˩/bɛ˥˩``). Any ``[ML]`` tag is stripped.
    """
    if not cell:
        return
    for chunk in str(cell).replace("[ML]", "").split("|"):
        for part in chunk.split("/"):
            part = part.strip()
            if part:
                yield part
