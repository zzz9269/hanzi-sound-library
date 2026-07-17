"""UI-free core for the 漢字音庫 app: data loading, IPA rendering/approximation,
TTS, Google translation/romanization, and Japanese/Korean helpers.

Ported from the 漢字音庫_v9.ipynb cell so the Streamlit app (``app.py``) and any
other front-end can share one implementation. Nothing here imports Streamlit or
ipywidgets — functions return data or HTML strings.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import html as _html
import itertools
import logging
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import paths
from .schema import PREFERRED_ORDER  # single source of truth (was drifting here)

# Silent-degradation points (missing credentials, dead scraper, unreadable
# cache) log here instead of vanishing — enable with
# ``logging.basicConfig(level=logging.INFO)`` or via Streamlit's logger config.
log = logging.getLogger("hanzihub")

# --------------------------------------------------------------- voices ----
VOICE_JA = ("ja-JP", "ja-JP-Wavenet-B")
VOICE_KO = ("ko-KR", "ko-KR-Wavenet-A")
VOICE_ZH = ("cmn-CN", "cmn-CN-Wavenet-A")
VOICE_YUE = ("yue-HK", "yue-HK-Standard-A")
VOICE_VI = ("vi-VN", "vi-VN-Wavenet-A")

PROJECT_ID = "zach-ipa-tts-2025"
PARENT = f"projects/{PROJECT_ID}/locations/global"

EXCLUDE_COLS = {"fanqie_upper", "fanqie_lower"}
COMBINED_CSV = str(paths.COMBINED_CSV if paths.COMBINED_CSV.exists()
                   else paths.LEGACY_COMBINED_CSV)
IPA_FILE = str(paths.IPA_LIBRARY_TXT)
CACHE_DIR = str(paths.ROOT / "cache")

_RE_HANGUL = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힯]+")
_HANZI_RE = re.compile(r"[㐀-鿿\U00020000-\U0002FFFF]")


# =====================================================================
# Google Cloud clients (Application Default Credentials)
# =====================================================================
@lru_cache(maxsize=1)
def translate_client():
    try:
        from google.cloud import translate_v3 as translate
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return translate.TranslationServiceClient()
        legacy = paths.ROOT / "TTS" / "tts-robot-key.json"
        return (translate.TranslationServiceClient.from_service_account_file(str(legacy))
                if legacy.exists() else translate.TranslationServiceClient())
    except Exception as e:
        log.warning("translate client unavailable: %s", e)
        return None


@lru_cache(maxsize=1)
def tts_client():
    try:
        from google.cloud import texttospeech as gcp_tts
        return gcp_tts.TextToSpeechClient()
    except Exception as e:
        log.warning("TTS client unavailable: %s", e)
        return None


def gt_ready() -> bool:
    return translate_client() is not None


def gtrans_translate_text(text: str, target: str, source: str | None = None) -> str:
    cli = translate_client()
    if not cli or not text:
        return ""
    try:
        req = {"parent": PARENT, "contents": [text], "target_language_code": target}
        if source:
            req["source_language_code"] = source
        resp = cli.translate_text(request=req)
        return resp.translations[0].translated_text or "" if resp.translations else ""
    except Exception as e:
        log.warning("translate_text failed: %s", e)
        return ""


def gtrans_romanize(text: str, source_lang: str) -> str:
    cli = translate_client()
    if not cli or not text:
        return ""
    try:
        resp = cli.romanize_text(request={
            "parent": PARENT, "contents": [text], "source_language_code": source_lang})
        return resp.romanizations[0].romanized_text or "" if resp.romanizations else ""
    except Exception as e:
        log.warning("romanize_text failed: %s", e)
        return ""


def rom_zh(s: str) -> str:
    return gtrans_romanize(s, "zh") or ""


@lru_cache(maxsize=1)
def char_meta() -> dict:
    """char → {{'strokes': int, 'radical': int}} from Unihan IRGSources (cache)."""
    import json
    p = paths.ROOT / "data" / "raw" / "unihan" / "char_meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("char_meta cache unreadable: %s", e)
        return {}


def kangxi_radical(n: int) -> str:
    """Kangxi radical glyph for radical number ``n`` (1–214), e.g. 143 → ⾎."""
    return chr(0x2F00 + n - 1) if isinstance(n, int) and 1 <= n <= 214 else ""


def pinyin(text: str) -> str:
    """Local tone-marked Hanyu Pinyin for a Han string (offline, via pypinyin)."""
    try:
        from pypinyin import lazy_pinyin, Style
        return "".join(lazy_pinyin(text, style=Style.TONE))
    except Exception:
        return gtrans_romanize(text, "zh") or ""


class TranslationError(RuntimeError):
    """Raised when the Google Translation API call fails (quota, auth, …)."""


def _friendly_translate_error(e: Exception) -> str:
    s = str(e)
    if "RESOURCE_EXHAUSTED" in s or "429" in s:
        return ("Google Translation daily quota exceeded. It resets each day; to "
                "lift it, raise the quota or confirm billing for project "
                f"{PROJECT_ID} in the Google Cloud console.")
    if "PERMISSION_DENIED" in s or "403" in s:
        return ("Translation API permission denied — enable the Cloud Translation "
                "API and check the service-account has access.")
    return f"{type(e).__name__}: {s[:200]}"


def translate_text(text: str, target: str, source: str | None = None) -> str:
    """Translate ``text`` → ``target``. Returns ``''`` only for empty input, but
    **raises** :class:`TranslationError` on any API failure, so callers surface
    quota/credential problems instead of silently echoing the input."""
    if not text:
        return ""
    cli = translate_client()
    if cli is None:
        raise TranslationError("Translation client not initialized (no credentials).")
    try:
        req = {"parent": PARENT, "contents": [text], "target_language_code": target}
        if source:
            req["source_language_code"] = source
        resp = cli.translate_text(request=req)
        return (resp.translations[0].translated_text or "") if resp.translations else ""
    except Exception as e:
        raise TranslationError(_friendly_translate_error(e))


# =====================================================================
# TTS (Google Cloud → mp3 bytes, disk-cached)
# =====================================================================
def _tts_cache_path(token, lang, voice) -> Path:
    key = hashlib.sha1(f"{token}|{lang}|{voice}".encode("utf-8")).hexdigest()
    p = Path(CACHE_DIR) / "tts_cache" / f"{key}.mp3"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def tts_bytes(text: str, lang: str, voice: str | None) -> bytes:
    p = _tts_cache_path(text, lang, voice or "")
    if p.exists():
        return p.read_bytes()
    cli = tts_client()
    if cli is None:
        raise RuntimeError("Google Cloud TTS not available")
    from google.cloud import texttospeech as gcp_tts
    sinput = gcp_tts.SynthesisInput(text=text)
    aconf = gcp_tts.AudioConfig(audio_encoding=gcp_tts.AudioEncoding.MP3)
    try:
        vsel = gcp_tts.VoiceSelectionParams(language_code=lang, name=voice)
        data = cli.synthesize_speech(input=sinput, voice=vsel, audio_config=aconf).audio_content
    except Exception:
        vsel = gcp_tts.VoiceSelectionParams(language_code=lang)
        data = cli.synthesize_speech(input=sinput, voice=vsel, audio_config=aconf).audio_content
    p.write_bytes(data)
    return data


def audio_html(text: str, lang: str, voice: str, label: str | None = None) -> str:
    """Inline autoplay-off <audio> player with a clickable label."""
    try:
        mp3 = tts_bytes(text, lang, voice)
    except Exception as e:
        log.info("TTS synth failed for %r: %s", text, e)
        return _html.escape(label or text)
    b64 = base64.b64encode(mp3).decode("utf-8")
    return ('<audio controls preload="none" style="height:28px;vertical-align:middle">'
            f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>')


# --- Taiwanese Hokkien TTS (意傳科技 ithuan.tw) -------------------------
# Google Cloud has no Min voice. 意傳's open services fill the gap: hokbu
# annotates Hanzi with tâi-lô (KIP) and hapsing synthesizes it with their
# SuiSiann voice. The model is trained on natural Taiwanese speech, so TONE
# SANDHI IS APPLIED by the model itself — the audio matches the "↳ spoken:"
# surface-tone line, not the citation readings. It is a free community
# service: responses are disk-cached like Google TTS, one request per phrase.
ITHUAN_ANNOTATE_URL = "https://hokbu.ithuan.tw/tau"
ITHUAN_SYNTH_URL = "https://hapsing.ithuan.tw/bangtsam"


def hokkien_tailo(text: str) -> str:
    """Tâi-lô (KIP) romanisation of Hanzi ``text`` from 意傳's 標漢字音標
    service. Characters it cannot read come back as ``?``."""
    import requests
    r = requests.post(ITHUAN_ANNOTATE_URL, data={"taibun": text}, timeout=30)
    r.raise_for_status()
    return ((r.json().get("kiatko") or [{}])[0].get("KIP") or "").strip()


def hokkien_tts_bytes(text: str) -> tuple[bytes, str]:
    """``(mp3, tâi-lô)`` for Hanzi ``text`` spoken in Taiwanese Hokkien with
    natural tone sandhi. Raises on network failure or unreadable input."""
    p = _tts_cache_path(text, "nan-TW", "ithuan-suisiann")
    kp = p.with_suffix(".kip.txt")
    if p.exists() and kp.exists():
        return p.read_bytes(), kp.read_text("utf-8")
    kip = hokkien_tailo(text)
    if not re.search(r"[A-Za-zÀ-ȳ]", kip):
        raise RuntimeError(f"no tâi-lô reading for {text!r}")
    import requests
    r = requests.get(ITHUAN_SYNTH_URL, params={"taibun": kip}, timeout=60)
    r.raise_for_status()
    mp3 = r.content
    # a real answer is MP3 (ID3 tag or raw frame sync), not an error page
    if len(mp3) < 512 or not (mp3.startswith(b"ID3") or mp3[:1] == b"\xff"):
        raise RuntimeError("ithuan.tw synthesis returned no audio")
    p.write_bytes(mp3)
    kp.write_text(kip, "utf-8")
    return mp3, kip


# =====================================================================
# Japanese / Korean local helpers
# =====================================================================
@lru_cache(maxsize=1)
def jpvariant_map() -> dict:
    try:
        import opencc
        path = os.path.join(os.path.dirname(opencc.__file__), "dictionary", "JPVariants.txt")
    except Exception:
        return {}
    mapping = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and len(parts[1]) == 1:
                    mapping[parts[0]] = parts[1]
    except Exception:
        pass
    return mapping


def to_shinjitai_per_char(s: str) -> str:
    m = jpvariant_map()
    return "".join(m.get(ch, ch) for ch in (s or ""))


def kana_hira_to_kata(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in (s or ""))


def prep_ja_tts(kana: str, fallback_kanji: str) -> str:
    k = re.sub(r"\s+", "", (kana or ""))
    return kana_hira_to_kata(k) if k else fallback_kanji


@lru_cache(maxsize=1)
def _kana_romaji_mod():
    """Load the repo-root ``kana_romaji_utils.py`` by path — no sys.path hack."""
    import importlib.util
    p = paths.ROOT / "kana_romaji_utils.py"
    spec = importlib.util.spec_from_file_location("kana_romaji_utils", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def romaji_to_hiragana(s: str) -> str:
    try:
        return _kana_romaji_mod().romaji_to_hiragana(s)
    except Exception as e:
        log.info("romaji_to_hiragana failed: %s", e)
        return ""


@lru_cache(maxsize=1)
def _kakasi():
    import pykakasi
    return pykakasi.kakasi()


def kata_to_romaji(s: str) -> str:
    """One kana reading → lowercase Hepburn romaji (シン → 'shin'). '' on failure."""
    try:
        return "".join(x["hepburn"] for x in _kakasi().convert(s)).lower() if s else ""
    except Exception:
        return ""


@lru_cache(maxsize=1)
def _ko_transliter():
    from hangul_romanize import Transliter
    from hangul_romanize.rule import academic
    return Transliter(academic)


def rom_ko(s: str) -> str:
    try:
        return _ko_transliter().translit(s) if s else ""
    except Exception:
        return ""


def ko_from_hanzi_local(src_hanzi: str):
    try:
        from hanja import translate as hanja_to
        hangul = hanja_to(src_hanzi, "substitution") or ""
    except Exception:
        hangul = ""
    return hangul, (rom_ko(hangul) if hangul else "")


def ko_per_char_pairs(text: str) -> str:
    from hanja import translate as hanja_to
    pairs = []
    for ch in text:
        try:
            hg = hanja_to(ch, "substitution") or ""
        except Exception:
            hg = ""
        rom = rom_ko(hg) if hg else ""
        pairs.append(f"{ch}({hg} {rom})" if hg and rom else (f"{ch}({hg})" if hg else ch))
    return " ".join(pairs)


def has_hangul(s: str) -> bool:
    return bool(_RE_HANGUL.search(s or ""))


def looks_like_hanzi(s: str) -> bool:
    return bool(_HANZI_RE.search(s or ""))


def hanzi_only(s: str) -> str:
    """Just the Hanzi of ``s`` — for wording comparisons that should ignore
    punctuation/whitespace differences (MT normalizes punctuation)."""
    return "".join(_HANZI_RE.findall(s or ""))


# =====================================================================
# Text helpers
# =====================================================================
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()


def inline_tokens(val: str) -> str:
    return " ".join(t for t in re.split(r"[\/\|,;]+\s*|\s+", (val or "").strip()) if t)


def split_opts(s: str):
    return [t for t in re.split(r"[\/\|,;]+\s*|\s+", (s or "").strip()) if t]


def sorted_cols(cols):
    return sorted(cols, key=lambda k: (
        PREFERRED_ORDER.index(k) if k in PREFERRED_ORDER else 10_000, k.lower()))


# =====================================================================
# Data loading
# =====================================================================
def _read_wide_table(csv_path: str) -> pd.DataFrame:
    """Read the wide table, via a self-maintaining parquet mirror: if a sibling
    ``.parquet`` at least as new as the CSV exists it is read instead (~10×
    faster); otherwise the CSV is read and the mirror is (best-effort) written
    for next start."""
    p_csv = Path(csv_path)
    p_parq = p_csv.with_suffix(".parquet")
    try:
        if p_parq.exists() and p_parq.stat().st_mtime >= p_csv.stat().st_mtime:
            return pd.read_parquet(p_parq).fillna("").astype(str)
    except Exception as e:
        log.warning("parquet mirror unreadable (%s) — falling back to CSV", e)
    df = pd.read_csv(p_csv, dtype=str, keep_default_na=False)
    try:
        df.to_parquet(p_parq, index=False)
    except Exception as e:
        log.info("could not write parquet mirror: %s", e)
    return df


def load_combined(csv_path: str = COMBINED_CSV):
    df = _read_wide_table(csv_path)
    cols = list(df.columns)
    ch_col = next((c for c in cols if _norm(c) in {"char", "character", "zi", "漢字", "字"}), cols[0])
    excl = {re.sub(r"\s+", " ", c.lower()) for c in EXCLUDE_COLS}
    dialect_cols = [c for c in cols if c != ch_col
                    and re.sub(r"\s+", " ", c.lower()) not in excl]
    # Vectorised build (iterrows took ~19s on 67k×99; this takes <2s): pull the
    # value matrix once and zip; NFC-normalise only non-ASCII values.
    _nfc = unicodedata.normalize
    chars = df[ch_col].astype(str).str.strip()
    values = df[dialect_cols].to_numpy()
    data = {}
    for ch, row in zip(chars.to_numpy(), values):
        if len(ch) != 1:
            continue
        bucket = {}
        for d, val in zip(dialect_cols, row):
            v = val.strip()
            if v and v != "-" and v.lower() != "nan":
                bucket[d] = v if v.isascii() else _nfc("NFC", v)
        if bucket:
            data[ch] = bucket
    return data, dialect_cols


# --------------------------------------------------------------------------
# Romanisation reverse index: latin reading token → {char: {columns}}
# Lets the search box accept "tian", "tin1", "then" (Baxter MC!), "ten",
# "thien" … and find the characters that carry that reading in any column.
# --------------------------------------------------------------------------
_LATIN_TOKEN_RE = re.compile(r"[a-z0-9'\-]+")


def fold_reading_query(q: str) -> str:
    """Diacritic-stripped, lowercased form of a reading query (tiān → tian)."""
    base = unicodedata.normalize("NFD", (q or "").strip())
    return "".join(c for c in base if not unicodedata.combining(c)).lower()


def build_reading_index(data: dict) -> dict[str, dict[str, set]]:
    """token → {char: {columns it appears in}} over all non-locality columns.
    Tokens are indexed both as-is (tin1) and tone-digit-stripped (tin)."""
    idx: dict[str, dict[str, set]] = {}
    for ch, bucket in data.items():
        for col, val in bucket.items():
            if col.startswith("dial:") or col == "Definition":
                continue
            for tok in re.split(r"[\s|/,;·()\[\]]+", val):
                tok = fold_reading_query(tok.strip("*[](){}"))
                if not (1 < len(tok) <= 12) or not _LATIN_TOKEN_RE.fullmatch(tok):
                    continue
                keys = {tok}
                bare = tok.rstrip("0123456789")
                if len(bare) > 1:
                    keys.add(bare)
                for k in keys:
                    idx.setdefault(k, {}).setdefault(ch, set()).add(col)
    return idx


# --------------------------------------------------------------------------
# Per-character markdown report (download/export)
# --------------------------------------------------------------------------
_REPORT_SECTIONS = [
    ("Sinitic topolects", ["Mandarin", "Cantonese", "Hokkien", "Teochew",
                           "Eastern Min (Fuzhou)", "Northern Min (Jian'ou)",
                           "Hainanese (Haikou)", "Hakka", "Wu", "Hui (Shexian)",
                           "Gan", "Xiang", "Jin"]),
    ("Historical layers", ["Old Chinese", "Old Chinese (Zhengzhang)",
                           "Proto-Min", "Middle Chinese",
                           "Middle Chinese (Baxter)", "Middle Chinese (position)",
                           "Tang", "Fanqie"]),
    ("Sinosphere", ["Japanese", "Japanese On", "Japanese Kun", "Okinawan",
                    "Korean (Hangul)", "Korean (romanized)", "Korean (Yale)",
                    "Vietnamese", "Zhuang"]),
]


def char_report_md(ch: str, bucket: dict, prov_rows=None, meta=None) -> str:
    """Self-contained markdown report for one character: readings by section
    (tones unified to Chao letters), locality layer, provenance."""
    meta = meta or {}
    lines = [f"# {ch} — 漢字音庫 · Hanzi Sound Library", ""]
    chips = [f"U+{ord(ch):04X}"]
    if meta.get("strokes"):
        chips.append(f"{meta['strokes']} strokes")
    if meta.get("radical"):
        chips.append(f"radical {meta['radical']}")
    lines.append(" · ".join(chips))
    if bucket.get("Definition"):
        lines += ["", f"**Definition:** {bucket['Definition']}"]
    for title, cols in _REPORT_SECTIONS:
        rows = [(c, tones_to_chao(bucket[c], c)) for c in cols if bucket.get(c)]
        if not rows:
            continue
        lines += ["", f"## {title}", "", "| Reading of | Value |", "|---|---|"]
        lines += [f"| {c} | {v.replace('|', ' / ')} |" for c, v in rows]
    dial = [(c, tones_to_chao(bucket[c], c)) for c in sorted(bucket)
            if c.startswith("dial:") and bucket[c]]
    if dial:
        lines += ["", f"## Locality readings ({len(dial)} points)", "",
                  "| Locality | Reading |", "|---|---|"]
        lines += [f"| {c[5:]} | {v.replace('|', ' / ')} |" for c, v in dial]
    if prov_rows:
        lines += ["", "## Provenance", "",
                  "| Column | Reading | Source | Conf |", "|---|---|---|---|"]
        for col, reading, source, conf in prov_rows:
            c = "" if conf in (None, "") or conf != conf else f"{float(conf):.2f}"
            lines.append(f"| {col} | {str(reading).replace('|', ' / ')} "
                         f"| {source} | {c} |")
    lines += ["", "---", "Generated by 漢字音庫 (Hanzi Sound Library). "
              "Tones are Chao tone letters; ¹⁻⁸ on Proto-Min / Baxter MC are "
              "tone categories, not pitches."]
    return "\n".join(lines) + "\n"


def load_provenance(root=None) -> dict:
    p = Path(root or paths.ROOT) / "data" / "out" / "readings_long.parquet"
    if not p.exists():
        return {}
    try:
        ldf = pd.read_parquet(p)
    except Exception as e:
        log.warning("provenance parquet unreadable: %s", e)
        return {}
    keep = [c for c in ("char", "column", "reading", "source", "conf") if c in ldf.columns]
    prov: dict[str, list] = {}
    for r in ldf[keep].itertuples(index=False):
        ch = str(getattr(r, "char", "") or "")
        if len(ch) == 1:
            prov.setdefault(ch, []).append((
                getattr(r, "column", ""), getattr(r, "reading", ""),
                getattr(r, "source", ""), getattr(r, "conf", None)))
    return prov


@lru_cache(maxsize=1)
def _s2t_converter():
    try:
        import opencc
        return opencc.OpenCC("s2t")
    except Exception:
        return None


@lru_cache(maxsize=4096)
def s2t_text(text: str) -> str:
    """Phrase-aware simplified→traditional conversion (OpenCC), used to fall
    back to the traditional form's readings — the dataset is keyed by
    traditional characters, so simplified input otherwise finds starved rows.
    Returns ``text`` unchanged if OpenCC is unavailable or the conversion is
    not 1:1 per character (callers need positional alignment)."""
    conv = _s2t_converter()
    if not text or conv is None:
        return text
    try:
        out = conv.convert(text)
    except Exception:
        return text
    return out if len(out) == len(text) else text


def per_char_tokens(data, dialect, s, alt=None):
    """``[(char, reading-or-None), …]`` for each char of ``s``. An empty cell
    falls back to the same position in ``alt`` (the s2t_text conversion of
    ``s``) before giving up."""
    if not (alt and len(alt) == len(s)):
        alt = None
    pairs = []
    for i, ch in enumerate(s):
        tok = split_opts(data.get(ch, {}).get(dialect, ""))
        if not tok and alt and alt[i] != ch:
            tok = split_opts(data.get(alt[i], {}).get(dialect, ""))
        pairs.append((ch, tok[0] if tok else None))
    return pairs


def concat_per_char(data, dialect, s, alt=None):
    return " ".join((tok or ch) for ch, tok in per_char_tokens(data, dialect, s, alt) if tok or ch)


def with_trad_fallback(data, ch):
    """``(bucket, trad)`` — the char's bucket with empty columns backfilled
    from its traditional form; ``trad`` is that form when any backfill
    happened, else None."""
    bucket = dict(data.get(ch, {}))
    trad = s2t_text(ch)
    if trad == ch or trad not in data:
        return bucket, None
    used = False
    for col, v in data[trad].items():
        if v and not bucket.get(col):
            bucket[col] = v
            used = True
    return bucket, (trad if used else None)


def per_char_pairs_from_csv(data, text, dialect):
    pairs = []
    for ch in text:
        tok = split_opts(data.get(ch, {}).get(dialect, ""))
        pairs.append(f"{ch}({tok[0] if tok else ch})")
    return " ".join(pairs)


# =====================================================================
# IPA: [ML] styling, English approximation, legend
# =====================================================================
_ALT_SEP = " <span style='color:#5a6172'>·</span> "

# Amber "predicted" pill appended to any machine-imputed reading so generated
# pronunciations stand out at a glance (was a faint grey <sup>ML</sup>).
ML_TOOLTIP = "Machine-predicted — inferred by model, not attested in any source"
ML_BADGE = (
    f'<span title="{ML_TOOLTIP}" style="display:inline-block;margin-left:5px;'
    "padding:0 5px;border-radius:6px;font-size:.7em;font-weight:700;"
    "letter-spacing:.4px;vertical-align:middle;background:rgba(225,168,70,.16);"
    'color:#e0a846;border:1px solid rgba(225,168,70,.45)">🤖 ML</span>'
)


def is_ml_reading(val: str) -> bool:
    """True if any alternative in the cell is a machine-predicted ([ML]) reading."""
    return "[ML]" in (val or "")


def render_readings_html(val: str, column: str | None = None) -> str:
    """Render a cell's ``|``-separated alternative readings, each visibly
    separated, with any ``[ML]``-tagged alternative styled as inferred and
    tagged with a prominent amber 🤖 ML pill. ``column`` drives the unified
    Chao tone-letter display (scheme choice + category-column exemptions)."""
    alts = [t.strip() for t in re.split(r"\s*[|/]\s*", (val or "").strip()) if t.strip()]
    out = []
    for t in alts:
        if t.endswith("[ML]"):
            out.append(f'<span style="color:#d8c79b;font-style:italic" title="{ML_TOOLTIP}">'
                       f"{chao_html(tones_to_chao(t[:-4], column))}</span>{ML_BADGE}")
        else:
            out.append(chao_html(tones_to_chao(t, column)))
    return _ALT_SEP.join(out)


def approx_text(val: str) -> str:
    """Plain ``a / b`` English approximation of a cell's alternatives (for tables)."""
    aps: list[str] = []
    for a in re.split(r"\s*[|/]\s*", (val or "").strip()):
        x = ipa_to_english(tones_to_chao(a))
        if x and x not in aps:
            aps.append(x)
    return " / ".join(aps)


