
# 🎧 IPA Guide for Chinese Dialects & Languages in This Database

*A practical reading guide for all dialect IPA/Romanised fields*

---

## 0. What This Guide Is For

This database stores **Hanzi** and their pronunciations across multiple **Chinese dialects and related languages** (e.g. Mandarin, Cantonese, Hokkien, Teochew, Hakka, Wu, Gan, Xiang, Jin, Vietnamese, Zhuang, etc.).

The pronunciations are either:

* already in **IPA**, or
* in some **romanisation** but mapped to IPA in this project.

This guide explains:

* how to **read the IPA** used in these fields
* how to interpret **consonants, vowels, tones, and diacritics**
* what to **pay attention to** vs what you can safely **ignore** when just “roughly pronouncing” things

It is **not** a complete IPA textbook — it is tuned for **Sinitic & Viet** patterns in this dataset, and for the symbol set in your IPA library. 

---

# 1. Big Picture: How to Read Entries

A typical IPA transcription in this database will look something like:

```text
Mandarin:      lɔ̌   / lâu / ʂʊ́
Cantonese:     lok˥  / lau˨˥ / sɐp˨
Hokkien:       lɔk˥  / lau˨˧ / sap˨
Teochew:       lag˥  / lau˧˥ / sap˧
Hakka:         log˥  / leu˧˥ / sap˧
Wu, Gan, etc.: similar structures
Vietnamese:    lɔk˧ / lau˧˥ / sâp˧˥ (tones written with ˩–˥)
```

Each transcription is basically:

```text
(initial consonant) + (vowel / glide) + (coda) + (tone mark)
```

You read it as:

1. **Consonant(s)** at the beginning
2. **Vowel(s) / diphthong / triphthong**
3. Optional **final consonant** (nasal or stop)
4. One or more **tone letters** (˩ ˨ ˧ ˦ ˥, with or without ˤ etc.)

---

# 2. Tone System: Chao 5-Level Notation

Most Chinese dialects in this database use **Chao 5-level tone letters**:

```text
˩  ˨  ˧  ˦  ˥
```

* **˩** = very low
* **˨** = low-mid
* **˧** = mid
* **˦** = high-mid
* **˥** = high 

### 2.1 Single Tone Letters

* **˥** = high level (like Cantonese tone 1, Mandarin high tone portion of 1)
* **˧** = mid level
* **˩** = low level

These usually represent **level tones**.

### 2.2 Tone Contours (combinations)

* **˨˩** → low falling
* **˩˧** → low rising
* **˧˥** → mid → high (rising)
* **˥˩** → high falling
* **˧˩** → mid → low (falling)

In your file, there are also **pharyngealised tones**:

* **˩ˤ, ˨ˤ, ˧ˤ, ˦ˤ, ˥ˤ**
  → same pitch, but with a **throaty / constricted** quality (pharyngealised tone). 

> **Quick rule:** Treat the line(s) as the melody of the syllable.
> Read left → right, from **start pitch** to **end pitch**.

---

# 3. Consonants: Places & Manners You’ll Actually See

Below is a **practical consonant guide** focusing on what you’ll routinely see in Mandarin, Cantonese, Hokkien, Teochew, Hakka, Wu, Gan, Xiang, Jin, Vietnamese, etc.

### 3.1 Stops (plosives)

| Symbol | Place             | Example English-ish                                  |
| ------ | ----------------- | ---------------------------------------------------- |
| p, b   | bilabial          | p in *pin*, b in *bat*                               |
| t, d   | alveolar          | t in *top*, d in *dog*                               |
| k, ɡ   | velar             | k in *king*, g in *go*                               |
| q, ɢ   | uvular (back k/g) | further back k/g (in some Wu/Gan/Viet-like patterns) |

Aspirated versions are usually written with **ʰ** or by context (tʰ, kʰ, pʰ).

### 3.2 Nasals

