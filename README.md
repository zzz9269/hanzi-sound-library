# 漢字音庫 — Hanzi Sound Library

A multilingual lookup tool for the pronunciations of Han characters across the
**Sinitic languages** (Mandarin, Cantonese, Hokkien, Teochew, Fuzhou, Jian'ou,
Hainanese, Hakka, Wu, Hui, Gan, Xiang, Jin), their **historical layers** (Old
Chinese, Middle Chinese, Tang, a reconstructed Proto-Min) and the wider
Sinosphere (Japanese, Okinawan, Korean, Vietnamese). The dataset is built by
the `hanzihub` package and shown by a fast, installable web app (`web/`) that
runs entirely in the browser. **Open it at
<https://zzz9269.github.io/hanzi-sound-library/>.**

## Use it on your phone

Open <https://zzz9269.github.io/hanzi-sound-library/> on your phone and add it
to the home screen. It then opens full-screen like any other app:

- **iPhone (Safari):** Share button → **Add to Home Screen**.
- **Android (Chrome):** ⋮ menu → **Install app** (or **Add to Home screen**).

The app is a static site on GitHub Pages: it opens instantly, never sleeps,
and needs no server or API keys. Every character you look up is kept on the
device, and **Saved → Use offline** downloads all the readings (about 47 MB)
so lookups work with no connection. Audio uses the phone's own voices for
Mandarin, Cantonese, Japanese, Korean and Vietnamese, ithuan.tw's SuiSiann
voice for Taiwanese Hokkien and mogher.com recordings for Teochew.

Hokkien readings are **Taiwanese** and Teochew readings **Swatow (Shantou)**,
picked from Wiktionary's place-tagged readings (with Taipei / Shantou dialect
surveys for characters it lacks), with vernacular 白 / literary 文 marked where
Wiktionary says. Hokkien and Teochew phrases are read **syllable by syllable in
citation tones**: Min tone sandhi depends on word and phrase boundaries, and
a positional model got it wrong too often, so no sandhi is applied. Teochew
audio comes from a Chaozhou-city speaker; Swatow-only syllables (天 tiang1,
Chaozhou tiêng1) have no recording and show without a play button.

It deploys itself: every push to `main` that touches the data or `web/` runs
[`.github/workflows/pages.yml`](.github/workflows/pages.yml), which builds the
data with `python -m hanzihub.build_web` and publishes `web/`. To try it
locally:

```powershell
python -m hanzihub.build_web                     # writes web/data/ (~1 min)
python -m http.server 8600 --directory web       # then open http://localhost:8600
```

The committed `data/out/*.parquet` files *are* the dataset; the web build
reads them directly.

## Engine features