_IPA_ENG = {
    "tsʰ": "ts", "tɕʰ": "ch", "tʂʰ": "chr", "tʰ": "t", "pʰ": "p", "kʰ": "k",
    "cʰ": "ch", "ʈʰ": "tr", "kʷ": "kw", "ɡʷ": "gw",
    "ts": "dz", "tɕ": "j", "tʂ": "jr", "dʑ": "j", "dz": "dz", "dʐ": "jr",
    "uai": "wy", "iau": "yow", "uei": "way", "iou": "yoh", "yɛ": "yweh",
    "ai": "igh", "ɑi": "igh", "ɐi": "igh", "ei": "ay", "au": "ow", "ɑu": "ow",
    "ɐu": "ow", "ou": "oh", "ɔu": "ow",
    "ui": "wee", "ua": "wah", "uo": "waw", "uɔ": "waw", "uɛ": "weh",
    "uᴇ": "weh", "ue": "way", "uə": "wuh",
    "ia": "yah", "iɛ": "yeh", "iᴇ": "yeh", "ie": "yeh", "io": "yoh",
    "iu": "yoo", "iə": "yuh", "yn": "ewn", "ym": "ewm",
    "ɲ": "ny", "ŋ": "ng", "ɳ": "n", "ɱ": "m",
    "p": "b", "t": "d", "k": "g", "c": "j", "ʈ": "dr", "ɖ": "dr", "b": "b",
    "d": "d", "ɡ": "g", "g": "g", "q": "g", "ɢ": "g",
    "ɕ": "sh", "ʂ": "sh", "ʃ": "sh", "ʑ": "zh", "ʐ": "r", "ʒ": "zh", "s": "s",
    "z": "z", "f": "f", "v": "v", "h": "h", "x": "h", "ɣ": "gh", "ɦ": "h", "χ": "h",
    "m": "m", "n": "n", "l": "l", "ɬ": "hl", "ɭ": "l", "ɾ": "r", "r": "r",
    "ɹ": "r", "j": "y", "ɥ": "yu", "w": "w", "ʋ": "v", "ʔ": "'",
    "i": "ee", "y": "ew", "ɨ": "i", "ʉ": "u", "ɯ": "oo", "u": "oo",
    "ɪ": "ih", "ʏ": "ew", "ʊ": "uu", "e": "ay", "ᴇ": "eh", "ø": "er", "ɘ": "uh",
    "ɵ": "er", "ɤ": "uh", "o": "oh", "ə": "uh", "ɛ": "eh", "œ": "er", "ɜ": "er",
    "ʌ": "uh", "ɔ": "aw", "æ": "a", "ɐ": "uh", "a": "ah", "ɑ": "ah", "ɒ": "aw",
    "ɿ": "rr", "ʅ": "rr", "ɚ": "er", "ɝ": "er",
    # affricate ligatures (= ts / dz / tʃ / dʒ / tɕ / dʑ) + retroflex affricates
    "ʈʂʰ": "chr", "ʈʂ": "jr", "ɖʐ": "jr",
    "ʦʰ": "ts", "ʧʰ": "ch", "ʨʰ": "ch",
    "ʦ": "dz", "ʣ": "dz", "ʧ": "ch", "ʤ": "j", "ʨ": "j", "ʥ": "j",
    # implosives, extra fricatives, alveolo-palatal nasal, retroflex r
    "ɓ": "b", "ɗ": "d", "ɸ": "f", "β": "v", "θ": "th", "ð": "dh",
    "ȵ": "ny", "ɻ": "r", "ʁ": "r", "ɭ": "l",
    # superscript modifiers: pre-nasalisation, secondary articulation, release
    "ᵐ": "m", "ᵑ": "ng", "ᵐb": "mb", "ⁱ": "y", "ᵘ": "w", "ˡ": "l",
    "ʳ": "r", "ʸ": "y", "ᵏ": "k", "ᵗ": "t", "ᵖ": "p", "ᵇ": "b", "ᵈ": "d",
    "ʰ": "h", "ː": "", "ˤ": "", "ʲ": "y", "ʷ": "w", "ⁿ": "n",
    # labialized CODA (syllable-final) — the off-glide is reordered BEFORE the
    # stop by _CODA_LABIAL so it reads "ghawk" not "ghakw" (you can't voice a "w"
    # after a final "k"). The stop stays a plain final -k/-p/-t here (clearer to a
    # layman than the lenited g/b/d bare-coda gives).
    "ʷk": "wk", "ʷp": "wp", "ʷt": "wt", "ʷŋ": "wng",
    "̃": "ⁿ", "̩": "",
    # Chao tone letters pass through unchanged — the unified tone display
    # keeps the same contour glyphs in the ≈ gloss as in the reading itself
    "˥": "˥", "˦": "˦", "˧": "˧", "˨": "˨", "˩": "˩",
    # residual tone digits (category superscripts on exempt columns, or digits
    # tones_to_chao declined to convert) survive as superscripts in the gloss
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "⁰": "⁰", "¹": "¹", "²": "²", "³": "³", "⁴": "⁴",
    "⁵": "⁵", "⁶": "⁶", "⁷": "⁷", "⁸": "⁸", "⁹": "⁹",
}
_IPA_KEYS = sorted(_IPA_ENG, key=len, reverse=True)

