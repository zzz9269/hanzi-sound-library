"""Live web lookups used by the app (JapanDict, koreanhanja.app, Nom Foundation).

Ported from 漢字音庫_v9.ipynb. Each fetcher returns plain data; the ``*_html``
renderers return an HTML string (audio is injected by the caller via the ``tts``
callback ``tts(text, lang, voice) -> mp3 bytes`` so this module stays UI-free).
"""
from __future__ import annotations

import base64
import functools
import html as _html
import json
import logging
import re
import time
import urllib.parse
from io import StringIO
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("hanzihub")

_WIKT_API = "https://en.wiktionary.org/w/api.php"

# ---------------------------------------------------------------------------
# Per-character disk cache for the live Wiktionary fetches. Streamlit's
# st.cache_data is per-session memory only — every app restart re-hit the
# network for the same characters. Entries change rarely, so cache to JSON
# under cache/wikt/<kind>/ with a 30-day TTL; failed/empty fetches are NOT
# cached (a network blip must not pin an empty panel for a month).
# ---------------------------------------------------------------------------
_WIKT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "wikt"
_WIKT_CACHE_TTL = 30 * 86400


def _wikt_cache_path(kind: str, char: str) -> Path:
    cp = "-".join(f"{ord(c):X}" for c in char[:4])
    d = _WIKT_CACHE_DIR / kind
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{cp}.json"


