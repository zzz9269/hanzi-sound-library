"""漢字音庫 — Hanzi Sound Library (Streamlit front-end).

Run from the repo root:

    streamlit run app.py

Replaces the single-cell 漢字音庫_v9.ipynb UI. All non-UI logic lives in
``hanzihub.appkit`` and ``hanzihub.scrapers``.
"""
from __future__ import annotations

import base64
import html as _html
import re

import streamlit as st
import streamlit.components.v1 as components

from hanzihub import appkit as ak
from hanzihub import scrapers as sc
from hanzihub import soundlaws
from hanzihub import paths

st.set_page_config(page_title="漢字音庫 — Hanzi Sound Library", layout="wide")

# SIL webfonts ligate a run of Chao tone letters into ONE staff glyph — a
# vertical line with the pitch trace drawn onto it (˧˥ = a line rising from
# mid-staff) — which is how the unified tone display is meant to read.
_CHAO_FONT_IMPORT = ("@import url('https://fonts.googleapis.com/css2?"
                     "family=Charis+SIL&family=Gentium+Plus&display=swap');")
st.markdown(f"<style>{_CHAO_FONT_IMPORT}</style>", unsafe_allow_html=True)


# ----------------------------------------------------------------- data ----
@st.cache_resource(show_spinner="Loading dataset…")
def load_all():
    data, cols = ak.load_combined()
    return data, cols, ak.load_provenance(), ak.load_phonetic_symbols()


DATA, DIALECT_COLS, PROV, SYMBOLS = load_all()


@st.cache_resource(show_spinner="Indexing readings…")
def reading_index():
    return ak.build_reading_index(DATA)


# --------------------------------------------------------- cached network ---
@st.cache_data(show_spinner=False)
def c_translate(text, target, source=None):
    # Raises ak.TranslationError on API failure; st.cache_data does not cache
    # exceptions, so a quota reset is picked up on the next run.
    return ak.translate_text(text, target, source)


@st.cache_data(show_spinner=False)
def c_romanize(text, lang):
    return ak.gtrans_romanize(text, lang)


@st.cache_data(show_spinner="Querying Nôm Foundation…")
def c_nom_from_hanzi(ch):
    return sc.fetch_nom_df_from_hanzi(ch)


@st.cache_data(show_spinner="Querying Nôm Foundation…")
def c_nom_from_text(t):
    return sc.fetch_nom_dict_table_from_vi_or_en(t)


@st.cache_data(show_spinner="Querying koreanhanja.app…")
def c_hanja_from_hanzi(t):
    return sc.fetch_hanja_rows_from_hanzi(t)


@st.cache_data(show_spinner="Querying koreanhanja.app…")
def c_hanja_from_english(t):
    return sc.fetch_hanja_rows_from_english(t)


@st.cache_data(show_spinner="Querying JapanDict…")
def c_japandict(t):
    return sc.fetch_japandict_from_english(t)


@st.cache_data(show_spinner="Loading glyph origin…")
def c_glyph_origin(ch):
    return sc.fetch_glyph_origin_html(ch)


@st.cache_data(show_spinner="Loading Wiktionary readings…")
def c_wikt_readings(ch):
    return sc.fetch_wiktionary_readings(ch)


@st.cache_data(show_spinner="Loading Wiktionary entry…")
def c_wikt_entry(ch):
    return sc.fetch_wiktionary_entry(ch)


@st.cache_data(show_spinner="Querying JapanDict…")
def c_ja_kana(t):
    return sc.ja_romaji_and_kana(t, to_shinjitai=ak.to_shinjitai_per_char)


@st.cache_data(show_spinner="Synthesizing Taiwanese Hokkien (ithuan.tw)…")
def c_hokkien_tts(t):
    return ak.hokkien_tts_bytes(t)


@st.cache_data(show_spinner="Annotating tâi-lô (ithuan.tw)…")
def c_hokkien_tailo(t):
    return ak.hokkien_tailo(t)


@st.cache_data(show_spinner="Translating to colloquial Taiwanese (Lohankha)…")
def c_hokkien_colloquial(t):
    return ak.hokkien_colloquial(t)


@st.cache_data(show_spinner="Fetching Chaozhou Teochew syllables (mogher.com)…")
def c_teochew_phrase(toks, spoken):
    return ak.teochew_phrase_mp3(toks, spoken)


def spk_bytes(mp3: bytes, key) -> str:
    """A clickable 🔊 (with a hidden, preloaded <audio>) that plays one mp3 —
    compact replacement for the full-width st.audio bar."""
    b64 = base64.b64encode(mp3).decode("utf-8")
    aid = "a" + str(abs(hash(key)) % 10**9)
    return (f"<audio id='{aid}' preload='none'>"
            f"<source src='data:audio/mp3;base64,{b64}' type='audio/mp3'></audio>"
            f"<a href='#' onclick=\"document.getElementById('{aid}').play();return false;\" "
            f"title='Play' style='font-size:1.15em;text-decoration:none'>🔊</a>")


def spk(text, voice):
    """🔊 for one Google-TTS utterance (see ``spk_bytes``)."""
    try:
        return spk_bytes(ak.tts_bytes(text, *voice), (text, voice))
    except Exception:
        return "<span title='audio unavailable' style='opacity:.35'>🔇</span>"


def play_row(inner_html, height=34):
    """Render one inline reading line (text + 🔊 icons) in a themed iframe."""
    components.html(
        _SCRAPER_CSS + "<div style='display:flex;flex-wrap:wrap;"
        f"align-items:center;gap:4px 10px'>{inner_html}</div>",
        height=height, scrolling=False)


def audio(text, voice, label=""):
    """Compact speaker line (used where a reading isn't rendered inline)."""
    lab = (f"<span style='opacity:.7;font-size:.92em'>{_html.escape(label)}</span> "
           if label else "")
    play_row(lab + spk(text, voice), height=34)


# ----- single-char reading sections (group the long list) -----
_SINITIC = {"Mandarin", "Cantonese", "Hokkien", "Teochew", "Eastern Min (Fuzhou)",
            "Northern Min (Jian'ou)", "Hainanese (Haikou)", "Hakka", "Wu",
            "Hui (Shexian)", "Gan", "Xiang", "Jin"}
_HIST = {"Middle Chinese", "Middle Chinese (Baxter)", "Middle Chinese (position)",
         "Tang", "Fanqie", "fanqie_upper", "fanqie_lower", "Old Chinese",
         "Old Chinese (Zhengzhang)", "Proto-Min"}
_SINO = {"Vietnamese", "Zhuang", "Japanese", "Japanese On", "Japanese Kun",
         "Okinawan", "Korean (Hangul)", "Korean (romanized)", "Korean (Yale)"}

# Historical columns that are collapsed onto a single row: primary → (secondary,
# primary-label, secondary-label). Middle Chinese is ONE reading in two notations
# (Baxter transcription + its wikihan IPA), so no school labels. Old Chinese is
# two RIVAL reconstructions (Baxter–Sagart vs. Zhengzhang), so each is labelled.
_HIST_PAIRS = {
    "Middle Chinese": ("Middle Chinese (Baxter)", None, None),
    "Old Chinese": ("Old Chinese (Zhengzhang)", "Baxter–Sagart", "Zhengzhang"),
}


def _section_of(col):
    if col in _SINITIC:
        return "🗣️ Sinitic topolects"
    if col in _HIST:
        return "📜 Historical layers"
    if col in _SINO:
        return "🌏 Sinosphere"
    return "Other readings"