# --- monosyllabic respelling -------------------------------------------------
# A Han syllable has exactly one vowel nucleus; everything else in its vowel run
# is a glide (medial or off-glide), not another syllable. Mapping every vowel
# symbol to a full English digraph (ɛ→"eh", u→"oo") turns one syllable into two
# ("ehoo"). So within a vowel run we keep only the most-open vowel as the
# nucleus and respell the others as y / w / yu glides — except the curated
# diphthongs in _IPA_ENG (ai→"igh", au→"ow", iɛ→"yeh"…), which already read as a
# single syllable and have nicer spellings than the generic fold would give.
_V_BASE = set("aɑɒɐæeɛᴇəɘɤʌɵɜoɔøœiɨʉɯuʊyɪʏ")
_V_OPEN = {}
for _grp, _rank in (("aɑɒ", 6), ("ɐæ", 5), ("ɛɔœɜ", 4),
                    ("eoø", 3), ("əɘɤʌɵ", 2), ("ɪʏʊ", 1)):
    for _c in _grp:
        _V_OPEN[_c] = _rank          # unlisted high vowels (i y ɨ ʉ ɯ u) → 0
_GLIDE_FRONT = set("iɪeɛæ")          # front  → j  (renders "y")
_GLIDE_ROUND = set("yʏøœ")           # round front → ɥ (renders "yu")
_DIPH_KEEP = {k for k in _IPA_ENG if len(k) >= 2 and all(c in _V_BASE for c in k)}
_NONSYL = re.compile("([" + "".join(_V_BASE) + "])̯")


def _glide_for(v: str) -> str:
    if v in _GLIDE_ROUND:
        return "ɥ"
    if v in _GLIDE_FRONT:
        return "j"
    return "w"                        # back / central → w


def _fold_vowel_runs(r: str) -> str:
    out, i, L = [], 0, len(r)
    while i < L:
        if r[i] in _V_BASE:
            j = i
            while j < L and r[j] in _V_BASE:
                j += 1
            run = r[i:j]
            if len(run) >= 2 and run not in _DIPH_KEEP:
                nuc = max(range(len(run)), key=lambda k: _V_OPEN.get(run[k], 0))
                run = "".join(run[k] if k == nuc else _glide_for(run[k])
                              for k in range(len(run)))
            out.append(run); i = j
        else:
            out.append(r[i]); i += 1
    return "".join(out)


IPA_APPROX_COLS = {
    "Hokkien", "Teochew", "Hakka", "Wu", "Gan", "Xiang", "Jin",
    "Eastern Min (Fuzhou)", "Northern Min (Jian'ou)", "Hainanese (Haikou)",
    "Hui (Shexian)", "Middle Chinese (Baxter)", "Old Chinese (Zhengzhang)",
    # IPA-based reconstructions — clean ≈ via ipa_to_english. (The plain
    # "Middle Chinese" column is Baxter ASCII transcription, not IPA, so it is
    # deliberately excluded — running the IPA map on it leaks garbage.)
    "Tang", "Proto-Min",
}


# A labialized CODA consonant (syllable-final /Cʷ/) reads more naturally with the
# off-glide BEFORE the stop — "ghawk", not "ghakw" (a layman can't voice a "w"
# after a final "k"). Reorder /Cʷ/ → /ʷC/ only when the ʷ is syllable-final: at
# end of string, before whitespace, or before a tone marker/digit. ONSET /kʷa/
# (ʷ before a vowel) is left untouched so it still reads "kwah".
_CODA_LABIAL = re.compile(r"([kɡgptbdŋmnʔ])ʷ(?=$|\s|[˥˦˧˨˩⁰¹²³⁴⁵⁶⁷⁸⁹0-9])")


def ipa_to_english(reading: str) -> str:
    r = unicodedata.normalize("NFD", (reading or "").replace("[ML]", "").strip())
    # drop affricate tie bars so t͡s / t͡ɕ / ʈ͡ʂ match the ts / tɕ / ʈʂ keys
    r = r.replace("͡", "").replace("͜", "").replace("͠", "")
    # any non-syllabic vowel (V + U+032F) is a glide → j / w / ɥ (not just i/y/u)
    r = _NONSYL.sub(lambda m: _glide_for(m.group(1)), r)
    # drop the remaining combining marks (tone accents, length, syllabicity…),
    # keeping only the nasal tilde (mapped to ⁿ below). A tone accent sitting on
    # the nucleus would otherwise break a diphthong (ɑ̀u → "ah"+"oo" = "ahoo");
    # removing it keeps the vowel run contiguous so it stays one syllable.
    r = "".join(c for c in r if c == "̃" or not unicodedata.combining(c))
    # collapse each vowel run to one nucleus + glides → one English syllable
    r = _fold_vowel_runs(r)
    # syllable-final /Cʷ/ → /ʷC/ so the off-glide reads before the coda stop
    r = _CODA_LABIAL.sub(lambda m: "ʷ" + m.group(1), r)
    out, i, L = [], 0, len(r)
    while i < L:
        if r[i] == " ":
            out.append(" "); i += 1; continue
        for k in _IPA_KEYS:
            if r.startswith(k, i):
                out.append(_IPA_ENG[k]); i += len(k); break
        else:
            # keep only ASCII letters; drop CJK annotations (白/文/去聲…), digits,
            # combining marks, and any IPA symbol not in the map — never leak raw.
            if r[i].isascii() and r[i].isalpha():
                out.append(r[i])
            i += 1
    return "".join(out).strip()


def ipa_approx_html(val: str) -> str:
    return approx_html("__ipa__", val)


# --- romanisation (POJ / Peng'im / BUC / PFS / Wugniu / Changsha / …) → rough
# English sounds-like. The live Wiktionary readings are romanisations, not IPA,
# so the IPA map above does not apply. This is a deliberately rough, scheme-
# agnostic respelling — enough to give an English reader a "sounds-like", and
# generated per reading so the ≈ stays 1:1 with what's displayed.
_ROM_ENG = {
    # aspirated / digraph initials shared across the southern romanisations
    "chh": "ch", "tsh": "ts", "kh": "k", "ph": "p", "th": "t",
    "ch": "ch", "ts": "ts", "ng": "ng", "gn": "ny", "ny": "ny", "nn": "n",
    # vowel clusters / glides
    "oa": "wah", "oe": "er", "eo": "er", "eu": "ew", "au": "ow", "ao": "ow",
    "ai": "igh", "ei": "ay", "ou": "oh", "iu": "yoo", "ui": "wee",
    "ia": "yah", "ie": "yeh", "io": "yoh", "ua": "wah", "uo": "waw", "ue": "weh",
    "aa": "ah", "oo": "oo", "ee": "ee",
    # single letters (c/q/x/z follow the Peng'im / Changsha / Taiyuan values)
    "c": "ts", "q": "ch", "x": "sh", "z": "ds", "j": "j", "v": "v",
    "a": "ah", "e": "eh", "i": "ee", "o": "oh", "u": "oo", "y": "ew",
    "b": "b", "d": "d", "f": "f", "g": "g", "h": "h", "k": "k", "l": "l",
    "m": "m", "n": "n", "p": "p", "r": "r", "s": "s", "t": "t", "w": "w",
    "ⁿ": "n", "ŋ": "ng", "ʔ": "", "'": "",
}
_ROM_KEYS = sorted(_ROM_ENG, key=len, reverse=True)

# Wugniu (Wu) is identified by a LEADING tone digit and clashes with the
# scheme-agnostic defaults on a few letters: final ``-q`` is the entering-tone
# glottal stop (silent here, NOT Peng'im /tsʰ/ → "ch"); ``y-`` is the glide /j/
# (NOT Taiyuan /y/ → "ew"); ``gh-`` is voiced /ɦ/. These take priority over
# ``_ROM_ENG`` only when a Wugniu leading tone was found.
_WUGNIU_ENG = {"gh": "h", "q": "", "y": "y"}
_WUGNIU_KEYS = sorted(_WUGNIU_ENG, key=len, reverse=True)
_SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}

