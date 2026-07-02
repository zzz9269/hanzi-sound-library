"""Structured ML imputation of missing readings — a *reflex transducer*.

For each target dialect we fill **empty** target cells, but only when the
evidence is unambiguous. Predictions are recorded as ``source="ml"`` rows in the
long table (with the confidence as ``conf``) and surface in the wide CSV with the
``[ML]`` tag — they never overwrite sourced data. The public surface
(:func:`run`, :func:`evaluate`, :data:`IMPUTE_TARGETS`) is unchanged, so
``build_dataset`` keeps working as before.

Method — compositional per-slot prediction from sound-change categories
-----------------------------------------------------------------------
Sound change is *regular*: a modern Sinitic reading is, to first order, a
deterministic function of the **Middle Chinese category** a character descends
from (its 音韻地位: 母/開合/等/重紐/韻/聲) plus the dialect's own sound laws — the
exact thing comparative reconstruction exploits to predict Old/Middle Chinese.
So instead of copying a neighbour's exact IPA string (the old k-NN, which could
never produce an unseen syllable and abstained constantly), we *learn the
correspondences and recompose*:

1. Each target reading is segmented into ``(onset, rhyme, tone)`` slots
   (:mod:`hanzihub.segment`).
2. Features per character: the parsed MC category as one-hot **categoricals**
   (up-weighted — the historical source is the correct predictor), the sibling
   dialects' readings segmented into **aligned (onset, rhyme, tone) slot
   categoricals** (sound correspondences hold slot-by-slot), the character's
   Unihan **kPhonetic phonetic-series** class (諧聲 series-mates share a rhyme
   lineage — also the eligibility fallback for chars with no MC position), plus
   char-n-gram TF-IDF of the historical transcriptions (Baxter MC, OC, 反切,
   Tang) and of the raw sibling reading strings.
3. One small multinomial ``LogisticRegression`` per slot maps features → slot
   value. Crucially the per-slot class counts are tiny (onsets ~25, rhymes ~90,
   tones ~8), so — unlike the original whole-syllable LogReg with ~7.6k Cantonese
   classes that hung the build — each model is fast and well-posed.
4. The predicted syllable is ``onset+rhyme+tone``; the confidence is the product
   of the three slot probabilities. We accept only above a confidence gate tuned
   (against a held-out split) for **precision** — every emitted ``[ML]`` cell
   should be trustworthy.

Because prediction is compositional, the model generalises to syllables it never
saw in training, so coverage is far higher than exact-string retrieval at the
same precision.

Run ``python -m hanzihub.impute`` to print the held-out evaluation: per-slot
accuracy, whole-syllable top-1, and — the number that matters — the *precision of
accepted predictions* as the confidence gate varies.
"""
from __future__ import annotations

import re
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd

from .schema import SRC_ML
from . import merge, paths, segment

warnings.filterwarnings("ignore")

# Living-topolect + historical targets worth imputing (text-IPA columns).
IMPUTE_TARGETS = [
    "Cantonese", "Hokkien", "Teochew", "Hakka", "Wu", "Gan", "Xiang", "Jin",
    "Eastern Min (Fuzhou)", "Northern Min (Jian'ou)", "Hainanese (Haikou)",
    "Hui (Shexian)", "Middle Chinese (Baxter)",
]

# The Middle Chinese 音韻地位 descriptor — parsed into categorical features.
MC_POS_COL = "Middle Chinese (position)"
# Historical transcriptions used as char-n-gram features (finer than the
# category alone, and available for some chars that lack a parsed position).
HIST_COLS = [
    "Middle Chinese (Baxter)", "Old Chinese (Zhengzhang)", "Old Chinese",
    "Middle Chinese", "Fanqie", "Tang",
]

# Feature-group weights (categoricals dominate: they are the causal predictor).
W_MC = 3.0
W_HIST = 1.5
W_DIA = 1.0
W_SIB = 2.0    # aligned sibling (onset,rhyme,tone) slots — correspondences
W_PHON = 2.0   # Unihan kPhonetic series — chars sharing a phonetic rhyme

