# A field guide to the reading variants

A single Han character can be *read* in dozens of ways: across the modern Chinese
topolects, in reconstructed older stages of Chinese, and in the languages that
borrowed Chinese characters (Japanese, Korean, Vietnamese…). This app groups them
into three sections. Here's what each row means, where it comes from, and how to
read its notation.

---

## 🗣️ Sinitic topolects (modern spoken Chinese)

"Chinese" is not one language but a family of ~10 branches, as different from each
other as the Romance languages. Each row is one branch (its representative city in
brackets); the **🗺️ More locality readings** panel breaks several of them down to
the individual town.

| Row | Branch (Chinese) | Notes |
|---|---|---|
| **Mandarin** | 官話 | The northern branch; basis of the modern standard. Shown as **Pinyin** + IPA. |
| **Cantonese** | 粵語 (Yue) | Guangzhou/Hong Kong. Shown as **Jyutping** + IPA. Famous for keeping the -p/-t/-k stop endings. |
| **Hokkien** | 閩南語 (Southern Min) | Xiamen/Quanzhou/Zhangzhou + Taiwan. Strong literary vs. colloquial split. |
| **Teochew** | 潮州話 | A Southern Min cousin of Hokkien (Shantou). |
| **Eastern Min (Fuzhou)** | 閩東語 | Fuzhou. Heavy initial/tone "mutation". |
| **Northern Min (Jian'ou)** | 閩北語 | Jian'ou. |
| **Hainanese (Haikou)** | 海南話 | Southern Min branch on Hainan; has implosive ɓ/ɗ. |
| **Hakka** | 客家語 | Meixian. Spread across south China + diaspora. |
| **Wu** | 吳語 | Shanghai/Suzhou. Keeps **voiced** obstruents (b/d/g/z) that most branches lost. |
| **Hui (Shexian)** | 徽語 | A small, transitional branch in Anhui. |
| **Gan** | 贛語 | Jiangxi (Nanchang). |
| **Xiang** | 湘語 | Hunan (Changsha). |
| **Jin** | 晉語 | Shanxi (Taiyuan); often grouped with Mandarin but keeps the **entering tone**. |

The Min branches (Hokkien/Teochew/Eastern/Northern/Hainanese) are the most
divergent — Min split off earliest and preserves very old features.

Topolect readings are given in **IPA** (e.g. `tʰi˥˧`), with the tone written as
Chao pitch letters or digits (5 = high … 1 = low). The green **≈** beside each is
a *rough English approximation* of the sound, not a real transcription.

---

## 📜 Historical layers (reconstructed earlier Chinese)

These are not spoken today — they're scholarly reconstructions of how Chinese
sounded centuries ago, from which the modern readings descend.

| Row | Stage | What it is |
|---|---|---|
| **Old Chinese** | 上古漢語, ~1000 BCE (Zhou) | The **Baxter–Sagart 2014** reconstruction. A notation full of cover symbols (`*`, `[ ]`, `ˤ`, `-s`) marking uncertainty — see the *Baxter–Sagart Guide*. |
| **Old Chinese (Zhengzhang)** | same era | The **Zhengzhang Shangfang** reconstruction, written in plain IPA. |
| **Middle Chinese** | 中古漢語, ~600 CE (Qieyun) | Baxter's **transcription** of the standard described in the 切韻 rhyme dictionary. This is the great "pivot": nearly all modern + borrowed readings derive from it. |
| **Middle Chinese (Baxter)** | same | The same reading written as reconstructed **IPA**. |
| **Middle Chinese (position)** | same | The 音韻地位 — a compact *address* in the rhyme tables (initial · rounding · division · rhyme · tone). See the *Middle Chinese Position Guide*. |
| **Tang** | ~Tang dynasty (7th–10th c.) | A reconstruction of Tang-era pronunciation (from Unihan). |
| **Fanqie** | 反切 | Not a reading but the **traditional spelling method**: two characters, the first giving the initial consonant, the second the final + tone. |

A good workflow: read the **Middle Chinese (position)** breakdown to *understand*
the syllable's structure, then the **Middle Chinese (Baxter)** IPA to *hear* it.

---

## 🌏 Sinosphere (Chinese characters in other languages)

For ~1,500 years, neighbouring cultures borrowed Chinese characters along with an
approximation of their Chinese pronunciation. These borrowings are "fossils" of
the Chinese of the borrowing era (mostly Middle Chinese).

| Row | Language | What it is |
|---|---|---|
| **Japanese** | 日本語 | The combined list of readings. Japanese kanji have two kinds: |
| **Japanese On** | 音読み (on'yomi) | **Sino-Japanese** — the borrowed Chinese reading (itself layered: Go-on, Kan-on, Tō-on, from different periods/regions). |
| **Japanese Kun** | 訓読み (kun'yomi) | The **native Japanese** word matched to the character's meaning — *not* from Chinese. |
| **Okinawan** | 沖縄語 (Ryukyuan) | A separate Japonic language of Okinawa; the kanji's Okinawan reading (kana + romanisation), e.g. 血 → ちー *chī*. |
| **Korean (Hangul)** | 한자음 | **Sino-Korean** — the Korean reading of the character, in Hangul. Borrowed largely from Middle Chinese. |
| **Korean (romanized)** | — | The same in Latin letters. |
| **Vietnamese** | Hán-Việt | **Sino-Vietnamese** — the Vietnamese reading, in the Latin Quốc Ngữ script. A conservative snapshot of Tang-era Chinese. |
| **Zhuang** | Sawndip 古壯字 | Readings from the Han-derived characters traditionally used to write the Zhuang language. |

Because these borrowings froze at different times, comparing them (and the
reconstructions above) lets you triangulate how a character was pronounced
historically — the whole point of laying them side by side.

---

### Other things on screen
* **📜 Glyph origin** — the character's pictographic/structural history (oracle
  bone → seal script → modern), from Wiktionary.
* **🗺️ More locality readings** — the same Sinitic data, broken down to ~50
  individual towns, de-duplicated against the rows above.
* **🔎 Show sources** — every reading with its provenance and (for ML-predicted
  cells, tagged ᴹᴸ) a confidence score.
