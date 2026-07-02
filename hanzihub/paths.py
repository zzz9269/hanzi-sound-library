"""Central path configuration for 漢字音庫 (hanzihub).

Replaces the hard-coded ``C:\\Users\\zacha\\...`` / stale ``C:\\Users\\zzzac\\...``
paths scattered through the notebooks and ``漢字音庫.py``.

Resolution order for the project root:
  1. ``HANZIHUB_ROOT`` environment variable, if set.
  2. The repository directory that contains this package (default).

Everything else is derived from that root, so the project is portable as long as
the data files travel with it.
"""
from __future__ import annotations

import os
from pathlib import Path

# This file lives at <root>/hanzihub/paths.py → root is two levels up.
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    env = os.environ.get("HANZIHUB_ROOT")
    return Path(env).expanduser().resolve() if env else _DEFAULT_ROOT


ROOT = project_root()

# ---- Original source files (shipped in the repo) ----
UNIHAN_TXT = ROOT / "Unihan_Readings.txt"
BAXTER_SAGART_XLSX = ROOT / "BaxterSagartOC2015-10-13.xlsx"
WIKIHAN_TSV = ROOT / "wikihan-ipa.tsv"
HAKKA_XLSX = ROOT / "客家話.xlsx"
TEOCHEW_XLSX = ROOT / "潮州話.xlsx"
IPA_LIBRARY_TXT = ROOT / "ipa_full_library_complete.txt"

# Legacy combined CSV (input parity reference / fallback for the app).
LEGACY_COMBINED_CSV = ROOT / "combined_dialects_imputed_tagged_excl_jp_kr.csv"

# ---- Generated data tree ----
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # cached downloads (wiktionary/ytenx/qieyun)
OUT_DIR = DATA_DIR / "out"           # build outputs

# Per-source raw caches
WIKTIONARY_CACHE = RAW_DIR / "wiktionary"
YTENX_CACHE = RAW_DIR / "ytenx"
QIEYUN_CACHE = RAW_DIR / "qieyun"

# ---- Build outputs ----
READINGS_LONG = OUT_DIR / "readings_long.parquet"   # canonical, fully provenanced
COMBINED_CSV = OUT_DIR / "combined_readings.csv"     # wide, app-facing
COMBINED_PARQUET = OUT_DIR / "combined_readings.parquet"  # fast app-load mirror


def ensure_dirs() -> None:
    """Create the data tree if it does not yet exist."""
    for d in (DATA_DIR, RAW_DIR, OUT_DIR,
              WIKTIONARY_CACHE, YTENX_CACHE, QIEYUN_CACHE):
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print("ROOT             =", ROOT)
    print("UNIHAN_TXT       =", UNIHAN_TXT, "exists:", UNIHAN_TXT.exists())
    print("BAXTER_SAGART    =", BAXTER_SAGART_XLSX, "exists:", BAXTER_SAGART_XLSX.exists())
    print("WIKIHAN_TSV      =", WIKIHAN_TSV, "exists:", WIKIHAN_TSV.exists())
    print("HAKKA_XLSX       =", HAKKA_XLSX, "exists:", HAKKA_XLSX.exists())
    print("TEOCHEW_XLSX     =", TEOCHEW_XLSX, "exists:", TEOCHEW_XLSX.exists())
    print("OUT_DIR          =", OUT_DIR)