# --- tone DIACRITIC → traditional tone number, per romanisation scheme. The
# southern schemes (POJ/PFS/BUC) write tone as an accent over the vowel rather
# than a digit, so the ``≈`` approximation lost it. These tables (verified
# against the Wikipedia POJ / Pha̍k-fa-sṳ / Foochow-Romanized tone charts) let
# us recover the number. The SAME accent means different tones in different
# schemes (e.g. macron U+0304 = POJ 7 but BUC 2), so the column's scheme must be
# passed in. Combining-mark codepoints: U+0300 grave, U+0301 acute, U+0302
# circumflex, U+0304 macron, U+0306 breve, U+030A ring, U+030D vertical line.
_TONE_DIACRITIC = {
    "poj": {"́": "2", "̀": "3", "̂": "5", "̄": "7",
            "̍": "8"},                       # Hokkien Pe̍h-ōe-jī
    "pfs": {"̂": "1", "̀": "2", "́": "3", "̊": "5",
            "̍": "7"},                       # Hakka Pha̍k-fa-sṳ (Sixian)
    "buc": {"̆": "1", "̄": "2", "́": "3", "̀": "5",
            "̂": "6"},                       # Eastern Min Bàng-uâ-cê
}
# checked-tone (入聲) stop finals per scheme — these split the accents that mark
# two tones at once: POJ/PFS unmarked = level (1/4) vs checked (4/6); BUC breve
# = 上平 1 vs 下入 7 and acute = 上去 3 vs 上入 4, told apart by a stop final.
_CHECKED_FINALS = {"poj": ("p", "t", "k", "h"), "pfs": ("p", "t", "k"),
                   "buc": ("k", "h")}

# dialect column → its romanisation scheme. The scheme tells the ≈ approximation
# (a) how to read the tone (accent / trailing digit / leading Wugniu digit) and
# (b) which class→contour table to use.
ROM_SCHEME = {
    "Hokkien": "poj", "Hakka": "pfs", "Eastern Min (Fuzhou)": "buc",
    "Teochew": "teochew", "Wu": "wugniu", "Gan": "gan",
    "Xiang": "xiang", "Jin": "jin",
}

# --- traditional tone CLASS (1–8 by 陰/陽 × 平/上/去/入) → citation Chao pitch
# CONTOUR, per topolect. The romanisations write only the class (a digit or an
# accent), which under one green ≈ sat next to the IPA rows' real Chao contours
# (Shexian ³⁵, Haikou ²¹³) — and a lone class digit misreads as a flat tone. So
# the ≈ shows the *pitch melody* instead. Values are the standard citation
# (in-isolation) tones for the reference lect each romanisation encodes; they
# vary by speaker/source and are sandhi-stripped (see tone_number_guide.md).
# Checked (入聲) tones are genuinely short, so a single digit there is correct.
_TONE_CONTOUR = {
    # Hokkien POJ — Amoy/Taiwanese (Taipei) reference
    "poj":     {"1": "55", "2": "51", "3": "21", "4": "32",
                "5": "24", "7": "33", "8": "44"},
    # Hakka Pha̍k-fa-sṳ — Sixian (Taiwan)
    "pfs":     {"1": "24", "2": "11", "3": "31", "4": "55",
                "5": "33", "6": "2", "7": "5"},
    # Eastern Min Bàng-uâ-cê — Fuzhou
    "buc":     {"1": "55", "2": "33", "3": "213", "4": "24",
                "5": "53", "6": "242", "7": "5"},
    # Teochew Peng'im — Chaozhou
    "teochew": {"1": "33", "2": "52", "3": "213", "4": "2",
                "5": "55", "6": "35", "7": "11", "8": "4"},
    # Wu Wugniu — Shanghai (陰上/陰去 merge → 34; 陽平/陽上/陽去 merge → 23)
    "wugniu":  {"1": "53", "2": "34", "3": "34", "4": "5",
                "5": "23", "6": "23", "7": "23", "8": "12"},
    # Cantonese Jyutping — Guangzhou/Hong Kong citation values. Checked (入聲)
    # syllables reuse digits 1/3/6, whose level contours are already correct.
    "jyutping": {"1": "55", "2": "35", "3": "33",
                 "4": "21", "5": "13", "6": "22"},
    # Hainanese — Haikou, MCPDict category digits (odd=陰, even=陽; no 4 — the
    # 陽上 class merged). 9 is MCPDict's 長入 (long entering). Values follow
    # 梁猷剛《海口方言詞典》/ Wikipedia "Haikou dialect".
    "haikou":  {"1": "24", "2": "21", "3": "213", "5": "35",
                "6": "33", "7": "5", "8": "3", "9": "55"},
    # Gan — Nanchang
    "gan":     {"1": "42", "2": "24", "3": "213", "5": "45",
                "6": "21", "7": "5", "8": "21"},
    # Xiang — Changsha (New Xiang)
    "xiang":   {"1": "33", "2": "13", "3": "41", "4": "55",
                "5": "21", "6": "24"},
    # Jin — Taiyuan
    "jin":     {"1": "11", "2": "53", "3": "45", "4": "2", "5": "54"},
}


# =====================================================================
# Unified tone display: Chao tone letters (˥˦˧˨˩)
# =====================================================================
# Every displayed tone that denotes a PITCH CONTOUR is rendered as Chao tone
# letters — a vertical reference staff with the pitch trace attached (˧˥ =
# starts mid, rises high) — instead of digits. Three digit shapes occur in the
# data and each is handled differently:
#   * superscript / ASCII digit runs of 1–5 in IPA readings (kaikki ⁵⁵, Hakka
#     "(陰平44)") — already Chao NUMERALS → transliterate digit-for-digit;
#   * tone-CLASS digits in romanisations (Jyutping tin1, Peng'im tiang1,
#     MCPDict Haikou hi1, Wugniu 8laq) — a category, not a pitch → map class →
#     citation contour via _TONE_CONTOUR, then render as Chao letters;
#   * tone-CATEGORY superscripts with *no* defined pitch (Proto-Min *tʰin¹ =
#     8-way Min category, Baxter MC tʰen¹ = 平上去入) — must NOT be converted
#     (¹ would misread as low pitch) → exempt columns, left as-is.
_CHAO_LETTER = {"1": "˩", "2": "˨", "3": "˧", "4": "˦", "5": "˥"}
_SUP_TO_ASCII = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SUP_RUN_RE = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
# a digit run attached to the end of a letter (syllable), not a bare number
_TONE_DIGIT_RUN_RE = re.compile(r"(?<=[^\W\d_])[0-9]+")
_CHAO_RUN_RE = re.compile(r"[˥˦˧˨˩]+")

# In SIL fonts (Charis SIL / Gentium Plus) consecutive tone letters LIGATE into
# a single staff glyph — one vertical line with the contour drawn onto it, so
# ˧˥ really is a slanted rise from mid-staff. Elsewhere they degrade gracefully
# to adjacent bars. app.py @imports these webfonts.
CHAO_FONT_STACK = "'Charis SIL','Gentium Plus','Doulos SIL',sans-serif"

# wide-CSV columns whose readings carry a tone-CLASS digit (not a contour)
TONE_CLASS_SCHEME = {
    "Cantonese": "jyutping", "Teochew": "teochew",
    "Hainanese (Haikou)": "haikou", "dial:Min-Haikou": "haikou",
}
# columns whose digits are tone CATEGORIES, not pitch — never convert.
# (dial:Hui-Tunxi: MCPDict 屯溪 has no verified 調值 table, so its readings
# keep the honest class digit; converting 1→˩ would assert a false pitch.)
CHAO_EXEMPT_COLS = {"Proto-Min", "Middle Chinese (Baxter)", "Middle Chinese",
                    "Old Chinese", "Old Chinese (Zhengzhang)", "Tang",
                    "dial:Hui-Tunxi"}

# IPA-only markers — tone letters, modifier letters, combining diacritics and
# IPA-exclusive symbols. Distinguishes a true IPA reading (tʰĩ˥) from a plain
# romanisation (Teochew "tiang1"), gating the ASCII-digit→Chao conversion.
IPA_MARK_RE = re.compile(
    r"[˥˦˧˨˩ʰʷʲˡⁿ̯̃̃ʔɛɔəŋɲɕʑʐʂɻɤɯøœɐɑɒʊɪæɓɗʦȵɸβθːˀ]")


def has_ipa(val: str) -> bool:
    return bool(IPA_MARK_RE.search(val or ""))


def contour_to_chao(digits: str) -> str:
    """``"213"`` → ``"˨˩˧"`` if every digit is a pitch level 1–5, else ``""``
    (a 0/6–9 digit means it was a tone class, not a contour — don't convert)."""
    if digits and all(d in _CHAO_LETTER for d in digits):
        return "".join(_CHAO_LETTER[d] for d in digits)
    return ""


def tones_to_chao(val: str, column: str | None = None) -> str:
    """Unified tone display for one cell/reading: pitch-contour digits become
    Chao tone letters. ``column`` picks the tone-class scheme (Jyutping /
    Peng'im / Haikou) and guards the category-superscript columns (Proto-Min,
    Baxter MC), whose digits are classes, not pitches, and stay untouched."""
    if not val or column in CHAO_EXEMPT_COLS:
        return val or ""
    s = _SUP_RUN_RE.sub(
        lambda m: contour_to_chao(m.group(0).translate(_SUP_TO_ASCII)) or m.group(0),
        val)
    scheme = TONE_CLASS_SCHEME.get(column or "")
    if scheme:
        table = _TONE_CONTOUR.get(scheme, {})
        s = _TONE_DIGIT_RUN_RE.sub(
            lambda m: contour_to_chao(table.get(m.group(0), "")) or m.group(0), s)
    elif has_ipa(s):
        # inside an IPA reading a trailing digit run IS a Chao-numeral contour
        s = _TONE_DIGIT_RUN_RE.sub(
            lambda m: contour_to_chao(m.group(0)) or m.group(0), s)
    else:
        # plain-ASCII reading: a run of TWO+ digits all 1–5 is still a contour
        # ('pin13' from dial-pron) — tone-class digits are always single, so
        # length ≥2 disambiguates ('tin1' Jyutping / 'hi1' Haikou untouched).
        s = _TONE_DIGIT_RUN_RE.sub(
            lambda m: (contour_to_chao(m.group(0)) or m.group(0))
            if len(m.group(0)) >= 2 else m.group(0), s)
    return s


def wikt_rom_to_chao(rom: str, scheme: str | None) -> str:
    """Live-Wiktionary romanisation with its tone digit(s) shown as Chao
    letters: a trailing class digit (Peng'im / Gan / Xiang / Jin) is replaced
    in place; Wugniu's LEADING digit moves to the end (``8laq`` → ``laq˩˨``).
    Diacritic schemes (POJ/PFS/BUC) carry no digits and pass through."""
    if not rom or not scheme or scheme in _TONE_DIACRITIC:
        return rom or ""
    table = _TONE_CONTOUR.get(scheme, {})

    def one(syl: str) -> str:
        m = re.match(r"^(\d+)(.+)$", syl)
        if m and scheme == "wugniu":
            chao = contour_to_chao(table.get(m.group(1), ""))
            return (m.group(2) + chao) if chao else syl
        m = re.search(r"(\d+)$", syl)
        if m:
            chao = contour_to_chao(table.get(m.group(1), ""))
            if chao:
                return syl[:m.start()] + chao
        return syl

    return re.sub(r"[^\s/,]+", lambda m: one(m.group(0)), rom)


def chao_html(text: str) -> str:
    """HTML-escape ``text`` and wrap each Chao tone-letter run in a span whose
    font ligates the run into a single contour glyph (the slanted-line form)."""
    esc = _html.escape(text or "")
    return _CHAO_RUN_RE.sub(
        lambda m: f'<span style="font-family:{CHAO_FONT_STACK}">{m.group(0)}</span>',
        esc)


# --- tone sandhi (non-final position) — citation class → sandhi contour.
# Min sandhi is pervasive: EVERY non-final syllable changes tone. Hokkien
# follows the famous tone circle (1→7→3→2→1, 5→7, 4↔8; Taipei values);
# Teochew per the Chaozhou table (Wikipedia "Teochew Min"). Values are
# indicative citation figures like _TONE_CONTOUR's.
_SANDHI_CONTOUR = {
    "poj":     {"1": "33", "2": "55", "3": "51", "4": "44",
                "5": "33", "7": "21", "8": "32"},
    "teochew": {"1": "34", "2": "35", "3": "53", "4": "54",
                "5": "23", "6": "21", "7": "23", "8": "32"},
}