def _section_header(name):
    md(f"<div style='margin:16px 0 5px;color:#8fb98f;font-size:11px;font-weight:700;"
       "letter-spacing:1px;text-transform:uppercase;border-bottom:1px solid #2c313c;"
       f"padding-bottom:3px'>{name}</div>")


def md(html: str):
    st.markdown(html, unsafe_allow_html=True)


# Scraper tables render in a components.html iframe, which does NOT inherit the
# Streamlit dark theme — without this the text defaults to black-on-dark.
_SCRAPER_CSS = "<style>" + _CHAO_FONT_IMPORT + "</style>" + """
<style>
  html, body { margin:0; background:transparent;
    color:#e8e8e8; font-family:'Segoe UI', system-ui, sans-serif; font-size:14px; }
  table { width:100%; border-collapse:collapse; }
  th, td { padding:5px 10px; border-bottom:1px solid #3a3f4b;
    text-align:left; vertical-align:top; }
  th { color:#ffffff; font-weight:600; border-bottom:1px solid #5a6172; }
  tr:hover td { background:rgba(255,255,255,0.04); }
  a { color:#7db4ff; text-decoration:none; }
  a:hover { text-decoration:underline; }
  i { color:#9aa0a6; }
  b { color:#ffffff; }
  code { background:rgba(120,180,120,0.14); color:#bfe9bf; padding:1px 6px;
    border-radius:5px; font-family:'Consolas','Courier New',monospace; font-size:.95em; }
  audio { height:26px; vertical-align:middle; }
</style>
"""


def scraper_html(inner: str, height: int = 320, extra_css: str = ""):
    css = _SCRAPER_CSS + (f"<style>{extra_css}</style>" if extra_css else "")
    components.html(css + (inner or ""), height=height, scrolling=True)


# Glyph-origin script images are black line-art (invisible on dark) — invert them
# and firm up the historical-forms table borders.
_GLYPH_CSS = (
    "img{filter:invert(0.92) contrast(1.15);}"
    "table,td,th{border:1px solid #555 !important;background:transparent !important;}"
    "th{color:#fff;}"
)

# Full-entry (Wiktionary) panel: headings, definition lists, examples, links.
_ENTRY_CSS = (
    ".wikt-lang{color:#a9c9f0;font-size:1.18em;font-weight:700;margin:.2em 0 .45em;"
    "border-bottom:1px solid #3a3f4b;padding-bottom:.22em;}"
    ".wikt-lang:not(:first-child){margin-top:1.4em;}"
    "h3{color:#e6d6a9;font-size:1.06em;margin:.85em 0 .3em;}"
    "h4{color:#cdb98a;font-size:.97em;margin:.6em 0 .25em;}"
    "ol,ul{margin:.2em 0 .55em 1.25em;padding:0;}"
    "li{margin:.18em 0;}"
    "dl{margin:.1em 0 .35em .8em;color:#b7bcc6;}"
    "dd{margin:.05em 0 .05em 1em;}"
    "ruby rt{color:#9aa7bd;}"
    "b,strong{color:#fff;}"
    # backstop for Wiktionary's light table/box backgrounds (dialectal synonyms,
    # reading tables) — force them transparent with dark borders.
    "table{background:transparent !important;border-collapse:collapse;}"
    "th,td{background:transparent !important;border:1px solid #3a3f4b !important;"
    "padding:3px 8px;}"
    "tr,tbody,thead,.wikitable,.NavFrame,.NavHead,.NavContent,.NavContent>div"
    "{background:transparent !important;border-color:#3a3f4b !important;}"
    ".NavHead{color:#cdd3df !important;font-weight:600;}"
    ".wikt-src{color:#7f8794;font-size:.82em;margin-top:1.4em;"
    "border-top:1px solid #2c303a;padding-top:.5em;}"
)


def _safe_translate(text, target, source=None):
    """c_translate, but surface a quota/credential error inline and return ''."""
    try:
        return c_translate(text, target, source) if ak.gt_ready() else ""
    except ak.TranslationError as e:
        st.error(f"Translation unavailable — {e}")
        return ""


def romanize_native(native: str, lang: str) -> str:
    """Romanise a native word: local pinyin (zh) / Hangul romaniser (ko);
    Google romanisation for Japanese (which it handles well)."""
    if not native:
        return ""
    if lang == "zh":
        return ak.pinyin(native)
    if lang == "ko":
        return ak.rom_ko(native)
    if lang == "ja":
        return c_romanize(native, "ja")
    return ""


# =====================================================================
# Single character
# =====================================================================
# IPA detection (tʰĩ˥ vs plain romanisation "tiang1") lives in appkit now,
# shared with the unified Chao tone display.
_has_ipa = ak.has_ipa


def _wikt_chip(rom):
    return f"<b style='color:#a9c9f0'>{ak.chao_html(rom)}</b>"


def _proto_conf(ch):
    """Proto-Min nucleus vote-margin (daughters' agreement on the reconstructed
    vowel) from provenance, or None. Onset/coda/tone are MC-anchored, not in it."""
    for col, _reading, source, conf in PROV.get(ch, []):
        if col == "Proto-Min" and source == "recon":
            try:
                return float(conf)
            except (TypeError, ValueError):
                return None
    return None


def _conf_color(conf):
    return "#6fb96f" if conf >= 0.8 else "#e0a846" if conf >= 0.6 else "#d2756a"


def _conf_chip(conf):
    """Amber/green/red 'vowel NN%' chip for a Proto-Min reconstruction's nucleus
    confidence — the one slot the daughters (not Middle Chinese) decide."""
    if conf is None:
        return ""
    col = _conf_color(conf)
    return (f"<span title='How much the Min daughters agree on the reconstructed "
            f"vowel — the only slot not anchored on Middle Chinese. Onset, coda and "
            f"tone are MC-anchored and more reliable. Low % = the daughters diverge, "
            f"so the vowel is a best guess.' style='margin-left:7px;padding:0 6px;"
            f"border-radius:6px;font-size:.72em;font-weight:700;vertical-align:middle;"
            f"background:{col}22;color:{col};border:1px solid {col}66'>"
            f"vowel {round(conf * 100)}%</span>")