# Sibling columns whose primary reading is segmented into aligned
# (onset, rhyme, tone) categoricals. Sound correspondences hold slot-by-slot,
# so these beat raw char-n-grams of the same strings; the target column itself
# is excluded per-featurizer.
SIB_SLOT_SOURCES = IMPUTE_TARGETS + ["Mandarin"]

# Acceptance gate + training knobs.
TARGET_PRECISION = 0.88  # each target self-calibrates its gate to ≥ this (held-out)
CALIB_Z = 1.28           # Wilson one-sided ~90% lower bound on the calibrated precision
CONF_FLOOR = 0.50        # never accept below this confidence
CONF_CEIL = 0.95         # highest threshold the calibration grid will try
CALIB_FOLDS = 4          # k-fold out-of-fold calibration — the gate reflects the target's
                         # *true* precision, not one lucky split (kills 0↔N flicker)
MIN_VAL_ACCEPT = 25      # need ≥ this many accepted OOF cells before a bound is meaningful
MIN_CLASS_COUNT = 4      # ignore slot values rarer than this when training
MIN_OTHER_SOURCES = 2    # need ≥2 other non-empty readings (if no MC position)
MIN_TRAIN = 60           # too few labelled chars → don't bother

_IPA_OK = re.compile(r"^[^㐀-鿿]+$")  # reject Han-containing predictions


# --------------------------------------------------------------------------
# Feature plumbing
# --------------------------------------------------------------------------
def _clean(series: pd.Series) -> pd.Series:
    return (series.fillna("").astype(str)
            .str.replace(r"\[ML\]", "", regex=True).str.strip())


def _dialect_cols(wide_df: pd.DataFrame, target: str) -> list[str]:
    skip = {"char", "Definition", target, MC_POS_COL, *HIST_COLS}
    return [c for c in wide_df.columns if c not in skip]


def _mc_frame(wide_df: pd.DataFrame) -> pd.DataFrame:
    """Parse the MC position column into a 6-column categorical frame."""
    parsed = wide_df.get(MC_POS_COL, pd.Series("", index=wide_df.index))
    rows = [segment.parse_mc_position(s) or {} for s in _clean(parsed)]
    return pd.DataFrame(
        [[r.get(f, "") for f in segment.MC_FIELDS] for r in rows],
        columns=list(segment.MC_FIELDS), index=wide_df.index,
    )


def _joined_text(wide_df: pd.DataFrame, cols: list[str]) -> pd.Series:
    if not cols:
        return pd.Series("", index=wide_df.index)
    return wide_df[cols].apply(_clean).agg(" ".join, axis=1).str.strip()


# --- aligned sibling slots + phonetic series (computed once per wide_df) ---
_SLOT_FRAME_MEMO: dict[int, pd.DataFrame] = {}


def _slot_frame(wide_df: pd.DataFrame) -> pd.DataFrame:
    """(onset, rhyme, tone) of each SIB_SLOT_SOURCES column's primary reading,
    as categorical string columns named ``<col>\\x00<slot>``. Memoised on the
    wide_df object — it is segmented once, not once per target/fold."""
    key = id(wide_df)
    df = _SLOT_FRAME_MEMO.get(key)
    if df is None:
        out = {}
        for c in (c for c in SIB_SLOT_SOURCES if c in wide_df.columns):
            slots = _clean(wide_df[c]).map(_primary_slots)
            for j, part in enumerate(("ons", "rhy", "ton")):
                out[f"{c}\x00{part}"] = slots.map(
                    lambda s, j=j: s[j] if s else "")
        df = pd.DataFrame(out, index=wide_df.index)
        _SLOT_FRAME_MEMO.clear()          # keep exactly one wide_df cached
        _SLOT_FRAME_MEMO[key] = df
    return df


