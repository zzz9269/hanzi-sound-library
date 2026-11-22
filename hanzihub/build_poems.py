"""Build the bundled classical-poetry library for the 🎋 Poems page.

Downloads a handful of curated anthologies from the ``chinese-poetry/chinese-poetry``
database (the standard, comprehensive source), normalises their several different
JSON shapes into one flat record list, converts everything to **Traditional**
characters (some source files ship Simplified), and writes a single gzipped
``data/poems.json.gz`` so the app works offline like the rest of the dataset.

Run once (or whenever you want to refresh):  ``python -m hanzihub.build_poems``
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_RAW = "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/"
_OUT = Path(__file__).parent / "data" / "poems.json.gz"


def _fetch(rel: str):
    url = _RAW + urllib.parse.quote(rel)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _s2t():
    """OpenCC Simplified→Traditional converter (phrase-aware). Identity fallback
    if OpenCC is missing so the build still produces a (Simplified) file."""
    try:
        import opencc
        conv = opencc.OpenCC("s2t")
        return conv.convert
    except Exception:
        print("  ! OpenCC unavailable — leaving text as-is (may stay Simplified)")
        return lambda s: s


def _pid(*parts: str) -> str:
    return hashlib.sha1("｜".join(parts).encode("utf-8")).hexdigest()[:12]


# The chinese-poetry database uses older/authoritative editions, so a few famous
# poems come out in a form that differs from the version taught in schools today.
# For a study app the familiar text matters more, so we override those by
# (title, author) with the modern taught text. Keep this list to poems whose
# taught text is unambiguous — a wrong "correction" is worse than a variant.
_OVERRIDES = {
    ("靜夜思", "李白"): [           # source has the 宋本 (牀前看月光…舉頭望山月)
        "床前明月光，疑是地上霜。",
        "舉頭望明月，低頭思故鄉。",
    ],
}


def build() -> list[dict]:
    t = _s2t()
    out: list[dict] = []

    def add(anthology, kind, title, author, lines, note=""):
        title = t(title or "").strip() or "（無題）"
        author = t(author or "").strip() or "佚名"
        override = _OVERRIDES.get((title, author))
        lines = override or [t(ln).strip() for ln in lines if ln and ln.strip()]
        if not lines:
            return
        out.append({
            "id": _pid(anthology, title, author),
            "anthology": anthology, "kind": kind,
            "title": title, "author": author,
            "note": t(note or "").strip(),
            "lines": list(lines),
        })

    # 唐詩三百首 — 366 poems, already Traditional. {author, paragraphs, tags, title}
    print("· 唐詩三百首 …")
    for p in _fetch("全唐诗/唐诗三百首.json"):
        add("唐詩三百首", "tang", p.get("title"), p.get("author"),
            p.get("paragraphs", []))

    # 宋詞三百首 — 280 ci, Simplified. {author, paragraphs, rhythmic, tags}
    print("· 宋詞三百首 …")
    for p in _fetch("宋词/宋词三百首.json"):
        add("宋詞三百首", "song", p.get("rhythmic"), p.get("author"),
            p.get("paragraphs", []), note=p.get("rhythmic", ""))

    # 詩經 — 305 poems, Simplified. {title, chapter, section, content:[stanzas]}
    print("· 詩經 …")
    for p in _fetch("诗经/shijing.json"):
        sec = "·".join(x for x in (p.get("chapter"), p.get("section")) if x)
        add("詩經", "shijing", p.get("title"), "", p.get("content", []), note=sec)

    # 蒙學 primers — each is one long work; several JSON shapes.
    print("· 蒙學 …")
    for rel in ("蒙学/sanzijing-traditional.json", "蒙学/qianziwen.json",
                "蒙学/baijiaxing.json"):
        w = _fetch(rel)
        add("蒙學", "mengxue", w.get("title"), w.get("author"),
            w.get("paragraphs", []))
    # 弟子規 nests paragraphs under content:[{chapter, paragraphs}]
    dz = _fetch("蒙学/dizigui.json")
    dz_lines = [ln for ch in dz.get("content", []) for ln in ch.get("paragraphs", [])]
    add("蒙學", "mengxue", dz.get("title"), dz.get("author"), dz_lines)

    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    poems = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(_OUT, "wt", encoding="utf-8") as f:
        json.dump(poems, f, ensure_ascii=False)
    by = {}
    for p in poems:
        by[p["anthology"]] = by.get(p["anthology"], 0) + 1
    print(f"\n✓ {len(poems)} poems → {_OUT}")
    for k, v in by.items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
