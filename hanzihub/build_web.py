"""Export the dataset as static JSON for the web app in ``web/``.

    python -m hanzihub.build_web            # → web/data/

The web app is a static PWA (GitHub Pages): no server, so everything the UI
shows per character is PRE-COMPUTED here with the same display logic the
Streamlit app uses at request time — Chao tone letters, ≈ English
approximations, Min sandhi hints, fanqie / MC-position breakdowns, the
mogher.com recording file for Teochew readings and the tâi-lô for ithuan.tw
Hokkien audio. The browser only fetches one small shard per lookup.

Layout of ``web/data/``::

    meta.json            columns, sections, labels, shard scheme, build info
    c/<hex>.json         {char: entry} for code points (cp >> 8) == hex
    p/<hex>.json         provenance rows {char: [[col, reading, source, conf]]}
    s/en/<a>.json        English word → [chars]          (first letter a–z)
    s/rd/<a>.json        reading key → [[char, colIdx]]   (first letter)
    s2t.json             simplified → traditional (single chars)
    poems.json, passages.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

from . import appkit as ak
from . import paths
from .sources import unihan_readings, wiktionary_zhpron

OUT = paths.ROOT / "web" / "data"

SINITIC = ["Mandarin", "Cantonese", "Hokkien", "Teochew", "Eastern Min (Fuzhou)",
           "Northern Min (Jian'ou)", "Hainanese (Haikou)", "Hakka", "Wu",
           "Hui (Shexian)", "Gan", "Xiang", "Jin"]
HIST = ["Old Chinese", "Old Chinese (Zhengzhang)", "Proto-Min", "Middle Chinese",
        "Middle Chinese (Baxter)", "Middle Chinese (position)", "Fanqie", "Tang"]
SINO = ["Japanese", "Japanese On", "Japanese Kun", "Okinawan", "Korean (Hangul)",
        "Korean (romanized)", "Vietnamese", "Zhuang"]

# label, native name, romanisation scheme shown under the label, audio kind
COLUMN_INFO = {
    "Mandarin": ("Mandarin", "普通話", "Pinyin", "tts:zh-CN"),
    "Cantonese": ("Cantonese", "粵語", "Jyutping", "tts:zh-HK"),
    "Hokkien": ("Hokkien", "閩南語", "Pe̍h-ōe-jī", "ithuan"),
    "Teochew": ("Teochew", "潮州話", "Peng'im", "mogher"),
    "Eastern Min (Fuzhou)": ("Fuzhou", "福州話", "Foochow Romanized", ""),
    "Northern Min (Jian'ou)": ("Jian'ou", "建甌話", "Kienning Colloquial", ""),
    "Hainanese (Haikou)": ("Hainanese", "海南話", "IPA · Haikou", ""),
    "Hakka": ("Hakka", "客家話", "Pha̍k-fa-sṳ", ""),
    "Wu": ("Wu", "吳語", "Wugniu · Shanghai", ""),
    "Hui (Shexian)": ("Hui", "徽語", "IPA · Shexian", ""),
    "Gan": ("Gan", "贛語", "Nanchang", ""),
    "Xiang": ("Xiang", "湘語", "Changsha", ""),
    "Jin": ("Jin", "晉語", "Taiyuan", ""),
    "Old Chinese": ("Old Chinese", "上古漢語", "Baxter–Sagart 2014", ""),
    "Old Chinese (Zhengzhang)": ("Old Chinese", "上古漢語", "Zhengzhang Shangfang", ""),
    "Proto-Min": ("Proto-Min", "原始閩語", "comparative reconstruction", ""),
    "Middle Chinese": ("Middle Chinese", "中古漢語", "Baxter transcription", ""),
    "Middle Chinese (Baxter)": ("Middle Chinese", "中古漢語", "IPA", ""),
    "Middle Chinese (position)": ("Rime position", "音韻地位", "initial · grade · rime · tone", ""),
    "Fanqie": ("Fanqie", "反切", "Guangyun spelling", ""),
    "Tang": ("Late Middle Chinese", "唐代", "Tang reading", ""),
    "Japanese": ("Japanese", "日本語", "kana", "tts:ja-JP"),
    "Japanese On": ("On'yomi", "音読み", "romaji", ""),
    "Japanese Kun": ("Kun'yomi", "訓読み", "romaji", ""),
    "Okinawan": ("Okinawan", "沖縄語", "kana", ""),
    "Korean (Hangul)": ("Korean", "한국어", "Hangul", "tts:ko-KR"),
    "Korean (romanized)": ("Korean", "한국어", "Yale", ""),
    "Vietnamese": ("Vietnamese", "Tiếng Việt", "Hán-Việt", "tts:vi-VN"),
    "Zhuang": ("Zhuang", "Vahcuengh", "Sawndip", ""),
}
# romanisation scheme for ≈ English / Chao conversion of Wiktionary readings
ROM_SCHEME = {**ak.ROM_SCHEME, "Cantonese": "jyutping"}
KEEP_NATIVE_TONES = {"Mandarin", "Cantonese"}      # pinyin / jyutping as written
TOKEN_SPLIT_COLS = {"Japanese", "Japanese On", "Japanese Kun", "Korean (Hangul)",
                    "Korean (romanized)", "Vietnamese"}
_HAN_NOTE = re.compile(r"\s*\([^)]*[㐀-鿿][^)]*\)")
_ALT_SPLIT = re.compile(r"\s*[|/]\s*")
_KANA = re.compile(r"[぀-ヿㇰ-ㇿ]")


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").replace("≈", "").strip()


# --- Hokkien POJ → Tâi-lô (the spelling ithuan.tw's synthesiser reads) -----
def poj_to_tailo(s: str) -> str:
    t = unicodedata.normalize("NFC", s or "")
    t = t.replace("ⁿ", "nn").replace("o͘", "oo").replace("O͘", "Oo")
    t = re.sub(r"chh", "tsh", t)
    t = re.sub(r"ch", "ts", t)
    nfd = unicodedata.normalize("NFD", t)
    base = "".join(c for c in nfd if not unicodedata.combining(c))
    # vowel-sequence and coda respellings, done on the mark-free base then
    # the tone mark is re-applied to the same vowel letter
    marks = [(i, c) for i, c in enumerate(nfd) if unicodedata.combining(c)]
    if marks:
        # index of the base letter each mark sits on
        pos, bi = [], -1
        for c in nfd:
            if unicodedata.combining(c):
                pos.append(bi)
            else:
                bi += 1
        mark_at = {p: m for p, (_, m) in zip(pos, marks)}
    else:
        mark_at = {}
    letters = list(base)
    swaps = [("oa", "ua"), ("oe", "ue"), ("eng", "ing"), ("ek", "ik")]
    joined = "".join(letters)
    for a, b in swaps:
        joined = joined.replace(a, b)
    out = []
    for i, ch in enumerate(joined):
        out.append(ch + (mark_at.get(i, "")))
    return unicodedata.normalize("NFC", "".join(out))


_YUE_INITIALS = [("t͡sʰ", "c"), ("t͡s", "z"), ("kʷʰ", "kw"), ("kʷ", "gw"), ("pʰ", "p"),
                 ("tʰ", "t"), ("kʰ", "k"), ("p", "b"), ("t", "d"), ("k", "g"), ("ŋ", "ng"),
                 ("m", "m"), ("n", "n"), ("l", "l"), ("f", "f"), ("h", "h"), ("s", "s"),
                 ("j", "j"), ("w", "w")]
_YUE_RHYME = [("aː", "aa"), ("ɛː", "e"), ("iː", "i"), ("ɔː", "o"), ("uː", "u"), ("œː", "oe"),
              ("yː", "yu"), ("ɐ", "a"), ("ɪ", "i"), ("ʊ", "u"), ("ɵ", "eo"), ("i̯", "i"),
              ("u̯", "u"), ("y̯", "i"), ("ŋ", "ng")]
_YUE_TONE = {"˥": 1, "˥˥": 1, "˥˧": 1, "˧˥": 2, "˧": 3, "˧˧": 3, "˨˩": 4, "˩": 4, "˩˩": 4,
             "˩˧": 5, "˨˧": 5, "˨": 6, "˨˨": 6}


def yue_ipa_to_jyutping(ipa: str) -> str:
    """Guangzhou IPA syllable ('hɔːŋ˨˩', 't͡sʰœːŋ˧˥') -> Jyutping ('hong4',
    'coeng2'); "" when it isn't a clean single syllable."""
    m = re.fullmatch(r"([^˥˦˧˨˩]+)([˥˦˧˨˩]+)", (ipa or "").strip().replace("̚", ""))
    if not m or m.group(2) not in _YUE_TONE:
        return ""
    seg, tone = m.group(1), _YUE_TONE[m.group(2)]
    if seg in ("ŋ̩", "m̩"):
        return ("ng" if seg == "ŋ̩" else "m") + str(tone)
    ini = ""
    for a, b in _YUE_INITIALS:
        if seg.startswith(a) and len(seg) > len(a):
            ini, seg = b, seg[len(a):]
            break
    for a, b in _YUE_RHYME:
        seg = seg.replace(a, b)
    if not re.fullmatch(r"(aa|a|e|i|o|u|oe|eo|yu)(i|u)?(m|n|ng|p|t|k)?", seg):
        return ""
    if seg[-1] in "ptk" and tone not in (1, 3, 6):
        return ""
    return f"{ini}{seg}{tone}"


