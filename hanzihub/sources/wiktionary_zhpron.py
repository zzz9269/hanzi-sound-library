"""Offline snapshot of Wiktionary ``{{zh-pron}}`` romanisations.

The Streamlit app fetches a character's zh-pron live on every lookup (pinyin,
Jyutping, Hokkien POJ, Teochew Peng'im, Hakka PFS, Wugniu, Fuzhou BUC …). The
static web app can't wait on that, so this module snapshots it once:

    python -m hanzihub.sources.wiktionary_zhpron          # common chars
    python -m hanzihub.sources.wiktionary_zhpron --all    # every dataset char

It batches 50 pages per MediaWiki ``query`` request (≈200 requests for the
~10k common characters), and writes ``data/raw/wiktionary/zhpron.json`` = ``{char: {column: romanisation}}``,
parsed with the exact helpers the live path uses (scrapers._clean_zhpron …).
Re-runs only fetch characters not yet in the snapshot.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile

import requests

from ..paths import RAW_DIR

OUT = RAW_DIR / "wiktionary" / "zhpron.json"
API = "https://en.wiktionary.org/w/api.php"
UA = ("hanzi-sound-library/1.0 (https://github.com/zzz9269/hanzi-sound-library; "
      "batch zh-pron snapshot)")
BATCH = 50


def parse_zhpron(wikitext: str) -> dict[str, str]:
    """``{column: romanisation}`` from a page's wikitext (same rules as the
    live ``scrapers.fetch_wiktionary_readings``)."""
    from ..scrapers import (_ZHPRON_COL, _clean_zhpron, _extract_template,
                            _parse_hakka, _split_top_pipes)
    tpl = _extract_template(wikitext or "", "zh-pron")
    if not tpl:
        return {}
    params = {}
    for part in _split_top_pipes(tpl[2:-2]):
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


def _fetch_batch(sess, titles):
    """``{title: wikitext}`` for up to 50 titles (missing pages omitted)."""
    params = {"action": "query", "prop": "revisions", "rvprop": "content",
              "rvslots": "main", "titles": "|".join(titles), "format": "json",
              "formatversion": "2"}
    for attempt in range(4):
        try:
            r = sess.get(API, params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", [])
            out = {}
            for p in pages:
                revs = p.get("revisions") or []
                if revs:
                    out[p["title"]] = revs[0].get("slots", {}).get("main", {}).get("content", "")
            return out
        except Exception as e:
            print(f"  batch failed ({e}); retrying", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    return {}


def common_chars() -> list[str]:
    """The 8,105 通用規範漢字 (Unihan kTGH) in frequency order, plus their
    traditional forms (the dataset is keyed by traditional characters)."""
    z = zipfile.ZipFile(RAW_DIR / "unihan" / "Unihan.zip")
    tgh = {}
    for line in z.open("Unihan_OtherMappings.txt"):
        line = line.decode("utf-8")
        if "\tkTGH\t" in line:
            cp, _, v = line.rstrip("\n").split("\t")
            tgh[chr(int(cp[2:], 16))] = int(v.split()[0].split(":")[1])
    chars = sorted(tgh, key=tgh.get)
    try:
        import opencc
        conv = opencc.OpenCC("s2t")
        extra = [conv.convert(c) for c in chars]
        chars += [c for c in extra if len(c) == 1]
    except Exception:
        pass
    return list(dict.fromkeys(chars))


def crawl(chars, out=OUT, pause=1.0) -> dict:
    snap = json.loads(out.read_text("utf-8")) if out.exists() else {}
    todo = [c for c in chars if c not in snap]
    print(f"[zhpron] {len(snap):,} cached, {len(todo):,} to fetch")
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        texts = _fetch_batch(sess, batch)
        for c in batch:
            # {} = checked, nothing there. Simplified pages that only say
            # {{zh-see|…}} are NOT followed: 叶 points at both 協 and 葉, and
            # the app already falls back simplified → traditional itself.
            snap[c] = parse_zhpron(texts.get(c, ""))
        if (i // BATCH) % 20 == 0:
            print(f"[zhpron] {i + len(batch):,}/{len(todo):,}", flush=True)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(snap, ensure_ascii=False), "utf-8")
        time.sleep(pause)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, sort_keys=True), "utf-8")
    n = sum(1 for v in snap.values() if v)
    print(f"[zhpron] wrote {out} — {n:,}/{len(snap):,} chars with zh-pron")
    return snap


def load() -> dict:
    try:
        return json.loads(OUT.read_text("utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--all", action="store_true",
                    help="every character in the built dataset, not just common ones")
    a = ap.parse_args()
    chars = common_chars()
    if a.all:
        import pandas as pd
        from ..paths import COMBINED_PARQUET
        chars += list(pd.read_parquet(COMBINED_PARQUET, columns=["char"])["char"])
    crawl(list(dict.fromkeys(c for c in chars if len(c) == 1)))
