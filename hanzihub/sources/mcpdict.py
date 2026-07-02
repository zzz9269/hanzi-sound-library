"""Loader for 漢字音典 / MCPDict dialect tables (github.com/osfans/MCPDict).

MCPDict ships ~2,800 per-dialect 字表 as TSVs under ``tools/tables/data/``.
Originally this pulled just the two points kaikki/Wiktionary lack — Haikou
(Hainanese) and Shexian (Hui) — and was expanded 2026-07 to enrich the
canonical-39 localities the old dial-pron module capped at ~1k characters
(Suzhou, Wenzhou, Pingyao, Tunxi, Xiangtan, Nanning) plus one new,
linguistically precious point: **Shuangfeng (Old Xiang)**, which preserves
the Middle Chinese voiced initials.

Each table's layout and — crucially — its **tone digit semantics** were vetted
individually (see ``_POINTS``): pitch-contour digits are converted to Chao
letters at load; tone-CLASS digits are mapped through verified citation-value
tables (Wikipedia dialect pages / the table's own ``#调值`` declaration), and
where no trustworthy value table exists (Tunxi) the class digit is kept
honestly rather than guessed.

Each point fills a ``dial:`` locality column; branch columns then gap-fill
from their representative locality in :mod:`hanzihub.merge`.
"""
from __future__ import annotations

import csv
import re
import urllib.parse

from . import is_single_han, record
from ..paths import RAW_DIR
from ..schema import SRC_MCPDICT

MCPDICT_DIR = RAW_DIR / "mcpdict"
_RAW_BASE = "https://raw.githubusercontent.com/osfans/MCPDict/master/tools/tables/data/"

# (local cache name, upstream filename, format, dial: column, locality, opts)
#
# Formats:
#   ipa     — 漢字 / 音標 columns (reading ready-made)
#   ife     — cid / character / initial / final / tone(contour digits)
#   cols    — arbitrary column layout via opts: char/ipa/onset/rime/tone
#             indices; tone is either contour digits (tone_is_contour) or a
#             class mapped through opts["tone_map"] (VERIFIED citation values,
#             sources cited per point)
#   tongyin — 同音字表: '#rime' section headers, rows = onset + '[class]字字…'
#             groups; an embedded '#调值' line maps class → contour; without
#             one, the class digit is kept (honest — like Haikou
#             pre-verification)
_POINTS = [
    ("haikou.tsv", "海口2025-12-23.tsv", "ipa", "dial:Min-Haikou", "Haikou", {}),
    ("shexian.tsv", "歙县岩寺YB_21J03.tsv", "ife", "dial:Hui-Shexian", "Shexian", {}),
    # --- 2026-07 expansion: canonical-39 points starved at ~1k chars ---
    # Suzhou tones per Wikipedia "Suzhou dialect" (阳上 merged into 阳去 231)
    ("suzhou.tsv", "苏州 (正心整合修改版）.tsv", "cols", "dial:Wu-Suzhou",
     "Suzhou", {"char": 1, "onset": 2, "rime": 3, "tone": 4,
                "tone_map": {"1": "44", "2": "223", "3": "52", "5": "412",
                             "6": "231", "7": "4", "8": "23"}}),
    # Wenzhou tones per Wikipedia "Wenzhounese" (tone column holds NAMES)
    ("wenzhou.tsv", "温州方言同音字表2.0.tsv", "cols", "dial:Wu-Wenzhou",
     "Wenzhou", {"char": 1, "onset": 4, "rime": 5, "tone": 6,
                 "tone_map": {"阴平": "33", "阳平": "31", "阴上": "35",
                              "阳上": "24", "阴去": "42", "阳去": "11",
                              "阴入": "323", "阳入": "212"}}),
    # Xiangtan: the table itself carries 調值 (contour) — used directly
    ("xiangtan.tsv", "湘潭20251106.tsv", "cols", "dial:Xiang-Xiangtan",
     "Xiangtan", {"char": 3, "ipa": 0, "tone": 1, "tone_is_contour": True}),
    # Nanning 白話: the IPA column embeds the contour ('∅ɐ22'); no tone col
    ("nanning.tsv", "南寧白話單字讀音表(總表).tsv", "cols",
     "dial:Cantonese-Nanning", "Nanning",
     {"char": 1, "ipa": 3, "inline_contour": True}),
    # Shuangfeng (Old Xiang, 甘棠 town) — NEW point; tones per Wikipedia
    # "Shuangfeng dialect" (city citation values; the town may differ slightly)
    ("shuangfeng.tsv", "双峰甘棠.tsv", "cols", "dial:Xiang-Shuangfeng",
     "Shuangfeng", {"char": 2, "ipa": 0, "tone": 1, "no_header": True,
                    "tone_map": {"1": "55", "2": "23", "3": "21",
                                 "5": "35", "6": "33"}}),
    # Pingyao 同音字表 — the file declares its own 調值 map ('#调值' line)
    ("pingyao.tsv", "平遥话同音字表20220527.tsv", "tongyin",
     "dial:Jin-Pingyao", "Pingyao", {}),
    # Tunxi 同音字表 — NO verified 調值 table exists (zh-wiki conflicts with
    # the file's own class inventory) → tone kept as an honest class digit
    ("tunxi.tsv", "屯溪.tsv", "tongyin", "dial:Hui-Tunxi", "Tunxi", {}),
]

