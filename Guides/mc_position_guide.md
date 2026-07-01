# Reading Middle Chinese positions (音韻地位)

The **Middle Chinese (position)** field — e.g. `心合一寒平` — is *not* a
pronunciation. It's a compact **address** that locates a syllable in the rhyme
tables of the *Qieyun* / *Guangyun* (601–1008 CE), the standard reconstruction of
the Chinese of that era. Every Middle Chinese syllable has exactly one such
address, and modern readings (Mandarin, Cantonese, Hokkien, Sino-Japanese, …)
can all be *derived* from it by regular sound changes. That's why it's so useful.

## The five slots

A code is read left to right as up to five parts:

```
心  合   一    寒    平
│   │    │     │     └─ 聲  tone
│   │    │     └─────── 韻  rhyme
│   │    └───────────── 等  division (grade)
│   └────────────────── 呼  rounding
└────────────────────── 母  initial (the onset consonant)
```

| Slot | What it is | Values |
|---|---|---|
| **母 Initial** | the onset consonant | one of ~38 initials, e.g. 心 = *s*, 明 = *m*, 見 = *k*, 並 = *b* |
| **呼 Rounding** | is there a *-w-* glide? | 開 = open (plain) · 合 = rounded (-w-). Omitted if the rhyme doesn't distinguish. |
| **等 Division** | "grade" I–IV | 一二三四. Roughly tracks vowel quality + the *-j-* medial; Div. III/IV give palatalised modern reflexes. |
| **韻 Rhyme** | the main vowel + coda group | a rhyme name, e.g. 寒, 灰, 東. ~100+ rhymes. |
| **聲 Tone** | the tone category | 平 level · 上 rising · 去 departing · 入 entering (ends in -p/-t/-k) |

(A rare extra slot, **重紐 A/B**, distinguishes two flavours of certain Division-III
syllables.)

## Worked example

**`心合一寒平`**
- **心** initial → *s-*
- **合** → rounded, so there's a *-w-*
- **一** → Division I (a plain, back-ish vowel; no palatalisation)
- **寒** → the 寒 rhyme (an *-an* type rhyme)
- **平** → level tone

→ a Middle Chinese syllable roughly like **swan** (level tone). Its modern reflexes
fan out from there: Mandarin *suān/suan*, Cantonese *syun*, etc.

**`明一灰平`**
- **明** initial → *m-*
- (no 呼 listed)
- **一** → Division I
- **灰** → the 灰 rhyme (an *-oi/-uai* type rhyme)
- **平** → level tone

→ roughly **muoi** (level tone) → Mandarin *méi*, Cantonese *mui*, etc.

## Why a character can have several positions

If a character had more than one Middle Chinese reading (different meanings or
literary/colloquial layers), it gets **one position per reading**, shown
separated by `·`. The app decodes each one beneath the codes.

## In the app

Under the **Middle Chinese (position)** row, each code is expanded into a
plain-language line, e.g.

> 心合一寒平 → *sounded roughly like “**swan**”, level (flat) tone — 心‑ (s) ·
> Division I · 寒 rhyme*

The reconstructed spelling is **approximate** (meant to give you the gist of the
sound, not an exact value) — for the precise reconstructed IPA, see the
**Middle Chinese (Baxter)** row.
