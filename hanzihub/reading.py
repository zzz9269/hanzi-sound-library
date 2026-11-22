"""Passage-reading support for the 📖 Read page.

Word **segmentation** by deterministic bidirectional maximum matching over the
bundled CC-CEDICT lexicon (the same dictionary the reader glosses from, so known
compounds are always grouped), **sentence splitting** (for audio chunking and
tone sandhi), plus the compound-word gloss lookup, graded sample passages, and
URL import. Pure-stdlib + the bundled data — no jieba/ML, no network except the
optional URL import; nothing depends on the old ``atcre`` app or its DB.
"""

from __future__ import annotations

import gzip
import json
import re
import urllib.request
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

# CJK unified + ext-A + ext-B onward (matches appkit's hanzi test range).
_HANZI = re.compile(r"[㐀-鿿\U00020000-\U0002FFFF]")

def has_hanzi(tok: str) -> bool:
    return bool(_HANZI.search(tok or ""))


def _is_hanzi(ch: str) -> bool:
    return bool(_HANZI.match(ch))


# Longest CC-CEDICT entry we will group as a single word. Real compounds/idioms
# are ≤4 chars; a few names/terms run longer. 8 covers them without letting a
# greedy match swallow a whole clause.
_MAX_WORD = 8


@lru_cache(maxsize=1)
def _lexicon() -> frozenset:
    """Words segmentation may group on — the CC-CEDICT compound keys (both
    Traditional and Simplified). Built once from the gloss dict."""
    return frozenset(_cedict().keys())


def _match(text: str, forward: bool) -> list[str]:
    """One pass of maximum matching against the lexicon. Non-Hanzi runs
    (punctuation, spaces, latin, digits) become their own tokens."""
    lex = _lexicon()
    n = len(text)
    out: list[str] = []
    if forward:
        i = 0
        while i < n:
            if not _is_hanzi(text[i]):
                j = i + 1
                while j < n and not _is_hanzi(text[j]):
                    j += 1
                out.append(text[i:j]); i = j; continue
            tok = None
            for k in range(min(n, i + _MAX_WORD), i + 1, -1):   # longest first, len ≥ 2
                if text[i:k] in lex:
                    tok = text[i:k]; break
            out.append(tok or text[i]); i += len(tok) if tok else 1
    else:
        i = n
        while i > 0:
            if not _is_hanzi(text[i - 1]):
                j = i - 1
                while j > 0 and not _is_hanzi(text[j - 1]):
                    j -= 1
                out.append(text[j:i]); i = j; continue
            tok = None
            for k in range(max(0, i - _MAX_WORD), i - 1):       # longest first (smallest start)
                if text[k:i] in lex:
                    tok = text[k:i]; break
            out.append(tok or text[i - 1]); i -= len(tok) if tok else 1
        out.reverse()
    return out


def _singles(toks) -> int:
    return sum(1 for t in toks if len(t) == 1 and _is_hanzi(t))


def segment(text: str) -> list[str]:
    """Split a passage into word tokens by **bidirectional maximum matching** over
    the CC-CEDICT lexicon — the SAME dictionary the reader glosses from, so a known
    compound (飛機, 珍珠奶茶) is always grouped as one unit and can never fall back to
    its characters' individual senses. Fully deterministic (no statistical model),
    so there are no mis-segmentation surprises. Original glyphs are preserved — the
    lexicon carries both Traditional and Simplified forms, so either input matches
    directly; punctuation/whitespace return as their own tokens for tone-group
    breaks, and token concatenation always reconstructs the input exactly.

    Forward and backward matching are run independently; on disagreement the classic
    heuristic keeps the parse with fewer tokens, then fewer stray single characters,
    then (final tie) the backward parse — the combination that best resolves the
    greedy-matching ambiguities.
    """
    if not text:
        return []
    fwd = _match(text, True)
    bwd = _match(text, False)
    if fwd == bwd:
        return fwd
    return bwd if (len(bwd), _singles(bwd)) <= (len(fwd), _singles(fwd)) else fwd


_SENT_SPLIT = re.compile(r"([。！？!?；;…\n]+)")


def sentences(text: str) -> list[str]:
    """Break a passage into sentence-ish chunks (trailing punctuation kept with
    the sentence) for per-sentence audio and sandhi grouping. Chunks with no
    Hanzi are dropped."""
    parts = _SENT_SPLIT.split(text or "")
    out = []
    for i in range(0, len(parts), 2):
        seg = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
        if has_hanzi(seg):
            out.append(seg.strip())
    return out


# --------------------------------------------------------------- sources ----
_SAMPLES_JSON = Path(__file__).parent / "data" / "sample_passages.json"


_CEDICT_GZ = Path(__file__).parent / "data" / "cedict_words.json.gz"


@lru_cache(maxsize=1)
def _cedict() -> dict:
    """The bundled CC-CEDICT compound-word glosses (≥2 chars), keyed by both the
    Traditional and Simplified form. Loaded once, lazily (~183k entries)."""
    try:
        with gzip.open(_CEDICT_GZ, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def word_gloss(word: str) -> str:
    """English gloss for a multi-character word (e.g. 飛機 → 'airplane'), from
    CC-CEDICT — so the reader can show what a compound *means*, not just its
    characters' individual senses. '' for single chars or unknown words."""
    if not word or len(word) < 2:
        return ""
    return _cedict().get(word, "")


_POEMS_GZ = Path(__file__).parent / "data" / "poems.json.gz"


@lru_cache(maxsize=1)
def load_poems() -> list[dict]:
    """The bundled classical-poetry library for the 🎋 Poems page — 唐詩三百首,
    宋詞三百首, 詩經 and the 蒙學 primers, all in Traditional characters. Each
    record: ``{id, anthology, kind, title, author, note, lines}`` where ``lines``
    are the poem's lines/stanzas (join with newlines for a readable passage).
    Built once by ``python -m hanzihub.build_poems``; empty list if absent."""
    try:
        with gzip.open(_POEMS_GZ, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@lru_cache(maxsize=1)
def load_samples() -> list[dict]:
    """The bundled graded passages (absorbed from the old atcre app), easiest →
    hardest. Each: ``{title, text, difficulty, tags, source}``."""
    try:
        data = json.loads(_SAMPLES_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []
    return sorted(data, key=lambda p: p.get("difficulty", 0.5))


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping scripts/nav/etc. and breaking on blocks."""
    _SKIP = {"script", "style", "noscript", "header", "footer", "nav", "aside"}
    _BREAK = {"p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr"}

    def __init__(self):
        super().__init__()
        self.out, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        if tag in self._BREAK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)


def import_from_url(url: str, max_chars: int = 1200) -> dict:
    """Fetch a web page and pull its Chinese prose out — for the 📖 Read page's
    "import from URL". Returns ``{title, text, source}`` or ``{error: …}``. Keeps
    only Hanzi-bearing lines and trims to a whole sentence near ``max_chars``."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read().decode(charset, errors="replace")
    except Exception as e:
        return {"error": str(e)}

    p = _TextExtractor()
    p.feed(html)
    lines = [ln.strip() for ln in "".join(p.out).splitlines()]
    text = "\n".join(ln for ln in lines if has_hanzi(ln))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 20:
        return {"error": "No Chinese text found on this page."}
    if len(text) > max_chars:
        cut = text[:max_chars]
        stop = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"))
        text = cut[:stop + 1] if stop > max_chars // 3 else cut

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip()[:60] if m else url.rsplit("/", 1)[-1][:40]
    return {"title": title or "Imported", "text": text, "source": url}