def sandhi_hint_html(reading: str, scheme: str | None) -> str:
    """Muted chip showing how the FIRST reading's tone changes when another
    syllable follows (Min tone sandhi). ``""`` when inapplicable."""
    table = _SANDHI_CONTOUR.get(scheme or "")
    if not table:
        return ""
    first = re.split(r"\s*[|/]\s*", (reading or "").strip())[0].strip()
    if not first:
        return ""
    m = re.search(r"(\d+)$", first)
    tone = m.group(1) if m else _diacritic_tone(first, scheme)
    sand, cit = table.get(tone), _TONE_CONTOUR.get(scheme, {}).get(tone)
    if not sand or not cit:
        return ""
    arrow = f"{contour_to_chao(cit)}→{contour_to_chao(sand)}"
    return ("<span style='color:#8a93a5;font-size:.82em' title='Tone sandhi: in "
            "Min, every syllable that is NOT last in its phrase changes tone. "
            f"Citation {cit} is spoken {sand} before another syllable.'>"
            f"sandhi {chao_html(arrow)} non-final</span>")


def _diacritic_tone(syllable: str, scheme: str) -> str:
    """Recover the traditional tone number from a diacritic-marked syllable
    (POJ / PFS / BUC). Returns '' when no tone can be determined."""
    table = _TONE_DIACRITIC.get(scheme)
    if not table:
        return ""
    nfd = unicodedata.normalize("NFD", syllable)
    mark = next((c for c in nfd if c in table), "")
    base = "".join(c for c in nfd if not unicodedata.combining(c)).lower()
    checked = base.endswith(_CHECKED_FINALS.get(scheme, ()))
    if mark:
        t = table[mark]
        if scheme == "buc" and checked:
            t = {"3": "4", "1": "7"}.get(t, t)   # acute→上入, breve→下入
        return t
    # unmarked: only POJ (1/4) and PFS (4/6) leave the level/checked pair blank
    if scheme == "poj":
        return "4" if checked else "1"
    if scheme == "pfs":
        return "6" if checked else "4"
    return ""


# =====================================================================
# Phrase-level tone sandhi (multi-character input)
# =====================================================================
# Min sandhi is positional, not lexical: within a tone group (roughly a
# syntactic phrase) EVERY syllable except the last takes its sandhi tone and
# only the group-final syllable keeps citation. So given per-character
# citation readings, the surface tones of a phrase are deterministic once the
# group boundaries are known. We split groups at non-Hanzi input characters
# (punctuation / spaces), i.e. the user marks boundaries by typing them; an
# unpunctuated run is treated as one group. Known unmodelled cases: neutral
# tone (輕聲 — pronoun objects, the 仔 suffix, verbal complements), where the
# PRECEDING syllable keeps citation, and Teochew double sandhi.

# Hokkien local readings are IPA whose tone is already a Chao contour, so the
# citation CLASS is recovered from contour + coda. Inventory verified against
# the whole dataset (2026-07): open ˥=1, ˥˩=2, ˧˩=3, ˨˦=5, ˧(33)/˨(22)=7
# (both sources' 陽去 values); checked syllables (-p/-t/-k/-ʔ) split high=8 /
# low=4. Tone 6 (陽上) merged into 7 in Amoy/Taiwanese, so it never occurs.
_HOKKIEN_OPEN_CONTOUR_CLASS = {
    "˥": "1", "˥˥": "1", "˥˩": "2", "˥˧": "2", "˧˩": "3", "˨˩": "3",
    "˩": "3", "˨˦": "5", "˩˧": "5", "˧˥": "5", "˧": "7", "˧˧": "7",
    "˨": "7", "˨˨": "7",
}

# POJ checked-tone sandhi depends on the coda: -p/-t/-k swap 4↔8 (the values
# already in _SANDHI_CONTOUR), but glottal-final syllables (-h in POJ, -ʔ in
# IPA) lose the stop and join the open circle: 4→2, 8→3 (Taipei values).
_POJ_GLOTTAL_SANDHI = {"4": "51", "8": "21"}


def _hokkien_ipa_class(base: str, contour: str) -> str:
    """Citation tone class of a Hokkien IPA syllable, from its Chao contour
    and coda. '' when the contour is outside the known inventory."""
    if base.rstrip().endswith(("p", "t", "k", "ʔ")):
        return "8" if ("˥" in contour or "˦" in contour) else "4"
    return _HOKKIEN_OPEN_CONTOUR_CLASS.get(contour, "")


def _syllable_tone(tok: str, scheme: str):
    """``(base, tone_class, citation_contour)`` for one reading token, or
    ``None`` when no tone can be recovered. Handles the three token shapes:
    IPA + trailing Chao letters (Hokkien local), trailing class digit
    (Peng'im), and tone-diacritic romanisation (POJ, from live Wiktionary)."""
    s = (tok or "").strip().removesuffix("[ML]").strip()
    if not s:
        return None
    m = _CHAO_RUN_RE.search(s)
    if m and m.end() == len(s):
        base = s[:m.start()]
        cls = _hokkien_ipa_class(base, m.group(0)) if scheme == "poj" else ""
        return (base, cls, m.group(0)) if cls else None
    m = re.search(r"(\d+)$", s)
    if m:
        cit = _TONE_CONTOUR.get(scheme, {}).get(m.group(1), "")
        return (s[:m.start()], m.group(1), contour_to_chao(cit)) if cit else None
    cls = _diacritic_tone(s, scheme)
    if cls:
        cit = _TONE_CONTOUR.get(scheme, {}).get(cls, "")
        if cit:
            return (s, cls, contour_to_chao(cit))
    return None


def _sandhi_contour_of(cls: str, base: str, scheme: str) -> str:
    """Non-final (sandhi) contour for a citation class, coda-sensitive for
    POJ checked tones. '' when the class has no sandhi entry."""
    if scheme == "poj" and cls in _POJ_GLOTTAL_SANDHI and \
            base.rstrip().endswith(("h", "ʔ")):
        return _POJ_GLOTTAL_SANDHI[cls]
    return _SANDHI_CONTOUR.get(scheme, {}).get(cls, "")


def phrase_surface_tones(pairs, scheme: str):
    """Surface (spoken) tones for a phrase: ``[[syllable, …], …]`` — one list
    per tone group, each syllable a dict with ``char``, ``base``, ``surface``
    (Chao letters, '' if unknown), ``citation``, ``final`` and ``changed``.
    ``pairs`` is ``per_char_tokens`` output; groups split at non-Hanzi chars.
    Returns ``[]`` unless some group has ≥2 syllables (no sandhi otherwise)."""
    groups, cur = [], []
    for ch, tok in pairs:
        if not looks_like_hanzi(ch):
            if cur:
                groups.append(cur)
                cur = []
            continue
        cur.append((ch, tok))
    if cur:
        groups.append(cur)
    if not any(len(g) > 1 for g in groups):
        return []
    out = []
    for g in groups:
        syls = []
        for i, (ch, tok) in enumerate(g):
            final = i == len(g) - 1
            info = _syllable_tone(tok, scheme) if tok else None
            if not info:
                syls.append({"char": ch, "base": "", "surface": "",
                             "citation": "", "final": final, "changed": False})
                continue
            base, cls, cit = info
            sand = "" if final else contour_to_chao(
                _sandhi_contour_of(cls, base, scheme))
            surface = sand or cit
            syls.append({"char": ch, "base": base, "surface": surface,
                         "citation": cit, "final": final,
                         "changed": bool(sand) and sand != cit})
        out.append(syls)
    return out


def phrase_sandhi_html(pairs, dialect: str, label: str = "↳ spoken:") -> str:
    """Sub-line for the multi-character view showing how the phrase is
    actually SPOKEN: every non-group-final syllable with its sandhi tone,
    group-final syllables with citation. ``""`` when the dialect has no
    sandhi table or the input has no multi-syllable group."""
    scheme = ROM_SCHEME.get(dialect) or ""
    if scheme not in _SANDHI_CONTOUR:
        return ""
    groups = phrase_surface_tones(pairs, scheme)
    if not groups:
        return ""
    rendered = []
    for g in groups:
        chips = []
        for s in g:
            if not s["surface"]:
                chips.append(f"<span style='color:#4a5160' title='no reading / "
                             f"tone unknown'>{_html.escape(s['char'])}</span>")
            elif s["final"]:
                chips.append(f"<span title='group-final: keeps citation tone'>"
                             f"{chao_html(s['base'] + s['surface'])}</span>")
            else:
                tip = (f"non-final: citation {s['citation']} is spoken "
                       f"{s['surface']}" if s["changed"] else
                       "non-final (sandhi tone equals citation here)")
                col = "#d8b46e" if s["changed"] else "#cfcfcf"
                chips.append(f"<span style='color:{col}' title='{tip}'>"
                             f"{chao_html(s['base'] + s['surface'])}</span>")
        rendered.append(" ".join(chips))
    sep = " <span style='color:#4a5160'>‖</span> "
    return ("<span style='color:#8a93a5;font-size:.82em' title='Min tone "
            "sandhi applied across the phrase: every syllable that is not "
            "last in its tone group takes its sandhi tone; punctuation or "
            "spaces in your input mark group boundaries. Neutral-tone words "
            "(輕聲, e.g. the 仔 suffix, pronoun objects) are not modelled.'>"
            f"&nbsp;&nbsp;{label}</span> <code>" + sep.join(rendered)
            + "</code> <span style='color:#8a93a5;font-size:.82em'>"
            "(sandhi applied; last of each group = citation)</span>")


# --- reading disambiguation via ithuan's tâi-lô ------------------------
# The dataset records several readings per character (literary/colloquial
# variants) and per_char_tokens shows the first, but ithuan's annotator picks
# the reading that fits the phrase (台 in 台灣 is tone 5, not the standalone
# tone 1). Aligning its tâi-lô back onto the input lets the Hokkien row and
# the "↳ spoken:" line use the reading the TTS voice actually speaks.

# One spoken unit of a KIP string, in reading order: a tâi-lô syllable (Latin
# letters + combining tone marks) or a Hanzi ithuan echoed unread (glued to
# its neighbours without a hyphen). ithuan normalises punctuation to ASCII
# and glues it on too, so anything else is simply skipped.
_TAILO_UNIT_RE = re.compile(
    r"[A-Za-zÀ-ɏ̀-ͯ]+|" + _HANZI_RE.pattern)


def _tailo_units(kip: str):
    """``[(unit, tone_class), …]`` per spoken unit of a KIP string; echoed
    Hanzi (and syllables whose tone cannot be read) get class ``''``."""
    out = []
    for m in _TAILO_UNIT_RE.finditer(kip or ""):
        u = m.group(0)
        cls = "" if looks_like_hanzi(u) else _diacritic_tone(u, "poj")
        out.append((u, cls))
    return out


def _tailo_nasal(syl: str) -> bool:
    base = "".join(c for c in unicodedata.normalize("NFD", syl)
                   if not unicodedata.combining(c)).lower()
    return bool(re.search(r"nnh?$", base))


def tailo_matched_tokens(data, dialect, s, alt, kip):
    """``per_char_tokens`` with ithuan's tâi-lô as referee: among a character's
    alternate readings, prefer one whose citation tone class (and then
    nasality) matches the tâi-lô syllable spoken at that position. Alignment
    is positional — one tâi-lô unit per Hanzi char — and the plain
    first-reading pairs are returned whenever it fails."""
    pairs = per_char_tokens(data, dialect, s, alt)
    if ROM_SCHEME.get(dialect) != "poj":
        return pairs
    hanzi_pos = [i for i, (ch, _) in enumerate(pairs) if looks_like_hanzi(ch)]
    units = _tailo_units(kip)
    if not units or len(units) != len(hanzi_pos):
        return pairs
    if not (alt and len(alt) == len(s)):
        alt = None
    out = list(pairs)
    for (syl, kcls), i in zip(units, hanzi_pos):
        if not kcls:
            continue
        ch = s[i]
        opts = split_opts(data.get(ch, {}).get(dialect, ""))
        if not opts and alt and alt[i] != ch:
            opts = split_opts(data.get(alt[i], {}).get(dialect, ""))
        if len(opts) < 2:
            continue
        knasal = _tailo_nasal(syl)
        best = None
        for tok in opts:
            info = _syllable_tone(tok, "poj")
            if not info or info[1] != kcls:
                continue
            if best is None:
                best = tok
            if ("̃" in unicodedata.normalize("NFD", tok)) == knasal:
                best = tok
                break
        if best:
            out[i] = (ch, best)
    return out


# --- Mandarin → colloquial Taiwanese translation (Lohankha) -------------
# The sentences fed to this app are written with Mandarin vocabulary; Min
# speakers do not SAY 今天/很 but 今仔日/真, so a faithful "spoken" line
# needs real 華→台 translation first, not just character readings.
# Lohankha (translate.lohankha.tw) offers free syntax-aware MT between
# Mandarin and Taiwanese (hanzi / tâi-lô / POJ). Their server omits its
# TLS intermediates (Let's Encrypt gen-y, whose root is newer than
# certifi), so a CA bundle is built once by walking the certificate's own
# AIA (CA-Issuers) pointers — the same mechanism browsers use. Every
# fetched cert is signature-checked during verification, so trust stays
# anchored at certifi's ISRG Root X1; nothing is blindly trusted.
LOHANKHA_PAGE = "https://translate.lohankha.tw/en/"
LOHANKHA_API = "https://translate.lohankha.tw/api/translate/"
_AIA_URL_RE = re.compile(rb"http://[\x21-\x7e]+?\.i\.lencr\.org/")


