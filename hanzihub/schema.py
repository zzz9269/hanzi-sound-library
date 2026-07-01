"""Canonical schema for the merged reading dataset.

Defines:
  * the source/provenance tags,
  * the Wiktionary ``dial-pron`` locality order (39 points) and their Sinitic
    branch grouping, exactly as hard-coded in en.wiktionary ``Module:zh-pron``,
  * the representative locality used to gap-fill each branch column,
  * the canonical column ordering for the wide app-facing CSV.

The locality order is positional: ``Module:zh/data/dial-pron/<char>`` returns a
flat list whose i-th entry corresponds to ``LOCALITIES[i]``.
"""
from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------
# Provenance / source tags (stored in the long table's ``source`` column)
# --------------------------------------------------------------------------
SRC_UNIHAN = "unihan"
SRC_BAXTER = "baxter-sagart"
SRC_WIKIHAN = "wikihan"
SRC_HAKKA = "hakka-xlsx"
SRC_TEOCHEW = "teochew-xlsx"
SRC_WIKTIONARY = "wiktionary"
SRC_YTENX = "ytenx"
SRC_QIEYUN = "qieyun"
SRC_KAIKKI = "kaikki"        # machine-readable Wiktionary (kaikki.org) — locality IPA
SRC_MCPDICT = "mcpdict"      # 漢字音典 / MCPDict — Haikou (Hainanese) + Shexian (Hui)
SRC_OKINAWAN = "okinawan"    # kaikki Okinawan (Ryukyuan) kanji readings
SRC_RECON = "recon"          # comparative reconstruction (Proto-Min) — approximate, *-flagged
SRC_ML = "ml"

# --------------------------------------------------------------------------
# Wiktionary dial-pron locality order (positional, 39 points)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Locality:
    branch: str       # Sinitic branch group as Wiktionary labels it
    name: str         # English locality name
    han: str          # Han name (for display / dial: column key)
    subgroup: str = ""  # finer Min sub-branch, where relevant


# Order MUST match Module:zh/data/dial-pron/<char> list positions.
LOCALITIES: list[Locality] = [
    # ---- Mandarin (17) ----
    Locality("Mandarin", "Beijing", "北京"),
    Locality("Mandarin", "Harbin", "哈爾濱"),
    Locality("Mandarin", "Tianjin", "天津"),
    Locality("Mandarin", "Jinan", "濟南"),
    Locality("Mandarin", "Qingdao", "青島"),
    Locality("Mandarin", "Zhengzhou", "鄭州"),
    Locality("Mandarin", "Xi'an", "西安"),
    Locality("Mandarin", "Xining", "西寧"),
    Locality("Mandarin", "Yinchuan", "銀川"),
    Locality("Mandarin", "Lanzhou", "蘭州"),
    Locality("Mandarin", "Ürümqi", "烏魯木齊"),
    Locality("Mandarin", "Wuhan", "武漢"),
    Locality("Mandarin", "Chengdu", "成都"),
    Locality("Mandarin", "Guiyang", "貴陽"),
    Locality("Mandarin", "Kunming", "昆明"),
    Locality("Mandarin", "Nanjing", "南京"),
    Locality("Mandarin", "Hefei", "合肥"),
    # ---- Jin (3) ----
    Locality("Jin", "Taiyuan", "太原"),
    Locality("Jin", "Pingyao", "平遙"),
    Locality("Jin", "Hohhot", "呼和浩特"),
    # ---- Wu (4) ----
    Locality("Wu", "Shanghai", "上海"),
    Locality("Wu", "Suzhou", "蘇州"),
    Locality("Wu", "Hangzhou", "杭州"),
    Locality("Wu", "Wenzhou", "溫州"),
    # ---- Hui (2) ----
    Locality("Hui", "Shexian", "歙縣"),
    Locality("Hui", "Tunxi", "屯溪"),
    # ---- Xiang (2) ----
    Locality("Xiang", "Changsha", "長沙"),
    Locality("Xiang", "Xiangtan", "湘潭"),
    # ---- Gan (1) ----
    Locality("Gan", "Nanchang", "南昌"),
    # ---- Hakka (2) ----
    Locality("Hakka", "Meixian", "梅縣"),
    Locality("Hakka", "Taoyuan", "桃源"),
    # ---- Cantonese / Yue (3) ----
    Locality("Cantonese", "Guangzhou", "廣州"),
    Locality("Cantonese", "Nanning", "南寧"),
    Locality("Cantonese", "Hong Kong", "香港"),
    # ---- Min (5) ----
    Locality("Min", "Xiamen", "廈門", subgroup="Southern Min"),
    Locality("Min", "Fuzhou", "福州", subgroup="Eastern Min"),
    Locality("Min", "Jian'ou", "建甌", subgroup="Northern Min"),
    Locality("Min", "Shantou", "汕頭", subgroup="Southern Min (Teochew)"),
    Locality("Min", "Haikou", "海口", subgroup="Southern Min (Hainanese)"),
]