def _reading_row(ch, dialect, val, wikt=None):
    """Render one reading row (markdown, or a compact 🔊 line for audio rows)."""
    dl = ak._norm(dialect)
    if dialect == "Japanese":
        toks = [t for t in val.split() if t]
        parts = [f"<b>{_html.escape(dialect)}:</b>"]
        for tok in toks:
            cell = f"<code>{_html.escape(tok)}</code>"
            if any("぀" <= c <= "ヿ" or "ㇰ" <= c <= "ㇿ" for c in tok):
                cell += spk(ak.prep_ja_tts(tok, tok), ak.VOICE_JA)
            parts.append(cell)
        play_row(" ".join(parts), height=40 if len(toks) <= 4 else 64)
        return
    if dialect in ("Japanese On", "Japanese Kun", "Korean (romanized)"):
        md(f"**{dialect}:** `{ak.inline_tokens(val).lower()}`"); return
    if dialect == "Korean (Hangul)":
        runs = ak._RE_HANGUL.findall(val) or []
        if runs:
            parts = [f"<b>{_html.escape(dialect)}:</b>"] + [
                f"<code>{_html.escape(r)}</code>{spk(r, ak.VOICE_KO)}" for r in runs]
            play_row(" ".join(parts), height=40)
        else:
            md(f"**{dialect}:** `{val}`")
        return
    if "vietnam" in dl:
        md(f"**{dialect}:** `{ak.inline_tokens(val)}`"); return
    if dl.startswith("mandarin"):
        play_row(f"<b>{_html.escape(dialect)}:</b> "
                 f"<code>{_html.escape(ak.inline_tokens(val))}</code> {spk(ch, ak.VOICE_ZH)}",
                 height=40)
        return
    if dl.startswith("cantonese"):
        play_row(f"<b>{_html.escape(dialect)}:</b> {ak.render_readings_html(val, dialect)} "
                 f"{spk(ch, ak.VOICE_YUE)}", height=40)
        return
    if dialect == "Fanqie":
        # 反切: upper char = initial, lower char = final + tone. Decompose each
        # spelling with the spellers' own Baxter MC readings from the dataset.
        md(f"**{dialect}:** `{ak.inline_tokens(val)}`")
        target_mc = DATA.get(ch, {}).get("Middle Chinese", "")
        for pair in ak.parse_fanqie_pairs(val)[:3]:
            info = ak.fanqie_explain(
                pair,
                DATA.get(pair[0], {}).get("Middle Chinese", ""),
                DATA.get(pair[1], {}).get("Middle Chinese", ""),
                target_mc)
            if not info:
                continue
            tick = (" <span style='color:#6fb96f'>= its MC ✓</span>"
                    if info["matches"] else "")
            md("<span style='color:#9aa7bd;font-size:.85em'>&nbsp;&nbsp;↳ "
               f"<b style='color:#bfe9bf'>{info['upper']}</b> gives the initial "
               f"<code>{_html.escape(info['initial'])}-</code> ＋ "
               f"<b style='color:#bfe9bf'>{info['lower']}</b> gives the final "
               f"<code>-{_html.escape(info['final'])}</code> and the "
               f"{_html.escape(info['tone'])} tone → "
               f"<code>{_html.escape(info['composed'])}</code>{tick}</span>")
        return
    if dialect == "Middle Chinese (position)":
        codes = [c.strip() for c in re.split(r"\s*\|\s*", val) if c.strip()]
        md(f"**{dialect}:** `{'   ·   '.join(codes)}`")
        for code in codes:
            parts = ak.mc_position_breakdown(code)
            if not parts:
                continue
            syl = ak.mc_readable_syllable(code)
            head = f" — sounded roughly like “{_html.escape(syl)}”" if syl else ""
            md(f"<span style='color:#cfcfcf;font-size:.9em'>↳ <b>{_html.escape(code)}</b>{head}</span>")
            for glyph, expl in parts:
                md("<span style='color:#9aa7bd;font-size:.85em'>&nbsp;&nbsp;&nbsp;&nbsp;"
                   f"<b style='color:#bfe9bf'>{_html.escape(glyph)}</b> = {_html.escape(expl)}</span>")
        return
    if dialect == "Proto-Min":
        # Reconstructed (not sourced): show the reading + ≈ English + a nucleus
        # confidence chip (Min daughters' agreement on the vowel). The trailing
        # superscript is the 8-way Min tone CATEGORY, not a pitch — the column
        # is Chao-exempt so it stays a number.
        line = ak.render_readings_html(val, dialect)
        ap = ak.approx_html(dialect, val)
        if ap:
            line += "&nbsp;&nbsp;" + ap
        md(f"**{dialect}:** {line}{_conf_chip(_proto_conf(ch))}")
        return
    rom = (wikt or {}).get(dialect)
    if rom:
        # comma-separated alternates (Wugniu's "8laq,1la") → " / " so each reading
        # is one chip token AND one ≈ approximation, kept 1:1 (else they merge).
        rom = re.sub(r"\s*,\s*", " / ", rom)
        # Wiktionary reading wins outright — show its romanisation as the reading,
        # never alongside the raw DB IPA. The ≈ English sounds-like is generated
        # from the romanisation itself, one per reading, so it stays 1:1 with the
        # readings shown. Class digits become Chao contour letters in the chip;
        # the ≈ is computed from the ORIGINAL rom (its digit is the tone class).
        line = _wikt_chip(ak.wikt_rom_to_chao(rom, ak.ROM_SCHEME.get(dialect)))
        ap = ak.rom_approx_html(rom, ak.ROM_SCHEME.get(dialect))
        if ap:
            line += "&nbsp;&nbsp;" + ap
        hint = ak.sandhi_hint_html(rom, ak.ROM_SCHEME.get(dialect))
        if hint:
            line += "&nbsp;&nbsp;" + hint
        md(f"**{dialect}:** {line}")
        return
    # No Wiktionary reading — fall back to the local database IPA (+ ≈ approx).
    has_ipa = _has_ipa(val)
    line = ak.render_readings_html(val, dialect)
    if has_ipa:
        ap = ak.approx_html(dialect, val)
        if ap:
            line += "&nbsp;&nbsp;" + ap
    hint = ak.sandhi_hint_html(val, ak.ROM_SCHEME.get(dialect))
    if hint:
        line += "&nbsp;&nbsp;" + hint
    md(f"**{dialect}:** {line}")


def _hist_inline(col, val):
    """Inner HTML for one historical reading — the reading plus its ≈ gloss, with
    no ``Label:`` prefix (so two can share a line). The ≈ is shown only for IPA
    readings, matching the standalone-row behaviour: ``approx_html`` yields the
    Baxter–Sagart gloss for Old Chinese and an IPA sounds-like otherwise, and ""
    for the Baxter ASCII transcription (which is not IPA)."""
    line = ak.render_readings_html(val, col)
    if _has_ipa(val):
        ap = ak.approx_html(col, val)
        if ap:
            line += "&nbsp;&nbsp;" + ap
    return line


def _merged_hist_row(ch, primary, secondary, plabel, slabel, bucket):
    """Render a collapsed historical pair (two notations / rival reconstructions)
    on one ``Primary:`` line, joined by ``·``, each optionally school-labelled."""
    segs = []
    for col, label in ((primary, plabel), (secondary, slabel)):
        v = bucket.get(col, "")
        if not v:
            continue
        seg = _hist_inline(col, v)
        if label:
            seg += (f" <span style='color:#8a93a5;font-size:.82em'>({_html.escape(label)})</span>")
        segs.append(seg)
    if not segs:
        return
    sep = " <span style='color:#4a5160'>·</span> "
    md(f"**{primary}:** " + sep.join(segs))


def render_section(title, cols, bucket, ch, collapsed=False, wikt=None):
    """Render a reading section in two columns (optionally inside an expander)."""
    w = wikt or {}
    present = {c for c in cols if (c in bucket and bucket[c]) or w.get(c)}
    # collapse merged historical pairs: drop a secondary when its primary is also
    # present (the primary's row draws both); keep it standalone otherwise.
    _sec_of = {v[0]: p for p, v in _HIST_PAIRS.items()}
    rows = [c for c in cols if c in present
            and not (c in _sec_of and _sec_of[c] in present)]
    if not rows:
        return

    def body():
        half = (len(rows) + 1) // 2
        left, right = st.columns(2, gap="large")
        for group, container in ((rows[:half], left), (rows[half:], right)):
            with container:
                for col in group:
                    if col in _HIST_PAIRS and _HIST_PAIRS[col][0] in present:
                        sec, pl, sl = _HIST_PAIRS[col]
                        _merged_hist_row(ch, col, sec, pl, sl, bucket)
                    else:
                        _reading_row(ch, col, bucket.get(col, ""), wikt)

    if collapsed:
        with st.expander(title):
            body()
    else:
        _section_header(title)
        body()