def _lohankha_ca(rebuild: bool = False) -> str:
    """Path to a CA bundle (certifi + Lohankha's missing intermediates)."""
    import ssl
    import socket
    import certifi
    import requests
    p = Path(CACHE_DIR) / "lohankha_ca.pem"
    if rebuild or not p.exists():
        host = "translate.lohankha.tw"
        ctx = ssl._create_unverified_context()  # only to READ the AIA chain
        with socket.create_connection((host, 443), 30) as sk:
            with ctx.wrap_socket(sk, server_hostname=host) as tls:
                der = tls.getpeercert(True)
        pems, seen, queue = [], set(), [der]
        while queue and len(seen) < 8:
            d, queue = queue[0], queue[1:]
            for u in set(_AIA_URL_RE.findall(d)) - seen:
                seen.add(u)
                r = requests.get(u.decode("ascii"), timeout=30)
                if r.ok and r.content[:1] == b"\x30":   # a DER certificate
                    pems.append(ssl.DER_cert_to_PEM_cert(r.content))
                    queue.append(r.content)
        p.write_text(Path(certifi.where()).read_text("utf-8")
                     + "\n" + "\n".join(pems), "utf-8")
    return str(p)


def hokkien_colloquial(text: str) -> tuple[str, str]:
    """``(hanzi, tâi-lô)`` — the sentence as actually SAID in Taiwanese
    Hokkien (今天我很開心 → 今仔日我真爽快), via Lohankha's 華→台 machine
    translation. Disk-cached; raises on network/MT failure."""
    import requests
    p = _tts_cache_path(text, "zh2nan", "lohankha").with_suffix(".txt")
    if p.exists():
        han, _, lmj = p.read_text("utf-8").partition("\t")
        return han, lmj
    s = requests.Session()
    for attempt in (0, 1):      # retry once with a rebuilt bundle: the
        try:                    # intermediates rotate every few months
            ca = _lohankha_ca(rebuild=bool(attempt))
            page = s.get(LOHANKHA_PAGE, timeout=30, verify=ca).text
            break
        except requests.exceptions.SSLError:
            if attempt:
                raise
    m = re.search(r"'X-CSRFToken':\s*\"([^\"]+)\"", page)
    if not m:
        raise RuntimeError("Lohankha page had no CSRF token")
    r = s.post(LOHANKHA_API, timeout=90, verify=ca,
               data={"key": text, "input_lang": "zh-tw",
                     "output_format": "tai-han", "lmj": "tailo", "ip": ""},
               headers={"X-CSRFToken": m.group(1), "Referer": LOHANKHA_PAGE})
    r.raise_for_status()
    j = r.json()
    han = ((j.get("result") or {}).get("output") or "").strip()
    lmj = ((j.get("result") or {}).get("lmj") or "").strip()
    if not (j.get("success") and han):
        raise RuntimeError(f"Lohankha: {j.get('error') or 'empty result'}")
    p.write_text(f"{han}\t{lmj}", "utf-8")
    return han, lmj


# --- Teochew colloquial source (via the Hokkien translation) ------------
# No Mandarin→Teochew MT exists, but Teochew and Hokkien are sister
# Southern Min languages sharing most core vocabulary (食/行/厝/伊/毋/
# 歡喜…), so Lohankha's TAIWANESE wording is a far closer source text for
# the Teochew rendition than the Mandarin original. A small table swaps
# the best-attested Taiwan-specific items for their Teochew equivalents;
# the rest is read as-is and labelled "via Hokkien" in the UI.
_TW_TO_TEOCHEW = {
    "今仔日": "今日", "明仔載": "明日", "昨昏": "昨日",
    "佗位": "底塊", "啥物": "乜個", "佇": "在", "矣": "了",
}
_TW_TO_TEOCHEW_RE = re.compile(
    "|".join(sorted(_TW_TO_TEOCHEW, key=len, reverse=True)))


def teochew_colloquial_source(tw_han: str) -> str:
    """Teochew-friendly hanzi derived from a TAIWANESE sentence: shared
    Southern Min vocabulary is kept, listed Taiwan-specific words swapped."""
    return _TW_TO_TEOCHEW_RE.sub(
        lambda m: _TW_TO_TEOCHEW[m.group(0)], tw_han or "")


# --- Teochew reading disambiguation via the Hokkien cognate -------------
# Teochew has no annotation service to referee its literary/colloquial
# doublets, but both sister languages' doublets descend from the same
# Middle Chinese categories, so ithuan's tâi-lô for the SAME hanzi is a
# usable referee here too: the cognate normally shares the traditional
# tone class (陽上 6 merged into Taiwanese 7, so 7 matches either) and a
# predictable initial correspondence (tâi-lô l→Peng'im l/n, k→g, g→gh,
# ts→z, …). 樂 in 快樂 is tâi-lô lo̍k (l-, tone 8) → Peng'im lag8, not
# the ghauh8 doublet. When no stored reading matches, mogher.com's
# character entry supplies the missing doublet.
_PENGIM_INITIALS = ("bh", "gh", "ng", "b", "p", "m", "d", "t", "n", "l",
                    "g", "k", "h", "z", "c", "s", "r")

_TAILO_TO_PENGIM_INITIAL = (
    ("tsh", ("c",)), ("ts", ("z",)), ("ph", ("p",)), ("th", ("t",)),
    ("kh", ("k",)), ("ng", ("ng",)), ("p", ("b",)), ("t", ("d",)),
    ("k", ("g",)), ("b", ("bh",)), ("g", ("gh",)), ("j", ("r", "z")),
    ("m", ("m",)), ("n", ("n", "l")), ("l", ("l", "n")), ("s", ("s",)),
    ("h", ("h",)),
)


def _pengim_initial(base: str) -> str:
    for i in _PENGIM_INITIALS:
        if base.startswith(i):
            return i
    return ""


def _pengim_initials_for_tailo(syl: str):
    base = "".join(c for c in unicodedata.normalize("NFD", (syl or "").lower())
                   if not unicodedata.combining(c))
    for pre, outs in _TAILO_TO_PENGIM_INITIAL:
        if base.startswith(pre):
            return outs
    return ("",)


def _teochew_cognate_score(tok: str, kcls: str, initials) -> int:
    """0–3: how well one Peng'im reading matches the tâi-lô cognate —
    initial correspondence is worth 2 (it separates the doublets), the
    traditional tone class 1. -1 when the token has no readable tone."""
    info = _syllable_tone(tok, "teochew")
    if not info:
        return -1
    base, cls, _ = info
    tone_ok = cls == kcls or (kcls == "7" and cls in ("6", "7"))
    init_ok = _pengim_initial(base) in initials if initials != ("",) \
        else _pengim_initial(base) == ""
    return 2 * init_ok + tone_ok


MOGHER_CHAR_URL = "https://www.mogher.com/{}"
_MOGHER_READING_RE = re.compile(r'href="/dic/czpy/([a-zê]+\d)"')


def mogher_char_readings(ch: str) -> list[str]:
    """Every Peng'im reading mogher's dictionary lists for one character
    (the missing-doublet source for the cognate referee). Disk-cached."""
    import requests
    p = _tts_cache_path(ch, "readings", "mogher").with_suffix(".txt")
    if p.exists():
        t = p.read_text("utf-8").strip()
        return t.split(",") if t else []
    r = requests.get(MOGHER_CHAR_URL.format(ch), timeout=30)
    outs = list(dict.fromkeys(_MOGHER_READING_RE.findall(r.text))) \
        if r.ok else []
    if r.ok:
        p.write_text(",".join(outs), "utf-8")
    return outs


def teochew_tailo_matched_tokens(data, dialect, s, alt, kip):
    """``per_char_tokens`` for the Teochew column, refereed by the tâi-lô
    of the same hanzi (see above). A reading is only replaced by a
    strictly better-scoring one, and mogher's extra candidates need at
    least an initial match; first readings are returned untouched
    whenever the alignment fails."""
    pairs = per_char_tokens(data, dialect, s, alt)
    if ROM_SCHEME.get(dialect) != "teochew":
        return pairs
    hanzi_pos = [i for i, (ch, _) in enumerate(pairs) if looks_like_hanzi(ch)]
    units = _tailo_units(kip)
    if not units or len(units) != len(hanzi_pos):
        return pairs
    if not (alt and len(alt) == len(s)):
        alt = None
    out = list(pairs)
    for (syl, kcls), i in zip(units, hanzi_pos):
        if not kcls:
            continue
        ch = s[i]
        opts = split_opts(data.get(ch, {}).get(dialect, ""))
        if not opts and alt and alt[i] != ch:
            opts = split_opts(data.get(alt[i], {}).get(dialect, ""))
        if not opts:
            continue
        initials = _pengim_initials_for_tailo(syl)
        best, best_score = opts[0], _teochew_cognate_score(opts[0], kcls,
                                                           initials)
        for tok in opts[1:]:
            sc = _teochew_cognate_score(tok, kcls, initials)
            if sc > best_score:
                best, best_score = tok, sc
        if best_score < 2:          # nothing matches even the initial —
            try:                    # ask mogher for the missing doublet
                extra = mogher_char_readings(ch)
                if not extra and alt and alt[i] != ch:
                    extra = mogher_char_readings(alt[i])
            except Exception:
                extra = []
            for tok in extra:
                sc = _teochew_cognate_score(tok, kcls, initials)
                if sc >= 2 and sc > best_score:
                    best, best_score = tok, sc
        if best != (out[i][1] or ""):
            out[i] = (ch, best)
    return out


# --- Teochew phrase audio (mogher.com syllable recordings) --------------
# No public Teochew TTS engine exists (checked 2026-07: Teochew-Wild has
# published vocoders + ASR on HuggingFace but no acoustic model yet). The
# next best thing is mogher.com — the 潮州音字典, Chaozhou-city standard —
# which serves one native recording per syllable+tone. Its mp3 file names
# use mogher's own POJ-ish spelling (zu1 → tsu1.mp3, suan2 → sua~2.mp3),
# NOT Peng'im, and guessing collides with other syllables (Peng'im gai7
# would fetch their [g]- initial file), so each syllable's dictionary page
# /dic/czpy/<pengim> is scraped once for the authoritative file name; the
# mp3 is then disk-cached like the other TTS audio.
MOGHER_PAGE_URL = "https://www.mogher.com/dic/czpy/{}"
MOGHER_SOUND_URL = "https://www.mogher.com/sound/syllabes/{}"
_MOGHER_MP3_RE = re.compile(r"sound/syllabes/([^\"'<>]+?\.mp3)")


def _mogher_variants(syl: str):
    """Spellings to try on mogher: as-is, then the Shantou⇄Chaozhou vowel
    alternations (our sources mix both; mogher is Chaozhou-standard), then
    the checked-coda letter swaps — official Peng'im writes -b/-g where
    some of our sources write -p/-k (rik8 vs mogher's rig8)."""
    out = [syl]

    def add(v):
        if v and v not in out:
            out.append(v)

    for a, b in (("io", "ie"), ("ie", "io"), ("uang", "ueng"),
                 ("uag", "ueg"), ("iau", "iou"), ("iou", "iau"),
                 ("au", "ao"), ("ao", "au")):
        add(syl.replace(a, b))
    for a, b in (("k", "g"), ("g", "k"), ("p", "b"), ("b", "p")):
        add(re.sub(rf"{a}(\d)$", rf"{b}\1", syl))
    return out


def teochew_syllable_mp3(syl: str) -> bytes:
    """One mogher.com recording for a Peng'im syllable+tone (``ho2``).
    Raises when mogher lists no recording for it (or any spelling variant) —
    coverage is genuinely partial (e.g. ho2/ho7 recorded but not ho6), so
    that outcome is remembered in a ``.miss`` marker to spare the network."""
    import requests
    p = _tts_cache_path(syl, "nan-teochew", "mogher")
    miss = p.with_suffix(".miss")
    if p.exists():
        return p.read_bytes()
    if miss.exists():
        raise RuntimeError(f"mogher.com has no recording for {syl}")
    why = None
    for v in _mogher_variants(syl):
        r = requests.get(MOGHER_PAGE_URL.format(v), timeout=30)
        m = _MOGHER_MP3_RE.search(r.text) if r.ok else None
        if not m:
            continue
        a = requests.get(MOGHER_SOUND_URL.format(m.group(1)), timeout=30)
        if a.ok and len(a.content) > 512 and (
                a.content.startswith(b"ID3") or a.content[:1] == b"\xff"):
            p.write_bytes(a.content)
            return a.content
        why = f"mogher.com: audio fetch failed for {m.group(1)!r} ({syl})"
    if why is None:                      # pages answered, just no recording
        miss.touch()
        why = f"mogher.com has no recording for {syl}"
    raise RuntimeError(why)