def _audio_key(col: str, rom: str) -> str:
    if col == "Teochew" and re.fullmatch(r"[a-zê]+\d", rom):
        f = ak.pengim_to_mogher_file(rom)
        return f"m:{f}" if f else ""
    if col == "Hokkien" and rom and not ak.has_ipa(rom):
        return "h:" + poj_to_tailo(rom)
    return ""


def _reading(t, e="", ml=False, a=""):
    r = {"t": t}
    if e:
        r["e"] = e
    if ml:
        r["m"] = 1
    if a:
        r["a"] = a
    return r


def _ipa_en(col, alt):
    if col == "Old Chinese":
        return ak.baxter_sagart_approx(alt)
    if col in ak.IPA_APPROX_COLS or col.startswith("dial:") or ak.has_ipa(alt):
        return ak.ipa_to_english(ak.tones_to_chao(alt, None if col.startswith("dial:") else col))
    return ""


def _alts(val):
    return [a.strip() for a in _ALT_SPLIT.split((val or "").strip()) if a.strip()]


MAX_ROMS = 6


def build_entry(ch, bucket, zh, meta, rank, data, colidx, prov_conf, uh=None):
    e = {}
    if bucket.get("Definition"):
        e["d"] = bucket["Definition"]
    m = meta.get(ch, {})
    k = [m.get("strokes") or 0, m.get("radical") or 0, rank or 0]
    if any(k):
        e["k"] = k
    v, ipa, notes, hint, wik = {}, {}, {}, {}, {}
    for col in SINITIC:
        val, rom_w = bucket.get(col, ""), (zh or {}).get(col, "")
        roms, ipas, ipa_raw = [], [], []
        for alt in _alts(val):
            ml = alt.endswith("[ML]")
            a = _HAN_NOTE.sub("", alt.removesuffix("[ML]")).strip()
            if not a:
                continue
            if ak.has_ipa(a):
                ipas.append(_reading(ak.tones_to_chao(a, col), _ipa_en(col, a), ml))
                ipa_raw.append((a, ml))
            else:
                roms.append((a, ml))
        scheme = ROM_SCHEME.get(col)
        if rom_w:
            roms = [(r.strip(), False) for r in rom_w.split(" / ") if r.strip()]
            wik[colidx[col]] = 1
        # every reading, not just the main one: the dataset keeps a single
        # pinyin/jyutping per character (長 had zhǎng but not cháng)
        extra = []
        if col == "Mandarin" and uh:
            extra = [(r, False) for r in uh[0]]
        elif col == "Cantonese":
            extra = [(yue_ipa_to_jyutping(a), ml) for a, ml in ipa_raw]
            extra += [(r, False) for r in (uh[1] if uh else [])]
        have = {r for r, _ in roms}
        for r, ml in extra:
            if r and r not in have and len(roms) < MAX_ROMS:
                roms.append((r, ml))
                have.add(r)
        if col == "Mandarin" and uh and uh[0] and uh[0][0] in have:
            # kMandarin is Unihan's "most customary" reading: lead with it
            # (Wiktionary lists 的 as dì, dí, de, dī)
            roms.sort(key=lambda x: x[0] != uh[0][0])
        out = []
        for r, ml in roms:
            disp = r if col in KEEP_NATIVE_TONES else ak.wikt_rom_to_chao(r, scheme)
            if col == "Teochew" and disp == r:
                disp = ak.tones_to_chao(r, col)
            en = ak.romanization_to_english(r, scheme) if scheme else ""
            out.append(_reading(disp, en, ml, _audio_key(col, r)))
        out = list({r["t"]: r for r in out}.values())
        ipas = list({r["t"]: r for r in ipas}.values())
        if out:
            v[colidx[col]] = out
        if ipas:
            ipa[colidx[col]] = ipas
        if roms and scheme in ("poj", "teochew"):
            h = _strip_tags(ak.sandhi_hint_html(roms[0][0], scheme))
            if h:
                hint[colidx[col]] = h.replace("sandhi", "").replace("non-final", "").strip()
    for col in HIST + SINO + ["Definition"]:
        if col == "Definition" or not bucket.get(col):
            continue
        val = bucket[col]
        if col in TOKEN_SPLIT_COLS:
            alts = ak.split_opts(val)
        elif col in ("Middle Chinese (position)", "Fanqie"):
            alts = _alts(val) if col != "Fanqie" else ak.split_opts(val)
        else:
            alts = _alts(val)
        out = []
        for alt in alts:
            ml = alt.endswith("[ML]")
            a = alt.removesuffix("[ML]").strip()
            if col in ("Japanese On", "Japanese Kun", "Korean (romanized)"):
                a = a.lower()
            disp = ak.tones_to_chao(a, col)
            en = _ipa_en(col, a) if col not in SINO else ""
            out.append(_reading(disp, en, ml))
        out = list({r["t"]: r for r in out}.values())
        if out:
            v[colidx[col]] = out
        if col == "Fanqie":
            lines = []
            target_mc = bucket.get("Middle Chinese", "")
            for pair in ak.parse_fanqie_pairs(val)[:3]:
                info = ak.fanqie_explain(pair, data.get(pair[0], {}).get("Middle Chinese", ""),
                                         data.get(pair[1], {}).get("Middle Chinese", ""),
                                         target_mc)
                if info:
                    lines.append({"u": info["upper"], "l": info["lower"],
                                  "i": info["initial"], "f": info["final"],
                                  "tone": info["tone"], "c": info["composed"],
                                  "ok": 1 if info["matches"] else 0})
            if lines:
                notes[colidx[col]] = lines
        if col == "Middle Chinese (position)":
            codes = _alts(val)
            mc_ipas = _alts(bucket.get("Middle Chinese (Baxter)", ""))
            lines = []
            for i, code in enumerate(codes):
                mc_ipa = (mc_ipas[i] if len(mc_ipas) == len(codes)
                          else mc_ipas[0] if len(mc_ipas) == 1 else "")
                parts = ak.mc_position_breakdown(code, mc_ipa)
                if parts:
                    lines.append({"code": code, "syl": ak.mc_readable_syllable(code, mc_ipa),
                                  "parts": [[g, x] for g, x in parts]})
            if lines:
                notes[colidx[col]] = lines
    if ch in prov_conf:
        notes[colidx["Proto-Min"]] = [{"conf": round(prov_conf[ch], 2)}]
    loc = {}
    for col, val in bucket.items():
        if col.startswith("dial:") and val:
            loc[colidx[col]] = [_reading(ak.tones_to_chao(a), ak.ipa_to_english(ak.tones_to_chao(a)))
                                for a in _alts(val)]
    for key, d in (("v", v), ("i", ipa), ("n", notes), ("h", hint), ("w", wik), ("l", loc)):
        if d:
            e[key] = d
    return e