| Symbol | Place    | Example      |
| ------ | -------- | ------------ |
| m      | lips     | m in *man*   |
| n      | alveolar | n in *no*    |
| ŋ      | velar    | ng in *sing* |

In many Sinitic dialects:

* Finals **-m, -n, -ŋ** are super important (e.g. Cantonese, Minnan, Hakka).

### 3.3 Fricatives

| Symbol | Place                                     | Example           |
| ------ | ----------------------------------------- | ----------------- |
| f      | labiodental                               | f in *fine*       |
| s, z   | alveolar                                  | s/z in *see/zero* |
| ʂ, ʐ   | retroflex (Mandarin sh/zh)                |                   |
| ɕ      | palatal fricative (Mandarin x as in *xi*) |                   |
| h      | glottal                                   | h in *he*         |

### 3.4 Affricates (stop + fricative)

In many dialects, written as:

* **ts, tsʰ, dz** (Cantonese / Hakka / some Mandarin)
* **tɕ, tɕʰ, dʑ** (Mandarin palatal series)
* **tʂ, tʂʰ, dʐ** (Mandarin retroflex series)

Sometimes you may see **t͡s, t͡ɕ** style (with the tie bar), but often just `ts`, `tɕ` etc.

### 3.5 Laterals & Rhotics

| Symbol | Meaning                                         |
| ------ | ----------------------------------------------- |
| l      | “l” sound (common in many dialect initials)     |
| ɭ      | retroflex l (less common)                       |
| r, ɻ   | various “r”/retroflex approximants (Mandarin r) |

### 3.6 Implosives & rare consonants

Most exotic symbols (clicks, ejectives) never appear in the Chinese rows. **One real exception:** **Hainanese (Haikou)** uses **implosives** —

| Symbol | Meaning | Example |
| --- | --- | --- |
| **ɓ** | implosive "b" (made with an inward breath); often written **ʔb** | 邊 ɓi1 |
| **ɗ** | implosive "d"; often written **ʔd** | 地 ɗi1, 大 ɗua1 |

For a rough reading, a plain **b / d** is fine. Everything else in the symbol library is there only so the reference is complete.

---

# 4. Vowels & Glides (j, w etc.)

Sinitic dialects in your database mostly use:

### 4.1 Core vowels

| Symbol | Approx value       | Example                  |
| ------ | ------------------ | ------------------------ |
| i      | high front         | “ee” in *see*            |
| y      | high front rounded | French *tu*              |
| u      | high back rounded  | “oo” in *food*           |
| e, e̞  | mid front          | “e” in *bed* (varies)    |
| o      | mid back rounded   | “o” in *tone*            |
| ɤ      | back unrounded     | Mandarin *e*             |
| ə      | mid central        | “uh”                     |
| a      | open (front-ish)   | “a” in *father*          |
| ɐ      | near-open central  | like Cantonese reduced a |

### 4.2 Diphthongs & Triphthongs

Common combinations:

* **ai, au, ei, ou**
* **ia, ie, iou (often [jou]), ua, uo, ui**
* In IPA you may see forms like: **aɪ, aʊ, eɪ, oʊ, ia, uo, ie, yː** etc.

### 4.3 Glides

| Symbol | Meaning                             |
| ------ | ----------------------------------- |
| j      | “y” as in *yes* (palatal glide)     |
| w      | “w” as in *we* (labial-velar glide) |

In syllables:

* **jV** ≈ yV (Mandarin: *ya, ye, yu* etc.)
* **wV** ≈ wV (Mandarin: *wa, wo, wei* etc.)

---

# 5. Finals in Chinese Dialects

In many dialects, final consonants (coda) strongly affect both **tone** and **syllable type**.

### 5.1 Nasal Codas

* **-m, -n, -ŋ** are common in:

  * Cantonese, Minnan (Hokkien/Teochew), Hakka, some Wu, Vietnamese, etc.

