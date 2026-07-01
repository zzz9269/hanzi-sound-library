# 漢字音庫 — Hanzi Sound Library

A multilingual lookup tool for the pronunciations of Han characters across the
**Sinitic languages** (Mandarin, Cantonese, the Min/Wu/Hakka/Gan/Xiang/Jin
topolects, Middle & Old Chinese reconstructions) plus the wider Sinosphere
(Japanese, Korean, Vietnamese). The dataset is built by the `hanzihub` package.

## Running the app

```bash
pip install -r requirements.txt
streamlit run app.py          # opens the lookup UI in your browser
```

The Streamlit UI (`app.py`, logic in `hanzihub/appkit.py` + `hanzihub/scrapers.py`)
shows per-topolect IPA with a **rough English approximation**, machine-predicted
readings flagged `ᴹᴸ`, a collapsible 39-point locality layer, per-reading
provenance, TTS for Mandarin/Cantonese/Japanese/Korean/Vietnamese, a per-character
**glyph-origin** panel (Wiktionary historical forms + etymology, fetched on
demand), and live JapanDict / koreanhanja / Nôm lookups. (The original
`漢字音庫_v9.ipynb` notebook remains as a legacy front-end.)

## Architecture

```
sources ──► hanzihub.merge ──► data/out/readings_long.parquet   (canonical, provenanced)
                          └──► data/out/combined_readings.csv    (wide, app-facing)
                                        │
                          漢字音庫_v9.ipynb  (ipywidgets lookup UI)
```

### Data sources (all aggregated with per-source provenance)

| Source | Provides | Coverage |
|---|---|---|
| Unihan `Unihan_Readings.txt` | Mandarin, Cantonese, Tang, JP/KO/VI, Fanqie, Zhuang, definitions | ~40k chars |
| Baxter–Sagart 2014 xlsx | Old Chinese + Middle Chinese (transcription) | ~5k |
| `wikihan-ipa.tsv` | branch IPA (Yue/Gan/Hakka/Jin/Mandarin/Hokkien/Wu/Xiang) + MC Baxter IPA | ~30k |
| 客家話.xlsx / 潮州話.xlsx | Hakka / Teochew | ~4–7k |
| **ytenx (韻典網)** | Old Chinese (Zhengzhang) IPA | ~13k |
| **nk2028 qieyun-data (廣韻)** | Fanqie + Middle Chinese rime position | ~19k |
| **Wiktionary `dial-pron`** | 39 locality-level IPA readings incl. Min: Fuzhou/Jian'ou/Shantou/Haikou | ~1k common chars |
| **kaikki.org** (machine-readable Wiktionary) | per-character locality IPA across ~45 points — Min Dong (Fuzhou), Min Bei (Jian'ou), Quanzhou/Zhangzhou/Taipei/Penang, Ningbo/Chongming, Taishan, the Hakka sub-lects, etc. | ~17.6k chars |
| **漢字音典 / MCPDict** (`osfans/MCPDict`) | the two points absent from Wiktionary: Hainanese (Haikou) + Hui (Shexian) | ~3.8k / ~1.7k chars |
| **kaikki.org Okinawan** | Okinawan (Ryukyuan) kanji readings (kana + romanisation) | ~185 chars |

The **long table** (`readings_long.parquet`) stores one row per
`(char, column, reading, source, conf)` so every reading is auditable and
conflicts between sources are visible. The **wide CSV** is derived from it: it
keeps the legacy branch columns (gap-filled from a representative locality),
adds reconstruction columns, and appends a full `dial:<branch>-<locality>` layer
(e.g. `dial:Min-Fuzhou`). ML-imputed cells carry a `[ML]` suffix and never
overwrite sourced data.

## Building the dataset

```bash
pip install -r requirements.txt

# Full rebuild (uses the cached Wiktionary crawl under data/raw/):
python -m hanzihub.build_dataset

# Re-crawl Wiktionary for new/changed characters:
python -m hanzihub.build_dataset --refresh-wiktionary

# Offline, sources-only (skip Wiktionary + ML):
python -m hanzihub.build_dataset --no-wiktionary --no-impute
```

Paths are resolved from the repo root by default, or from the `HANZIHUB_ROOT`
environment variable — no more hard-coded user paths.

## Credentials (Google Cloud TTS + Translation)

The app uses Google Cloud Text-to-Speech and Translation. **Do not commit the
service-account key.** Point the standard environment variable at it instead:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\tts-robot-key.json"
```

> ⚠️ The previously committed key `TTS/tts-robot-key.json` should be **rotated**
> in the Google Cloud console — it has been stored in a synced OneDrive folder.
> It is now listed in `.gitignore`.

## Layout

```
hanzihub/
  paths.py        central path config (HANZIHUB_ROOT / repo root)
  schema.py       columns, 39-locality order + branch map, source tags
  _http.py        cached, rate-limit-aware downloader
  sources/        one loader per source (uniform record shape)
  merge.py        sources -> long table -> wide CSV
  impute.py       gated ML imputation (calibrated, abstains when unsure)
  build_dataset.py  CLI orchestrator
data/raw/         cached downloads (gitignored)
data/out/         build outputs (gitignored)
```