# initial-aspiration digraphs → IPA; zero-initial markers → ""
_ASP = {"th": "tʰ", "ph": "pʰ", "kh": "kʰ", "tsh": "tsʰ", "tʃh": "tʃʰ",
        "tɕh": "tɕʰ", "tʂh": "tʂʰ", "ch": "tɕʰ"}
_ZERO = {"∅", "0", "Ø", "ø", "Ǿ", "ǿ", "", "-"}
_CHAO = {"1": "˩", "2": "˨", "3": "˧", "4": "˦", "5": "˥"}


def _chao(digits: str) -> str:
    """Contour digits → Chao letters ('' if any digit isn't a 1–5 level)."""
    if digits and all(d in _CHAO for d in digits):
        return "".join(_CHAO[d] for d in digits)
    return ""


def download(*, force: bool = False) -> None:
    """Fetch the needed TSVs into the cache (small; skips existing unless force)."""
    import requests
    MCPDICT_DIR.mkdir(parents=True, exist_ok=True)
    for cache_name, upstream, *_ in _POINTS:
        dest = MCPDICT_DIR / cache_name
        if dest.exists() and not force:
            continue
        url = _RAW_BASE + urllib.parse.quote(upstream)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        dest.write_text(r.text, encoding="utf-8")


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t"))


def _parse_ipa(rows):
    out = []
    for r in rows[1:]:
        if len(r) >= 2 and is_single_han(r[0].strip()) and r[1].strip():
            out.append((r[0].strip(), r[1].strip()))
    return out


def _parse_ife(rows):
    out = []
    for r in rows[1:]:
        if len(r) < 5 or not is_single_han(r[1].strip()):
            continue
        ini, fin, tone = r[2].strip(), r[3].strip(), r[4].strip()
        ini = _ASP.get(ini, ini)
        if ini in _ZERO:
            ini = ""
        chao = "".join(_CHAO.get(c, "") for c in tone)
        ipa = (ini + fin + chao).strip()
        if ipa:
            out.append((r[1].strip(), ipa))
    return out


_BRACE_NOTE = re.compile(r"[{（(][^{}（）()]*[}）)]")   # inline gloss annotations
_TONE_GROUP = re.compile(r"[［\[](\d+)[］\]]([^［\[]*)")  # [class]字字… (both bracket widths)
_INLINE_CONTOUR = re.compile(r"^(.*?)(\d+)$")


