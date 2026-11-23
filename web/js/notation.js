// Reading the historical reconstructions: Old Chinese (Baxter–Sagart 2014,
// Zhengzhang 2003), Middle Chinese (Baxter's system in IPA) and the app's
// Proto-Min. Each form is split into symbols, every symbol gets a plain-English
// explanation, and the same pass builds a rough respelling an English reader
// can say (*l̥ˤi[n] → "hleen · throaty").
//
// Systems: "bs" Baxter–Sagart, "zz" Zhengzhang, "mc" Middle Chinese, "pm" Proto-Min.

const COMBINING_VOICELESS = /[̥̊]/;   // ̥ ̊
const NONSYL = "̯";                         // ̯

const CONS = {
  p: ["p", "p as in “spin”: no puff of air"],
  t: ["t", "t as in “stop”: no puff of air"],
  k: ["k", "k as in “skin”: no puff of air"],
  b: ["b", "a fully voiced b"],
  d: ["d", "a fully voiced d"],
  g: ["g", "a fully voiced g as in “go”"],
  "ɡ": ["g", "a fully voiced g as in “go”"],
  q: ["k", "a k made further back, at the uvula (like Arabic q)"],
  "ɢ": ["g", "a g made far back, at the uvula"],
  c: ["ky", "a stop between t and k, with the tongue on the hard palate"],
  "ʔ": ["'", "a glottal stop, the catch in “uh-oh”"],
  s: ["s", "s as in “see”"],
  z: ["z", "z as in “zoo”"],
  h: ["h", "h as in “hat”"],
  x: ["kh", "the rasping ch of Scottish “loch”"],
  "χ": ["kh", "a rasping ch made at the uvula, further back than “loch”"],
  "ɣ": ["gh", "a voiced “loch” sound: a soft, gargled g"],
  "ɦ": ["h", "a breathy, voiced h, as in “ahead”"],
  "ɕ": ["sh", "sh with the tongue pushed forward, as in “sheep”"],
  "ʑ": ["zh", "the voiced partner of ɕ: the s in “measure”, tongue forward"],
  "ʂ": ["sh", "sh with the tongue tip curled back (retroflex)"],
  "ʐ": ["zh", "the voiced partner of ʂ, tongue tip curled back"],
  "ʈ": ["tr", "t with the tongue tip curled back (retroflex)"],
  "ɖ": ["dr", "d with the tongue tip curled back (retroflex)"],
  "ɳ": ["n", "n with the tongue tip curled back (retroflex)"],
  m: ["m", "m as in “me”"],
  n: ["n", "n as in “no”"],
  "ŋ": ["ng", "ng as in “sing”; it can also begin a syllable"],
  "ɲ": ["ny", "ny as in “canyon”"],
  "ȵ": ["ny", "ny as in “canyon”"],
  l: ["l", "l as in “leaf”"],
  r: ["r", "an r, probably tapped or trilled"],
  j: ["y", "y as in “yes”"],
  w: ["w", "w as in “wet”"],
};
const AFFRICATES = {
  ts: ["ts", "ts as in “cats”"], dz: ["dz", "dz as in “adze”"],
  "tɕ": ["ch", "ch as in “cheap”, tongue forward"], "dʑ": ["j", "j as in “jeep”, tongue forward"],
  "tʂ": ["ch", "ch with the tongue tip curled back (retroflex)"], "dʐ": ["j", "j with the tongue tip curled back"],
};
const VOWELS = {
  i: ["ee", "ee as in “see”"],
  u: ["oo", "oo as in “food”"],
  e: ["e", "e as in “bed”, a little closer (like French é)"],
  o: ["o", "a pure o, as in “go” without the glide"],
  a: ["a", "a as in “father”"],
  "ə": ["uh", "uh, the vowel in “about”"],
  "ɨ": ["ih", "a central i, between “ee” and “oo” with spread lips"],
  "ɯ": ["uh", "an “oo” said with spread, unrounded lips"],
  "æ": ["a", "a as in “cat”"],
  "ɛ": ["eh", "e as in “bed”"],
  "ɔ": ["aw", "aw as in “law”"],
  "ɑ": ["ah", "a far back in the mouth, as in “spa”"],
  "ʌ": ["uh", "u as in “cup”"],
  "ɤ": ["uh", "an o said with unrounded lips, a back “uh”"],
  y: ["ü", "ee said with rounded lips (German ü)"],
  "ø": ["ö", "e said with rounded lips (German ö)"],
};
const SUP = { "¹": 1, "²": 2, "³": 3, "⁴": 4, "⁵": 5, "⁶": 6, "⁷": 7, "⁸": 8 };
const MC_TONE = { 1: "平 level", 2: "上 rising", 3: "去 departing", 4: "入 entering (checked: ends in -p, -t or -k)" };

