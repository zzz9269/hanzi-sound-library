# Data sources and attribution

The code in this repository is MIT-licensed (see `LICENSE`). The pronunciation
data in `data/raw/` (source caches) and `data/out/` (the built dataset) is
**compiled from the third-party sources below, which keep their own terms**.
Every reading in `data/out/readings_long.parquet` records which source it came
from, so any row can be traced back.

Because parts of the dataset are derived from Wiktionary, the built tables in
`data/out/` are shared under **CC BY-SA 4.0**, with credit to the sources
listed here.

| Source | Used for | Where it comes from | Terms |
|---|---|---|---|
| Unicode **Unihan** database | Mandarin, Cantonese, Tang, Japanese, Korean, Vietnamese, fanqie, definitions, phonetic series | <https://www.unicode.org/charts/unihan.html> | Unicode License v3 |
| **Wiktionary** (zh-pron, dial-pron, glyph origin, etymology; also fetched live by the app) | Sinitic romanisations, 39 dial-pron localities | <https://en.wiktionary.org> | CC BY-SA 4.0 |
| **kaikki.org** machine-readable Wiktionary (Chinese + Okinawan) | locality IPA (~45 points), Okinawan readings | <https://kaikki.org> | CC BY-SA 4.0 (Wiktionary-derived) |
| **WikiHan** (`wikihan-ipa.tsv`) | branch IPA, MC Baxter IPA | Chang et al. 2022, <https://github.com/kalvinchang/wikihan> | CC BY-SA 4.0 (Wiktionary-derived) |
| **漢字音典 / MCPDict** (`osfans/MCPDict`, pinned commit) | ~50 locality tables, Hán-Việt, Korean hanja, 廣韻 | <https://github.com/osfans/MCPDict> | see the repository; each table credits its published 方言志 / 調查報告 |
| **Baxter–Sagart** Old Chinese reconstruction (2014, v1.1) | Old Chinese, Middle Chinese transcription | <https://ocbaxtersagart.lsait.lsa.umich.edu> | distributed by the authors; see their site |
| **韻典網 ytenx** | Old Chinese (Zhengzhang) | <https://ytenx.org> | see the site |
| **nk2028 qieyun-data** (廣韻) | fanqie, MC rime positions | <https://github.com/nk2028/qieyun-data> | see the repository |
| `客家話.xlsx`, `潮州話.xlsx` | Hakka, Teochew (Peng'im) | compiled spreadsheets bundled with the project | |

Services the app calls at run time, for display only (nothing is stored in the
dataset): Wiktionary, JapanDict, koreanhanja.app, the Nôm Foundation lookup,
ithuan.tw (Taiwanese TTS), mogher.com (Teochew recordings), Lohankha, and
Google Cloud Text-to-Speech / Translation (needs your own key).

If you are a rights holder and something here should be credited differently
or removed, please open an issue.