def _mp3_frames(mp3: bytes) -> bytes:
    """Strip the ID3v2 header / ID3v1 trailer so several files can be
    byte-concatenated into one playable stream."""
    if mp3[:3] == b"ID3" and len(mp3) > 10:
        size = 0
        for byte in mp3[6:10]:
            size = (size << 7) | (byte & 0x7F)
        mp3 = mp3[10 + size:]
    if len(mp3) > 128 and mp3[-128:-125] == b"TAG":
        mp3 = mp3[:-128]
    return mp3


# Non-final syllables are played with the citation recording that best
# approximates their SANDHI contour — mogher has only the 8 citation tones
# (33, 52, 213, 2, 55, 35, 11, 4), so this is an admitted approximation:
#   1: 33→34  near-unchanged, keep its own recording
#   2: 52→35  exactly citation tone 6
#   3: 213→53 ≈ the 52 of tone 2
#   4: 2→54   checked high = tone 8 (the classic 4↔8 swap)
#   5: 55→23  rising ≈ the 35 of tone 6
#   6: 35→21  low ≈ the 11 of tone 7
#   7: 11→23  rising ≈ the 35 of tone 6
#   8: 4→32   checked low = tone 4
_TEOCHEW_SANDHI_AUDIO = {"1": "1", "2": "6", "3": "2", "4": "8",
                         "5": "6", "6": "7", "7": "6", "8": "4"}


def teochew_audio_plan(pairs, spoken: bool):
    """``[pengim, …]`` — one syllable+tone per Hanzi char, ready for
    ``teochew_syllable_mp3``. ``spoken=True`` replaces each non-group-final
    syllable's tone with the citation tone nearest its sandhi contour
    (groups split at non-Hanzi chars, as in phrase_surface_tones).
    ``None`` when any character lacks a plain Peng'im reading."""
    groups, cur = [], []
    for ch, tok in pairs:
        if not looks_like_hanzi(ch):
            if cur:
                groups.append(cur)
                cur = []
            continue
        cur.append(tok)
    if cur:
        groups.append(cur)
    plan = []
    for g in groups:
        for i, tok in enumerate(g):
            info = _syllable_tone(tok, "teochew") if tok else None
            if not info or not re.fullmatch(r"[a-zê]+", info[0]):
                return None
            base, cls, _ = info
            if spoken and i < len(g) - 1:
                cls = _TEOCHEW_SANDHI_AUDIO.get(cls, cls)
            plan.append(base + cls)
    return plan or None


def teochew_phrase_mp3(pairs, spoken: bool) -> bytes | None:
    """Stitched mogher recordings for a phrase — citation tones, or the
    sandhi-approximated "spoken" variant. ``None`` when a reading is
    missing; raises when mogher lacks a recording."""
    plan = teochew_audio_plan(pairs, spoken)
    if not plan:
        return None
    return b"".join(_mp3_frames(teochew_syllable_mp3(s)) for s in plan)


def romanization_to_english(reading: str, scheme: str | None = None) -> str:
    """Rough English sounds-like for ONE romanised syllable. The tone is shown
    as a superscript **Chao pitch contour** (e.g. ``sì`` → ``see²¹``): the tone
    *class* is read from a leading digit (Wugniu), a trailing digit (Peng'im /
    Gan / Xiang / Jin) or — for the diacritic systems ``poj``/``pfs``/``buc`` —
    the accent over the vowel, then mapped to its citation contour via
    ``_TONE_CONTOUR[scheme]``. Without a known ``scheme`` the raw class digit is
    kept. A leading tone marks Wugniu, whose ``-q``/``y-``/``gh-`` get Wu
    values."""
    s = (reading or "").strip()
    if not s:
        return ""
    tone = ""
    mlead = re.match(r"^(\d+)(.+)$", s)
    mtail = re.search(r"(\d+)$", s)
    wugniu = False
    if mlead:
        tone, s = mlead.group(1), mlead.group(2)
        wugniu = True
    elif mtail:
        tone, s = mtail.group(1), s[:mtail.start()]
    elif scheme in _TONE_DIACRITIC:
        tone = _diacritic_tone(s, scheme)
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if not unicodedata.combining(c)).lower()
    out, i, L = [], 0, len(s)
    while i < L:
        if wugniu and (k := next((w for w in _WUGNIU_KEYS if s.startswith(w, i)), "")):
            out.append(_WUGNIU_ENG[k]); i += len(k); continue
        for k in _ROM_KEYS:
            if s.startswith(k, i):
                out.append(_ROM_ENG[k]); i += len(k); break
        else:
            if s[i].isascii() and s[i].isalpha():
                out.append(s[i])
            i += 1
    # tone class → citation Chao contour, rendered as Chao tone LETTERS (the
    # unified tone display); an unknown scheme keeps the raw class digit as a
    # superscript — a class number must never masquerade as a pitch trace.
    mapped = _TONE_CONTOUR.get(scheme, {}).get(tone)
    if mapped is not None:
        tail = contour_to_chao(mapped) or "".join(_SUP.get(d, "") for d in mapped)
    else:
        tail = "".join(_SUP.get(d, "") for d in tone)
    return "".join(out) + tail


def rom_approx_html(rom: str, scheme: str | None = None) -> str:
    """Green ``≈`` span for a romanised wiki reading — one rough English
    sounds-like per ``/``-separated reading, kept 1:1 with the display.
    ``scheme`` (``poj``/``pfs``/``buc``) lets diacritic tones become numbers."""
    aps = [romanization_to_english(r, scheme)
           for r in re.split(r"\s*/\s*", (rom or "").strip()) if r]
    aps = [a for a in aps if a]
    if not aps:
        return ""
    return ("<span style='color:#3a8f3a;font-size:90%' "
            "title='Rough English approximation - not exact'>"
            "≈ " + chao_html(" / ".join(aps)) + "</span>")


# --- Baxter–Sagart Old Chinese reconstruction → rough readable gloss ---
# The reconstruction is *not* IPA: it uses cover symbols (* reconstructed,
# [k] uncertain consonant, ( ) optional, < > infix, . loose preinitial,
# ˤ pharyngealisation / type-A, -s/-ʔ suffixes). We strip that markup to a
# readable gloss — e.g. ``*[k]ʷʰˤret-s`` → ``khwret-s`` — not a precise sound.
_BS_NOTE = re.compile(r"\([^)]*[ >㐀-鿿][^)]*\)")   # parenthetical prose notes
_BS_STRIP = str.maketrans("", "", "*[]<>.()")
_BS_CLUSTERS = [
    ("kʷʰ", "khw"), ("kʰʷ", "khw"), ("gʷʰ", "ghw"), ("qʷʰ", "khw"), ("ɢʷʰ", "ghw"),
    ("kʰ", "kh"), ("pʰ", "ph"), ("tʰ", "th"), ("tsʰ", "tsh"), ("qʰ", "kh"), ("cʰ", "ch"),
    ("kʷ", "kw"), ("gʷ", "gw"), ("qʷ", "kw"), ("ɢʷ", "gw"), ("ŋʷ", "ngw"), ("hʷ", "hw"),
    ("ʔʷ", "'w"),
]
_BS_MAP = {"ˤ": "", "ʷ": "w", "ʰ": "h", "ʔ": "'", "ɢ": "g", "q": "k", "ŋ": "ng",
           "ɲ": "ny", "ɦ": "h", "χ": "kh", "A": "a", "E": "e", "O": "o"}
_BS_JUNK = set(",:?~!;+&>‘’")


def baxter_sagart_approx(form: str) -> str:
    """One Baxter–Sagart form → rough readable gloss (markup stripped)."""
    s = _BS_NOTE.sub("", (form or "").strip()).lstrip("*").strip()
    if not s:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    s = s.translate(_BS_STRIP)
    for a, b in _BS_CLUSTERS:
        s = s.replace(a, b)
    s = "".join(_BS_MAP.get(c, c) for c in s)
    s = "".join(c for c in s if c not in _BS_JUNK)
    return s.strip().strip("-").strip()


def approx_html(column: str, val: str) -> str:
    """Green ``≈`` approximation span suited to the column: a rough reading of
    the Baxter–Sagart reconstruction for ``Old Chinese``, else an English
    sounds-like for IPA columns. ``""`` for non-phonetic columns."""
    # unify contour digits to Chao letters BEFORE glossing (exempt columns —
    # Proto-Min / Baxter MC category superscripts — pass through untouched)
    val = tones_to_chao(val, None if column == "__ipa__" else column)
    variants = [t for t in re.split(r"\s*[|/]\s*", (val or "").strip()) if t]
    if column == "Old Chinese":
        label, fn = "Rough reading of the Baxter–Sagart reconstruction", baxter_sagart_approx
    elif column == "__ipa__" or column in IPA_APPROX_COLS:
        label, fn = "Rough English approximation of the IPA", ipa_to_english
    else:
        return ""
    aps: list[str] = []
    for v in variants:
        a = fn(v)
        if a and a not in aps:
            aps.append(a)
    if not aps:
        return ""
    return (f"<span style='color:#3a8f3a;font-size:90%' title='{label} - not exact'>"
            "≈ " + chao_html(" / ".join(aps)) + "</span>")


def remove_cjk_chars(text: str) -> str:
    return re.sub(r"[㐀-鿿\U00020000-\U0002FFFF]+", "", str(text or ""))


# --------------------------------------------------------------------------
# 反切 (fanqie) breakdown — show HOW the traditional spelling works.
# A fanqie spells a syllable with two characters: the UPPER gives the initial,
# the LOWER gives the final + tone. Both spellers usually have their own
# Baxter Middle Chinese transcription in the dataset, so we can decompose them
# and recompose the target: 他前 → th(a) + (dz)en → "then".
# --------------------------------------------------------------------------
# Baxter MC initials, longest-first ('y' can BE the initial 以, but after a
# sibilant it is part of the palatal digraph: syo = ɕ + o, not s + yo).
_BAXTER_INITIALS = sorted(
    ["tsyh", "tsrh", "tsh", "trh", "dzr", "tsy", "dzy", "tsr", "ny", "sy",
     "zy", "tr", "dr", "nr", "sr", "zr", "ts", "dz", "ph", "th", "kh", "ng",
     "hj", "p", "b", "m", "t", "d", "n", "k", "g", "x", "h", "z", "s", "l",
     "y", "w", "j", "'"],
    key=len, reverse=True)
_BAXTER_TONE = {"X": "上 rising", "H": "去 departing"}


def baxter_parts(mc: str) -> tuple[str, str, str] | None:
    """Split one Baxter MC transcription into ``(initial, final, tone-label)``.
    ``dzyangX`` → ``("dzy", "ang", "上 rising")``; ``nyip`` → ``("ny", "ip",
    "入 entering")``; ``then`` → ``("th", "en", "平 level")``."""
    s = (mc or "").strip()
    if not s:
        return None
    tone = "平 level"
    if s[-1] in _BAXTER_TONE:
        tone, s = _BAXTER_TONE[s[-1]], s[:-1]
    elif s[-1] in "ptk":
        tone = "入 entering"
    onset = next((i for i in _BAXTER_INITIALS if s.startswith(i)), "")
    return onset, s[len(onset):], tone


def parse_fanqie_pairs(val: str) -> list[str]:
    """Distinct two-character fanqie spellings from a cell. Handles ``|`` and
    space separators and the ``X〈Y〉`` editorial correction (→ Y)."""
    pairs: list[str] = []
    for tok in re.split(r"[|\s]+", (val or "").strip()):
        tok = re.sub(r".〈(.)〉", r"\1", tok.strip())
        if len(tok) == 2 and _HANZI_RE.search(tok) and tok not in pairs:
            pairs.append(tok)
    return pairs


def fanqie_explain(pair: str, upper_mc: str, lower_mc: str,
                   target_mc: str = "") -> dict | None:
    """Decompose one fanqie spelling using the spellers' own MC readings.

    Returns ``{upper, lower, initial, final, tone, composed, matches}`` where
    ``composed`` is initial+final(+tone mark) in Baxter letters and ``matches``
    says whether it equals one of the target's own MC readings (``None`` when
    the target MC is unknown). Any missing speller reading → ``None``."""
    up = baxter_parts((upper_mc or "").split("|")[0])
    lo = baxter_parts((lower_mc or "").split("|")[0])
    if not up or not lo or len(pair) != 2:
        return None
    initial, (_, final, tone) = up[0], lo
    mark = {"上 rising": "X", "去 departing": "H"}.get(tone, "")
    composed = initial + final + mark
    targets = [t.strip() for t in (target_mc or "").split("|") if t.strip()]
    return {
        "upper": pair[0], "lower": pair[1],
        "initial": initial or "∅", "final": final, "tone": tone,
        "composed": composed,
        "matches": (composed in targets) if targets else None,
    }