def render_locality_table(present):
    body = ["<tr><th>Branch</th><th>Locality</th><th>Reading</th><th>≈ English</th></tr>"]
    for col, v in present:
        m = re.match(r"^dial:([^-]+)-(.+)$", col)
        branch = m.group(1) if m else ""
        place = m.group(2) if m else col
        ap = ak.approx_text(v)
        body.append(f"<tr><td style='color:#9aa7bd'>{_html.escape(branch)}</td>"
                    f"<td><b>{_html.escape(place)}</b></td>"
                    f"<td>{ak.render_readings_html(v, col)}</td>"
                    f"<td style='color:#6fb96f'>{ak.chao_html(ap)}</td></tr>")
    scraper_html("<table>" + "".join(body) + "</table>",
                 height=min(620, 60 + len(present) * 30))


def hero_header(ch, bucket):
    meta = ak.char_meta().get(ch, {})
    chips = []
    if meta.get("strokes"):
        chips.append(f"{meta['strokes']} strokes")
    if meta.get("radical"):
        chips.append(f"radical {meta['radical']} {ak.kangxi_radical(meta['radical'])}")
    chips.append(f"U+{ord(ch):04X}")
    defn = bucket.get("Definition", "")
    md("<div style='display:flex;align-items:center;gap:20px;margin:2px 0 12px'>"
       f"<div style='font-size:58px;line-height:1.05'>{_html.escape(ch)}</div>"
       "<div><div style='color:#9aa7bd;font-size:13px'>"
       + " &nbsp;·&nbsp; ".join(chips) +
       f"</div><div style='color:#cfcfcf;font-size:14px;margin-top:5px'>{_html.escape(defn)}</div>"
       "</div></div>")


# =====================================================================
# Sound-evolution tree (one character's pronunciation through history)
# Simplified Sinitic phylogeny: Old Chinese → Middle Chinese → the modern
# branches as *siblings* (not a chain!), with Min splitting off early and the
# Sino-Xenic loans (JP/KO/VI) branching as borrowings around the Tang.
# (id, name, era label, [columns, first found wins], parent, edge style, colour)
_EVO = [
    ("oc",  "Old Chinese",  "~1000 BCE",        ["Old Chinese (Zhengzhang)", "Old Chinese"], None,  "solid",  "#5e3636"),
    ("mc",  "Middle Chinese", "~600 CE · Qieyun", ["Middle Chinese (Baxter)", "Middle Chinese"], "oc", "solid", "#5e4a30"),
    ("tang", "Tang koine",  "618–907 CE",        ["Tang"], "mc", "solid", "#55552c"),
    ("pmin", "proto-Min",   "early split (~Han)", ["Proto-Min"], "oc", "solid", "#27514b"),
    ("hok", "Hokkien", "", ["Hokkien"], "pmin", "solid", "#27514b"),
    ("teo", "Teochew", "", ["Teochew"], "pmin", "solid", "#27514b"),
    ("emin", "Eastern Min (Fuzhou)", "", ["Eastern Min (Fuzhou)"], "pmin", "solid", "#27514b"),
    ("nmin", "Northern Min (Jian'ou)", "", ["Northern Min (Jian'ou)"], "pmin", "solid", "#27514b"),
    ("hai", "Hainanese (Haikou)", "", ["Hainanese (Haikou)"], "pmin", "solid", "#27514b"),
    ("man", "Mandarin", "", ["Mandarin"], "mc", "solid", "#324563"),
    ("jin", "Jin", "", ["Jin"], "mc", "solid", "#324563"),
    ("yue", "Cantonese (Yue)", "", ["Cantonese"], "mc", "solid", "#315831"),
    ("hak", "Hakka", "", ["Hakka"], "mc", "solid", "#315831"),
    ("wu",  "Wu", "", ["Wu"], "mc", "solid", "#315831"),
    ("gan", "Gan", "", ["Gan"], "mc", "solid", "#315831"),
    ("xia", "Xiang", "", ["Xiang"], "mc", "solid", "#315831"),
    ("hui", "Hui (Shexian)", "", ["Hui (Shexian)"], "mc", "solid", "#315831"),
    ("sj",  "Sino-Japanese", "borrowed ~7–9c", ["Japanese On", "Japanese"], "tang", "dashed", "#473055"),
    ("sk",  "Sino-Korean",   "borrowed ~Tang", ["Korean (Hangul)", "Korean (romanized)"], "tang", "dashed", "#473055"),
    ("sv",  "Sino-Vietnamese", "borrowed ~late Tang", ["Vietnamese"], "tang", "dashed", "#473055"),
]
_MIN_CHILDREN = {"hok", "teo", "emin", "nmin", "hai"}

# dial:<branch>-<city> → which tree node the locality hangs under
_BRANCH_NODE = {"Mandarin": "man", "Jin": "jin", "Wu": "wu", "Cantonese": "yue",
                "Hakka": "hak", "Xiang": "xia", "Gan": "gan", "Hui": "hui"}
_MIN_CITY_NODE = {  # the Min localities split across the Min sub-branches
    "Xiamen": "hok", "Quanzhou": "hok", "Zhangzhou": "hok", "Taipei": "hok",
    "Kaohsiung": "hok", "Tainan": "hok", "Taichung": "hok", "Lukang": "hok",
    "Yilan": "hok", "Kinmen": "hok", "Penang": "hok", "Klang": "hok",
    "Zhangpu": "hok", "Changtai": "hok", "Nan'an": "hok", "Tong'an": "hok",
    "Hui'an": "hok", "Jinjiang": "hok", "Putian": "hok",
    "Shantou": "teo", "Fuzhou": "emin", "Jian'ou": "nmin",
    "Haikou": "hai", "Leizhou": "hai",
}


def _branch_localities(bucket):
    out = {}
    for col, v in bucket.items():
        if not col.startswith("dial:") or not v.strip():
            continue
        m = re.match(r"^dial:([^-]+)-(.+)$", col)
        if not m:
            continue
        branch, city = m.group(1), m.group(2)
        node = _MIN_CITY_NODE.get(city) if branch == "Min" else _BRANCH_NODE.get(branch)
        if not node:
            continue
        rd = re.split(r"\s*[|/]\s*", v.replace("[ML]", "").strip())[0].strip()
        if rd:
            out.setdefault(node, []).append((city, rd))
    return out


def _first_reading(bucket, cols):
    for c in cols:
        v = bucket.get(c, "")
        if v:
            first = re.split(r"\s*[|/]\s*", v.replace("[ML]", "").strip())[0].strip()
            if first:
                return first
    return ""


def _h(s):  # minimal HTML-label escaping
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_EVO_GROUP = {
    "man": "north", "jin": "north",
    "yue": "sinitic", "hak": "sinitic", "wu": "sinitic", "gan": "sinitic",
    "xia": "sinitic", "hui": "sinitic",
    "hok": "min", "teo": "min", "emin": "min", "nmin": "min", "hai": "min",
    "sj": "xenic", "sk": "xenic", "sv": "xenic",
}

def _pair_script_rom(scripts, roms, romanize):
    """script-list + romaji-list → 'script (romaji), …' — each reading paired
    with its OWN romanisation (index-matched, else computed), comma-separated."""
    out = []
    for i, s in enumerate(scripts[:4]):
        r = roms[i] if i < len(roms) else romanize(s)
        out.append(f"{s} ({r})" if r else s)
    return ", ".join(out)


