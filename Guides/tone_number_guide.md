# Romanisation tone guide (the tone letters on readings and the green ≈ line)

Both the displayed reading chips and the rough English **sounds-like** (the
green `≈` under each reading) end in **Chao tone letters** — `leem˥˩`,
`loong˥˨`, `nyeen˨˧`. That mark is a **pitch contour**: the *melody* of the
tone, read left-to-right on a staff from ˩ (low) to ˥ (high). `˥˥` is
high-level, `˨˩` falls low, `˨˩˧` dips and rises. It is **not** a tone-class
label, and it matches the contours shown on the IPA rows (Shexian `˧˥`, Haikou
`˨˩˧`), so every tone across the panel means the same thing. When the scheme of
a romanisation is unknown, the raw class digit is kept as a superscript instead
— a class number must never masquerade as a pitch trace. See the
[Tone contour guide](tone_contour_guide.md) for how to read Chao values.

## How the contour is found

The sourced romanisations write only the tone **class**, in one of three ways,
and the app converts that class to its citation pitch contour:

* a **trailing digit** — Cantonese Jyutping `tin1`, Teochew Peng'im `lung2`,
  Haikou `hi1`, Gan `nyiin3`, Xiang `ren3`, Jin `reng2` — the digit is replaced
  by the contour letters in the displayed chip too (`tin˥˥`);
* a **leading digit** — Wu Wugniu `6gnin` (moved to the end: `gnin˨˧`);
* an **accent over the vowel** — Hokkien POJ `lím`, Hakka PFS `ngiûn`, Eastern
  Min BUC `ŭng` (see the diacritic tables below). The accent stays in the chip
  — it is not a number — and the contour appears on the `≈` line.

Contours are the standard **citation (in-isolation)** tones of the reference lect
each romanisation encodes (named per table). Real speech applies **tone sandhi**
— heavy in Min and Wu — so a syllable's surface pitch in a word can differ.
Checked (入聲) tones are genuinely short, so a single digit there is correct.

## Accent → tone class (diacritic schemes)

**Hokkien — Pe̍h-ōe-jī (POJ)**

| Accent | Class | Name | Accent | Class | Name |
|--------|-------|------|--------|-------|------|
| (none) | 1 | 陰平 | ˆ circumflex | 5 | 陽平 |
| ´ acute | 2 | 陰上 | ¯ macron | 7 | 陽去 |
| ` grave | 3 | 陰去 | ˌ vertical line | 8 | 陽入 (checked) |
| (none) + stop `-p -t -k -h` | 4 | 陰入 (checked) | | | |

**Hakka — Pha̍k-fa-sṳ (Sixian)**: ˆ→1 陰平, `→2 陽平, ´→3 上聲, (none)→4 去聲,
˚ ring→5 陽去, (none)+stop→6 陰入, ˌ vertical line→7 陽入.

**Eastern Min — Bàng-uâ-cê (BUC)**: ˘ breve→1 上平 (→7 下入 if `-k/-h`),
¯ macron→2 上聲, ´ acute→3 上去 (→4 上入 if `-k/-h`), ` grave→5 下平,
ˆ circumflex→6 下去. (A diaeresis *below* a vowel — `ĕ̤` — is vowel quality, not
tone, and is ignored.)

## Tone class → Chao contour (by reference lect)

| Class | Cantonese (GZ/HK) | Hokkien (Taipei) | Teochew (Chaozhou) | Hainanese (Haikou) | Hakka (Sixian) | E. Min (Fuzhou) | Wu (Shanghai) | Gan (Nanchang) | Xiang (Changsha) | Jin (Taiyuan) |
|------:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | 55 | 55 | 33 | 24 | 24 | 55 | 53 | 42 | 33 | 11 |
| 2 | 35 | 51 | 52 | 21 | 11 | 33 | 34 | 24 | 13 | 53 |
| 3 | 33 | 21 | 213 | 213 | 31 | 213 | 34 | 213 | 41 | 45 |
| 4 | 21 | 32· | 2· | — | 55 | 24· | 5· | — | 55 | 2· |
| 5 | 13 | 24 | 55 | 35 | 33 | 53 | 23 | 45 | 21 | 54· |
| 6 | 22 | — | 35 | 33 | 2· | 242 | 23 | 21 | 24· | — |
| 7 | — | 33 | 11 | 5· | 5· | 5· | 23 | 5· | — | — |
| 8 | — | 44· | 4· | 3· | — | — | 12· | 21· | — | — |
| 9 | — | — | — | 55· | — | — | — | — | — | — |

Cantonese Jyutping's checked (入聲) syllables reuse digits 1/3/6, whose level
contours are already correct. Haikou follows MCPDict's category digits (odd =
陰, even = 陽; no class 4 — 陽上 merged; 9 = the long entering 長入).

`·` marks a **checked / entering** (入聲) tone — short and stop-final. Empty cells
mean that lect has no tone in that historical class (mergers vary): Shanghai folds
陰上/陰去 into one tone and 陽平/陽上/陽去 into another; Sixian Hakka merges the
two 去 tones; Fuzhou, Changsha and Taiyuan have smaller tone inventories.

Contour values are typical citation figures and differ across descriptions and
sub-dialects; treat them as indicative, not canonical.