assert len(LOCALITIES) == 39, f"expected 39 localities, got {len(LOCALITIES)}"


def locality_col(loc: Locality) -> str:
    """Namespaced wide-CSV column key for a locality, e.g. ``dial:Min-Fuzhou``."""
    return f"dial:{loc.branch}-{loc.name}"


# --------------------------------------------------------------------------
# Representative locality → existing/new branch column (for gap-filling)
# Maps a wide branch column to the index in LOCALITIES whose reading fills it.
# --------------------------------------------------------------------------
def _idx(name: str) -> int:
    for i, loc in enumerate(LOCALITIES):
        if loc.name == name:
            return i
    raise KeyError(name)


# branch column -> representative locality index
BRANCH_REPRESENTATIVE: dict[str, int] = {
    "Mandarin": _idx("Beijing"),
    "Jin": _idx("Taiyuan"),
    "Wu": _idx("Suzhou"),
    "Xiang": _idx("Changsha"),
    "Gan": _idx("Nanchang"),
    "Hakka": _idx("Meixian"),
    "Cantonese": _idx("Guangzhou"),
    "Hokkien": _idx("Xiamen"),
    "Teochew": _idx("Shantou"),
    # new branch columns for previously-absent Min varieties
    "Eastern Min (Fuzhou)": _idx("Fuzhou"),
    "Northern Min (Jian'ou)": _idx("Jian'ou"),
    "Hainanese (Haikou)": _idx("Haikou"),
    "Hui (Shexian)": _idx("Shexian"),
}

# --------------------------------------------------------------------------
# Reconstruction (historical layer) columns added by ytenx / qieyun
# --------------------------------------------------------------------------
RECONSTRUCTION_COLS = [
    "Old Chinese",                 # Baxter–Sagart 2014 transcription (BS xlsx)
    "Old Chinese (Zhengzhang)",    # ytenx, IPA
    "Middle Chinese",              # Baxter transcription (BS xlsx)
    "Middle Chinese (Baxter)",     # Baxter–Sagart IPA (wikihan)
    "Middle Chinese (position)",   # Qieyun 音韻地位 rime descriptor (qieyun-data)
    "Tang",                        # Unihan kTang
    "Fanqie",                      # 反切 (Unihan + qieyun 廣韻)
]

# --------------------------------------------------------------------------
# Canonical column order for the wide CSV (display priority).
# Columns not listed here are appended afterwards (e.g. dial:* localities),
# sorted by their natural grouping.
# --------------------------------------------------------------------------
PREFERRED_ORDER = [
    "Definition",
    "Mandarin", "Cantonese",
    "Proto-Min",
    "Hokkien", "Teochew", "Eastern Min (Fuzhou)",
    "Northern Min (Jian'ou)", "Hainanese (Haikou)",
    "Hakka", "Wu", "Hui (Shexian)", "Gan", "Xiang", "Jin",
    "Middle Chinese", "Middle Chinese (Baxter)", "Middle Chinese (position)",
    "Tang", "Fanqie", "fanqie_upper", "fanqie_lower",
    "Old Chinese", "Old Chinese (Zhengzhang)",
    "Vietnamese", "Zhuang",
    "Japanese", "Japanese On", "Japanese Kun", "Okinawan",
    "Korean (Hangul)", "Korean (romanized)", "Korean (Yale)",
]