* **Unified Chao tone letters** — every pitch contour displays as tone letters
  (`tin˥˥`, `tʰieŋ˥˥`); tone-*class* digits (Jyutping / Peng'im / Wugniu) are
  mapped through per-scheme citation-contour tables; tone-*category*
  superscripts (Proto-Min `*tʰin¹`, Baxter MC `tʰen¹`) are deliberately left
  as numbers. See `Guides/`.
* **Sound-evolution tree with per-character sound laws** (`hanzihub/soundlaws.py`).
* **反切 breakdown**, **reading search** (`tian`, `tin1`, `thien`, Baxter `then`),
  **Markdown export**.

Run the test suite with `python -m pytest tests` (needs
`pip install -r requirements-build.txt`).

## Data sources (all aggregated with per-source provenance)

| Source | Provides |
|---|---|
| Unihan `Unihan_Readings.txt` | Mandarin, Cantonese, Tang, Japanese, Korean, Vietnamese, Fanqie, Zhuang, definitions |
| Baxter–Sagart 2014 xlsx | Old Chinese + Middle Chinese (transcription) |
| `wikihan-ipa.tsv` | branch IPA (Yue/Gan/Hakka/Jin/Mandarin/Hokkien/Wu/Xiang) + MC Baxter IPA |
| 客家話.xlsx / 潮州話.xlsx | Hakka / Teochew (Peng'im) |
| ytenx (韻典網) | Old Chinese (Zhengzhang) IPA |
| nk2028 qieyun-data (廣韻) | Fanqie + Middle Chinese rime position |
| Wiktionary `dial-pron` | 39 canonical localities (~1k common chars) |
| kaikki.org (machine-readable Wiktionary) | per-character locality IPA, ~45 points |
| **漢字音典 / MCPDict** (`osfans/MCPDict`, commit-pinned) | ~50 locality tables transcribed from the published 音檔 / 方言志 references — every branch representative (太原, 南昌, 長沙, 建甌, 福州, 梅縣, 厦門, 汕頭/潮州, 上海, 海口, 歙縣) plus Hui (屯溪, 績溪), Min (臺北, 泉州, 漳州, 莆田, 雷州), Hakka, Wu, Yue and 16 Mandarin points; **Hán-Việt** readings (Vietnamese); Naver **Hanja** readings (Korean); Baxter MC transcription from 廣韻 |
| kaikki.org Okinawan | Okinawan (Ryukyuan) kanji readings |

How sources combine: the **long table** (`readings_long.parquet`) stores one
row per `(char, column, reading, source)` so every reading is auditable. The
**wide table** (`combined_readings.parquet`) is derived from it: branch columns
are gap-filled from their representative locality, and a full
`dial:<branch>-<locality>` layer is appended. ML-imputed cells carry `[ML]`
and never overwrite sourced data.

MCPDict tables that land in a column already covered by Wiktionary/kaikki are
**gap-fill only** (a cell never mixes two transcriptions of one place), and
their tones are **harmonised**: MCPDict's tone *category* is kept, rendered
with the contour the column's primary source uses for that category
(`merge.harmonize_fallback_tones`). Korean/MC gap-fills follow the same rule;
the converters (Telex → Quốc Ngữ, Revised Romanization → Hangul → Yale) are
validated against Unihan (Korean 99.9% agreement; 廣韻→Baxter 97.7% vs
Baxter–Sagart).

## Building the dataset

```powershell
pip install -r requirements-build.txt

# Full rebuild (cached Wiktionary crawl; fetches MCPDict tables if missing):
python -m hanzihub.build_dataset

# Re-crawl Wiktionary for new/changed characters:
python -m hanzihub.build_dataset --refresh-wiktionary

# Offline, sources-only (skip Wiktionary + ML):
python -m hanzihub.build_dataset --no-wiktionary --no-impute
```

To move to a newer MCPDict snapshot, bump `MCPDICT_SHA` in
`hanzihub/sources/mcpdict.py`, delete `data/raw/mcpdict/`, rebuild and re-run
the tests. Paths resolve from the repo root, or from `HANZIHUB_ROOT`.

## Licence

Code: MIT (`LICENSE`). Data: compiled from third-party sources with their own
terms; the built tables are shared under CC BY-SA 4.0 — see
[`DATA_SOURCES.md`](DATA_SOURCES.md) for full attribution.

## Layout

```
web/              the web app (static PWA; data/ is generated)
hanzihub/
  paths.py        central path config (HANZIHUB_ROOT / repo root)
  schema.py       columns, 39-locality order + branch map, source tags
  sources/        one loader per source (uniform record shape)
  sinoxenic.py    Telex / Revised-Romanization / Yale converters
  merge.py        sources -> long table -> wide table (gap-fill + harmonise)
  reconstruct.py  comparative Proto-Min reconstruction
  impute.py       gated ML imputation (calibrated, abstains when unsure)
  build_dataset.py  CLI orchestrator
  build_web.py    dataset -> web/data/ shards
  appkit.py / scrapers.py / reading.py   shared reading logic
data/raw/         source caches (committed, small)
data/out/         build outputs (parquet committed; CSV local only)
Guides/           reference guides
tests/            pytest suite
```