_HAN_CHAR = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0003134f]")


def word_pinyin(entries: dict, man_idx: int) -> dict[str, dict[str, str]]:
    """Context readings for Mandarin: ``{first_char: {word: "cháng chéng"}}``
    for every CC-CEDICT word (traditional and simplified) whose pinyin in
    pypinyin's phrase dictionary differs from its characters' default
    readings. 長城 is cháng chéng, not zhǎng chéng; 銀行 is yín háng. Only the
    differences are kept, so the reader can fall back to per-character
    readings everywhere else."""
    from pypinyin import Style, lazy_pinyin
    from pypinyin.constants import PHRASES_DICT

    from .reading import _cedict

    key = str(man_idx)

    def default(c):
        e = entries.get(c) or entries.get(ak.s2t_text(c)) or {}
        r = e.get("v", {}).get(man_idx) or e.get("v", {}).get(key)
        return r[0]["t"] if r else None

    out: dict[str, dict[str, str]] = defaultdict(dict)
    for w in _cedict():
        if not 2 <= len(w) <= 8 or not all(_HAN_CHAR.fullmatch(c) for c in w):
            continue
        s = ak.t2s_text(w)
        if len(s) != len(w) or s not in PHRASES_DICT:
            continue
        py = [unicodedata.normalize("NFC", p) for p in lazy_pinyin(s, style=Style.TONE)]
        if len(py) != len(w) or py == [default(c) for c in w]:
            continue
        out[w[0]][w] = " ".join(py)
    return out