/** "*l̥ˤi[n] (W dialect: …)" → { form: "*l̥ˤi[n]", note: "W dialect: …" }.
 *  A parenthesis holding prose (spaces, arrows, ?, :) is a note, not markup. */
export function splitNote(t) {
  const notes = [];
  const form = t.replace(/\s*\(([^()]*[\s<>:?!,][^()]*)\)/g, (_, n) => { notes.push(n.trim()); return ""; }).trim();
  return { form, note: notes.join("; ") };
}

/** Merge readings that only differ by a note: same form shown once, notes joined. */
export function mergeForms(rs) {
  const out = [];
  for (const r of rs) {
    const { form, note } = splitNote(r.t);
    const hit = out.find((o) => o.form === form);
    if (hit) { if (note && !hit.notes.includes(note)) hit.notes.push(note); continue; }
    out.push({ ...r, form, notes: note ? [note] : [] });
  }
  return out;
}

function tokenize(s) {
  s = s.normalize("NFD").replace(/[͜͡]/g, "");   // tie bars
  const toks = [];
  for (let i = 0; i < s.length;) {
    const two = s.slice(i, i + 2);
    let base;
    if (AFFRICATES[two]) { base = two; i += 2; } else { base = s[i]; i++; }
    let mods = "";
    while (i < s.length && /[̀-ͯ]/.test(s[i])) { mods += s[i]; i++; }
    toks.push(base + mods);
  }
  return toks;
}