def _sino_reading(nid, bucket):
    """Native script + per-reading lowercase romanisation for the Sino-Xenic
    loan nodes (each katakana/hangul gets its own romaji, comma-separated)."""
    if nid == "sj":  # on'yomi: each katakana from 'Japanese' → its own Hepburn
        kata = [t for t in bucket.get("Japanese", "").split()
                if any("゠" <= c <= "ヿ" for c in t)]
        return _pair_script_rom(kata, [], ak.kata_to_romaji) or None
    if nid == "sk":  # each hangul → its stored (Yale) romanisation, else computed
        h = bucket.get("Korean (Hangul)", "").split()
        r = bucket.get("Korean (romanized)", "").lower().split()
        return _pair_script_rom(h, r, ak.rom_ko) or None
    return None


def _node_reading(bucket, cols, wikt):
    """The reading the main panel shows for a tree node — Wiktionary romanisation
    first (the panel is wiki-primary), except Mandarin/Cantonese which the panel
    draws from the local DB; falls back to the first local DB reading. Keeps the
    tree consistent with the topolect panel above it.

    Returns ``(reading, is_ml)`` — ``is_ml`` flags a machine-predicted reading
    that no attested (Wiktionary) source overrode, so the node can be shown as
    inferred, matching the 🤖 ML badge in the panel above."""
    for c in cols:
        if c not in ("Mandarin", "Cantonese"):
            w = (wikt or {}).get(c)
            if w:
                w = ak.wikt_rom_to_chao(w, ak.ROM_SCHEME.get(c))
                return w.replace(" / ", " ").strip(), False
        v = bucket.get(c, "")
        if v:
            raw = re.split(r"\s*[|/]\s*", v.strip())[0].strip()
            first = ak.tones_to_chao(raw.replace("[ML]", "").strip(), c)
            if first:
                return first, raw.endswith("[ML]")
    return "", False


def evolution_dot(ch, bucket, wikt=None):
    # Per-branch sound-law notes derived from THIS character's 音韻地位 —
    # shown as hover tooltips on the tree nodes.
    _mc_code = re.split(r"\s*\|\s*",
                        bucket.get("Middle Chinese (position)", ""))[0].strip()
    law_notes = soundlaws.edge_notes(_mc_code) if _mc_code else {}
    _info = {n[0]: (_node_reading(bucket, n[3], wikt) if n[3] else ("", False)) for n in _EVO}
    reading = {k: v[0] for k, v in _info.items()}
    is_ml = {k: v[1] for k, v in _info.items()}
    for nid in ("sj", "sk"):
        reading[nid] = _sino_reading(nid, bucket) or reading[nid]
    present = {n[0] for n in _EVO if (not n[3]) or reading[n[0]]}
    # proto-Min is a structural branch point: show it whenever this character has
    # any Min daughter — even when it has no reconstruction of its own — so the
    # Min varieties never appear to hang directly off Old Chinese.
    if present & _MIN_CHILDREN:
        present.add("pmin")
    else:
        present.discard("pmin")

    # Nearest present ancestor: if a node's parent is absent for this character
    # (e.g. no Tang reading), climb the lineage so the node still attaches. The
    # Sino-Xenic loans thus fall back from Tang to its parent, Middle Chinese —
    # a faithful one-stage-coarser anchor (Tang *is* Late Middle Chinese), with
    # the dashed "borrowed" edge and era label preserved.
    _parent_of = {n[0]: n[4] for n in _EVO}

    def _anchor(nid):
        p = _parent_of.get(nid)
        while p and p not in present:
            p = _parent_of.get(p)
        return p

    nodes, edges = [], []
    for nid, name, era, cols, parent, style, fill in _EVO:
        if nid not in present:
            continue
        head = (f'<font point-size="16">{_h(ch)}</font>  ' if nid == "oc" else "")
        # comma-separate multiple readings (the Sino nodes are already formatted)
        disp = reading[nid] if nid in ("sj", "sk") else ", ".join(reading[nid].split())
        rd = (f'<br/><font color="#c9d6e6" point-size="11">«{_h(disp)}»</font>'
              if disp else "")
        er = (f'<br/><font color="#cbb9b9" point-size="8">{_h(era)}</font>' if era else "")
        # Machine-predicted node → amber "ML-predicted" tag + dashed amber border,
        # mirroring the 🤖 ML badge the reading panel shows for the same reading.
        ml = (f'<br/><font color="#e0a846" point-size="8">ML-predicted</font>'
              if is_ml.get(nid) else "")
        # proto-Min → vowel-confidence (daughters' nucleus agreement) under the reading.
        if nid == "pmin":
            pc = _proto_conf(ch)
            if pc is not None:
                ml += (f'<br/><font color="{_conf_color(pc)}" point-size="8">'
                       f'vowel {round(pc * 100)}%</font>')
        ml_attr = (' color="#e0a846" penwidth=1.3 style="filled,rounded,dashed"'
                   if is_ml.get(nid) else "")
        # hover tooltip: the regular sound changes that produced this branch's
        # form of THIS character (from its 音韻地位)
        tip_attr = ""
        if law_notes.get(nid):
            tip = "\\n".join("• " + t.replace('"', "'") for t in law_notes[nid])
            tip_attr = f' tooltip="{tip}"'
        nodes.append(f'{nid} [label=<{head}<b>{_h(name)}</b>{rd}{ml}{er}> '
                     f'fillcolor="{fill}"{ml_attr}{tip_attr}];')
        anchor = _anchor(nid)
        if anchor:
            extra = ' style=dashed color="#9a7bb5"' if style == "dashed" else ""
            edges.append(f"{anchor} -> {nid} [{extra}];")

    return ("digraph G {\n"
            'rankdir=LR; bgcolor="transparent"; splines=true; nodesep=0.18; ranksep=0.7;\n'
            'node [shape=box style="filled,rounded" penwidth=0 fontname="Helvetica" '
            'fontsize=13 margin="0.16,0.09" fontcolor="#f4f4f4"];\n'
            'edge [color="#5a6573" arrowsize=0.7 penwidth=1.2];\n'
            + "\n".join(nodes) + "\n" + "\n".join(edges) + "\n}")


