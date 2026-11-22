"""Loader for 漢字音典 / MCPDict dialect tables (github.com/osfans/MCPDict).

MCPDict aggregates ~3,400 per-locality 字表, most transcribed from the
standard published references (《漢語方音字彙》-era 音檔 series: 《太原话音档》,
《南昌方言同音字汇》, 《建瓯话音档》, 《福州方言志》, 《厦门方言同音字汇》 …).

Two kinds of table are used:

* **Normalised output tables** (``tools/tables/output/<簡稱>.tsv``) — MCPDict's
  own uniform rendering: ``字 \\t IPA+tone-class[tag] \\t 註``. The class digit
  is mapped to that table's citation contour using the ``聲調`` block of
  MCPDict's ``_詳情.json`` metadata (from the same reference as the data), then
  rendered as Chao letters. ``tag`` is MCPDict's reading-type marker
  (``-`` 白 ``=`` 文 ``+`` 又 ``*`` 俗 ``@`` 訓 ``?`` 存疑); 存疑 readings are dropped.
  This is now the default for every point — one parser, stable filenames.
* **Hand-vetted raw tables** (``tools/tables/data/…``) kept where the raw file
  is richer than MCPDict's chosen output (Suzhou, Wenzhou, Xiangtan, Nanning,
  Shuangfeng-甘棠, Pingyao, Shexian-岩寺); each has its own vetted parser.

Points whose locality column is already populated by kaikki / Wiktionary are
loaded as **gap-fill** (``fallback=True``): merge keeps them only for
characters that have no reading there yet, so one cell never mixes two
transcriptions of the same place.

Also loaded here, from MCPDict's Sino-Xenic and historical tables:
  * 越南 — Hán-Việt readings (Telex → Quốc Ngữ, :mod:`hanzihub.sinoxenic`);
  * 朝鮮 — Naver Hanja dictionary readings (RR → Hangul + Yale), gap-fill;
  * 廣韻 — Baxter's MC transcription (nk2028 derivation), gap-fill for the
    ``Middle Chinese`` column (97.7% agreement with Baxter–Sagart 2014 on
    the 3.9k shared characters).

All URLs are pinned to one upstream commit so a fresh clone rebuilds the exact
same dataset.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.parse

from . import is_single_han, record
from .. import sinoxenic
from ..paths import RAW_DIR
from ..schema import SRC_MCPDICT

MCPDICT_DIR = RAW_DIR / "mcpdict"
OUT_DIR = MCPDICT_DIR / "output"
TONES_JSON = MCPDICT_DIR / "tones.json"

# Pinned upstream commit (bump deliberately, then rebuild + re-run the tests).
MCPDICT_SHA = "0322cfe7b609d9024ea4cbd72193a4c648734a02"
_RAW = f"https://raw.githubusercontent.com/osfans/MCPDict/{MCPDICT_SHA}/tools/tables/"
_RAW_BASE = _RAW + "data/"
_RAW_OUT = _RAW + "output/"

# ---------------------------------------------------------------------------
# Normalised output tables: (簡稱, dial: column, locality, fallback)
# ---------------------------------------------------------------------------
_OUT_POINTS: list[tuple[str, str, str, bool]] = [
    # --- primary: MCPDict is (or replaces) this column's main source ---
    ("海口", "dial:Min-Haikou", "Haikou", False),       # 《海口话音档》
    ("歙縣", "dial:Hui-Shexian", "Shexian", False),     # 《歙县话音档》 (徽城)
    ("屯溪", "dial:Hui-Tunxi", "Tunxi", False),         # 《屯溪话音档》
    ("績溪", "dial:Hui-Jixi", "Jixi", False),           # 《徽州方言研究》
    ("潮州", "dial:Min-Chaozhou", "Chaozhou", False),   # Chaozhou city
    # --- gap-fill: the canonical branch representatives ---
    ("太原", "dial:Jin-Taiyuan", "Taiyuan", True),      # 《太原话音档》
    ("南昌", "dial:Gan-Nanchang", "Nanchang", True),    # 《南昌方言同音字汇》
    ("長沙", "dial:Xiang-Changsha", "Changsha", True),  # 《长沙方言研究》
    ("建甌", "dial:Min-Jian'ou", "Jian'ou", True),      # 《建瓯话音档》
    ("福州", "dial:Min-Fuzhou", "Fuzhou", True),        # 《福州方言志》
    ("梅縣", "dial:Hakka-Meixian", "Meixian", True),    # 《梅县话音档》
    ("厦門", "dial:Min-Xiamen", "Xiamen", True),        # 《厦门方言同音字汇》
    ("汕頭", "dial:Min-Shantou", "Shantou", True),
    ("上海", "dial:Wu-Shanghai", "Shanghai", True),     # 《上海市区方言志》
    # --- gap-fill: further locality points ---
    ("臺北", "dial:Min-Taipei", "Taipei", True),
    ("泉州", "dial:Min-Quanzhou", "Quanzhou", True),
    ("漳州", "dial:Min-Zhangzhou", "Zhangzhou", True),
    ("莆田", "dial:Min-Putian", "Putian", True),
    ("雷州", "dial:Min-Leizhou", "Leizhou", True),
    ("臺灣四縣腔", "dial:Hakka-Sixian", "Sixian", True),
    ("臺灣海陸腔", "dial:Hakka-Hailu", "Hailu", True),
    ("長汀", "dial:Hakka-Changting", "Changting", True),
    ("杭州", "dial:Wu-Hangzhou", "Hangzhou", True),
    ("寧波", "dial:Wu-Ningbo", "Ningbo", True),
    ("金華", "dial:Wu-Jinhua", "Jinhua", True),
    ("台山", "dial:Cantonese-Taishan", "Taishan", True),
    ("東莞", "dial:Cantonese-Dongguan", "Dongguan", True),
    ("哈爾濱", "dial:Mandarin-Harbin", "Harbin", True),
    ("天津", "dial:Mandarin-Tianjin", "Tianjin", True),
    ("濟南", "dial:Mandarin-Jinan", "Jinan", True),
    ("青島", "dial:Mandarin-Qingdao", "Qingdao", True),
    ("鄭州", "dial:Mandarin-Zhengzhou", "Zhengzhou", True),
    ("西安", "dial:Mandarin-Xi'an", "Xi'an", True),
    ("西寧", "dial:Mandarin-Xining", "Xining", True),
    ("銀川", "dial:Mandarin-Yinchuan", "Yinchuan", True),
    ("蘭州", "dial:Mandarin-Lanzhou", "Lanzhou", True),
    ("烏魯木齊", "dial:Mandarin-Ürümqi", "Ürümqi", True),
    ("武漢", "dial:Mandarin-Wuhan", "Wuhan", True),
    ("成都", "dial:Mandarin-Chengdu", "Chengdu", True),
    ("貴陽", "dial:Mandarin-Guiyang", "Guiyang", True),
    ("昆明", "dial:Mandarin-Kunming", "Kunming", True),
    ("南京", "dial:Mandarin-Nanjing", "Nanjing", True),
    ("合肥", "dial:Mandarin-Hefei", "Hefei", True),
]
# Sino-Xenic / historical tables (same output directory, special parsers)
_SX_TABLES = ("越南", "朝鮮", "廣韻")

# ---------------------------------------------------------------------------
# Hand-vetted raw tables: (local cache name, upstream filename, format,
# dial: column, locality, opts)
#
# Formats:
#   ife     — cid / character / initial / final / tone(contour digits)
#   cols    — arbitrary column layout via opts: char/ipa/onset/rime/tone
#             indices; tone is either contour digits (tone_is_contour) or a
#             class mapped through opts["tone_map"] (VERIFIED citation values,
#             sources cited per point)
#   tongyin — 同音字表: '#rime' section headers, rows = onset + '[class]字字…'
#             groups; an embedded '#调值' line maps class → contour
# ---------------------------------------------------------------------------
_POINTS = [
    # 岩寺 (a town of old 歙縣) — kept as its own point now that the city
    # table above owns dial:Hui-Shexian
    ("shexian.tsv", "歙县岩寺YB_21J03.tsv", "ife", "dial:Hui-Yansi", "Yansi", {}),
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
    # Shuangfeng (Old Xiang, 甘棠 town); tones per Wikipedia "Shuangfeng dialect"
    ("shuangfeng.tsv", "双峰甘棠.tsv", "cols", "dial:Xiang-Shuangfeng",
     "Shuangfeng", {"char": 2, "ipa": 0, "tone": 1, "no_header": True,
                    "tone_map": {"1": "55", "2": "23", "3": "21",
                                 "5": "35", "6": "33"}}),
    # Pingyao 同音字表 — the file declares its own 調值 map ('#调值' line)
    ("pingyao.tsv", "平遥话同音字表20220527.tsv", "tongyin",
     "dial:Jin-Pingyao", "Pingyao", {}),
]

# columns where every MCPDict record is gap-fill only (merge drops it when a
# higher-priority source already covers that char)
FALLBACK_COLUMNS = {"Korean (Hangul)", "Korean (romanized)", "Middle Chinese"}

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


# ---------------------------------------------------------------- download --
def _get(url: str) -> str:
    import requests
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def download(*, force: bool = False) -> None:
    """Fetch every configured table (pinned commit) into ``data/raw/mcpdict``,
    plus the per-table tone metadata (a small extract of ``_詳情.json``)."""
    MCPDICT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for cache_name, upstream, *_ in _POINTS:
        dest = MCPDICT_DIR / cache_name
        if force or not dest.exists():
            dest.write_text(_get(_RAW_BASE + urllib.parse.quote(upstream)),
                            encoding="utf-8")
    names = [p[0] for p in _OUT_POINTS] + list(_SX_TABLES)
    for name in names:
        dest = OUT_DIR / f"{name}.tsv"
        if force or not dest.exists():
            dest.write_text(_get(_RAW_OUT + urllib.parse.quote(f"{name}.tsv")),
                            encoding="utf-8")
    if force or not TONES_JSON.exists() or \
            set(names) - set(json.loads(TONES_JSON.read_text(encoding="utf-8"))):
        meta = json.loads(_get(_RAW_OUT + urllib.parse.quote("_詳情.json")))
        keep = {}
        for name in names:
            m = meta.get(name) or {}
            tones = m.get("聲調") or "{}"
            keep[name] = {"語言": m.get("語言", ""),
                          "字表來源": re.sub(r"<[^>]+>", "", m.get("字表來源") or ""),
                          "聲調": json.loads(tones) if isinstance(tones, str) else tones}
        TONES_JSON.write_text(json.dumps(keep, ensure_ascii=False, indent=1),
                              encoding="utf-8")


def missing_files() -> list[str]:
    """Configured tables not yet in the local cache (empty = fully cached)."""
    out = [c for c, *_ in _POINTS if not (MCPDICT_DIR / c).exists()]
    out += [n for n in [p[0] for p in _OUT_POINTS] + list(_SX_TABLES)
            if not (OUT_DIR / f"{n}.tsv").exists()]
    if not TONES_JSON.exists():
        out.append(TONES_JSON.name)
    return out


# ------------------------------------------------------ normalised parser --
# reading = segmental IPA + tone class (digits, optional a/b) + optional tag
_OUT_READING = re.compile(r"^(?P<seg>[^\d\s]+?)(?P<cls>\d+[ab]?)(?P<tag>[-=+*/\\@?]*)$")


def tone_table(meta_tones: dict) -> dict[str, str]:
    """MCPDict ``聲調`` block ``{class: [contour, …]}`` → ``{class: Chao}``,
    keeping only classes whose contour is a valid 1–5 pitch string."""
    out = {}
    for cls, info in (meta_tones or {}).items():
        contour = (info[0] if isinstance(info, list) and info else "") or ""
        chao = _chao(str(contour).strip())
        if chao:
            out[str(cls)] = chao
    return out


def parse_out_classes(lines, tones: dict[str, str]) -> list[tuple[str, str, str]]:
    """Normalised MCPDict table → ``(char, IPA+Chao, tone class)``. Readings
    whose tone class has no attested contour, or tagged 存疑 (``?``), are
    skipped — never guessed."""
    out = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2 or not is_single_han(parts[0].strip()):
            continue
        m = _OUT_READING.match(parts[1].strip())
        if not m or "?" in m.group("tag"):
            continue
        tone = tones.get(m.group("cls"))
        if not tone:
            continue
        out.append((parts[0].strip(), m.group("seg") + tone, m.group("cls")))
    return out


def parse_out(lines, tones: dict[str, str]) -> list[tuple[str, str]]:
    """:func:`parse_out_classes` without the class column."""
    return [(c, r) for c, r, _ in parse_out_classes(lines, tones)]


def _read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def _sx_pairs(path) -> list[tuple[str, str]]:
    out = []
    for line in _read_lines(path):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and is_single_han(parts[0].strip()) and parts[1].strip():
            out.append((parts[0].strip(), parts[1].strip()))
    return out


def _sx_records() -> list[dict]:
    recs: list[dict] = []
    vn = OUT_DIR / "越南.tsv"
    if vn.exists():
        seen = set()
        for ch, tok in _sx_pairs(vn):
            q = sinoxenic.telex_to_vietnamese(tok)
            if q and (ch, q) not in seen:
                seen.add((ch, q))
                recs.append(record(ch, "Vietnamese", q, SRC_MCPDICT))
    ko = OUT_DIR / "朝鮮.tsv"
    if ko.exists():
        by_char: dict[str, list[str]] = {}
        for ch, tok in _sx_pairs(ko):
            for h in sinoxenic.naver_korean(tok):
                lst = by_char.setdefault(ch, [])
                if h not in lst:
                    lst.append(h)
        for ch, hs in by_char.items():
            # one space-joined record, exactly like Unihan kHangul/kKorean, so
            # the app's index pairing Hangul ↔ Yale keeps working
            yale = [sinoxenic.hangul_to_yale(h) for h in hs]
            recs.append(record(ch, "Korean (Hangul)", " ".join(hs), SRC_MCPDICT))
            if all(yale):
                recs.append(record(ch, "Korean (romanized)", " ".join(yale), SRC_MCPDICT))
    gy = OUT_DIR / "廣韻.tsv"
    if gy.exists():
        seen = set()
        for ch, val in _sx_pairs(gy):
            fields = val.split("/")
            bax = fields[1].strip() if len(fields) > 1 else ""
            if bax and bax.isascii() and (ch, bax) not in seen:
                seen.add((ch, bax))
                recs.append(record(ch, "Middle Chinese", bax, SRC_MCPDICT))
    for r in recs:
        r["fallback"] = r["column"] in FALLBACK_COLUMNS
    return recs


# ------------------------------------------------------ hand-vetted parsers --
def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t"))


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


_PARSERS = {"ife": lambda rows, opts: _parse_ife(rows),
            "cols": _parse_cols,
            "tongyin": _parse_tongyin}


# -------------------------------------------------------------------- load --
def load() -> list[dict]:
    """Records for every configured table present in the local cache
    (tables not yet downloaded are skipped — run :func:`download`)."""
    records: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(char, column, reading, locality, fallback, tone_class=None):
        key = (char, column, reading)
        if key in seen:
            return
        seen.add(key)
        r = record(char, column, reading, SRC_MCPDICT, locality=locality)
        r["fallback"] = fallback
        if tone_class is not None:
            r["tone_class"] = tone_class
        records.append(r)

    tones_meta = (json.loads(TONES_JSON.read_text(encoding="utf-8"))
                  if TONES_JSON.exists() else {})
    for name, column, locality, fallback in _OUT_POINTS:
        path = OUT_DIR / f"{name}.tsv"
        tones = tone_table((tones_meta.get(name) or {}).get("聲調"))
        if not path.exists() or not tones:
            continue
        for char, reading, cls in parse_out_classes(_read_lines(path), tones):
            add(char, column, reading, locality, fallback, cls)

    # Hand-vetted tables share their columns with Wiktionary dial-pron, whose
    # citation values sometimes differ (Pingyao 平 ˨˨ vs ˩˧) — so they are
    # gap-fill too, with the contour itself as the harmonisation class key.
    for cache_name, _upstream, fmt, column, locality, opts in _POINTS:
        path = MCPDICT_DIR / cache_name
        if not path.exists():
            continue
        for char, reading in _PARSERS[fmt](_rows(path), opts):
            m = re.search(r"[˥˦˧˨˩]+$", reading)
            add(char, column, reading, locality, True, m.group(0) if m else None)

    records += _sx_records()
    return records


if __name__ == "__main__":
    import sys
    from collections import Counter
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    download()
    recs = load()
    by_col = Counter(r["column"] for r in recs)
    print(f"[mcpdict] {len(recs):,} records")
    for col, n in sorted(by_col.items()):
        print(f"  {col:32s} {n:7,}")
