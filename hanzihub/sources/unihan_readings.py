"""Compact Unihan extract for the web build: every standard Mandarin and
Cantonese reading of each character, plus the kTGH frequency ranks.

The combined dataset keeps one pinyin per character (kMandarin) and the rest
only as IPA, so polyphonic characters like 長 (cháng/zhǎng) or 行 (xíng/háng)
lost their other romanisations. Unihan lists them all. ``Unihan.zip`` is too
big to commit, so this writes two small JSON files that are committed and
read by ``build_web`` (which also runs in CI, where the zip is absent):

    data/raw/unihan/readings.json   {char: [[pinyin…], [jyutping…]]}
    data/raw/unihan/tgh.json        {char: rank in 通用規範漢字表}

Run: ``python -m hanzihub.sources.unihan_readings``
"""
from __future__ import annotations

import json
import re
import zipfile

from .. import paths

DIR = paths.RAW_DIR / "unihan"
ZIP = DIR / "Unihan.zip"
READINGS = DIR / "readings.json"
TGH = DIR / "tgh.json"

_FIELDS = {"kMandarin", "kXHC1983", "kTGHZ2013", "kHanyuPinyin", "kCantonese", "kTGH"}


def _readings_after_colon(val: str) -> list[str]:
    """'0436.020:háng 1285.050:xíng,xìng' -> ['háng', 'xíng', 'xìng']."""
    out = []
    for entry in val.split():
        if ":" in entry:
            out += [r for r in entry.split(":", 1)[1].split(",") if r]
    return out


def _dedupe(xs):
    return list(dict.fromkeys(xs))


def extract() -> tuple[dict, dict]:
    raw: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(ZIP) as z:
        for name in ("Unihan_Readings.txt", "Unihan_DictionaryLikeData.txt",
                     "Unihan_OtherMappings.txt"):
            if name not in z.namelist():
                continue
            for line in z.read(name).decode("utf-8").splitlines():
                if not line.startswith("U+"):
                    continue
                cp, field, val = line.split("\t", 2)
                if field in _FIELDS:
                    raw.setdefault(chr(int(cp[2:], 16)), {})[field] = val
    readings, tgh = {}, {}
    for ch, f in raw.items():
        # Mandarin: the main reading(s) first, then the modern dictionaries
        # (現代漢語詞典, 通用規範漢字字典); 漢語大字典's long tail of archaic
        # readings only when neither modern dictionary covers the character
        modern = _readings_after_colon(f.get("kTGHZ2013", "")) + _readings_after_colon(f.get("kXHC1983", ""))
        man = f.get("kMandarin", "").split() + modern
        if not modern:
            man += _readings_after_colon(f.get("kHanyuPinyin", ""))
        man = _dedupe(r.strip() for r in man if r.strip())
        can = _dedupe(f.get("kCantonese", "").split())
        if man or can:
            readings[ch] = [man, can]
        m = re.match(r"\d+:(\d+)", f.get("kTGH", ""))
        if m:
            tgh[ch] = int(m.group(1))
    return readings, tgh


def write():
    readings, tgh = extract()
    READINGS.write_text(json.dumps(readings, ensure_ascii=False, separators=(",", ":"),
                                   sort_keys=True), "utf-8")
    TGH.write_text(json.dumps(tgh, ensure_ascii=False, separators=(",", ":"), sort_keys=True), "utf-8")
    print(f"[unihan] {len(readings):,} chars with readings → {READINGS}")
    print(f"[unihan] {len(tgh):,} kTGH ranks → {TGH}")


def load() -> dict:
    try:
        return json.loads(READINGS.read_text("utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    write()