def render_single(ch: str):
    bucket, trad_src = ak.with_trad_fallback(DATA, ch)
    if not bucket:
        st.warning(f"No data for '{ch}'."); return
    hero_header(ch, bucket)
    if trad_src:
        st.caption(f"{ch} is a simplified form — columns it lacks are shown from "
                   f"traditional **{trad_src}**.")
    st.download_button(
        "⬇️ Export report (markdown)",
        data=ak.char_report_md(ch, bucket, PROV.get(ch), ak.char_meta().get(ch)),
        file_name=f"{ch}_U{ord(ch):04X}_hanzihub.md", mime="text/markdown")
    wikt = c_wikt_readings(ch)

    glyph = c_glyph_origin(ch)
    if glyph:
        with st.expander("📜 Glyph origin (character evolution)"):
            scraper_html(glyph, height=460, extra_css=_GLYPH_CSS)

    entry = c_wikt_entry(ch)
    if entry:
        with st.expander("📖 Full dictionary entry — etymology, meanings & descendants (Wiktionary)"):
            blocks = [f"<div class='wikt-lang'>{_html.escape(lang)}</div>{html}"
                      for lang, html in entry]
            body = ("<div class='wikt-entry'>" + "".join(blocks)
                    + "<div class='wikt-src'>Source: English Wiktionary (CC BY-SA 4.0)</div></div>")
            scraper_html(body, height=640, extra_css=_ENTRY_CSS)

    with st.expander("🌳 Sound evolution (Old Chinese → today)", expanded=True):
        st.graphviz_chart(evolution_dot(ch, bucket, wikt), width="content")
        st.caption("**Hover a branch node** to see the regular sound changes that produced "
                   "this character's form there (derived from its Middle Chinese category). "
                   "Cantonese is *not* Mandarin's ancestor — the modern branches are cousins "
                   "from Middle Chinese; **Min** (teal) split off early; **dashed purple** = borrowed "
                   "into Japanese/Korean/Vietnamese; an **amber dashed border + “ML-predicted”** marks a "
                   "reading inferred by the model (🤖 ML in the panel above), not attested in a source. "
                   "*Kun'yomi, Okinawan and Zhuang are omitted: native words, not Chinese-derived.* "
                   "See Guides → *Sound Evolution & Chronology*.")

    pref = ak.PREFERRED_ORDER
    sinitic = [c for c in pref if c in _SINITIC]
    hist = [c for c in pref if c in _HIST]
    sino = [c for c in pref if c in _SINO]
    known = _SINITIC | _HIST | _SINO | {"Definition"}
    other = [c for c in ak.sorted_cols(DIALECT_COLS)
             if c not in known and not c.startswith("dial:")]

    render_section("🗣️ Sinitic topolects", sinitic, bucket, ch, wikt=wikt)
    render_section("📜 Historical layers", hist, bucket, ch, collapsed=True)
    render_section("🌏 Sinosphere", sino, bucket, ch, collapsed=True)
    if other:
        render_section("Other readings", other, bucket, ch, collapsed=True)

    # Locality (dial:) layer — deduped against the main rows (each reading once).
    # Tokens are compared in unified Chao form, so tʰi⁵³ (kaikki) and tʰi˥˧
    # (wikihan) count as the same reading.
    def _toks(v, c=None):
        v = ak.tones_to_chao((v or "").replace("[ML]", ""), c)
        return {t for t in re.split(r"\s*\|\s*|\s+", v.strip()) if t}
    shown = set()
    for _c, _v in bucket.items():
        if not _c.startswith("dial:"):
            shown |= _toks(_v, _c)
    present = [(c, bucket[c]) for c in DIALECT_COLS
               if c.startswith("dial:") and c in bucket and bucket[c]
               and not _toks(bucket[c], c) <= shown]
    if present:
        with st.expander(f"🗺️ More locality readings ({len(present)} points)"):
            render_locality_table(present)

    rows = PROV.get(ch)
    if rows:
        with st.expander("🔎 Show sources (provenance)"):
            body = ["<tr><th>Column</th><th>Reading</th><th>Source</th><th>Conf</th></tr>"]
            for col, reading, source, conf in rows:
                c = "" if conf in (None, "") or (isinstance(conf, float) and conf != conf) else f"{float(conf):.2f}"
                sty = " style='color:#9aa0a6;font-style:italic'" if source == "ml" else ""
                body.append(f"<tr{sty}><td>{col}</td><td>{reading}</td><td>{source}</td><td>{c}</td></tr>")
            scraper_html("<table>" + "".join(body) + "</table>",
                         height=min(560, 60 + len(rows) * 28))