@lru_cache(maxsize=1)
def _phonetic_series() -> dict:
    """char → primary Unihan kPhonetic class ('中' → '322'). Characters in the
    same class share a phonetic component, hence (usually) a rhyme lineage —
    the single strongest reading predictor for chars lacking an MC position."""
    import json
    p = paths.RAW_DIR / "unihan" / "kphonetic.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {ch: v.split()[0] for ch, v in raw.items() if v}


class _Featurizer:
    """Fit MC one-hot + sibling-slot one-hot + phonetic-series one-hot +
    historical/dialect TF-IDF on a train mask; transform any."""

    def __init__(self, wide_df: pd.DataFrame, target: str):
        self.mc = _mc_frame(wide_df)
        # aligned sibling slots — every source column EXCEPT the target
        sib_all = _slot_frame(wide_df)
        self.sib = sib_all[[c for c in sib_all.columns
                            if not c.startswith(target + "\x00")]]
        # phonetic series (kPhonetic) — one categorical column
        phon_map = _phonetic_series()
        self.phon = wide_df["char"].map(
            lambda ch: phon_map.get(ch, "")).to_frame("phon") \
            if "char" in wide_df.columns and phon_map else None
        self.hist = _joined_text(wide_df, [c for c in HIST_COLS
                                           if c in wide_df.columns])
        self.dia = _joined_text(wide_df, _dialect_cols(wide_df, target))
        self.has_mc = self.mc.ne("").any(axis=1)
        self.has_phon = (self.phon["phon"].ne("") if self.phon is not None
                         else pd.Series(False, index=wide_df.index))
        self.n_dia = (wide_df[_dialect_cols(wide_df, target)].apply(_clean)
                      .ne("").sum(axis=1)) if _dialect_cols(wide_df, target) \
            else pd.Series(0, index=wide_df.index)
        self._enc = None
        self._enc_sib = None
        self._enc_phon = None
        self._vec_hist = None
        self._vec_dia = None

    def fit(self, mask: pd.Series) -> None:
        from sklearn.preprocessing import OneHotEncoder
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._enc = OneHotEncoder(handle_unknown="ignore")
        self._enc.fit(self.mc[mask])
        self._enc_sib = OneHotEncoder(handle_unknown="ignore")
        self._enc_sib.fit(self.sib[mask])
        if self.phon is not None:
            self._enc_phon = OneHotEncoder(handle_unknown="ignore")
            self._enc_phon.fit(self.phon[mask])
        for attr, text, ng in (("_vec_hist", self.hist, (1, 3)),
                               ("_vec_dia", self.dia, (1, 2))):
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=ng, min_df=2)
            try:
                vec.fit(text[mask])
            except ValueError:
                vec = None  # empty vocabulary
            setattr(self, attr, vec)

    def transform(self, mask: pd.Series):
        from scipy.sparse import hstack, csr_matrix
        parts = [self._enc.transform(self.mc[mask]) * np.sqrt(W_MC),
                 self._enc_sib.transform(self.sib[mask]) * np.sqrt(W_SIB)]
        if self._enc_phon is not None:
            parts.append(self._enc_phon.transform(self.phon[mask])
                         * np.sqrt(W_PHON))
        for vec, text, w in ((self._vec_hist, self.hist, W_HIST),
                             (self._vec_dia, self.dia, W_DIA)):
            if vec is not None:
                parts.append(vec.transform(text[mask]) * np.sqrt(w))
        return hstack([csr_matrix(p) for p in parts]).tocsr()


# --------------------------------------------------------------------------
# Labels: segment a cell into (onset, rhyme, tone) slots
# --------------------------------------------------------------------------
def _cell_slots(cell: str) -> list[tuple[str, str, str]]:
    """All ``(onset, rhyme, tone)`` tuples for a wide cell (variants included)."""
    out = []
    for reading in segment.iter_readings(cell):
        slots = segment.split_syllable(reading)
        if slots is not None:
            out.append(slots)
    return out