### 5.2 Stop Codas (entering tone  入聲)

* **-p, -t, -k** indicate **checked syllables**:

  * Very common in Cantonese, Minnan, Hakka, some Wu, Vietnamese Sino-Xenic etc.
  * They are often shorter, clipped syllables, associated with specific tone categories.

> If you see a final **-p, -t, -k** in Cantonese / Hokkien / Hakka / Teochew / Viet data, it usually corresponds to **Middle Chinese 入聲** and an OC final stop.

---

# 6. Diacritics & Modifiers Used in This Project

Your IPA symbol file defines a lot of diacritics. Here are the ones you will **actually care about** most often when reading dialect data.

### 6.1 Length: ː

* **ː** = “lengthen the sound (hold it longer)” for the preceding segment. 
* Example:

  * **aː** = long “aa”
  * **oː** = long “oo”

In many Sinitic dialects, vowel length interacts with tone or syllable type.

---

### 6.2 Pharyngealisation: ˤ

* **ˤ** after a consonant or tone = “pharyngealized / throaty sound (constrict the throat slightly)”. 
* You may see:

  * **qˤ, kˤ, tˤ, pˤ**
  * **˧ˤ, ˦ˤ** (pharyngealised tones)

For reading:

* Treat it as **a darker, throatier quality**.
* For a quick approximate reading you can **ignore ˤ and just pronounce a normal consonant/tone**.

---

### 6.3 Secondary Articulation: ʲ, ʷ, ˠ, ˣ-style things

Your file describes things like:

* **ʲ** → “modifier letter small j” = **palatalisation**
* **ʷ** → “rounded with lips (add a 'w' quality)”
* **ˠ** → “modifier letter small gamma” = **velarisation / dark quality**
* Combinations like:

  * **kʲ, kʷ, kʷˠ, tʲ, tʷ** etc. 

**How to read:**

* **Cʲ** ≈ C + “y” color (like **tʲa ≈ tya**)
* **Cʷ** ≈ C + “w” color (**kʷa ≈ kwa**)
* **Cˠ** ≈ slightly “darker” / velarised consonant; often safe to ignore in a rough reading.

---

### 6.4 “Nasalize the previous sound”: ̰

Your library often glosses **̰** as:

> “nasalize the previous sound (make it nasal)” 

You may see this attached to voiced stops or vowels. In practical Sinitic terms:

* **V̰** ≈ nasalised vowel (like French *bon*)
* **d̰, b̰** etc. are probably not common in your Chinese dialect rows; if they appear, just read them as **slightly nasalised**.

For rough reading, you can usually **ignore ̰** and just read the base segment, unless you specifically care about nasal timbre.

---

### 6.5 Glottalisation: ˀ, ʼ

The file describes variants like:

* **qˀ, tˀ, kˀ, pˀ** = “glottalization (a catch in the throat)” 
* **qʼ, tʼ, kʼ, pʼ** = ejective-like (modifier letter apostrophe)

In Sinitic context, if they appear:

* think of a slight **“catch”** or stiff onset/offset
* you can approximate by a normal consonant if you’re just trying to **read aloud**.

---

# 7. Dialect-Specific Reading Notes (Very Short Cheats)

### 7.1 Mandarin (Modern Standard)

* Usually **no final -p/-t/-k** in modern speech
* Finals are: **-n, -ŋ** or open vowels.
* Retroflexes (ʂ, ʐ, tʂ, tʂʰ) and palatals (tɕ, tɕʰ, ɕ) are common.
* Tone is often represented either with numbers or Chao letters (˥, ˧˥, ˨˩˦, ˥˩).

### 7.2 Cantonese

* Full set of **finals**: -m, -n, -ŋ, -p, -t, -k.
* Tone rich; many level and contour tones, e.g. ˥, ˧, ˨, ˧˥, ˨˩, etc.
* Initials include **unaspirated/aspirated** pairs: p pʰ, t tʰ, k kʰ, ts tsʰ.