# =====================================================================
# Multi character
# =====================================================================
def render_multi(text: str):
    st.subheader(f"Pronunciations for {text}")

    # Per-character drill-down: each Hanzi becomes a button that re-runs the
    # search on that single character, opening the full single-character view
    # (glyph origin, sound-evolution tree, provenance, …).
    chars = [c for c in dict.fromkeys(text) if ak.looks_like_hanzi(c)]
    if len(chars) > 1:
        st.caption("Look up an individual character:")
        per_row = 8
        for start in range(0, len(chars), per_row):
            row = chars[start:start + per_row]
            cols = st.columns(per_row)
            for col, ch in zip(cols, row):
                col.button(ch, key=f"drill_{ch}", use_container_width=True,
                           on_click=lambda c=ch: st.session_state.update(query=c))

    with st.container(border=True):
        st.markdown("**Definition** — the meaning, then each language's *native* word for it")
        if not ak.gt_ready():
            st.info("Google Translation client not initialized — check credentials / billing.")
        try:
            en = c_translate(text, "en")          # meaning of the input, auto-detect source
            if not en:
                st.info("No English translation returned for this input.")
            else:
                md(f"**Meaning (English):** {en}")
                # Pivot through the English meaning so we get each language's native
                # word (e.g. 苦瓜 → 'bitter melon' → ko 여주, vi 'mướp đắng'), not 苦瓜.
                for label, tgt, romlang in [("Chinese", "zh-TW", "zh"),
                                            ("Japanese", "ja", "ja"),
                                            ("Korean", "ko", "ko"),
                                            ("Vietnamese", "vi", None)]:
                    native = c_translate(en, tgt, "en")
                    if not native:
                        continue
                    rom = romanize_native(native, romlang) if romlang else ""
                    md(f"{label}: <code>{native}{(' — ' + rom) if rom else ''}</code>")
        except ak.TranslationError as e:
            st.error(f"Translation unavailable — {e}")

    st.divider()
    st.markdown("### Per-character readings & audio")

    st.markdown("**Japanese**")
    jp_shin = ak.to_shinjitai_per_char(text)
    ja_romaji, ja_kana = c_ja_kana(text)
    md(f"<code>{ja_romaji or '(n/a)'}</code>")
    audio(ak.prep_ja_tts(ja_kana, jp_shin), ak.VOICE_JA, jp_shin)

    st.markdown("**Korean**")
    ko_hangul, ko_romaji = ak.ko_from_hanzi_local(text)
    if ko_hangul:
        md(f"Hangul: <code>{ko_hangul}</code> &nbsp; Romanized: <code>{ko_romaji}</code>")
        md(f"<code>{ak.ko_per_char_pairs(text)}</code>")
        audio(ko_hangul, ak.VOICE_KO, ko_hangul)
        with st.expander("Hanja per character (koreanhanja.app)"):
            html = sc.render_koreanhanja_html(c_hanja_from_hanzi(text),
                                              f"https://koreanhanja.app/{text}",
                                              tts=ak.tts_bytes, voice_ko=ak.VOICE_KO)
            scraper_html(html, 320)
    else:
        md("<code>(n/a)</code>")

    st.markdown("**Vietnamese (Chữ Nôm)**")
    with st.expander("Chữ Nôm table (with Quốc Ngữ audio)"):
        df, _ = c_nom_from_hanzi(text)
        scraper_html(sc.render_nom_html(df, tts=ak.tts_bytes, voice_vi=ak.VOICE_VI), 360)

    st.markdown("**Other topolects**")
    trad = ak.s2t_text(text)
    if trad != text:
        conv = " ".join(f"{s}→{t}" for s, t in zip(text, trad) if s != t)
        st.caption(f"Simplified input — missing readings are filled from the "
                   f"traditional forms: {conv}")
    for dialect in ak.sorted_cols(DIALECT_COLS):
        dl = ak._norm(dialect)
        if dialect.startswith("dial:") or dl in ("definition", "fanqie", "fanqie_upper", "fanqie_lower"):
            continue
        if "japanese" in dl or dl.startswith("korean") or "vietnam" in dl:
            continue
        toks = ak.per_char_tokens(DATA, dialect, text, trad)
        if not any(tok for _, tok in toks):
            continue
        hok_coll = None             # (hanzi, tâi-lô) translation | Exception
        if dl.startswith("hokkien"):
            # ithuan's tâi-lô picks the in-context reading among each
            # character's alternates (台 in 台灣 = tone 5)
            try:
                toks = ak.tailo_matched_tokens(DATA, dialect, text, trad,
                                               c_hokkien_tailo(trad))
            except Exception:
                pass                            # keep the first readings
            # the written sentence is Mandarin vocabulary — fetch how it is
            # actually SAID in Taiwanese (今天我很開心 → 今仔日我真爽快)
            try:
                hok_coll = c_hokkien_colloquial(trad)
            except Exception as e:
                hok_coll = e
        elif dl.startswith("teochew"):
            # no Teochew annotation service exists, but the Hokkien tâi-lô
            # of the same hanzi referees the literary/colloquial doublet
            # choice (cognates share MC tone class + initial correspondence:
            # 樂 in 快樂 = lo̍k → lag8, not ghauh8); mogher.com supplies
            # doublets missing from our data
            try:
                toks = ak.teochew_tailo_matched_tokens(
                    DATA, dialect, text, trad, c_hokkien_tailo(trad))
            except Exception:
                pass
        parts = []
        for ch, tok in toks:
            if tok:
                t = _html.escape(ak.tones_to_chao(tok.removesuffix("[ML]"), dialect))
                if tok.endswith("[ML]"):
                    t = (f"<span style='color:#d8c79b;font-style:italic' "
                         f"title='{ak.ML_TOOLTIP}'>{t}</span>")
                parts.append(t)
            else:
                parts.append(f"<span style='color:#4a5160' title='no {_html.escape(dialect)} "
                             f"reading recorded for {ch}'>{ch}</span>")
        block = f"**{dialect}:** <code>{' '.join(parts)}</code>"
        ap = ak.approx_html(dialect, " ".join(tok for _, tok in toks if tok))
        if ap:
            block += "  " + ap
        md(block)
        sandhi_line = ak.phrase_sandhi_html(toks, dialect)
        if sandhi_line:
            md(sandhi_line)
        if dl.startswith("mandarin"):
            audio(text, ak.VOICE_ZH, text)
        elif dl.startswith("cantonese"):
            audio(text, ak.VOICE_YUE, text)
        elif dl.startswith("hokkien"):
            # 意傳's SuiSiann voice speaks natural Taiwanese, sandhi
            # included. When Lohankha's 華→台 translation differs from the
            # written sentence, the COLLOQUIAL wording is what gets spoken —
            # nobody says the Mandarin-vocabulary text aloud in Hokkien.
            coll = hok_coll if isinstance(hok_coll, tuple) else None
            differs = bool(coll) and ak.hanzi_only(coll[0]) != ak.hanzi_only(trad)
            speak = coll[0] if differs else trad
            mp3 = kip = None
            try:
                mp3, kip = c_hokkien_tts(speak)
            except Exception as e:
                st.caption("Taiwanese Hokkien audio unavailable (ithuan.tw): "
                           f"{e}")
            if differs:
                inner = ("<span style='opacity:.85'>↳ colloquial: </span>"
                         f"<b>{_html.escape(coll[0])}</b> "
                         "<span style='opacity:.7;font-size:.92em'>"
                         f"{_html.escape(kip or coll[1])}</span> "
                         "<span style='opacity:.6;font-size:.85em' "
                         "title='The written sentence uses Mandarin "
                         "vocabulary; this is how it is actually SAID in "
                         "Taiwanese Hokkien — words and grammar translated "
                         "by Lohankha 華→台 MT (今天→今仔日, 很→真), then "
                         "synthesized by ithuan.tw. Machine translation can "
                         "err.'>(colloquial Taiwanese Hokkien — Lohankha MT)"
                         "</span> " + (spk_bytes(mp3, ("nan", speak))
                                       if mp3 else ""))
                play_row(inner, 40)
                toks_c = ak.tailo_matched_tokens(
                    DATA, dialect, speak, ak.s2t_text(speak), kip or "")
                coll_line = ak.phrase_sandhi_html(
                    toks_c, dialect, label="&nbsp;&nbsp;↳ colloquial spoken:")
                if coll_line:
                    md(coll_line)
            elif mp3:
                play_row("<span style='opacity:.7;font-size:.92em'>"
                         f"{_html.escape(kip)} <span style='opacity:.6' "
                         "title='Hokkien varies by region (Amoy, Quanzhou/"
                         "Zhangzhou, Penang, Singapore…); this voice and its "
                         "sandhi are specifically the TAIWANESE variety "
                         "(臺灣話, 意傳 SuiSiann).'>(Taiwanese Hokkien, "
                         "ithuan.tw)</span></span> "
                         + spk_bytes(mp3, ("nan", speak)))
            if isinstance(hok_coll, Exception):
                st.caption("Colloquial Taiwanese translation unavailable "
                           f"(Lohankha): {hok_coll}")
        elif dl.startswith("teochew"):
            # No Teochew TTS or Mandarin→Teochew MT exists anywhere
            # (2026-07). But Teochew shares most core vocabulary with its
            # sister language Hokkien, so the Lohankha TAIWANESE translation
            # (with common Taiwan-only words swapped, 今仔日→今日) is a far
            # closer wording than the written Mandarin; audio is stitched
            # from mogher.com's per-syllable dictionary recordings, fetched
            # independently so one missing tone doesn't silence both plays.
            teo_src, via = text, False
            try:
                cand = ak.teochew_colloquial_source(c_hokkien_colloquial(trad)[0])
                if ak.hanzi_only(cand) != ak.hanzi_only(trad):
                    teo_src, via = cand, True
            except Exception:
                pass
            toks_t = toks
            if via:
                try:
                    toks_t = ak.teochew_tailo_matched_tokens(
                        DATA, dialect, teo_src, ak.s2t_text(teo_src),
                        c_hokkien_tailo(teo_src))
                except Exception:
                    toks_t = ak.per_char_tokens(DATA, dialect, teo_src,
                                                ak.s2t_text(teo_src))
                md("<span style='color:#8a93a5;font-size:.82em'>"
                   "&nbsp;&nbsp;↳ colloquial:</span> "
                   f"<b>{_html.escape(teo_src)}</b> "
                   "<span style='opacity:.6;font-size:.85em' title='No "
                   "Mandarin→Teochew translator exists, but Teochew is a "
                   "sister Southern Min language sharing most core "
                   "vocabulary with Hokkien — so this borrows the Taiwanese "
                   "translation, with common Taiwan-specific words swapped "
                   "for Teochew ones (今仔日→今日, 佗位→底塊). Remaining "
                   "vocabulary may still differ from natural Teochew; an "
                   "approximation.'>(via Hokkien — approximate)</span>")
                coll_line = ak.phrase_sandhi_html(
                    toks_t, dialect, label="&nbsp;&nbsp;↳ colloquial spoken:")
                if coll_line:
                    md(coll_line)
            teo, errs = {}, []
            for name, spoken in (("citation", False), ("spoken", True)):
                try:
                    teo[name] = c_teochew_phrase(toks_t, spoken)
                except Exception as e:
                    errs.append(str(e))
            cit, spo = teo.get("citation"), teo.get("spoken")
            if cit or spo:
                tip = ("Stitched from single-syllable dictionary "
                       "recordings — not natural connected speech, and "
                       "the CHAOZHOU-CITY variety specifically (Teochew "
                       "varies: Shantou, Chenghai, Jieyang…). The spoken "
                       "version plays each non-final syllable with the "
                       "citation-tone recording nearest its sandhi "
                       "contour — an approximation. "
                       + ("Plays the ↳ colloquial wording above."
                          if via else
                          "Reads the sentence AS WRITTEN, word by word — "
                          "colloquial wording unavailable for this input."))
                row = ("<span style='opacity:.7;font-size:.92em' "
                       f"title='{tip}'>(Chaozhou Teochew, mogher.com, "
                       "stitched)</span>")
                if cit:
                    row += " citation " + spk_bytes(cit, ("teo-cit", teo_src))
                if spo and spo != cit:
                    row += "&nbsp;&nbsp;spoken " + spk_bytes(spo, ("teo-spk", teo_src))
                play_row(row)
            if errs:
                st.caption("Chaozhou Teochew audio partly unavailable "
                           f"(mogher.com): {'; '.join(sorted(set(errs)))}")