def _primary_slots(cell: str):
    s = _cell_slots(cell)
    return s[0] if s else None


# --------------------------------------------------------------------------
# Per-slot model
# --------------------------------------------------------------------------
def _fit_slot(X, y):
    """Train one multinomial LogReg for a slot; return (clf, classes) or None."""
    from sklearn.linear_model import LogisticRegression
    vc = pd.Series(y).value_counts()
    keep = set(vc[vc >= MIN_CLASS_COUNT].index)
    m = np.array([v in keep for v in y])
    if m.sum() < MIN_TRAIN or len(keep) < 2:
        return None
    clf = LogisticRegression(max_iter=200, C=4.0)
    clf.fit(X[m], np.asarray(y)[m])
    return clf, clf.classes_


def _predict_slot(model, X):
    """Return (pred_values, max_proba) for a fitted slot model over rows X."""
    clf, classes = model
    P = clf.predict_proba(X)
    idx = P.argmax(axis=1)
    return classes[idx], P[np.arange(P.shape[0]), idx]


def _fit_models(wide_df: pd.DataFrame, target: str, train_mask: pd.Series):
    """Fit the featurizer + three slot models for ``target``. Returns or None."""
    feat = _Featurizer(wide_df, target)
    feat.fit(train_mask)
    X_tr = feat.transform(train_mask)

    slots = _clean(wide_df[target])[train_mask].map(_primary_slots)
    valid = slots.notna().to_numpy()
    if valid.sum() < MIN_TRAIN:
        return None
    X_tr = X_tr[valid]
    ons = np.array([s[0] for s in slots[valid]])
    rhy = np.array([s[1] for s in slots[valid]])
    ton = np.array([s[2] for s in slots[valid]])

    models = tuple(_fit_slot(X_tr, y) for y in (ons, rhy, ton))
    if any(m is None for m in models):
        return None
    return feat, models


def _predict(feat: _Featurizer, models, mask: pd.Series):
    """Predict (recomposed string, confidence) for every row in ``mask``."""
    Xq = feat.transform(mask)
    (po, co), (pr, cr), (pt, ct) = (_predict_slot(m, Xq) for m in models)
    readings = [f"{o}{r}{t}" for o, r, t in zip(po, pr, pt)]
    conf = co * cr * ct
    return readings, conf


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def _eligible(feat: _Featurizer) -> pd.Series:
    """Rows with enough evidence to predict: an MC category, ≥N sibling
    readings, or a known phonetic series (kPhonetic) — series-mates share a
    rhyme lineage, so the gate can judge those predictions honestly too."""
    return feat.has_mc | feat.n_dia.ge(MIN_OTHER_SOURCES) | feat.has_phon


def _wilson_lower(k: int, n: int, z: float = CALIB_Z) -> float:
    """Wilson lower confidence bound for a binomial proportion k/n.

    Used so a threshold is trusted only when its *worst-case* precision (not the
    lucky point estimate) clears the target — small val slices are distrusted
    automatically, which is what kept Hokkien's gate honest.
    """
    if n == 0:
        return 0.0
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return center - half


def _conf_ok(wide_df, target, feat, models, mask):
    """Confidence and correctness arrays for the rows in ``mask`` (eval/calib)."""
    readings, conf = _predict(feat, models, mask)
    pred_slots = [segment.split_syllable(r) for r in readings]
    truth = [_cell_slots(c) for c in wide_df[target][mask]]
    ok = np.array([ps is not None and ps in ts
                   for ps, ts in zip(pred_slots, truth)])
    return conf, ok


def _pick_threshold(conf, ok) -> float | None:
    """Lowest confidence threshold whose Wilson-lower-bounded precision reaches
    :data:`TARGET_PRECISION`. ``None`` ⇒ abstain (precision-first contract)."""
    for thr in np.round(np.arange(CONF_FLOOR, CONF_CEIL + 1e-9, 0.05), 2):
        sel = conf >= thr
        n = int(sel.sum())
        if n >= MIN_VAL_ACCEPT and _wilson_lower(int(ok[sel].sum()), n) >= TARGET_PRECISION:
            return float(thr)
    return None


