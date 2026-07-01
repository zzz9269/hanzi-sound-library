# Tone contour guide

Most languages in this database are **tonal**: the *pitch melody* of a syllable
changes its meaning. This guide explains how those tones are written, then
compares the common contours across several languages.

## The Chao 5-level system

Tones are written with **Chao tone letters** — a little staircase from 1 (lowest)
to 5 (highest):

```
˥ = 5 (high)   ˦ = 4   ˧ = 3 (mid)   ˨ = 2   ˩ = 1 (low)
```

You read a tone left-to-right as a **pitch melody**:

* one letter = a **level** tone — `˥` high-level, `˧` mid-level, `˩` low-level
* two+ letters = a **contour** — `˧˥` rises mid→high, `˥˩` falls high→low,
  `˨˩˦` dips down then up (Mandarin's 3rd tone)

The same melody is often written as **digits** instead of bars (55 = `˥˥`,
213 = `˨˩˧`). The app's sources use both, but the app now displays **one
unified form — Chao tone letters — everywhere**: source digits that denote a
pitch contour (`tʰi⁵³`, `tʰin213`) are converted on display, and romanisations
that carry only a tone *class* digit (Jyutping `tin1`, Peng'im `tiang1`,
Haikou `hi1`, Wugniu `8laq`) are shown with that class's **citation contour**
as tone letters instead (`tin˥˥`, `tiang˧˧`, `hi˨˦`, `laq˩˨`). The provenance
panel keeps the original source spellings.

Two kinds of superscript number remain and are **deliberately not converted**,
because they are tone *categories*, not pitches: Proto-Min `*tʰin¹` (the 8-way
Min class 陰平…陽入) and Middle Chinese (Baxter) `tʰen¹` (平上去入). Reading
`¹` there as "low pitch" would be wrong — nobody knows Proto-Min's pitch values.

Two properties describe a tone: its **register** (overall high vs low) and its
**contour** (level / rising / falling / dipping).

## Checked (entering) tones 入聲

Syllables ending in a **-p, -t, -k** stop (or a glottal stop `ʔ`) are **checked**:
short, clipped, and historically a separate tone category (入聲). Cantonese,
Hokkien, Hakka, Teochew and Sino-Vietnamese keep them; Mandarin has lost them.

## A caution: tone sandhi

In many languages — especially **Min (Hokkien/Teochew)** and **Wu** — a tone
*changes* depending on the tones around it (**tone sandhi**). The IPA in this
database is the **citation (in-isolation) tone**; running speech can differ
substantially.

## Cross-language comparison

The table below lines up the common contours. Empty cells just mean that
language doesn't have a clean match for that exact contour (not that it's
toneless). Pitch values vary by speaker and analysis, so treat them as typical.

| Contour (Chao) — IPA — Label | Mandarin | Cantonese (Jyutping) | Vietnamese (Hanoi) | Hakka (Meixian) | Teochew (Chaozhou) | Notes / Caveats & Sources |
|-------------------------------|-----------|-----------------------|--------------------|-----------------|--------------------|-----------------------------|
| **55 — ˥ — High (high-level)** | T1 = 55 (妈 mā). *PMC* | Tone 1 ≈ 55 (high-level). *jyutping.org* | — | — | Tone 2 ≈ 55 (high-level citation). *SAGE Journals* | Widely attested citation high. Mandarin, Cantonese, and Chaozhou all show clear 55 tones. *PMC, jyutping.org* |
| **53 — ˥˩ — High fall (high-departing)** | — | (Partial) T1/T2 variants ≈ 53 (analysis-dependent). *sfu.ca* | — | — | Tone 3 ≈ 53 (high falling). *SAGE Journals* | Cantonese shows 53 in some analyses; Chaozhou Tone 3 clearly ~53. *SAGE Journals* |
| **52 — ˥˩ — High falling** | — | — | — | 52 (citation tone). *isca-archive.org* | — | Meixian citation includes a 52 falling tone. *isca-archive.org* |
| **51 — ˥˩ — High falling (departing)** | T4 = 51 (骂 mà). *PMC* | — | — | — | — | Classical Mandarin departing tone. *PMC* |
| **44 — ˧˥ — Mid-high / upper level** | — | — | — | 44 (yin-ping / high-level). *isca-archive.org* | — | Meixian upper-level tone distinct from Mandarin 55. *isca-archive.org* |
| **35 — ˧˥ — High rising** | T2 = 35 (麻 má). *PMC* | Tone 2 ≈ 35 (high rising). *jyutping.org* | *sắc* ≈ 35 (high rising). *kanji.org* | — | Tone 4/6 ≈ 35 (rising citation). *SAGE Journals* | Common high-rise contour across Mandarin, Cantonese, Hanoi, and Teochew. *PMC, jyutping.org* |
| **33 — ˧ — Mid level** | — | Tone 3 = 33 (mid level). *jyutping.org* | *ngang* ≈ 33 (mid level). *researchgate.net* | — | Tone 1 = 33 (mid-level). *SAGE Journals* | Shared mid-level tone: Cantonese T3, Hanoi *ngang*, Teochew T1. *jyutping.org, researchgate.net* |
| **31 — ˨˩ — Low fall / creaky** | — | — | *nặng* ≈ 31 (low fall, creaky). *kanji.org* | 31 (low falling). *isca-archive.org* | Tone 7 (≈11/31 variants). *SAGE Journals* | Vietnamese *nặng*, Meixian 31, and low Teochew tones occupy low/falling range (often creaky). *kanji.org* |
| **25 / 24 — ˨˦ — Low rise / mid rise** | — | Tone 5 ≈ 25 (low rising). *sfu.ca* | — | — | — | Cantonese low rising (T5 ≈ 25). *sfu.ca* |
| **21 — ˨˩ — Low falling** | — | Tone 4 ≈ 21 (low falling). *sfu.ca* | *huyền* ≈ 21 (low falling). *kanji.org* | — | Tone 4 (checked low ≈21). *SAGE Journals* | Cantonese T4, Vietnamese *huyền*, and Teochew checked tones share low-falling space. *sfu.ca, kanji.org* |
| **11 — ˩ — Low level (very low)** | — | Tone 6 = 11 (low level). *sfu.ca* | — | 11 (low level). *isca-archive.org* | Tone 6 = 11 (low level). *SAGE Journals* | Cantonese T6, Hakka 11, and Teochew 11 are all very low-level citation tones. *sfu.ca* |
| **214 / 213 — ˨˩˦ — Dipping (low dip)** | T3 = 214 / 213 (classical dipping). *PMC* | — | *hỏi* / *ngã* (complex dip/rise, glottalized). *kanji.org* | — | Tone 5 = 213 (low dipping). *SAGE Journals* | Mandarin T3, Vietnamese *hỏi/ngã*, and Teochew T5 are all low-dip types (different phonation). *PMC* |
| **313 / 353 — peaking / rise-fall (glottalized)** | — | — | *hỏi* / *ngã* (glottalized rise-fall ≈ 313/353). *kanji.org* | — | — | Vietnamese *hỏi/ngã* = typologically distinct glottalized peaking tones. *kanji.org* |
| **Checked / Entering — short, stop-final (˥ʔ / ˧ʔ / ˨ʔ)** | — | Yes — checked tones preserved (T7/8/9). *jyutping.org* | — | Yes — Meixian preserves checked tones. *isca-archive.org* | Yes — Tone 4 & 8 checked. *SAGE Journals* | Checked (entering) tones preserved in Cantonese, Hakka, Teochew; lost in Mandarin & modern Vietnamese. *jyutping.org, isca-archive.org* |
