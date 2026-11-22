# Sound evolution & chronology

Each character page in the web app has a **Readings | Family tree** switch.
The **Family tree** shows how *one* character's pronunciation descended from
Old Chinese (far left) to every modern variety (far right), with each branch
hanging where it split off. **Tap any box** to see what that stage or variety
is and which regular sound changes gave this character its form there (入聲
loss or retention, 全濁 devoicing and aspiration, palatalisation, 輕脣化, Min's
pre-split archaisms, Sino-Xenic tone correspondences, …), all derived from the
character's Middle Chinese 音韻地位. Notes about Mandarin's palatalisation and
w- are only shown when this character's Mandarin reading actually has them.

This guide explains the family tree it's based on, and corrects a very common myth.

## ⚠️ The myth: "Old Chinese → Middle Chinese → Cantonese → Mandarin"

This is **not** how it works. Cantonese is **not** the ancestor of Mandarin, and
neither descends from the other. The modern Chinese varieties are **cousins**:
all except Min descend from Late Middle Chinese and split from each other in
the last thousand years or so, like the Romance languages branching off Latin.
(Cantonese keeps some older features that Mandarin lost, which is why it *feels*
"older"; but older-sounding ≠ ancestor.)

## The family tree

The shape follows the mainstream classification (Norman 1988 *Chinese*; Li Rong
and the *Language Atlas of China*). Boxes without a reading are **groups**: they
mark where branches part, not a language with recorded forms.

```
Old Chinese 上古漢語  (Zhou, reconstructions target ~1000 BCE)
│
├─ Proto-Min 原始閩語 ── split c. Han, BEFORE the Qieyun
│    ├─ Coastal Min
│    │    ├─ Southern Min 閩南 ── Taiwanese Hokkien · Teochew (Swatow) · Hainanese
│    │    └─ Eastern Min (Fuzhou)
│    └─ Inland Min ── Northern Min (Jian'ou)
│
└─ Early Middle Chinese 中古漢語  (Qieyun 切韻, 601 CE)
     └─ Late Middle Chinese  (Tang Chang'an, 8th–10th c.)
          ├─ Northern Chinese ── Mandarin (via Early Mandarin, 中原音韻 1324) · Jin
          ├─ Wu · Hui · Xiang · Cantonese
          ├─ Hakka–Gan ── Gan · Hakka
          ├┄ Southern Min literary layer 文讀 (borrowed, dotted line)
          └┄ borrowed OUT, not descended (dashed):
               Sino-Japanese on'yomi   go-on 5–6th c. · kan-on 7–9th c.
               Sino-Korean             c. 8–10th c.
               Sino-Vietnamese         c. 9–10th c.
```

Things that make this tree "non-obvious":

1. **Min split early.** Min preserves distinctions from *before* Middle Chinese
   (知 read as t-, no f-), so it does not descend from the Qieyun. Its *literary*
   readings were later borrowed from the Tang–Song standard (the dotted line),
   while its *colloquial* layer is inherited, which is why Min characters often
   have two very different readings (白讀 vs 文讀).
2. **Late Middle Chinese innovations are shared by everyone else.** For example
   輕脣化 (p- → f- before certain rimes) and the 知 series becoming affricates
   are found in every non-Min variety, so they come from a common Tang ancestor.
3. **Hakka and Gan** share a signature change (MC voiced stops became aspirated
   in every tone), so they are grouped; **Mandarin and Jin** share the Northern
   developments, Jin being set apart mainly by keeping the entering tone.
4. **Japanese / Korean / Vietnamese didn't *inherit* these readings; they
   *borrowed* them** (dashed lines). They're snapshots of how Chinese sounded at
   the moment of borrowing, frozen in a foreign language. That's why a Tang-era
   loan in Japanese can preserve a final *-t/-k* that modern Mandarin dropped.

## The time periods

The tree's columns are rough periods (Zhou · Han–Sui · Tang · Song–Yuan ·
today); the dates of the group splits are approximate.

| Stage | When | Notes |
|---|---|---|
| **Old Chinese** 上古 | Shang–Han, reconstructions target **~1000 BCE** | Two leading systems shown: Zhengzhang (2003) and Baxter–Sagart (2014). Had consonant clusters, no tones yet. |
| **Proto-Min** | split **c. Han** | Reconstructed by this project from the Min daughters (comparative method). |
| **Early Middle Chinese** 中古 | **601 CE** | The *Qieyun* rhyme dictionary is the anchor; readings in Baxter's transcription. |
| **Late Middle Chinese** | **Tang, 8th–10th c.** | The prestige speech of Chang'an; source of most Sino-Xenic loans. Reading: Stimson (1976, via Unihan) where one exists. |
| **Modern branches** | crystallised over the **last ~1000 years** | Diverged through the Song–Yuan–Ming as regions developed separately. |

## How tones arose (tonogenesis)

Old Chinese had **no tones**. The four Middle Chinese tones came from lost final
consonants:

* no suffix → **level** (平)
* final *-ʔ* (glottal stop) → **rising** (上)
* final *-s* → **departing** (去)
* final *-p/-t/-k* → **entering / checked** (入)

Each modern branch then split those four tones further (often by whether the
initial was voiced), which is why Cantonese has 6–9 tones, Mandarin 4, etc.

## What's on the tree (and what isn't)

**On it**: everything whose pronunciation actually *descends from* or was
*borrowed from* Chinese: the reconstructions (Old Chinese, Proto-Min, Early and
Late Middle Chinese), the modern Sinitic varieties the app covers, and the three
Sino-Xenic loan traditions (Japanese *on'yomi*, Sino-Korean, Sino-Vietnamese).
Varieties with no recorded reading for a character are left off for that
character. Puxian, Pinghua, Leizhou and others are not shown.

**Deliberately off it**: readings that use the character but are **native
words**, not Chinese-derived, so they have no place on a *sound-evolution* tree:

* **Japanese *kun'yomi*** (天 = *ame/sora* "sky"): native Japanese.
* **Okinawan** (血 = *chī*): native Ryukyuan.
* **Zhuang** (Sawndip): native Tai; many Zhuang characters have no Chinese
  reading at all.

## Reading the tree in the app

* Left → right is **time**. Each box shows the variety, its reading(s) and, for
  stages, the era. 白 / 文 mark vernacular and literary readings; **ML** marks a
  machine-predicted reading.
* **Solid** lines = direct descent; **dashed** = borrowing into another
  language; **dotted** = the Southern Min literary layer.
* Colours: red = Old Chinese, amber = Middle Chinese, **jade = Min** (the early
  branch), blue = Northern (Mandarin/Jin), grey = other branches, purple = the
  Sino-Xenic loans.

> This is a deliberately **simplified** tree for one character. Real Sinitic
> classification is debated (e.g. where Hui and Jin belong, how Pinghua groups),
> and every branch also absorbed later waves of borrowing from the standard
> language. Treat it as a teaching aid, not the last word.