def _mask_of(wide_df, idx) -> pd.Series:
    return pd.Series(wide_df.index.isin(idx), index=wide_df.index)


def _oof_threshold(wide_df, target, pool_idx) -> float | None:
    """Calibrate the gate on out-of-fold predictions over the *whole* pool.

    Training on each fold and scoring the held-out fold gives one large,
    low-variance calibration set, so the chosen threshold reflects the target's
    true achievable precision rather than the luck of a single split.
    """
    from sklearn.model_selection import KFold

    pool = np.asarray(pool_idx)
    confs, oks = [], []
    for fit_pos, val_pos in KFold(CALIB_FOLDS, shuffle=True,
                                  random_state=42).split(pool):
        trained = _fit_models(wide_df, target, _mask_of(wide_df, pool[fit_pos]))
        if trained is None:
            continue
        c, o = _conf_ok(wide_df, target, *trained, _mask_of(wide_df, pool[val_pos]))
        confs.append(c)
        oks.append(o)
    if not confs:
        return None
    return _pick_threshold(np.concatenate(confs), np.concatenate(oks))


def _impute_one(wide_df: pd.DataFrame, target: str) -> list[dict]:
    y = _clean(wide_df[target])
    feat0 = _Featurizer(wide_df, target)
    train_mask = y.ne("") & _eligible(feat0)
    pool_idx = wide_df.index[train_mask]
    if len(pool_idx) < MIN_TRAIN * 2:
        return []

    thr = _oof_threshold(wide_df, target, pool_idx)
    if thr is None:
        return []  # abstain: can't reliably reach the precision target here

    final = _fit_models(wide_df, target, train_mask)
    if final is None:
        return []
    feat, models = final

    cand_mask = y.eq("") & _eligible(feat)
    if cand_mask.sum() == 0:
        return []
    cand_idx = wide_df.index[cand_mask]

    readings, conf = _predict(feat, models, cand_mask)
    out = []
    for idx, reading, c in zip(cand_idx, readings, conf):
        if c < thr or not reading or not _IPA_OK.match(reading):
            continue
        out.append({
            "char": wide_df.at[idx, "char"], "column": target,
            "reading": reading, "source": SRC_ML, "locality": "",
            "conf": float(c),
        })
    return out


def run(long_df: pd.DataFrame, wide_df: pd.DataFrame, *, verbose: bool = True):
    """Train + gated-impute every target; return updated (long_df, wide_df)."""
    ml_records: list[dict] = []
    for target in IMPUTE_TARGETS:
        if target not in wide_df.columns:
            continue
        try:
            recs = _impute_one(wide_df, target)
        except Exception as e:  # one bad target must not sink the whole pass
            if verbose:
                print(f"[impute] {target:26} skipped ({type(e).__name__}: {e})")
            continue
        if verbose:
            print(f"[impute] {target:26} accepted {len(recs):,}")
        ml_records += recs

    if not ml_records:
        return long_df, wide_df
    long_df = pd.concat([long_df, pd.DataFrame.from_records(ml_records)],
                        ignore_index=True)
    wide_df = merge.wide_table(long_df)
    if verbose:
        print(f"[impute] total accepted predictions: {len(ml_records):,}")
    return long_df, wide_df