def _parse_cols(rows, opts):
    """Generic column-indexed table → (char, reading) pairs."""
    out = []
    start = 0 if opts.get("no_header") else 1
    tone_map = opts.get("tone_map", {})
    for r in rows[start:]:
        needed = [i for i in (opts.get("char"), opts.get("ipa"),
                              opts.get("onset"), opts.get("rime"),
                              opts.get("tone")) if i is not None]
        if not needed or len(r) <= max(needed):
            continue
        # segmental part
        if "ipa" in opts:
            seg = r[opts["ipa"]].strip()
        else:
            onset = r[opts["onset"]].strip()
            seg = ("" if onset in _ZERO else onset) + r[opts["rime"]].strip()
        if not seg:
            continue
        if seg[0] in _ZERO:
            seg = seg[1:]
        # tone
        tone = ""
        if opts.get("inline_contour"):
            m = _INLINE_CONTOUR.match(seg)
            if m and _chao(m.group(2)):
                seg, tone = m.group(1), _chao(m.group(2))
        elif "tone" in opts:
            raw = r[opts["tone"]].strip()
            if opts.get("tone_is_contour"):
                tone = _chao(raw)
            elif raw in tone_map:
                tone = _chao(tone_map[raw])
            elif raw:
                continue  # unmappable tone class → skip, never guess
        reading = seg + tone
        for ch in r[opts["char"]].strip():
            if is_single_han(ch):
                out.append((ch, reading))
    return out


def _parse_tongyin(rows, opts):
    """同音字表: '#rime' headers + rows of onset\\t'[class]字字…'. An embedded
    '#调值 ［1］22…' line maps classes to contours; otherwise the class digit
    itself is kept as the tone mark."""
    tone_map: dict[str, str] = dict(opts.get("tone_map", {}))
    out, rime = [], ""
    for r in rows:
        head = (r[0] if r else "").strip()
        body = (r[1] if len(r) > 1 else "").strip()
        if head.startswith("#"):
            token = head[1:].strip()
            if "调值" in token or "調值" in token:
                for cls, val in re.findall(r"[［\[](\d+)[］\]]\s*(\d+)", body or head):
                    tone_map[cls] = val
            elif token and "：" not in token and ":" not in token \
                    and "符号" not in token and "说明" not in token:
                rime = token
            continue
        if not rime or not body or head.startswith(("来源", "说明")):
            continue
        onset = "" if head in _ZERO else head
        for cls, chars in _TONE_GROUP.findall(body):
            tone = _chao(tone_map[cls]) if cls in tone_map else cls
            reading = onset + rime + tone
            for ch in _BRACE_NOTE.sub("", chars):
                if is_single_han(ch):
                    out.append((ch, reading))
    return out


_PARSERS = {"ipa": lambda rows, opts: _parse_ipa(rows),
            "ife": lambda rows, opts: _parse_ife(rows),
            "cols": _parse_cols,
            "tongyin": _parse_tongyin}


def load() -> list[dict]:
    """Return records for every configured point from the cached TSVs
    (``[]`` for any TSV not yet downloaded)."""
    records: list[dict] = []
    for cache_name, _upstream, fmt, column, locality, opts in _POINTS:
        path = MCPDICT_DIR / cache_name
        if not path.exists():
            continue
        pairs = _PARSERS[fmt](_rows(path), opts)
        seen: set[tuple[str, str]] = set()
        for char, reading in pairs:
            if (char, reading) in seen:
                continue
            seen.add((char, reading))
            records.append(record(char, column, reading, SRC_MCPDICT, locality=locality))
    return records


if __name__ == "__main__":
    download()
    recs = load()
    from collections import Counter
    by_col = Counter(r["column"] for r in recs)
    print(f"[mcpdict] {len(recs):,} records: {dict(by_col)}")
    print("  sample:", [(r["char"], r["reading"]) for r in recs[:4]])