# --------------------------------------------------------------------------
# Middle Chinese 音韻地位 (Qieyun position) — decode the compact codes
# A code is: 母(initial) + 呼(開/合, opt) + 等(一二三四, opt) + 重紐(A/B, opt)
#            + 韻(rime) + 聲(平上去入 tone). e.g. 心合一寒平.
# --------------------------------------------------------------------------
MC_INITIALS = {
    "幫": ("p", "p (unaspirated)"), "滂": ("pʰ", "p (aspirated)"), "並": ("b", "b (voiced)"), "明": ("m", "m"),
    "端": ("t", "t (unaspirated)"), "透": ("tʰ", "t (aspirated)"), "定": ("d", "d (voiced)"), "泥": ("n", "n"), "來": ("l", "l"),
    "知": ("ʈ", "retroflex t"), "徹": ("ʈʰ", "retroflex t (asp.)"), "澄": ("ɖ", "retroflex d"), "娘": ("ɳ", "retroflex n"), "孃": ("ɳ", "retroflex n"),
    "精": ("ts", "ts"), "清": ("tsʰ", "ts (aspirated)"), "從": ("dz", "dz (voiced)"), "心": ("s", "s"), "邪": ("z", "z (voiced)"),
    "莊": ("tʂ", "retroflex ts"), "初": ("tʂʰ", "retroflex ts (asp.)"), "崇": ("dʐ", "retroflex dz"), "生": ("ʂ", "retroflex s"), "俟": ("ʐ", "retroflex z"),
    "章": ("tɕ", "palatal ts"), "昌": ("tɕʰ", "palatal ts (asp.)"), "常": ("dʑ", "palatal dz"), "禪": ("dʑ", "palatal dz"), "書": ("ɕ", "palatal s"), "船": ("ʑ", "palatal z"), "日": ("ɲ", "palatal n"),
    "見": ("k", "k"), "溪": ("kʰ", "k (aspirated)"), "羣": ("ɡ", "g (voiced)"), "群": ("ɡ", "g (voiced)"), "疑": ("ŋ", "ng"),
    "影": ("ʔ", "glottal stop"), "曉": ("x", "h"), "匣": ("ɣ", "h (voiced)"), "云": ("ɦ/j", "glide"), "雲": ("ɦ/j", "glide"), "以": ("j", "y-glide"),
}
MC_HU = {"開": "開 open (plain)", "合": "合 rounded (-w-)"}
MC_DIV = {"一": "I", "二": "II", "三": "III", "四": "IV"}
MC_TONE = {"平": "平 level", "上": "上 rising", "去": "去 departing", "入": "入 entering (-p/-t/-k)"}
MC_TONE_PLAIN = {"平": "level (flat)", "上": "rising", "去": "falling (departing)",
                 "入": "short, checked (ends -p/-t/-k)"}

# Rough reconstructed final for each Guangyun rhyme (by its 平-tone name; the 入
# tone swaps the nasal coda for a stop). Inherently-rounded rhymes bake in -w-.
# Approximate (Baxter/Karlgren-ish) — enough to *hear* the syllable, not exact.
MC_RIMES = {
    "東": "uŋ", "冬": "oŋ", "鍾": "ɨoŋ", "江": "ɔŋ",
    "支": "je", "脂": "i", "之": "ɨ", "微": "ɨj",
    "魚": "ɨə", "虞": "u", "模": "o",
    "齊": "ej", "佳": "ɛ", "皆": "ɛj", "灰": "woj", "咍": "ʌj", "泰": "aj",
    "廢": "jɐj", "夬": "waj",
    "眞": "in", "諄": "win", "臻": "in", "文": "un", "欣": "ɨn", "殷": "ɨn",
    "元": "jɐn", "魂": "won", "痕": "ʌn",
    "寒": "an", "桓": "wan", "刪": "an", "山": "ɛn", "先": "en", "仙": "jen",
    "蕭": "ew", "宵": "jew", "肴": "aw", "豪": "ɑw",
    "歌": "a", "戈": "wa", "麻": "a",
    "陽": "jaŋ", "唐": "aŋ",
    "庚": "aŋ", "耕": "ɛŋ", "清": "jeŋ", "青": "eŋ",
    "蒸": "iŋ", "登": "əŋ",
    "尤": "uw", "侯": "ow", "幽": "iw",
    "侵": "im", "覃": "om", "談": "am", "鹽": "jem", "添": "em", "咸": "ɛm",
    "銜": "am", "嚴": "jɐm", "凡": "jɐm",
}


# IPA → readable spelling for the MC reconstruction (no b/d/g remapping — keep
# the actual stops; just spell out symbols a newbie can't read). Longest-match,
# single pass, so a generated letter (e.g. tɕ→"j") is not re-scanned (j→"y").
_MC_READ = {"tɕʰ": "ch", "tʂʰ": "chr", "ʈʰ": "tr", "tɕ": "j", "tʂ": "jr",
            "dʑ": "j", "dʐ": "jr", "ʈ": "tr", "ɖ": "dr", "ɕ": "sh", "ʑ": "zh",
            "ʂ": "sh", "ʐ": "r", "ɣ": "gh", "ɦ": "h", "ŋ": "ng", "ɲ": "ny",
            "ʔ": "'", "ɐ": "a", "ʌ": "u", "ɨ": "i", "ə": "uh", "j": "y"}
_MC_READ_KEYS = sorted(_MC_READ, key=len, reverse=True)


def _mc_readable(syl: str) -> str:
    out, i, L = [], 0, len(syl)
    while i < L:
        for k in _MC_READ_KEYS:
            if syl.startswith(k, i):
                out.append(_MC_READ[k]); i += len(k); break
        else:
            out.append(syl[i]); i += 1
    return "".join(out)


def _mc_syllable_ipa(p: dict) -> str:
    """Rough reconstructed Middle Chinese IPA for a parsed position."""
    fin = MC_RIMES.get(p["rime"])
    if not fin:
        return ""
    ini = MC_INITIALS.get(p["initial"])
    ini_ipa = ini[0].split("/")[0] if ini else ""
    # division-aware medial: 三等 has the -j- glide (弓 = kjuŋ, not kuŋ),
    # 四等 a front on-glide (先 = sien); skip when the rime already encodes it.
    medial = ""
    if p["div"] == "三" and fin[:1] not in ("j", "i"):
        medial = "j"
    elif p["div"] == "四" and fin[:1] == "e":
        medial = "i"
    if p["hu"] == "合" and fin[:1] not in "wuo":
        medial += "w"
    syl = ini_ipa + medial + fin
    if p["tone"] == "入":  # entering tone: nasal coda → matching stop
        for n, s in (("ŋ", "k"), ("n", "t"), ("m", "p")):
            if syl.endswith(n):
                syl = syl[:-1] + s
                break
    return syl


def parse_mc_position(code: str) -> dict | None:
    chars = list((code or "").strip())
    if not chars:
        return None
    tone = chars.pop() if chars and chars[-1] in MC_TONE else ""
    initial = chars.pop(0) if chars else ""
    hu = div = chongniu = ""
    rime = []
    for c in chars:
        if c in MC_HU:
            hu = c
        elif c in MC_DIV:
            div = c
        elif c in "AB":
            chongniu = c
        else:
            rime.append(c)
    return {"initial": initial, "hu": hu, "div": div, "chongniu": chongniu,
            "rime": "".join(rime), "tone": tone}


MC_DIV_HINT = {
    "一": "a plain, back-ish vowel; no -y- glide",
    "二": "a more open vowel (often with retroflex initials)",
    "三": "has a -y-/-i- like medial (palatal)",
    "四": "a front vowel with an -i- like quality",
}


def mc_readable_syllable(code: str) -> str:
    """Rough readable reconstruction of a whole position, e.g. 心合一寒平 → 'swan'."""
    p = parse_mc_position(code)
    if not p:
        return ""
    syl = _mc_syllable_ipa(p)
    return _mc_readable(syl) if syl else ""


def mc_position_breakdown(code: str):
    """Per-character elucidation: list of (glyph, role-explanation) for a code,
    in reading order, so a beginner sees what each character contributes."""
    p = parse_mc_position(code)
    if not p:
        return []
    rows = []
    if p["initial"]:
        ini = MC_INITIALS.get(p["initial"])
        rows.append((p["initial"],
                     f"the initial consonant — {ini[1]}" if ini else "the initial consonant"))
    if p["hu"]:
        rows.append((p["hu"], "rounding — rounded, adds a -w- glide"
                     if p["hu"] == "合" else "rounding — open, no -w-"))
    if p["div"]:
        rows.append((p["div"], f"division (grade) {MC_DIV[p['div']]} — {MC_DIV_HINT.get(p['div'], '')}"))
    if p["chongniu"]:
        rows.append((p["chongniu"], f"chóngniǔ sub-type {p['chongniu']}"))
    if p["rime"]:
        fin = MC_RIMES.get(p["rime"])
        rows.append((p["rime"], f"the rhyme — its vowel + ending, roughly “-{_mc_readable(fin)}”"
                     if fin else "the rhyme — its vowel + ending"))
    if p["tone"]:
        rows.append((p["tone"], f"the tone — {MC_TONE_PLAIN.get(p['tone'], p['tone'])}"))
    return rows


def explain_mc_position(code: str) -> str:
    """Newbie-friendly decode of one 音韻地位 code: lead with a rough reconstructed
    sound + plain-English tone, then a muted structural breakdown. e.g.
    ``心合一寒平`` → ``sounded ~ "swan", level (flat) tone — s‑ · Div. I · 寒 rhyme``."""
    p = parse_mc_position(code)
    if not p:
        return ""
    syl = _mc_syllable_ipa(p)
    tone = MC_TONE_PLAIN.get(p["tone"], p["tone"])

    bits = []
    ini = MC_INITIALS.get(p["initial"])
    bits.append(f"{p['initial']}‑ ({ini[1]})" if ini else f"{p['initial']}‑")
    if p["div"]:
        bits.append(f"Division {MC_DIV[p['div']]}")
    if p["rime"]:
        bits.append(f"{p['rime']} rhyme")
    breakdown = " · ".join(bits)

    if syl:
        return f'sounded roughly like “{_mc_readable(syl)}”, {tone} tone   —   {breakdown}'
    return f"{tone} tone   —   {breakdown}"


@lru_cache(maxsize=1)
def load_phonetic_symbols(csv_path: str = IPA_FILE):
    out = {}
    if not csv_path or not Path(csv_path).exists():
        return out
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192); f.seek(0)
        try:
            delim = csv.Sniffer().sniff(sample).delimiter
        except Exception:
            delim = "\t" if "\t" in sample else ","
        reader = csv.reader(f, delimiter=delim)
        first = next(reader, None)
        if first is None:
            return out
        header = [c.strip().lower() for c in first]
        keys = ("ipa_symbol", "ipa", "symbol", "phonetic", "phoneme")
        if any(any(k in c for k in keys) for c in header):
            sym_idx = next((i for i, c in enumerate(header)
                            if any(k in c for k in keys)), 0)
            desc_idx = next((i for i, c in enumerate(header)
                             if any(k in c for k in ("description", "desc", "meaning", "example"))), None)
            rows_iter = reader
        else:
            sym_idx, desc_idx = 0, (1 if len(first) > 1 else None)
            rows_iter = itertools.chain([first], reader)
        for row in rows_iter:
            if not row or len(row) <= sym_idx:
                continue
            sym = (row[sym_idx] or "").strip()
            if not sym:
                continue
            if desc_idx is not None and len(row) > desc_idx:
                desc = " ".join((row[i] or "").strip() for i in range(desc_idx, len(row)) if (row[i] or "").strip())
            else:
                desc = " ".join((x or "").strip() for x in row[1:] if (x or "").strip()) if len(row) > 1 else ""
            out[unicodedata.normalize("NFC", sym)] = (unicodedata.normalize("NFC", desc), "")
    return out


def ipa_legend_lines(pron_strs, symbols):
    if not symbols:
        return []
    combined = " ".join(remove_cjk_chars(unicodedata.normalize("NFC", s))
                        for s in (pron_strs or []) if s)
    combined = unicodedata.normalize("NFC", combined)
    TIE = "͡"
    for v in {"͡", "‿", "͜", "͝", "˕", "͡"}:
        combined = combined.replace(v, TIE)
    if not combined.strip():
        return []
    keys = sorted([unicodedata.normalize("NFC", k).replace("͡", TIE)
                   for k in symbols if k], key=len, reverse=True)
    if not keys:
        return []
    pattern = "|".join(re.escape(k) for k in keys)
    seen, seen_set = [], set()
    for m in re.finditer(pattern, combined):
        sym = m.group(0)
        if sym not in seen_set and sym in symbols:
            seen.append(sym); seen_set.add(sym)
    return [f"{sym}: {symbols[sym][0]}" for sym in seen]
