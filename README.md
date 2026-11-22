# 漢字音庫 — Hanzi Sound Library

A multilingual lookup tool for the pronunciations of Han characters across the
**Sinitic languages** (Mandarin, Cantonese, Hokkien, Teochew, Fuzhou, Jian'ou,
Hainanese, Hakka, Wu, Hui, Gan, Xiang, Jin), their **historical layers** (Old
Chinese, Middle Chinese, Tang, a reconstructed Proto-Min) and the wider
Sinosphere (Japanese, Okinawan, Korean, Vietnamese). The dataset is built by
the `hanzihub` package. There are two front-ends:

- **The web app** (`web/`): a fast, installable app that runs entirely in
  the browser. **Open it at <https://zzz9269.github.io/hanzi-sound-library/>.**
- **The Streamlit workbench** (`app.py`): the original research UI with
  quizzes, review, progress tracking and the guides.

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

It deploys itself: every push to `main` that touches the data or `web/` runs
[`.github/workflows/pages.yml`](.github/workflows/pages.yml), which builds the
data with `python -m hanzihub.build_web` and publishes `web/`. To try it
locally:

```powershell
python -m hanzihub.build_web                     # writes web/data/ (~1 min)
python -m http.server 8600 --directory web       # then open http://localhost:8600
```

### The Streamlit workbench

The Streamlit app can also run on a free
[Streamlit Community Cloud](https://share.streamlit.io) deployment:

1. Push this repository to GitHub (public or private both work).
2. On share.streamlit.io → **Create app** → pick the repo, branch `main`,
   main file `app.py`. Under *Advanced settings* choose Python 3.12.
3. *(Optional — enables Google TTS + translation)* In the app's
   **Settings → Secrets**, paste the `[gcp_service_account]` block from
   [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)
   filled with your service-account key's fields. Without it every reading
   still shows; only Google audio/translation are off (Hokkien and Teochew
   audio come from free public services and work regardless).
4. Open the app URL on your phone → browser menu → **Add to Home Screen**.
   It then launches full-screen like an app.

Keep the app's sharing setting **private** (only you) if Google credentials
are configured, so nobody else can spend your TTS/translation quota. Note the
hosted filesystem is ephemeral: the 📊 Progress / 🔄 Review study history
(`cache/progress.db`) resets whenever Streamlit restarts the app.

The committed `data/out/*.parquet` files *are* the dataset — the hosted app
needs no build step.

## Running locally

```powershell
pip install -r requirements.txt
streamlit run app.py          # opens the lookup UI in your browser
```

(`launch_app.bat` does the same with a fixed interpreter path.)

The UI shows per-topolect IPA with a **rough English approximation**,
machine-predicted readings flagged `🤖 ML`, a collapsible locality layer
(~75 points), per-reading provenance, TTS (Google voices for Mandarin /
Cantonese / Japanese / Korean / Vietnamese; ithuan.tw for Taiwanese Hokkien;
stitched mogher.com recordings for Chaozhou Teochew), a **glyph-origin** panel,
the full Wiktionary entry, a 📖 passage reader with per-word ruby readings in
any variety, a 🎋 classical-poetry library with recite mode, and quiz /
spaced-repetition review.

Notable engine features:

* **Unified Chao tone letters** — every pitch contour displays as tone letters
  (`tin˥˥`, `tʰieŋ˥˥`); tone-*class* digits (Jyutping / Peng'im / Wugniu) are
  mapped through per-scheme citation-contour tables; tone-*category*
  superscripts (Proto-Min `*tʰin¹`, Baxter MC `tʰen¹`) are deliberately left
  as numbers. See Guides → Tone contour guide.
* **Sound-evolution tree with per-character sound laws** (`hanzihub/soundlaws.py`).
* **反切 breakdown**, **reading search** (`tian`, `tin1`, `thien`, Baxter `then`),
  **Min tone sandhi** (phrase level), **Markdown export**.

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

## Credentials (Google Cloud TTS + Translation)

**Never commit the service-account key.** Any one of these works:

* `GOOGLE_APPLICATION_CREDENTIALS` pointing at the key file (local);
* a `[gcp_service_account]` block in `.streamlit/secrets.toml` (gitignored)
  or in the Streamlit Cloud Secrets box (hosted);
* the legacy `TTS/tts-robot-key.json` (gitignored).

> ⚠️ The key `TTS/tts-robot-key.json` has lived in a synced OneDrive folder —
> rotate it in the Google Cloud console and use the new key for the secrets.

## Licence

Code: MIT (`LICENSE`). Data: compiled from third-party sources with their own
terms; the built tables are shared under CC BY-SA 4.0 — see
[`DATA_SOURCES.md`](DATA_SOURCES.md) for full attribution.

## Layout

```
app.py            Streamlit front-end
hanzihub/
  paths.py        central path config (HANZIHUB_ROOT / repo root)
  schema.py       columns, 39-locality order + branch map, source tags
  sources/        one loader per source (uniform record shape)
  sinoxenic.py    Telex / Revised-Romanization / Yale converters
  merge.py        sources -> long table -> wide table (gap-fill + harmonise)
  reconstruct.py  comparative Proto-Min reconstruction
  impute.py       gated ML imputation (calibrated, abstains when unsure)
  build_dataset.py  CLI orchestrator
  appkit.py / scrapers.py / reading.py / progress.py   app logic
data/raw/         source caches (committed, small)
data/out/         build outputs (parquet committed; CSV local only)
Guides/           in-app guides
tests/            pytest suite
```
