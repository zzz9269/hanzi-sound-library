"""Validate the Proto-Min reconstruction against a published gold set.

No machine-readable Proto-Min lexicon exists, so :mod:`hanzihub.reconstruct`
carries *no precision guarantee* (see its docstring). This module closes that
gap. Drop reconstructions transcribed from a published authority (Jerry Norman's
Proto-Min tables) into ``data/gold/proto_min_norman.tsv`` and run::

    python -m hanzihub.eval_protomin

to get exact-match and per-slot (onset / rhyme / tone) accuracy of the
reconstructor's output against that gold. It re-runs the **production**
reconstructor (:func:`hanzihub.reconstruct.proto_min`) — it does not
re-implement it — so the reported number is the number the app ships.

The gold file ships empty: populating it means transcribing print tables (no
open dataset exists) and the values must be REAL, never fabricated — a wrong
gold form reports a confident, false accuracy.
"""
from __future__ import annotations

import argparse
import csv
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import paths, reconstruct, segment

GOLD_PATH = Path(paths.ROOT) / "data" / "gold" / "proto_min_norman.tsv"


def _norm(form: str) -> str:
    """Canonicalise a Proto-Min form for comparison: NFC, drop a leading
    reconstruction ``*`` and surrounding whitespace."""
    return unicodedata.normalize("NFC", (form or "").strip()).lstrip("*").strip()


# --------------------------------------------------------------------------
# Notation bridge: Norman's transcription -> the reconstructor's IPA output.
# Norman writes tš/dž/š/ž (palatals), ts/dz (no tie bar), softened *bh/*dh/*gh,
# vowel ɑ, ascii g, and a 4-way tone LETTER A/B/C/D (平/上/去/入) with the voicing
# register carried by the initial. The reconstructor emits IPA t͡ɕ/d͡ʑ/ɕ/ʑ, tie-bar
# affricates, plain voiced stops, ɡ, and an 8-way tone DIGIT. We bridge gold ->
# reconstructor notation so a comparison reflects linguistic agreement, not
# transcription style. (The softened *bh/*dh series is a real Proto-Min contrast
# the reconstructor does NOT make — that surfaces as a genuine onset mismatch,
# which is the point.)
_NORMAN_SEG = [  # longest-first; carons/digraphs occur only in onsets
    ("tšh", "t͡ɕʰ"), ("džh", "d͡ʑ"), ("tsh", "t͡sʰ"), ("dzh", "d͡z"),
    ("tš", "t͡ɕ"), ("dž", "d͡ʑ"), ("ts", "t͡s"), ("dz", "d͡z"),
    ("kh", "kʰ"), ("ph", "pʰ"), ("th", "tʰ"),   # aspirated stops: plain h -> ʰ
    ("bh", "b"), ("dh", "d"), ("gh", "ɡ"),
    ("ń", "ȵ"), ("š", "ɕ"), ("ž", "ʑ"), ("ɣ", "ɦ"), ("x", "h"),
]
_VOICED_ONSET = ("bh", "dh", "gh", "dzh", "džh", "dž", "dz", "b", "d", "g",
                 "z", "ž", "ɣ", "ɦ", "m", "n", "ń", "ŋ", "l")
_SHENG = {"A": "平", "B": "上", "C": "去", "D": "入"}


def to_recon_notation(form: str) -> str:
    """Convert a Norman-notation form to the reconstructor's IPA conventions.
    Near-identity on a form already in reconstructor notation (no A/B/C/D tone
    letter, tie-bar affricates shield the ``ts``/``dz`` rules)."""
    s = _norm(form).lstrip("-")              # softened-series hyphen (not modelled)
    tone_letter = ""
    if s and s[-1] in _SHENG:
        tone_letter, s = s[-1], s[:-1]
    voiced = any(s.startswith(p) for p in _VOICED_ONSET)
    for a, b in _NORMAN_SEG:
        s = s.replace(a, b)
    if tone_letter:
        num = reconstruct._TONE_CATEGORY.get((_SHENG[tone_letter],
                                              "陽" if voiced else "陰"))
        if num:
            s += reconstruct._SUPER[num]
    return s


def _canon(form: str) -> str:
    """Comparison-canonical form: drop glide tie-bars (i̯→i), unify ɑ→a and the
    two ``g`` glyphs, so notation-equal forms compare equal."""
    s = unicodedata.normalize("NFD", _norm(form)).replace("̯", "")
    s = unicodedata.normalize("NFC", s)
    return s.replace("ɑ", "a").replace("g", "ɡ").replace("∅", "")