### 7.3 Min (Hokkien, Teochew, Eastern/Northern Min, Hainanese)

Min is the most internally diverse branch, so its rows vary a lot:

* **Hokkien / Teochew (Southern Min)** — rich diphthongs + nasal finals, entering-tone stops (-p/-t/-k), and heavy **tone sandhi** (the citation IPA shown here is the *un-sandhied* form).
* **Eastern Min (Fuzhou)** — extensive initial/coda "mutation" in connected speech.
* **Northern Min (Jian'ou)** — simpler coda system.
* **Hainanese (Haikou)** — note the **implosives ɓ/ɗ** (§3.6).

### 7.4 Hakka, Wu, Gan, Xiang, Jin

* Each has its own pattern of:

  * initial voicing contrasts
  * rich tone systems with **checked vs unchecked** syllables
  * preservation vs reduction of nasal/stops in coda
* The same IPA principles apply: read **C + V + coda + tone letters**.

### 7.5 Vietnamese, Zhuang, etc.

* Vietnamese:

  * Has both **tones and rich vowel system**.
  * Some tones may be encoded with **Chao letters** instead of diacritics in this database.
* For Sino-Viet readings of Hanzi, expect:

  * clear **final stops** (-p, -t, -k) for entering tone
  * nasal finals (-m, -n, -ŋ).

---

# 8. What You Can Safely Ignore (for Quick Reading)

When you just want a **rough out-loud reading** rather than doing fine phonetics, you can usually:

* **Keep:**

  * segmental **consonants and vowels**
  * **nasal vs stop** codas
  * rough **tone contour** (low/mid/high; rising vs falling)

* **Optionally ignore or simplify:**

  * super detailed diacritics (**ˤ, ̰, ˠ, ʲ, ʷ**) – treat them as subtle colour
  * clicks/ejectives, which don't show up in the Chinese rows (the Hainanese
    implosives **ɓ/ɗ** *do* — see §3.6, but a plain b/d is a fine approximation)

For serious phonetic work, use the **IPA Legend** mode to look up the exact
meaning of every symbol in a character's readings. 

---

# 9. Micro-Workflow: How to Read Any Dialect Entry

Given a cell from the database like:

```text
tsʰa˧˥
```

Do this:

1. **Find the initial(s)**:

   * `tsʰ` = aspirated “ts” (like “ts” in *cats* but puff of air)
2. **Find the main vowel (& any glides)**:

   * `a` = “a” in *father*
3. **Look for a coda**:

   * none here.
4. **Interpret the tone letters**:

   * ˧˥ = mid → high rising

So you read it as **“tsʰa” with a mid-to-high rising tone**.

Another example:

```text
lok˨
```

1. `l` = “l”
2. `o` ≈ “o” in *lot* / *law* (dialect dependent)
3. `k` = final “k” (checked syllable)
4. ˨ = low-mid tone

→ Something like **“lok” with low-mid tone**, short and clipped.

---

# 10. Summary

* The database uses **standard IPA** plus a **rich set of diacritics** defined in your IPA library CSV. 
* Focus on:

  * consonant **place/manner**
  * vowel quality & glides
  * **nasal vs stop** codas
  * **Chao tone letters** ˩–˥ (with or without ˤ)
* Treat advanced diacritics (ˤ, ʲ, ʷ, ˠ, ̰ etc.) as **fine-tuning** of the basic sound; you can approximate them away if you only need a practical reading.

---

## Two shortcuts in the app

You rarely need to decode IPA by hand here:

* The green **≈** beside each IPA reading is a **rough English respelling** of the
  sound (e.g. `tʰi˥˧` → *“tee”*). It's approximate, not exact.
* The **IPA Legend** mode (sidebar) lists, for the character you're looking at,
  what every IPA symbol in its readings means in plain English.