# =====================================================================
# Reading lookup (romanisation → characters)
# =====================================================================
def render_reading_hits(q: str, hits: dict):
    """Characters carrying the queried reading (pinyin/jyutping/on'yomi/
    Baxter MC/…), richest-documented first, with drill-down buttons."""
    st.subheader(f"Characters read “{q}”")
    chars = sorted(hits, key=lambda c: -len(DATA.get(c, {})))
    st.caption(f"{len(chars)} character(s) carry this reading in some column "
               "(tone digits are ignored unless you type them).")
    per_row = 10
    for start in range(0, min(len(chars), 60), per_row):
        row = chars[start:start + per_row]
        cols = st.columns(per_row)
        for col, ch in zip(cols, row):
            col.button(ch, key=f"rhit_{ch}", use_container_width=True,
                       on_click=lambda c=ch: st.session_state.update(query=c))
    body = ["<tr><th>Char</th><th>Definition</th><th>Matched in</th></tr>"]
    for ch in chars[:15]:
        defn = DATA.get(ch, {}).get("Definition", "")[:80]
        body.append(f"<tr><td style='font-size:1.4em'>{_html.escape(ch)}</td>"
                    f"<td>{_html.escape(defn)}</td>"
                    f"<td style='color:#9aa7bd'>{_html.escape(', '.join(sorted(hits[ch])))}</td></tr>")
    scraper_html("<table>" + "".join(body) + "</table>",
                 height=min(560, 70 + 15 * 30))
    if st.checkbox(f"Also search “{q}” as an English word"):
        render_reverse(q)


# =====================================================================
# Reverse lookup (English)
# =====================================================================
def render_reverse(en: str):
    st.subheader(f"Reverse lookup: {en}")

    st.markdown("**Chinese topolects (via Traditional Chinese)**")
    zh = _safe_translate(en, "zh-TW", "en")
    if zh:
        md(f"<code>{zh}</code>")
        for dialect in ak.sorted_cols(DIALECT_COLS):
            dl = ak._norm(dialect)
            if dialect.startswith("dial:") or dl in ("definition", "fanqie", "fanqie_upper", "fanqie_lower"):
                continue
            if "japanese" in dl or dl.startswith("korean") or "vietnam" in dl:
                continue
            line = ak.inline_tokens(ak.concat_per_char(DATA, dialect, zh, ak.s2t_text(zh)))
            if line:
                md(f"**{dialect}:** `{ak.tones_to_chao(line, dialect)}`")

    st.markdown("---\n**Vietnamese (Nôm Foundation)**")
    vi = _safe_translate(en, "vi", "en")
    if vi:
        md(f"<code>{vi}</code>")
        df, url = c_nom_from_text(vi)
        scraper_html(sc.render_nom_html(df, tts=ak.tts_bytes, voice_vi=ak.VOICE_VI), 320)
        if url:
            md(f'<a href="{url}" target="_blank">View full page</a>')

    st.markdown("---\n**Korean (koreanhanja.app)**")
    rows, url = c_hanja_from_english(en)
    scraper_html(sc.render_koreanhanja_html(rows, url, tts=ak.tts_bytes, voice_ko=ak.VOICE_KO), 320)

    st.markdown("---\n**Japanese (JapanDict)**")
    entries, url = c_japandict(en)
    html = sc.render_japandict_html(entries, url, tts=ak.tts_bytes, voice_ja=ak.VOICE_JA,
                                    romaji_to_hiragana=ak.romaji_to_hiragana,
                                    kana_hira_to_kata=ak.kana_hira_to_kata)
    scraper_html(html, 360)


# =====================================================================
# IPA legend / guides / paper
# =====================================================================
def render_legend(s: str):
    if len(s) == 1 and s in DATA:
        readings = [v for v in DATA[s].values() if v]
    else:
        readings = [ak.concat_per_char(DATA, d, s, ak.s2t_text(s)) for d in DIALECT_COLS]
    lines = ak.ipa_legend_lines(readings, SYMBOLS)
    if not lines:
        st.info("No IPA symbols found (or IPA file missing)."); return
    st.subheader("📘 IPA Legend")
    for ln in lines:
        st.markdown(f"`{ln}`")


GUIDE_FILES = {
    "Reading Variants Guide": "variants_guide.md",
    "Sound Evolution & Chronology": "evolution_guide.md",
    "IPA Guide": "IPA_guide.md",
    "Tone Contour Guide": "tone_contour_guide.md",
    "Romanisation Tone (≈) Guide": "tone_number_guide.md",
    "Baxter–Sagart OC/MC Guide": "baxtersagart_guide.md",
    "Middle Chinese Position Guide": "mc_position_guide.md",
}


def render_guides():
    st.subheader("📚 Guides")
    title = st.selectbox("Guide", list(GUIDE_FILES.keys()))
    path = paths.ROOT / "Guides" / GUIDE_FILES[title]
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.warning(f"Missing: {path}")


def render_paper():
    st.subheader("Historical & Phonological Evolution of Sinitic Languages")
    path = paths.ROOT / "Guides" / "Historical and Phonological Evolution of Sinitic (Chinese) Languages.docx"
    if not path.exists():
        st.warning("Paper file not found."); return
    try:
        from docx import Document
        st.markdown("\n\n".join(p.text for p in Document(str(path)).paragraphs if p.text.strip()))
    except Exception as e:
        st.error(f"Error reading DOCX: {e}")


# =====================================================================
# Layout
# =====================================================================
with st.sidebar:
    st.title("漢字音庫")
    st.caption("Hanzi Sound Library")
    query = st.text_input("Enter Hanzi (single/multi) or English", key="query")
    mode = st.radio("Mode", ["Lookup", "IPA Legend", "Guides", "Sinitic Paper"])
    st.caption(f"{len(DATA):,} characters · {len(DIALECT_COLS)} columns")
    if not ak.gt_ready():
        st.caption("⚠️ Translation/TTS credentials not set")

q = (query or "").strip()
if mode == "Guides":
    render_guides()
elif mode == "Sinitic Paper":
    render_paper()
elif mode == "IPA Legend":
    if q:
        render_legend(q)
    else:
        st.info("Enter a Hanzi, then choose IPA Legend.")
elif not q:
    st.info("Enter Hanzi or an English word in the sidebar.")
elif ak.looks_like_hanzi(q):
    render_single(q) if len(q) == 1 else render_multi(q)
else:
    # single latin token that IS a known reading → reading lookup;
    # anything else (phrases, unknown words) → English reverse lookup
    _hits = (reading_index().get(ak.fold_reading_query(q))
             if re.fullmatch(r"[A-Za-zÀ-ÿĀ-ſ0-9'\-]+", q) else None)
    if _hits:
        render_reading_hits(q, _hits)
    else:
        render_reverse(q)