# --------------------------------------------------------------------------
# Held-out evaluation: how accurate / trustworthy are the predictions?
# --------------------------------------------------------------------------
def evaluate(wide_df: pd.DataFrame, *, test_size: float = 0.2,
             seed: int = 42, verbose: bool = True) -> pd.DataFrame:
    """Hide a fraction of *known* cells, predict them, and measure quality.

    Reports, per target on the held-out cells: per-slot accuracy
    (``onset``/``rhyme``/``tone``), whole-syllable ``top1``, and the
    confidence-gated ``coverage`` / ``precision`` (accuracy among accepted) —
    i.e. how often an emitted ``[ML]`` cell is correct. A prediction counts as
    correct if it matches *any* variant listed in the held-out cell.
    """
    from sklearn.model_selection import train_test_split

    rows = []
    pooled_conf: list[np.ndarray] = []
    pooled_ok: list[np.ndarray] = []
    for target in IMPUTE_TARGETS:
        if target not in wide_df.columns:
            continue
        y = _clean(wide_df[target])
        feat0 = _Featurizer(wide_df, target)
        pool_mask = y.ne("") & _eligible(feat0)
        pool_idx = wide_df.index[pool_mask]
        if len(pool_idx) < MIN_TRAIN * 2:
            continue

        train_idx, test_idx = train_test_split(
            pool_idx, test_size=test_size, random_state=seed)
        test_m = pd.Series(wide_df.index.isin(test_idx), index=wide_df.index)

        # Calibrate the gate exactly as run() does (OOF over the train pool),
        # then fit final models on all of train and score the held-out test.
        thr = _oof_threshold(wide_df, target, train_idx)
        trained = _fit_models(wide_df, target,
                              pd.Series(wide_df.index.isin(train_idx),
                                        index=wide_df.index))
        if trained is None:
            continue
        feat, models = trained

        readings, conf = _predict(feat, models, test_m)
        truth = [_cell_slots(c) for c in wide_df[target][test_m]]
        pred_slots = [segment.split_syllable(r) for r in readings]

        ok = np.array([ps is not None and ps in ts
                       for ps, ts in zip(pred_slots, truth)])
        # per-slot accuracy (against the primary variant)
        prim = [t[0] if t else None for t in truth]
        slot_acc = []
        for j in range(3):
            hit = [ps is not None and p is not None and ps[j] == p[j]
                   for ps, p in zip(pred_slots, prim)]
            slot_acc.append(float(np.mean(hit)) if hit else float("nan"))

        accept = conf >= thr if thr is not None else np.zeros(len(conf), bool)
        pooled_conf.append(conf)
        pooled_ok.append(ok)
        rows.append({
            "target": target, "n_test": len(readings),
            "onset": round(slot_acc[0], 3), "rhyme": round(slot_acc[1], 3),
            "tone": round(slot_acc[2], 3),
            "top1": round(float(ok.mean()), 3),
            "gate": thr if thr is not None else float("nan"),
            "coverage": round(float(accept.mean()), 3),
            "precision": (round(float(ok[accept].mean()), 3)
                          if accept.any() else float("nan")),
            "n_accept": int(accept.sum()),
        })

    res = pd.DataFrame(rows)
    if verbose and not res.empty:
        print("\nHeld-out evaluation (MC weight=%.1f, per-target gate ≥%.0f%% precision):"
              % (W_MC, 100 * TARGET_PRECISION))
        print(res.to_string(index=False))
        all_conf = np.concatenate(pooled_conf)
        all_ok = np.concatenate(pooled_ok)
        print("\nAccepted-precision vs. confidence threshold (all targets pooled):")
        print(" thresh   precision   coverage   n")
        for thr in (0.30, 0.40, 0.50, 0.60, 0.70, 0.80):
            sel = all_conf >= thr
            prec = all_ok[sel].mean() if sel.any() else float("nan")
            print(f"  {thr:.2f}    {prec:8.3f}   {sel.mean():8.3f}   {int(sel.sum()):6d}")
    return res


if __name__ == "__main__":
    import sys
    from . import paths
    for _s in (sys.stdout, sys.stderr):      # CJK/IPA-safe console (cp1252 → utf-8)
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    long_df = pd.read_parquet(paths.READINGS_LONG)
    long_df = long_df[long_df["source"] != SRC_ML]      # eval on sourced data only
    wide_df = merge.wide_table(long_df)
    evaluate(wide_df)