def _disk_cached(kind):
    """Decorator: JSON disk cache keyed on the first (char) argument."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(char, *args, **kwargs):
            c = (char or "").strip()
            if not c:
                return fn(char, *args, **kwargs)
            p = _wikt_cache_path(kind, c)
            try:
                if p.exists() and time.time() - p.stat().st_mtime < _WIKT_CACHE_TTL:
                    return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                log.info("wikt cache read failed (%s): %s", kind, e)
            val = fn(char, *args, **kwargs)
            if val:
                try:
                    p.write_text(json.dumps(val, ensure_ascii=False),
                                 encoding="utf-8")
                except Exception as e:
                    log.info("wikt cache write failed (%s): %s", kind, e)
            return val
        return wrapper
    return deco


def _wikt_api(params, retries=3):
    """GET the Wiktionary parse API as JSON, retrying transient failures
    (rate-limit / non-JSON responses). ``{}`` if all attempts fail."""
    err = None
    for i in range(retries):
        try:
            r = requests.get(_WIKT_API, params={**params, "format": "json"},
                             headers=_JD_HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            err = e
            if i < retries - 1:
                time.sleep(1.0 + i)
    log.warning("Wiktionary API failed after %d tries (%s): %s",
                retries, params.get("page", "?"), err)
    return {}

# {{zh-pron}} parameter → the app's Sinitic-topolect column
_ZHPRON_COL = {
    "m": "Mandarin", "c": "Cantonese", "g": "Gan", "j": "Jin",
    "mb": "Northern Min (Jian'ou)", "md": "Eastern Min (Fuzhou)",
    "mn": "Hokkien", "mn-t": "Teochew", "x": "Xiang",
    "w": "Wu", "w-j": "Wu", "w-u": "Wu", "w-sh": "Wu",
}


_HAN_RE = re.compile(r"[㐀-鿿]")
# a complete comment, or an unclosed one running to the end of the text
_HTML_COMMENT_RE = re.compile(r"<!--.*?(?:-->|$)", re.S)


def _extract_template(wt, name):
    """Return the full ``{{name…}}`` template text (brace-balanced, so nested
    templates in _note params don't truncate it), or ``None``. HTML comments
    are dropped first: editors park alternative readings in them
    (``|m=zhě<!--, zhe-->``) and their pipes would split parameters."""
    wt = _HTML_COMMENT_RE.sub("", wt or "")
    start = wt.find("{{" + name)
    if start < 0:
        return None
    i, depth = start + 2, 1
    while i < len(wt) and depth:
        two = wt[i:i + 2]
        if two == "{{":
            depth += 1; i += 2
        elif two == "}}":
            depth -= 1; i += 2
        else:
            i += 1
    return wt[start:i]


def _split_top_pipes(s):
    """Split on ``|`` only at brace/bracket depth 0 (so nested-template pipes in
    _note params stay intact)."""
    parts, cur, depth, i = [], [], 0, 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; cur.append(two); i += 2
        elif two in ("}}", "]]"):
            depth = max(0, depth - 1); cur.append(two); i += 2
        elif s[i] == "|" and depth == 0:
            parts.append("".join(cur)); cur = []; i += 1
        else:
            cur.append(s[i]); i += 1
    parts.append("".join(cur))
    return parts


def _clean_zhpron(v):
    """A zh-pron value → up to 4 ' / '-joined readings. Reading-groups are split
    on ``/`` or ``;``; the Min/Wu locality format ``loc1,loc2:reading`` keeps only
    the part after ``:``; bare simple readings may be comma-separated alternates.
    Drops sandhi targets (``a>b`` → ``a``), locality codes, sub-flags (``er=y``)
    and Han-character junk."""
    out = []
    for group in re.split(r"[/;]", v):
        group = group.strip()
        if not group:
            continue
        cands = [group.split(":", 1)[1].strip()] if ":" in group else group.split(",")
        for c in cands:
            c = c.split(">")[0].strip()  # sandhi: keep the citation form
            if c and "=" not in c and not _HAN_RE.search(c) and c not in out:
                out.append(c)
    return " / ".join(out[:4])


def _parse_hakka(hv):
    sub = {}
    for kv in hv.split(";"):
        if "=" in kv:
            k, val = kv.split("=", 1)
            sub[k.strip()] = val.strip()
    out = []
    for key in ("pfs", "hrs", "gd", "ct"):  # Sixian, Hailu, … (first wins as primary)
        if sub.get(key):
            cleaned = "/".join(re.sub(r"^[a-z]+:", "", p).strip()
                               for p in sub[key].split("/"))
            if cleaned and cleaned not in out:
                out.append(cleaned)
    return " / ".join(out[:2])


@_disk_cached("readings")
def fetch_wiktionary_readings(char):
    """Live: parse a character's {{zh-pron}} template → {column: romanisation}
    for the Sinitic topolects (Mandarin pinyin, Cantonese jyutping, Hokkien POJ,
    Fuzhou BUC, Jian'ou, Hakka, Wu, Gan, Xiang, Jin). ``{}`` if none."""
    char = (char or "").strip()
    if not char:
        return {}
    j = _wikt_api({"action": "parse", "page": char, "prop": "wikitext"})
    wt = j.get("parse", {}).get("wikitext", {}).get("*", "")
    tpl = _extract_template(wt, "zh-pron")
    if not tpl:
        return {}
    params = {}
    for part in _split_top_pipes(tpl[2:-2]):  # strip the outer {{ }}
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip()] = v.strip()
    out = {}
    for key, col in _ZHPRON_COL.items():
        v = params.get(key)
        if v and v not in ("y", "n"):
            cleaned = _clean_zhpron(v)
            if cleaned and col not in out:
                out[col] = cleaned
    if params.get("h"):
        hk = _parse_hakka(params["h"])
        if hk:
            out["Hakka"] = hk
    return out


@_disk_cached("glyph")
def fetch_glyph_origin_html(char: str) -> str:
    """Return cleaned HTML of a character's Wiktionary *Glyph origin* section
    (etymology prose + the oracle-bone→seal historical-forms images), or ``""``.

    Uses the section API so we get just that section, then absolutises image/
    link URLs so they render inside an iframe."""
    char = (char or "").strip()
    if not char:
        return ""
    secs = _wikt_api({"action": "parse", "page": char,
                      "prop": "sections"}).get("parse", {}).get("sections", [])
    idx = next((x["index"] for x in secs
                if x.get("line", "").strip().lower() == "glyph origin"), None)
    if not idx:
        return ""
    html = _wikt_api({"action": "parse", "page": char, "section": idx,
                      "prop": "text"}).get("parse", {}).get("text", {}).get("*", "")
    return _clean_wikt_html(html)


def _clean_wikt_html(html):
    """Strip edit-links/scripts, absolutise links & images so a Wiktionary
    section renders cleanly inside our iframe."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select(".mw-editsection, script, style, sup.reference, "
                           ".noprint, .nyms, .mw-heading"):
        tag.decompose()
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("/"):
            a["href"] = "https://en.wiktionary.org" + a["href"]
        a["target"] = "_blank"
    for img in soup.find_all("img"):
        for attr in ("src", "srcset"):
            if img.get(attr):
                img[attr] = re.sub(r"(^|,\s*|\s)//", r"\1https://", img[attr])
    return str(soup).strip()


# Languages whose full entry we surface (Chinese + the Sino-xenic borrowers).
_ENTRY_LANGS = ("Chinese", "Japanese", "Korean", "Vietnamese", "Okinawan", "Zhuang")

# Subsections dropped from the full entry: pronunciation is shown in our own
# formatted rows, glyph origin has its own panel, the rest is noise.
_DROP_SUBSECTIONS = ("pronunciation", "glyph origin", "references",
                     "reference", "further reading", "see also", "anagrams",
                     "compounds", "derived terms", "related terms",
                     "descendants in other languages")


def _heading_level(node):
    if not getattr(node, "get", None) or "mw-heading" not in (node.get("class") or []):
        return None
    h = node.find(re.compile(r"^h[1-6]$"))
    return int(h.name[1]) if h else None


def _pop_subsections(root, titles):
    """Remove any heading whose text starts with one of `titles` (+ its content
    up to the next same/higher heading). Returns the removed CONTENT html (the
    sub-headings' bodies, without the matched heading itself)."""
    taken = []
    for node in list(root.find_all(recursive=False)):
        if not node.parent:  # already removed as a sibling
            continue
        lvl = _heading_level(node)
        if lvl is None:
            continue
        h = node.find(re.compile(r"^h[1-6]$"))
        title = re.sub(r"\s+", " ", h.get_text()).strip().lower()
        if not any(title.startswith(t) for t in titles):
            continue
        sib = node.find_next_sibling()
        node.decompose()
        while sib:
            slvl = _heading_level(sib)
            if slvl is not None and slvl <= lvl:
                break
            nxt = sib.find_next_sibling()
            taken.append(str(sib))
            sib.decompose()
            sib = nxt
    return "".join(taken)


def _clean_entry_root(html):
    """Full language-section HTML → a cleaned BeautifulSoup root: drop
    pronunciation/glyph-origin/reference subsections, navboxes & char-boxes, the
    section's own language heading; neutralise Wiktionary's hardcoded light
    backgrounds; absolutise links/images. ``None`` if empty."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup
    for tag in root.select(
            ".mw-editsection, script, style, meta, .noprint, .navbox, "
            ".sister-wikipedia, .sister-project, .floatright, .floatleft, "
            ".thumb, sup.reference, .zhpron, .mw-references-wrap, .reflist, "
            "#toc, .toc, .mw-empty-elt, link"):
        tag.decompose()
    _pop_subsections(root, _DROP_SUBSECTIONS)
    # remove the section's own top-level language heading (we render our own label)
    for node in root.find_all(recursive=False):
        if _heading_level(node) == 2:
            node.decompose()
            break
    # neutralise Wiktionary's hardcoded LIGHT backgrounds / dark text so the
    # dialectal-synonyms & reading tables don't glare on our dark theme.
    for el in root.find_all(attrs={"bgcolor": True}):
        del el["bgcolor"]
    for el in root.find_all(style=True):
        s = re.sub(r"(background(-color)?|color)\s*:[^;]*;?", "", el["style"], flags=re.I)
        if s.strip():
            el["style"] = s
        else:
            del el["style"]
    for a in root.find_all("a", href=True):
        if a["href"].startswith("/"):
            a["href"] = "https://en.wiktionary.org" + a["href"]
        a["target"] = "_blank"
    for img in root.find_all("img"):
        for attr in ("src", "srcset"):
            if img.get(attr):
                img[attr] = re.sub(r"(^|,\s*|\s)//", r"\1https://", img[attr])
    return root


@_disk_cached("entry")
def fetch_wiktionary_entry(char):
    """Live: the full Wiktionary entry per language (Chinese/Japanese/Korean/
    Vietnamese): etymology, definitions, descendants, usage notes … minus
    pronunciation (our own rows) and glyph origin (its own panel). The big
    dialectal-synonyms table is pulled out of Chinese and appended LAST.
    Returns ``[(label, html), …]`` (Chinese first, Synonyms last), or ``[]``."""
    char = (char or "").strip()
    if not char:
        return []
    secs = _wikt_api({"action": "parse", "page": char,
                      "prop": "sections"}).get("parse", {}).get("sections", [])
    out, synonyms = [], ""
    for x in secs:
        if x.get("toclevel") != 1:
            continue
        lang = re.sub(r"<[^>]+>", "", x.get("line", "")).strip()
        if lang not in _ENTRY_LANGS:
            continue
        raw = _wikt_api({"action": "parse", "page": char, "section": x["index"],
                         "prop": "text"}).get("parse", {}).get("text", {}).get("*", "")
        root = _clean_entry_root(raw)
        if root is None:
            continue
        if lang == "Chinese":  # relocate the dialectal-synonyms table to the very end
            synonyms = _pop_subsections(root, ("synonyms",)) or synonyms
        html = str(root).strip()
        if html and len(BeautifulSoup(html, "html.parser").get_text(strip=True)) > 1:
            out.append((lang, html))
    order = {l: i for i, l in enumerate(_ENTRY_LANGS)}
    out.sort(key=lambda t: order.get(t[0], 99))
    if synonyms and BeautifulSoup(synonyms, "html.parser").get_text(strip=True):
        out.append(("Synonyms (across varieties)", synonyms))
    return out


_JD_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
_RE_JD_META = re.compile(r"([ぁ-ゖァ-ヺー]+)\s*-\s*([A-Za-z\- ]+)\s*-\s")
_JD_BASE_URL = "https://www.japandict.com/"


def _audio_link(mp3: bytes, label: str, uid: str) -> str:
    b64 = base64.b64encode(mp3).decode("utf-8")
    return (f'<audio id="{uid}" preload="auto" style="display:none">'
            f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
            f'<a href="#" onclick="document.getElementById(\'{uid}\').play();'
            f'return false;" style="text-decoration:none">{_html.escape(label)}</a>')


# ---------------------------------------------------------------- JapanDict ---
def ja_romaji_and_kana(kanji_text: str, *, to_shinjitai):
    """Prefer JapanDict (kana + romaji) via meta description; fall back to
    fugashi (kana) + pykakasi (romaji)."""
    if not kanji_text:
        return "", ""
    jp_text = to_shinjitai(kanji_text)
    try:
        url = _JD_BASE_URL + urllib.parse.quote(jp_text)
        r = requests.get(url, headers=_JD_HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            m = _RE_JD_META.search(meta.get("content", ""))
            if m:
                kana, romaji = m.group(1).strip(), m.group(2).strip()
                kana = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c
                               for c in kana)
                return romaji, kana
    except Exception:
        pass
    kana = ""
    try:
        from fugashi import Tagger
        kana = "".join((w.feature.kana or w.surface) for w in Tagger()(jp_text))
        kana = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in kana)
    except Exception:
        kana = ""
    romaji = ""
    if kana:
        try:
            import pykakasi
            romaji = "".join(x["hepburn"] for x in pykakasi.kakasi().convert(kana))
        except Exception:
            romaji = ""
    return romaji.strip(), kana.strip()


def _fetch_japandict_page(session, query, lang="eng", page=1):
    url = (f"{_JD_BASE_URL}?s={quote_plus(query)}&lang={lang}" if page <= 1
           else f"{_JD_BASE_URL}?s={quote_plus(query)}&page={page}&lang={lang}")
    r = session.get(url, headers=_JD_HEADERS, timeout=12)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a.list-group-item.list-group-item-action"):
        hw = a.select_one("span.xlarge.text-normal")
        rd = a.select_one("i.text-muted.xsmall")
        out.append({
            "href": a.get("href"),
            "headword": hw.get_text(strip=True) if hw else None,
            "reading": rd.get_text(strip=True) if rd else None,
            "meanings": [m.get_text(strip=True)
                         for m in a.select("ul.list-unstyled li")],
        })
    return out


def fetch_japandict_from_english(eng: str, max_pages: int = 50):
    query = (eng or "").strip()
    if not query:
        return [], None
    first = f"{_JD_BASE_URL}?s={quote_plus(query)}&lang=eng"
    results, seen = [], set()
    with requests.Session() as s:
        for page in range(1, max_pages + 1):
            page_res = _fetch_japandict_page(s, query, "eng", page)
            if not page_res:
                break
            new_any = False
            for e in page_res:
                if e["href"] not in seen:
                    seen.add(e["href"]); results.append(e); new_any = True
            if not new_any:
                break
    return results, first


def render_japandict_html(entries, source_url=None, *, tts, voice_ja,
                          romaji_to_hiragana, kana_hira_to_kata):
    if not entries:
        body = "<i style='color:#888'>No JapanDict entries parsed.</i>"
        if source_url:
            body += f'<br><a href="{source_url}" target="_blank">More on JapanDict</a>'
        return body
    rows, uid = [], 0
    for e in entries:
        jp = (e.get("headword") or "") if isinstance(e, dict) else (e[0] if e else "")
        reading = (e.get("reading") or "") if isinstance(e, dict) else ""
        meanings = e.get("meanings") if isinstance(e, dict) else (e[1] if len(e) > 1 else "")
        meaning_text = "; ".join(map(str, meanings)) if isinstance(meanings, (list, tuple)) else str(meanings)
        jp_cell = _html.escape(jp)
        tts_text = jp
        if reading.strip():
            hira = romaji_to_hiragana(reading)
            if hira:
                tts_text = kana_hira_to_kata(hira)
        if tts_text.strip():
            try:
                uid += 1
                jp_cell = _audio_link(tts(tts_text, *voice_ja), jp, f"ja_d_{uid}")
            except Exception:
                jp_cell = _html.escape(jp)
        rows.append(f"<tr><td>{jp_cell}</td><td>{_html.escape(reading)}</td>"
                    f"<td>{_html.escape(meaning_text)}</td></tr>")
    html = ("<table style='width:100%;font-size:90%;border-collapse:collapse'>"
            "<tr><th>Japanese</th><th>Reading</th><th>Meanings</th></tr>"
            + "".join(rows) + "</table>")
    if source_url:
        html += f'<br><a href="{source_url}" target="_blank">More on JapanDict</a>'
    return html


# ------------------------------------------------------------ koreanhanja ---
def fetch_hanja_rows_from_hanzi(hanzi: str):
    hanzi = (hanzi or "").strip()
    if not hanzi:
        return []
    r = requests.get(f"https://koreanhanja.app/{quote_plus(hanzi)}", timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) >= 3:
            rows.append((tds[0].get_text(" ", strip=True),
                         tds[1].get_text(" ", strip=True),
                         tds[2].get_text(" ", strip=True)))
        elif len(tds) >= 2:
            rows.append((tds[0].get_text(" ", strip=True), "",
                         tds[1].get_text(" ", strip=True)))
    return rows


def fetch_hanja_rows_from_english(eng: str):
    eng = (eng or "").strip()
    if not eng:
        return [], None
    url = f"https://koreanhanja.app/{quote_plus(eng)}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) >= 3:
            rows.append((tds[0].get_text(" ", strip=True),
                         tds[1].get_text(" ", strip=True),
                         tds[2].get_text(" ", strip=True)))
    q = eng.lower()
    return [r for r in rows if q in (r[2] or "").lower()], url


def render_koreanhanja_html(rows, source_url=None, *, tts, voice_ko):
    if not rows:
        out = "<i style='color:#888'>No Korean hanja results.</i>"
        if source_url:
            out += f'<br><a href="{source_url}" target="_blank">koreanhanja.app</a>'
        return out
    body, uid = [], 0
    for h, hg, m in rows:
        hg = hg or ""
        cell = ""
        if hg.strip():
            try:
                uid += 1
                cell = _audio_link(tts(hg, *voice_ko), hg, f"ko_{uid}")
            except Exception:
                cell = _html.escape(hg)
        body.append(f"<tr><td>{_html.escape(h or '')}</td><td>{cell}</td>"
                    f"<td>{_html.escape(m or '')}</td></tr>")
    html = ("<table style='width:100%;font-size:90%;border-collapse:collapse'>"
            "<tr><th>Hanja</th><th>Hangul</th><th>Meaning</th></tr>"
            + "".join(body) + "</table>")
    if source_url:
        html += f'<br><a href="{source_url}" target="_blank">koreanhanja.app</a>'
    return html


# -------------------------------------------------------------------- Nôm ---
def _nom_url(text: str) -> str:
    return ("https://www.nomfoundation.org/nom-tools/Nom-Lookup-Tool/Nom-Lookup-Tool"
            f"?input_type=rqn_or_hn&inputText={quote_plus(text)}&uiLang=en&GO=GO")


def fetch_nom_df_from_hanzi(hanzi: str):
    hanzi = (hanzi or "").strip()
    if not hanzi:
        return None, None
    url = _nom_url(hanzi)
    resp = requests.get(url, timeout=12)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    dfs = []
    for table in soup.find_all("table"):
        try:
            dfs.append(pd.read_html(StringIO(str(table)))[0])
        except Exception:
            pass
    df = next((d for d in dfs if any(
        c in ("Quốc Ngữ", "Quốc ngữ", "Quốc Ngữ") for c in d.columns)), None)
    return df, url


def fetch_nom_dict_table_from_vi_or_en(text: str):
    text = (text or "").strip()
    if not text:
        return None, None
    url = _nom_url(text)
    resp = requests.get(url, timeout=12)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    for table in soup.find_all("table"):
        try:
            df = pd.read_html(StringIO(str(table)))[0]
        except Exception:
            continue
        cols = [str(c) for c in df.columns]
        if (any("Quốc Ngữ" in c or "Quốc Ngữ" in c for c in cols)
                and any("Hán" in c for c in cols)
                and any("English" in c for c in cols)):
            return df, url
    return None, url


def render_nom_html(df, *, tts, voice_vi):
    if df is None or getattr(df, "empty", True):
        return "<i style='color:#888'>No Nôm dictionary results.</i>"
    qn_col = next((c for c in df.columns
                   if str(c) in ("Quốc Ngữ", "Quốc ngữ", "Quốc Ngữ")), None)
    rows, uid = [], 0
    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = str(row[col]) if pd.notna(row[col]) else ""
            if qn_col is not None and col == qn_col and val.strip():
                uid += 1
                try:
                    cells.append(f"<td>{_audio_link(tts(val, *voice_vi), val, f'vi_{uid}')}</td>")
                except Exception:
                    cells.append(f"<td>{_html.escape(val)}</td>")
            else:
                cells.append(f"<td>{_html.escape(val)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    thead = "<tr>" + "".join(f"<th>{_html.escape(str(c))}</th>" for c in df.columns) + "</tr>"
    return ("<table style='width:100%;font-size:90%;border-collapse:collapse'>"
            + thead + "".join(rows) + "</table>")