def _slots(form: str) -> tuple[str, str, str]:
    """``(onset, rhyme, tone)`` for a (canonicalised) form; ``("","","")`` if blank."""
    return segment.split_syllable(_canon(form)) or ("", "", "")


# --------------------------------------------------------------------------
# Gold set
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class GoldForm:
    char: str
    proto: str            # Norman's reconstruction, normalised (no leading *)
    citation: str = ""
    notes: str = ""


def load_gold(path: Path = GOLD_PATH) -> list[GoldForm]:
    """Read the gold TSV (``#`` comment lines skipped; first remaining line is
    the header). Rows missing a char or a proto form are dropped."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader((ln for ln in f if not ln.lstrip().startswith("#")),
                                delimiter="\t")
        out: list[GoldForm] = []
        for row in reader:
            char = (row.get("char") or "").strip()
            proto = _norm(row.get("proto_min") or "")
            if char and proto:
                out.append(GoldForm(char, proto,
                                    (row.get("citation") or "").strip(),
                                    (row.get("notes") or "").strip()))
        return out


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
@dataclass
class Report:
    total: int                       # gold forms loaded
    covered: int                     # gold chars the reconstructor produced a form for
    exact: int = 0
    onset_ok: int = 0
    rhyme_ok: int = 0
    tone_ok: int = 0
    rows: list[tuple] = field(default_factory=list)  # (char, gold, pred, exact, o, r, t)

    def _pct(self, n: int) -> float:
        return 100.0 * n / self.covered if self.covered else 0.0

    @property
    def coverage_pct(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 0.0

    @property
    def exact_pct(self) -> float:
        return self._pct(self.exact)

    @property
    def onset_pct(self) -> float:
        return self._pct(self.onset_ok)

    @property
    def rhyme_pct(self) -> float:
        return self._pct(self.rhyme_ok)

    @property
    def tone_pct(self) -> float:
        return self._pct(self.tone_ok)


def evaluate(gold: list[GoldForm], preds: dict[str, str]) -> Report:
    """Compare reconstructor predictions to gold. ``preds`` maps char -> form.
    Per-slot accuracy is over *covered* forms (where a prediction exists)."""
    rep = Report(total=len(gold), covered=0)
    for g in gold:
        gold_form = _canon(to_recon_notation(g.proto))   # bridge Norman -> IPA
        pred = _canon(preds.get(g.char, ""))
        if not pred:
            rep.rows.append((g.char, gold_form, "", False, False, False, False))
            continue
        rep.covered += 1
        ex = pred == gold_form
        (go, gr, gt), (po, pr, pt) = _slots(gold_form), _slots(pred)
        oo, rr, tt = po == go, pr == gr, pt == gt
        rep.exact += ex
        rep.onset_ok += oo
        rep.rhyme_ok += rr
        rep.tone_ok += tt
        rep.rows.append((g.char, gold_form, pred, ex, oo, rr, tt))
    return rep


def predictions(long_df: pd.DataFrame) -> dict[str, str]:
    """char -> production reconstructor output (normalised, no leading *)."""
    return {r["char"]: _norm(r["reading"])
            for r in reconstruct.proto_min(long_df, verbose=False)}


# --------------------------------------------------------------------------
# Onset-only validation (Norman's ~276 initials table — onset-slot at scale)
# --------------------------------------------------------------------------
ONSET_GOLD_PATH = Path(paths.ROOT) / "data" / "gold" / "proto_min_norman_initials.tsv"


def bridge_onset(raw_norman_onset: str) -> str:
    """A bare Norman onset (``*ph``, ``*lh``, ``*∅``) → the reconstructor's onset
    IPA. Reuses the full notation bridge (no tone letter present)."""
    return _canon(to_recon_notation(raw_norman_onset))


def load_onset_gold(path: Path = ONSET_GOLD_PATH) -> dict[str, list[str]]:
    """char -> list of Norman onset labels (verbatim, e.g. ``*lh``)."""
    if not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader((ln for ln in f if not ln.lstrip().startswith("#")),
                                delimiter="\t")
        for row in reader:
            char = (row.get("char") or "").strip()
            onset = (row.get("proto_onset") or "").strip()
            if char and onset:
                out.setdefault(char, []).append(onset)
    return out


def _lenient_variants(raw: str) -> set[str]:
    """Extra onsets to accept when Norman marks a contrast the reconstructor
    cannot model from surface reflexes alone: the **aspirated sonorants**
    (*lh/*mh/*nh/*ŋh) and the **softened** (*-C) series. For those we also accept
    the plain base onset, so a second metric measures accuracy on the distinctions
    the method actually *attempts*."""
    s = raw.lstrip("*")
    extra: set[str] = set()
    if s.startswith("-"):                         # softened → accept plain base
        extra.add(bridge_onset("*" + s[1:]))
    if len(s) >= 2 and s.endswith("h") and s[:-1] in {"m", "n", "ń", "ŋ", "l"}:
        extra.add(bridge_onset("*" + s[:-1]))     # aspirated sonorant → plain
        if s[:-1] == "n":
            extra.add("ȵ")                        # 日-series reflex
    return extra


@dataclass
class OnsetReport:
    total: int
    covered: int = 0
    correct: int = 0            # strict: exact Norman onset (incl. unmodellable contrasts)
    modellable: int = 0         # also-correct once unmodellable *Ch / *-C contrasts forgiven
    rows: list[tuple] = field(default_factory=list)       # (char, labels, pred_onset, ok)
    confusions: dict[tuple, int] = field(default_factory=dict)  # (norman_label, pred)->n

    @property
    def coverage_pct(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 0.0

    @property
    def acc_pct(self) -> float:
        return 100.0 * self.correct / self.covered if self.covered else 0.0

    @property
    def modellable_pct(self) -> float:
        return 100.0 * self.modellable / self.covered if self.covered else 0.0


def evaluate_onsets(gold: dict[str, list[str]], preds: dict[str, str]) -> OnsetReport:
    """Onset accuracy: predicted onset must match ANY of a char's Norman onsets
    (after the notation bridge). Reports both strict accuracy and accuracy with
    the unmodellable aspirated-sonorant / softened contrasts forgiven, and tracks
    the commonest miss patterns."""
    rep = OnsetReport(total=len(gold))
    for char, labels in gold.items():
        pred = preds.get(char, "")
        if not pred:
            continue
        rep.covered += 1
        pred_onset = _slots(pred)[0]
        accept = {bridge_onset(lab) for lab in labels}
        lenient = accept.union(*(_lenient_variants(lab) for lab in labels))
        ok = pred_onset in accept
        rep.correct += ok
        rep.modellable += pred_onset in lenient
        rep.rows.append((char, labels, pred_onset, ok))
        if not ok:
            key = (labels[0], pred_onset or "∅")
            rep.confusions[key] = rep.confusions.get(key, 0) + 1
    return rep


# --------------------------------------------------------------------------
# Proto-Southern Min (Kwok 2018) triangulation — a DIFFERENT, shallower node.
# Scores onset / tone / nucleus-vowel at scale (~600 chars). Full-rhyme is NOT
# scored: Southern Min's innovated -ʔ codas & nasal vowels differ from the
# reconstructor's MC-restored codas by proto-node design, not by error.
# --------------------------------------------------------------------------
KWOK_GOLD_PATH = Path(paths.ROOT) / "data" / "gold" / "proto_southern_min_kwok.tsv"
_SUP_TO_DIGIT = {s: d for d, s in zip("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")}
_KWOK_SEG = [("tsʰ", "t͡sʰ"), ("tɕʰ", "t͡ɕʰ"), ("ts", "t͡s"),
             ("dz", "d͡z"), ("tɕ", "t͡ɕ"), ("dʑ", "d͡ʑ")]
_fold = segment.fold_vowels   # vowel-class folding (o/ɔ, ɯ/u …), shared with reconstruct


def _tone_digit(tone: str) -> str:
    return "".join(_SUP_TO_DIGIT.get(c, c) for c in tone)


def _kwok_to_recon(form: str) -> str:
    s = _norm(form)
    for a, b in _KWOK_SEG:
        s = s.replace(a, b)
    return s


def _nucleus(form: str) -> str:
    """Bare vowel skeleton of a form's rhyme (drop onset, coda, glide/nasal marks)."""
    return segment.nucleus(_slots(form)[1])


def load_kwok_gold(path: Path = KWOK_GOLD_PATH) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader((ln for ln in f if not ln.lstrip().startswith("#")),
                                delimiter="\t")
        for row in reader:
            char = (row.get("char") or "").strip()
            pm = (row.get("proto_sm") or "").strip()
            if char and pm:
                out.append((char, pm))
    return out


@dataclass
class KwokReport:
    total: int
    covered: int = 0
    onset_ok: int = 0
    tone_ok: int = 0
    nucleus_ok: int = 0        # strict
    nucleus_fold: int = 0      # vowel-class folded
    nuc_conf: dict = field(default_factory=dict)

    def _p(self, n):
        return 100.0 * n / self.covered if self.covered else 0.0


def evaluate_kwok(gold: list[tuple[str, str]], preds: dict[str, str]) -> KwokReport:
    rep = KwokReport(total=len(gold))
    for char, kf in gold:
        pred = preds.get(char, "")
        if not pred:
            continue
        rep.covered += 1
        g = _kwok_to_recon(kf)
        if _slots(g)[0] == _slots(pred)[0]:
            rep.onset_ok += 1
        if _tone_digit(_slots(g)[2]) == _tone_digit(_slots(pred)[2]):
            rep.tone_ok += 1
        gn, pn = _nucleus(g), _nucleus(pred)
        rep.nucleus_ok += gn == pn
        rep.nucleus_fold += _fold(gn) == _fold(pn)
        if _fold(gn) != _fold(pn):                       # only count true (folded) misses
            rep.nuc_conf[(gn, pn)] = rep.nuc_conf.get((gn, pn), 0) + 1
    return rep


def daughter_nucleus_agreement(long_df) -> tuple[int, int, list[float]]:
    """Internal consistency of the weak slot, with NO external gold: for every char
    attested in ≥2 IPA Min daughters, do the daughters agree on the (folded) nucleus?
    Returns (unanimous, total, [winning-vote fraction per char])."""
    from collections import Counter
    daughters = reconstruct._IPA_DAUGHTERS
    sub = long_df[long_df["column"].isin(daughters)]
    by_char: dict[str, list[str]] = {}
    for char, _col, reading in sub[["char", "column", "reading"]].itertuples(index=False):
        first = next(segment.iter_readings(reading), "")
        s = segment.split_syllable(first)
        if s:
            nuc = segment.nucleus(s[1], fold=True)   # s[1] is the rhyme
            if nuc:
                by_char.setdefault(char, []).append(nuc)
    unanimous = total = 0
    margins: list[float] = []
    for nucs in by_char.values():
        if len(nucs) < 2:
            continue
        total += 1
        top = Counter(nucs).most_common(1)[0][1]
        margins.append(top / len(nucs))
        unanimous += top == len(nucs)
    return unanimous, total, margins


def _format_kwok(rep: KwokReport, show: int) -> str:
    if rep.total == 0:
        return f"No Kwok gold found in {KWOK_GOLD_PATH}."
    lines = [
        f"Proto-Southern Min (Kwok 2018) triangulation — DIFFERENT node, scale ref",
        f"  gold chars        {rep.total}",
        f"  covered           {rep.covered}/{rep.total}  ({rep._p(rep.covered):.1f}%)",
        f"  onset agree       {rep.onset_ok}/{rep.covered}  ({rep._p(rep.onset_ok):.1f}%)",
        f"  tone agree        {rep.tone_ok}/{rep.covered}  ({rep._p(rep.tone_ok):.1f}%)",
        f"  nucleus agree     {rep.nucleus_ok}/{rep.covered}  ({rep._p(rep.nucleus_ok):.1f}%)"
        "  strict",
        f"  nucleus agree     {rep.nucleus_fold}/{rep.covered}  ({rep._p(rep.nucleus_fold):.1f}%)"
        "  vowel-class folded (o/ɔ, e/ɛ, ɯ/u … merged)",
    ]
    if rep.nuc_conf:
        top = sorted(rep.nuc_conf.items(), key=lambda kv: -kv[1])
        lines.append("\n  commonest TRUE nucleus disagreements (Kwok → reconstructor, n):")
        for (g, p), n in top[:show]:
            lines.append(f"      {g or '∅':4} → {p or '∅':4}  ×{n}")
    return "\n".join(lines)


def _format_onsets(rep: OnsetReport, show: int) -> str:
    if rep.total == 0:
        return f"No onset gold found in {ONSET_GOLD_PATH}."
    lines = [
        f"Proto-Min ONSET validation ({ONSET_GOLD_PATH.name})",
        f"  gold chars        {rep.total}",
        f"  covered           {rep.covered}/{rep.total}  ({rep.coverage_pct:.1f}%)",
        f"  onset correct     {rep.correct}/{rep.covered}  ({rep.acc_pct:.1f}%)  strict",
        f"  modellable-only   {rep.modellable}/{rep.covered}  ({rep.modellable_pct:.1f}%)  "
        "(forgiving the *Ch / *-C contrasts no surface method can recover)",
    ]
    if rep.confusions:
        top = sorted(rep.confusions.items(), key=lambda kv: -kv[1])
        lines.append(f"\n  commonest onset misses (Norman → predicted, n):")
        for (lab, pred), n in top[:show]:
            lines.append(f"      {lab:5} → {pred or '∅':6}  ×{n}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _format(rep: Report, show_mismatches: int) -> str:
    if rep.total == 0:
        return (f"No gold forms found in {GOLD_PATH}.\n"
                "Populate it with REAL reconstructions from a published source "
                "(see the header in that file) — never fabricated — then re-run.")
    lines = [
        f"Proto-Min reconstruction vs gold ({GOLD_PATH.name})",
        f"  gold forms        {rep.total}",
        f"  covered           {rep.covered}/{rep.total}  ({rep.coverage_pct:.1f}% — "
        "reconstructor produced a form)",
        f"  exact match       {rep.exact}/{rep.covered}  ({rep.exact_pct:.1f}%)",
        f"  onset correct     {rep.onset_ok}/{rep.covered}  ({rep.onset_pct:.1f}%)",
        f"  rhyme correct     {rep.rhyme_ok}/{rep.covered}  ({rep.rhyme_pct:.1f}%)",
        f"  tone correct      {rep.tone_ok}/{rep.covered}  ({rep.tone_pct:.1f}%)",
    ]
    misses = [r for r in rep.rows if r[2] and not r[3]]   # predicted but not exact
    uncovered = [r for r in rep.rows if not r[2]]
    if misses and show_mismatches:
        lines.append(f"\n  mismatches (showing {min(show_mismatches, len(misses))} "
                     f"of {len(misses)}):  char  gold  →  predicted   [O R T]")
        for ch, gold, pred, _ex, oo, rr, tt in misses[:show_mismatches]:
            flag = "".join(x for x, ok in (("O", oo), ("R", rr), ("T", tt)) if not ok)
            lines.append(f"      {ch}  {gold:<10} → {pred:<10}  miss:{flag or '-'}")
    if uncovered:
        lines.append(f"\n  {len(uncovered)} gold char(s) had no reconstruction "
                     "(missing the ≥2 IPA Min daughters reconstruct.py needs).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    from .build_dataset import _make_stdio_utf8  # CJK-safe console (path has 漢字音庫)
    _make_stdio_utf8()
    ap = argparse.ArgumentParser(description="Score Proto-Min reconstruction vs a gold set.")
    ap.add_argument("--gold", type=Path, default=GOLD_PATH, help="gold TSV path")
    ap.add_argument("--long", type=Path, default=paths.READINGS_LONG,
                    help="readings_long.parquet (defaults to the built dataset)")
    ap.add_argument("--show", type=int, default=25, help="max mismatches to list")
    ap.add_argument("--onsets", action="store_true",
                    help="onset-only validation against the Norman initials table")
    ap.add_argument("--kwok", action="store_true",
                    help="onset/tone/nucleus triangulation vs Proto-Southern Min (Kwok 2018)")
    args = ap.parse_args(argv)

    if not Path(args.long).exists():
        raise SystemExit(f"long table not found: {args.long} — run "
                         "`python -m hanzihub.build_dataset` first.")
    long_df = pd.read_parquet(args.long)
    preds = predictions(long_df)

    if args.onsets:
        print(_format_onsets(evaluate_onsets(load_onset_gold(), preds), args.show))
        return
    if args.kwok:
        print(_format_kwok(evaluate_kwok(load_kwok_gold(), preds), args.show))
        uni, tot, margins = daughter_nucleus_agreement(long_df)
        if tot:
            avg = sum(margins) / len(margins)
            print(f"\nInternal nucleus consistency (NO external gold — do the Min "
                  f"daughters agree?):\n"
                  f"  chars with ≥2 IPA daughters   {tot}\n"
                  f"  unanimous nucleus             {uni}/{tot}  ({100*uni/tot:.1f}%)\n"
                  f"  mean winning-vote fraction    {avg:.2f}   "
                  "(1.00 = daughters always agree; .50 = coin-flip)")
        return

    gold = load_gold(args.gold)
    if not gold:
        print(_format(Report(total=0, covered=0), args.show))
        return
    print(_format(evaluate(gold, preds), args.show))


if __name__ == "__main__":
    main()