/** Analyse one form. Returns { respell, parts: [[symbol, explanation]] }. */
export function analyse(form, sys) {
  if (sys === "tang") return analyseTang(form);
  const toks = tokenize(form);
  const parts = [], seen = new Set();
  const add = (sym, txt) => { const k = sym + "|" + txt; if (!seen.has(k)) { seen.add(k); parts.push([sym, txt]); } };
  let out = "", depth = 0, optional = false, throaty = false, longV = false, sawVowel = false;
  const nextReal = (i) => { for (let j = i + 1; j < toks.length; j++) if (!/^[\])>]$/.test(toks[j])) return toks[j]; return ""; };
  const prevReal = (i) => { for (let j = i - 1; j >= 0; j--) if (!/^[\[(<]$/.test(toks[j])) return toks[j]; return ""; };
  const atEnd = (i) => { const n = nextReal(i); return !n || n === "-" || SUP[n] != null; };

  toks.forEach((tk, i) => {
    const b = tk[0];
    const voiceless = COMBINING_VOICELESS.test(tk);
    const nonsyl = tk.includes(NONSYL);
    if (tk === "*") { add("*", "reconstructed: worked out by comparison, not directly recorded"); return; }
    if (tk === "[") { depth++; add("[ ]", "uncertain: the evidence also allows a different sound here"); return; }
    if (tk === "]") { depth--; return; }
    if (tk === "(") { optional = true; add("( )", "may or may not have been present"); return; }
    if (tk === ")") { optional = false; return; }
    if (tk === "<" || tk === ">") { add("< >", "an infix: a sound inserted inside the word"); return; }
    if (tk === "-") { add("-", "a boundary between the root and a prefix or suffix"); out += "-"; return; }
    if (tk === ".") { add(".", "a loose “preinitial”: a lightly attached consonant before the main syllable, later lost"); return; }
    if (tk === "·") { add("·", "a loose preinitial consonant (Zhengzhang's notation), later lost"); return; }
    if (tk === "'" || tk === "ʼ") {
      if (sys === "zz" && prevReal(i).startsWith("l"))
        add("l'", "Zhengzhang's second l-sound, kept apart from plain l: it became t- / d- in Middle Chinese, where plain l became y-");
      else out += "'";
      return;
    }
    if (tk === "C") { add("C", "some consonant was here, but the evidence doesn't show which"); return; }
    if (tk === "N") { add("N", "a nasal consonant of uncertain type"); out += "n"; return; }
    if (SUP[tk] != null) {
      const n = SUP[tk];
      if (sys === "mc") add(tk, `tone ${n}: ${MC_TONE[n] || ""}`);
      else if (sys === "pm") add(tk, `tone category ${n} of the reconstruction (Middle Chinese 平 上 去 入, each split by the old voicing of the initial)`);
      return;
    }
    if (tk === "ʰ") { add("ʰ", "aspirated: a strong puff of air after the consonant (respelt h, so “th” is t + puff, not the th of “thin”)"); out += "h"; return; }
    if (tk === "ʷ") {
      if (sawVowel && atEnd(i) && /(ng|k)$/.test(out)) {   // rounded coda: heard as -wng / -wk
        add("ʷ", "the final consonant is lip-rounded, heard as a w before it (Baxter writes -wng, -wk)");
        out = out.replace(/(ng|k)$/, "w$1");
      } else { add("ʷ", "lip-rounded: said with rounded lips, like adding a w"); out += "w"; }
      return;
    }
    if (tk === "ʲ") { add("ʲ", "palatalised: with a y-like colour"); out += "y"; return; }
    if (tk === "ˤ") {
      throaty = true;
      add("ˤ", sys === "bs"
        ? "pharyngealised: the throat is tightened while saying the sound, giving a darker, deeper quality. It marks a “type A” syllable in Baxter–Sagart (type B syllables later gained a -y- glide)"
        : "pharyngealised: the throat is tightened, giving a darker, deeper quality");
      return;
    }
    if (tk === "ː") {
      longV = true;
      add("ː", sys === "zz"
        ? "a long vowel. Zhengzhang marks “type A” syllables with vowel length, where Baxter–Sagart writes pharyngealisation ˤ"
        : "a long vowel");
      return;
    }
    if (optional) {                         // uncertain extra sound: explain, don't respell
      const c = CONS[b] || VOWELS[b];
      if (c) add(`(${tk.normalize("NFC")})`, `possibly ${c[1]}`);
      return;
    }
    const sym = tk.normalize("NFC");
    if (AFFRICATES[tk]) { add(sym, AFFRICATES[tk][1]); out += AFFRICATES[tk][0]; return; }
    if (VOWELS[b] && !nonsyl) {
      sawVowel = true;
      add(sym, VOWELS[b][1]);
      let r = VOWELS[b][0];
      if (b === "a" && atEnd(i)) r = "ah";   // father-a; æ (cat) stays "a"
      if (r === "e" && atEnd(i)) r = "eh";
      out += r;
      return;
    }
    if (VOWELS[b] && nonsyl) {
      add(sym, `a short glide (${b === "i" ? "y" : "w"}), not a vowel of its own`);
      out += b === "i" ? "y" : b === "u" ? "w" : VOWELS[b][0];
      return;
    }
    const c = CONS[b];
    if (!c) { if (/\S/.test(b)) out += b; return; }
    const final = atEnd(i) && sawVowel;
    if (voiceless) {
      add(sym, `a voiceless ${c[0]}: breathed rather than voiced, like an h and ${c[0]} at once${b === "l" ? " (Welsh “ll”)" : ""}`);
      out += "h" + c[0];
      return;
    }
    // final consonants with a job of their own
    if (final && (sys === "bs" || sys === "zz") && b === "ʔ") {
      add("-ʔ", "a final glottal stop: the source of the later rising tone (上聲)"); out += "'"; return;
    }
    if (final && (sys === "bs" || sys === "zz") && b === "s") {
      add("-s", "a final -s suffix: the source of the later departing tone (去聲)"); out += "s"; return;
    }
    if (final && sys === "zz" && "bdgɡ".includes(b)) {
      add(`-${sym}`, `a final stop: Zhengzhang writes final stops as -b -d -ɡ (Baxter–Sagart -p -t -k); it was unreleased, like the k in “book” said without letting go`);
      out += { b: "p", d: "t", g: "k", "ɡ": "k" }[b];
      return;
    }
    if (final && "ptk".includes(b)) {
      add(`-${sym}`, `a final ${b}, unreleased (like the k in “book” said without letting go)${sys === "mc" || sys === "pm" ? ": the entering tone (入聲)" : ""}`);
      out += b; return;
    }
    if (final && b === "j") { add("-j", "a final -y glide, as in “boy”"); out += "y"; return; }
    if (final && b === "w") { add("-w", "a final -w glide, as in “cow”"); out += "w"; return; }
    if (!(sys === "zz" && b === "l" && /^['ʼ]$/.test(toks[i + 1] || ""))) add(sym, c[1]);   // l' explained as one
    out += c[0];
  });
  out = out.replace(/^-+|-+$/g, "").replace(/-{2,}/g, "-");
  const tags = [throaty && "throaty", longV && sys === "zz" && "long vowel"].filter(Boolean);
  return { respell: out + (tags.length ? ` · ${tags.join(", ")}` : ""), parts };
}

// ---------------------------------------------------------------- Tang --
// Stimson's Late Middle Chinese spelling (T'ang Poetic Vocabulary, 1976, as
// given in Unihan kTang). It is pinyin-like: b d g are PLAIN (unaspirated)
// p t k, p t k carry a puff of air, and bh dh gh are the voiced (濁) initials.
// Each initial's Middle Chinese value was checked against the 音韻地位 of the
// characters in this dataset. [spelling, respelling, explanation]
const TANG_INI = [
  ["jrh", "jr", "a voiced j with the tongue tip curled back (Middle Chinese 崇 initial)"],
  ["jh", "j", "a voiced j, as in “jeep” (Middle Chinese 船 initial)"],
  ["dzh", "dz", "dz, voiced (Middle Chinese 從 initial)"],
  ["djh", "d", "a voiced d with the tongue tip curled back (Middle Chinese 澄 initial)"],
  ["bh", "b", "a voiced b (Middle Chinese 並 initial); Stimson writes voiced sounds with h"],
  ["dh", "d", "a voiced d (Middle Chinese 定 initial)"],
  ["gh", "g", "a voiced g (Middle Chinese 羣 initial)"],
  ["dj", "t", "a plain t with the tongue tip curled back (Middle Chinese 知 initial)"],
  ["tj", "th", "an aspirated t with the tongue tip curled back (Middle Chinese 徹 initial)"],
  ["tz", "ts", "ts as in “cats”, no puff of air (Middle Chinese 精 initial)"],
  ["ts", "tsh", "ts with a puff of air (Middle Chinese 清 initial)"],
  ["ch", "chh", "ch with a puff of air (Middle Chinese 昌 / 初 initials)"],
  ["zh", "zh", "a voiced sh, like the s in “measure” (Middle Chinese 常 initial)"],
  ["sh", "sh", "sh as in “she” (Middle Chinese 書 / 生 initials)"],
  ["nj", "ny", "ny as in “canyon” (Middle Chinese 日 initial)"],
  ["ng", "ng", "ng as in “sing”, here at the start of a syllable (Middle Chinese 疑 initial)"],
  ["b", "p", "a plain p, no puff of air (Middle Chinese 幫 initial); Stimson spells it b, as pinyin does"],
  ["p", "ph", "p with a puff of air (Middle Chinese 滂 initial)"],
  ["d", "t", "a plain t, no puff of air (Middle Chinese 端 initial); spelt d, as in pinyin"],
  ["t", "th", "t with a puff of air (Middle Chinese 透 initial)"],
  ["g", "k", "a plain k, no puff of air (Middle Chinese 見 initial); spelt g, as in pinyin"],
  ["k", "kh", "k with a puff of air (Middle Chinese 溪 initial)"],
  ["j", "ch", "a plain ch, no puff of air (Middle Chinese 章 / 莊 initials); spelt j, as in pinyin"],
  ["q", "'", "a glottal stop, the catch in “uh-oh” (Middle Chinese 影 initial)"],
  ["x", "kh", "the rasping ch of Scottish “loch” (Middle Chinese 曉 initial)"],
  ["h", "h", "a voiced, breathy h (Middle Chinese 匣 / 云 initials)"],
  ["z", "z", "z as in “zoo” (Middle Chinese 邪 initial)"],
  ["s", "s", "s as in “see”"],
  ["m", "m", "m as in “me”"],
  ["n", "n", "n as in “no”"],
  ["l", "l", "l as in “leaf”"],
];
const TANG_V = {
  a: ["a", "a as in “father”"], "ɑ": ["ah", "a far back in the mouth, as in “spa”"],
  "æ": ["a", "a as in “cat”"], "ɛ": ["eh", "e as in “bed”"], E: ["eh", "an e-type vowel (Stimson's E)"],
  e: ["e", "e as in “bed”, a little closer (like French é)"], "ə": ["uh", "uh, the vowel in “about”"],
  i: ["ee", "ee as in “see”"], o: ["o", "a pure o, as in “go”"], u: ["oo", "oo as in “food”"],
};
const TANG_TONE = { "\u0300": ["◌̀", "a grave accent marks the departing tone (去聲)"],
                    "\u030C": ["◌̌", "a caron marks the rising tone (上聲)"] };

/** Unihan kTang can hold several space-separated readings, and lists a
 *  reading both with and without Stimson's * ("*qit qit"): split them, and
 *  show each reading once (starred if any copy is). */
export function tangReadings(rs) {
  const all = rs.flatMap((r) => r.t.split(/\s+/).filter(Boolean).map((t) => ({ ...r, t })));
  const starred = new Set(all.filter((r) => r.t.startsWith("*")).map((r) => r.t.slice(1)));
  return mergeForms(all.filter((r) => r.t.startsWith("*") || !starred.has(r.t)));
}

function analyseTang(form) {
  const parts = [], seen = new Set();
  const add = (sym, txt) => { const k = sym + "|" + txt; if (!seen.has(k)) { seen.add(k); parts.push([sym, txt]); } };
  let s = form.trim().normalize("NFD"), out = "", tone = "";
  if (s.startsWith("*")) {
    add("*", "Stimson's mark for a reading that is common in Tang poetry; here it does not mean “reconstructed”");
    s = s.slice(1);
  }
  const ini = TANG_INI.find(([sp]) => s.startsWith(sp) && !(sp === "ts" && s.startsWith("tsh")));
  if (ini) {
    add(ini[0], ini[2]); out += ini[1]; s = s.slice(ini[0].length);
    if (s.startsWith("r")) {        // shr, jr, chr…: the retroflex 莊 series
      add(ini[0] + "r", "r after the consonant: the tongue tip curled back (retroflex; Middle Chinese 莊 series)");
      out += "r"; s = s.slice(1);
    }
  }
  else if (/^[aɑæɛEeəiou]/.test(s)) add("(none)", "no initial consonant (Middle Chinese 以 initial, a y- sound)");
  let sawV = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (TANG_TONE[c]) { tone = c; add(...TANG_TONE[c]); continue; }
    if (c === "(" ) { const j = s.indexOf(")", i); add(s.slice(i, j + 1).normalize("NFC"), "may or may not have been present"); i = j; continue; }
    if (c === "y" || ((c === "i" || c === "u") && !sawV && /[aɑæɛEeəiou]/.test(s[i + 1] || "") && s[i + 1] !== c)) {
      add(c === "y" ? "y" : `${c}-`, `a short glide (${c === "u" ? "w" : "y"}) before the main vowel`);
      out += c === "u" ? "w" : "y"; continue;
    }
    const v = TANG_V[c];
    if (v) { sawV = true; add(c, v[1]); out += v[0]; continue; }
    const rest = s.slice(i);
    if (rest.startsWith("ng")) { add("-ng", "a final ng as in “sing”"); out += "ng"; i++; continue; }
    if ("ptk".includes(c)) { add(`-${c}`, `a final ${c}, unreleased (like the k in “book” said without letting go): the entering tone (入聲)`); out += c; continue; }
    if ("nm".includes(c)) { add(`-${c}`, `a final ${c}`); out += c; continue; }
    out += c;
  }
  // a vowel ending in i / u after the main vowel is a glide: respell -y / -w
  out = out.replace(/(a|ah|eh|e|uh|o)ee$/, "$1y").replace(/(a|ah|eh|e|uh|ee)oo$/, "$1w").replace(/ooo$/, "ou");
  if (!tone && !/[ptk]$/.test(out)) add("(no mark)", "no tone mark: the level tone (平聲)");
  return { respell: out + (tone ? ` · ${tone === "\u0300" ? "falling" : "rising"}` : ""), parts };
}

export const SYSTEM_NAME = { bs: "Baxter–Sagart", zz: "Zhengzhang", mc: "Middle Chinese (Baxter, IPA)", pm: "Proto-Min", tang: "Stimson (Tang)" };