_STOP = set("a an the of to in on and or for with by as at is be it its into from "
            "used also etc one two kind type sort name surname variant same character "
            "radical number kangxi".split())


def _en_words(defn):
    words = re.findall(r"[a-z][a-z'\-]+", (defn or "").lower())
    return [w.strip("'-") for w in words if w.strip("'-") not in _STOP and len(w) > 1]


def _fold(s):
    s = unicodedata.normalize("NFD", (s or "").replace("ⁿ", "n"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), "utf-8")


def build(out: Path = OUT, verbose=True):
    t0 = time.time()
    data, cols = ak.load_combined(str(paths.COMBINED_PARQUET.with_suffix(".csv")))
    meta = ak.char_meta()
    zh = wiktionary_zhpron.load()
    uh = unihan_readings.load()
    try:
        tgh = json.loads((paths.RAW_DIR / "unihan" / "tgh.json").read_text("utf-8"))
    except Exception:
        tgh = {}
    # Proto-Min nucleus confidence from provenance
    prov_rows = defaultdict(list)
    prov_conf = {}
    lp = paths.ROOT / "data" / "out" / "readings_long.parquet"
    if lp.exists():
        ldf = pd.read_parquet(lp, columns=["char", "column", "reading", "source", "conf"])
        for r in ldf.itertuples(index=False):
            if len(r.char) != 1:
                continue
            conf = None if r.conf is None or r.conf != r.conf else round(float(r.conf), 2)
            prov_rows[r.char].append([r.column, r.reading, r.source, conf])
            if r.column == "Proto-Min" and r.source == "recon" and conf is not None:
                prov_conf[r.char] = conf

    dial_cols = sorted([c for c in cols if c.startswith("dial:")],
                       key=lambda c: (c.split(":")[1].split("-")[0], c))
    all_cols = SINITIC + HIST + SINO + dial_cols
    colidx = {c: i for i, c in enumerate(all_cols)}
    columns = []
    for c in all_cols:
        if c.startswith("dial:"):
            m = re.match(r"^dial:([^-]+)-(.+)$", c)
            columns.append({"id": c, "label": m.group(2), "branch": m.group(1),
                            "section": "local"})
            continue
        label, native, scheme, audio = COLUMN_INFO.get(c, (c, "", "", ""))
        sec = "sinitic" if c in SINITIC else "hist" if c in HIST else "sino"
        columns.append({"id": c, "label": label, "native": native, "scheme": scheme,
                        "audio": audio, "section": sec})

    if out.exists():
        # delete files but keep the folders: OneDrive often refuses rmdir on
        # a synced folder (WinError 5) even when it is empty
        for f in out.rglob("*"):
            if f.is_file():
                f.unlink()
    shards = defaultdict(dict)
    pshards = defaultdict(dict)
    en_idx = defaultdict(dict)       # word -> {char: score}
    rd_idx = defaultdict(dict)       # key -> {char: colIdx}
    def rank_of(c):
        r = tgh.get(c)
        if r is None:
            s = ak.t2s_text(c)
            r = tgh.get(s) if len(s) == 1 else None
        return r or 99999
    for ch, bucket in data.items():
        entry = build_entry(ch, bucket, zh.get(ch), meta, rank_of(ch) if rank_of(ch) < 99999 else 0,
                            data, colidx, prov_conf, uh.get(ch))
        if not entry:
            continue
        key = f"{ord(ch) >> 8:x}"
        shards[key][ch] = entry
        if prov_rows.get(ch):
            pshards[key][ch] = prov_rows[ch]
        for pos, w in enumerate(_en_words(entry.get("d", ""))):
            s = rank_of(ch) + (0 if pos == 0 else 20000 + pos)
            if s < en_idx[w].get(ch, 10**9):
                en_idx[w][ch] = s
        for ci, reads in entry.get("v", {}).items():
            col = all_cols[ci]
            if col in ("Middle Chinese (position)", "Fanqie", "Old Chinese",
                       "Japanese", "Korean (Hangul)", "Okinawan"):
                continue
            for r in reads:
                for tok in re.split(r"[\s|/,;·()\[\]]+", r["t"]):
                    f = _fold(tok.strip("*"))
                    f = re.sub(r"[˥˦˧˨˩]+$", "", f)
                    if not re.fullmatch(r"[a-z][a-z0-9'\-]{0,11}", f):
                        continue
                    for k in sorted({f, f.rstrip("0123456789")}):  # sorted: stable across hash seeds
                        if len(k) > 1:
                            rd_idx[k].setdefault(ch, ci)
    # word-level Mandarin readings, stored on each word's first character
    # (simplified-only characters get a stub entry holding just their words)
    all_entries = {c: e for d in shards.values() for c, e in d.items()}
    n_words = 0
    for first, words in word_pinyin(all_entries, colidx["Mandarin"]).items():
        key = f"{ord(first) >> 8:x}"
        shards[key].setdefault(first, {})["x"] = dict(sorted(words.items()))
        n_words += len(words)
    if verbose:
        print(f"[web] {n_words:,} word readings (Mandarin, in context)")
    for key, d in shards.items():
        _dump(out / "c" / f"{key}.json", d)
    for key, d in pshards.items():
        _dump(out / "p" / f"{key}.json", d)
    by_letter = defaultdict(dict)
    for w, chs in en_idx.items():
        by_letter[w[0]][w] = [c for c, _ in sorted(chs.items(), key=lambda x: x[1])[:60]]
    for letter, d in by_letter.items():
        _dump(out / "s" / "en" / f"{letter}.json", d)
    by_letter = defaultdict(dict)
    for k, chs in rd_idx.items():
        if not k or not k[0].isalpha():
            continue
        # Mandarin matches first, then Cantonese, Hokkien… (column order),
        # most common characters first within each
        top = sorted(chs.items(), key=lambda x: (x[1], rank_of(x[0])))[:80]
        by_letter[k[0]][k] = [[c, ci] for c, ci in top]
    for letter, d in by_letter.items():
        _dump(out / "s" / "rd" / f"{letter}.json", d)
    s2t = {}
    for ch in sorted(set(data) | set(tgh)):
        t = ak.s2t_text(ch)
        if t != ch and len(t) == 1 and t in data:
            s2t[ch] = t
    _dump(out / "s2t.json", s2t)
    # poems + sample passages (already bundled with the package)
    pz = paths.ROOT / "hanzihub" / "data" / "poems.json.gz"
    if pz.exists():
        _dump(out / "poems.json", json.loads(gzip.decompress(pz.read_bytes())))
    sp = paths.ROOT / "hanzihub" / "data" / "sample_passages.json"
    if sp.exists():
        _dump(out / "passages.json", json.loads(sp.read_text("utf-8")))
    common = sorted(tgh, key=tgh.get)[:3500]
    # content hash: the app appends ?v=<hash> to every data request, so the
    # service worker never serves a shard from one build with meta from another
    h = hashlib.sha1()
    offline = []                                  # files "Use offline" downloads
    size = 0
    for f in sorted(out.rglob("*.json")):
        b = f.read_bytes()
        h.update(f.relative_to(out).as_posix().encode() + b)
        rel = f.relative_to(out).as_posix()
        if not rel.startswith("p/"):
            offline.append(rel)
            size += len(b)
    columns_json = json.dumps(columns, ensure_ascii=False, sort_keys=True).encode()
    h.update(columns_json)
    _dump(out / "meta.json", {
        "built": time.strftime("%Y-%m-%d"), "v": h.hexdigest()[:10], "chars": len(data),
        "columns": columns, "shardShift": 8, "common": "".join(common),
        "offline": offline, "offlineBytes": size,
    })
    if verbose:
        size = sum(f.stat().st_size for f in out.rglob("*.json"))
        print(f"[web] {len(data):,} chars → {len(shards)} shards, "
              f"{size / 1e6:.1f} MB raw JSON in {time.time() - t0:.0f}s → {out}")


if __name__ == "__main__":
    build()
