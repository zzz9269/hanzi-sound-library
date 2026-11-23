import * as D from "./data.js";
import * as A from "./audio.js";
import * as W from "./wikt.js";
import * as T from "./tree.js";
import * as N from "./notation.js";

// ---------------------------------------------------------------- helpers --
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const ICON = {
  play: '<svg viewBox="0 0 24 24"><path d="M7 4.5v15l13-7.5z"/></svg>',
  chev: '<svg viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg>',
  star: '<svg viewBox="0 0 24 24"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/></svg>',
  copy: '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
  share: '<svg viewBox="0 0 24 24"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',
  ext: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M4 5.5C6.5 4 9.5 4 12 5.5v14c-2.5-1.5-5.5-1.5-8 0z"/><path d="M20 5.5C17.5 4 14.5 4 12 5.5v14c2.5-1.5 5.5-1.5 8 0z"/></svg>',
};

let settings = Object.assign(
  { theme: "auto", ipa: true, en: true, hidden: [], readLang: "Mandarin", view: "list" },
  D.store.get("settings", {}));
function saveSettings() { D.store.set("settings", settings); applySettings(); }
function applySettings() {
  const root = document.documentElement;
  if (settings.theme === "auto") delete root.dataset.theme; else root.dataset.theme = settings.theme;
  try { localStorage.setItem("hz.theme", settings.theme); } catch { /* */ }
  document.body.classList.toggle("hide-ipa", !settings.ipa);
  document.body.classList.toggle("hide-en", !settings.en);
}

let toastTimer;
function toast(msg, ms = 2200) {
  const t = $("#toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), ms);
}
function hideToast() { clearTimeout(toastTimer); $("#toast")?.classList.remove("show"); }

/** Copy text; falls back to a hidden text box where the Clipboard API is blocked. */
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* fall back */ }
  const ta = document.createElement("textarea");
  ta.value = text; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
  document.body.appendChild(ta); ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  document.body.removeChild(ta);
  return ok;
}

const kangxi = (n) => (n >= 1 && n <= 214 ? String.fromCodePoint(0x2f00 + n - 1) : "");
const COL = (id) => D.cols()[D.colIdx(id)];
const SINITIC = () => D.cols().filter((c) => c.section === "sinitic");
const READ_LANGS = ["Mandarin", "Cantonese", "Hokkien", "Teochew", "Hakka", "Wu",
  "Eastern Min (Fuzhou)", "Northern Min (Jian'ou)", "Hainanese (Haikou)", "Hui (Shexian)",
  "Gan", "Xiang", "Jin", "Korean (Hangul)", "Vietnamese", "Japanese On",
  "Middle Chinese (Baxter)", "Old Chinese (Zhengzhang)"];
const LANG_NAME = {
  "Korean (Hangul)": "Korean", "Japanese On": "Japanese on'yomi",
  "Middle Chinese (Baxter)": "Middle Chinese", "Old Chinese (Zhengzhang)": "Old Chinese",
};
const langName = (id) => LANG_NAME[id] || COL(id)?.label || id;

// recent + saved
const recent = () => D.store.get("recent", []);
function pushRecent(ch) { D.store.set("recent", [ch, ...recent().filter((c) => c !== ch)].slice(0, 40)); }
const saved = () => D.store.get("saved", []);
function toggleSaved(ch) {
  const s = saved();
  const on = !s.includes(ch);
  D.store.set("saved", on ? [ch, ...s] : s.filter((c) => c !== ch));
  return on;
}

// ------------------------------------------------------------ play buttons --
const VOICE_NAME = { "zh-CN": "Mandarin", "zh-TW": "Mandarin", "zh-HK": "Cantonese",
  "ja-JP": "Japanese", "ko-KR": "Korean", "vi-VN": "Vietnamese" };
const noVoiceMsg = (lang) => `No ${VOICE_NAME[lang] || lang} voice on this device. Add one in your system's language or speech settings.`;
/** A device-voice button. Without a matching voice it stays clickable but
 *  greyed, and a tap explains why nothing plays. */
function ttsBtn(text, lang, { small = false, label = "Play" } = {}) {
  const ok = A.canSpeak(lang);
  return `<button class="play${small ? " small" : ""}${ok ? "" : " novoice"}" data-tts="${lang}" data-text="${esc(text)}"
    aria-label="${esc(label)}" ${ok ? "" : `aria-disabled="true" title="${esc(noVoiceMsg(lang))}"`}>${ICON.play}</button>`;
}
function urlBtn(urls, { small = false, label = "Play", gap = 0 } = {}) {
  const list = (Array.isArray(urls) ? urls : [urls]).filter(Boolean);
  if (!list.length) return "";
  return `<button class="play${small ? " small" : ""}" data-urls="${esc(JSON.stringify(list))}"${gap ? ` data-gap="${gap}"` : ""} aria-label="${esc(label)}" title="${esc(label)}">${ICON.play}</button>`;
}
function remoteHost(btn) {
  try {
    const u = new URL(JSON.parse(btn.dataset.urls || "[]")[0], location.href);
    return u.origin === location.origin ? "" : u.hostname.replace(/^(www|hapsing)\./, "");
  } catch { return ""; }
}

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest(".play");
  if (!btn || btn.disabled) return;
  ev.preventDefault(); ev.stopPropagation();
  if (btn.classList.contains("novoice")) {
    if (A.canSpeak(btn.dataset.tts)) { btn.classList.remove("novoice"); btn.removeAttribute("aria-disabled"); btn.removeAttribute("title"); }
    else { toast(noVoiceMsg(btn.dataset.tts), 4000); return; }
  }
  if (btn.classList.contains("playing") || btn.classList.contains("busy")) { A.stop(); return; }
  // recordings fetched from another site (mogher.com, ithuan.tw) can be slow:
  // say whose server we're waiting on, so it doesn't look like the app froze
  const host = remoteHost(btn);
  const slow = host && setTimeout(() => {
    if (btn.classList.contains("busy")) toast(`Waiting for ${host}…`);
  }, 1500);
  try {
    if (btn.dataset.tts) await A.speak(btn.dataset.text, btn.dataset.tts, { btn, rate: +(btn.dataset.rate || 0.9) });
    else if (btn.dataset.urls) await A.playUrls(JSON.parse(btn.dataset.urls), btn, { gap: +(btn.dataset.gap || 0) });
  } catch {
    toast(btn.dataset.tts ? `Your device's ${VOICE_NAME[btn.dataset.tts] || ""} voice didn't start. Try again, or check your speech settings.`
      : host ? `${host} didn't send the recording. Try again in a moment.`
      : "No recording available for this reading");
  } finally {
    clearTimeout(slow);
  }
});
document.addEventListener("voices-ready", () => {
  $$("button.play.novoice[data-tts]").forEach((b) => {
    if (A.canSpeak(b.dataset.tts)) { b.classList.remove("novoice"); b.removeAttribute("aria-disabled"); b.removeAttribute("title"); }
  });
});

// -------------------------------------------------------------- readings ----
const STRATUM = {
  v: ["白", "Vernacular (白讀): the everyday spoken reading"],
  l: ["文", "Literary (文讀): the reading used in formal words and when reciting classical texts"],
};
function readingHTML(r, { audio = "" } = {}) {
  const k = STRATUM[r.k];
  return `<span class="reading${r.m ? " ml" : ""}"><span class="t">${esc(r.t)}</span>`
    + (k ? `<span class="badge-k ${r.k}" title="${esc(k[1])}">${k[0]}</span>` : "")
    + (r.q ? `<span class="badge-q" title="Unverified spelling: from a survey spreadsheet that writes one letter for two vowels">?</span>` : "")
    + (r.m ? `<span class="badge-ml" title="Machine-predicted: inferred by a model, not attested in a source">ML</span>` : "")
    + (r.e ? `<span class="e">${esc(r.e)}</span>` : "") + (r.tag ? `<span class="tag">${esc(r.tag)}</span>` : "") + (r.rom ? `<span class="rom">${esc(r.rom)}</span>` : "") + audio + `</span>`;
}

function rowAudio(col, e, r) {
  if (r?.a) return urlBtn(A.keyUrl(r.a), { small: true, label: `Play ${r.t}` });
  return "";
}

function rowHTML(col, e, extra = "") {
  const k = D.colIdx(col.id);
  const roms = e.v?.[k] || [];
  const ipas = e.i?.[k] || [];
  if (!roms.length && !ipas.length) return "";
  let main = roms.length ? roms : ipas;
  const perReading = roms.some((r) => r.a);
  const items = main.map((r) => readingHTML(r, { audio: perReading ? rowAudio(col, e, r) : "" })).join("");
  let rowPlay = "";
  // a recording per reading beats the device voice reading the character
  if (!perReading && col.audio?.startsWith("tts:")) rowPlay = ttsBtn(e.ch, col.audio.slice(4), { small: true, label: `Play ${col.label}` });
  const ipaLine = roms.length && ipas.length
    ? `<div class="ipa-line"><span class="lbl">IPA</span>${ipas.map((r) =>
        `<span>${esc(r.t)}${r.m ? '<span class="badge-ml">ML</span>' : ""}</span>`).join("")}</div>` : "";
  return `<div class="rd-row">
    <div class="rd-label"><b>${esc(col.label)}</b><span class="native">${esc(col.native || "")}</span><span class="scheme">${esc(col.scheme || "")}</span></div>
    <div class="rd-vals"><div class="readings">${items}${rowPlay}</div>${ipaLine}${extra}</div>
  </div>`;
}

function simpleRow(label, native, scheme, inner) {
  return `<div class="rd-row"><div class="rd-label"><b>${esc(label)}</b><span class="native">${esc(native || "")}</span><span class="scheme">${esc(scheme || "")}</span></div>
    <div class="rd-vals">${inner}</div></div>`;
}

// ------------------------------------------------- Japanese / Korean text --
// Romaji is computed from each kana chip, so the romanisation always matches
// the reading it sits under (and what the voice is given to say).
const KANA = (() => {
  const rows = {
    "": "あいうえお", k: "かきくけこ", s: "さしすせそ", t: "たちつてと", n: "なにぬねの",
    h: "はひふへほ", m: "まみむめも", y: "や ゆ よ", r: "らりるれろ", w: "わゐ ゑを",
    g: "がぎぐげご", z: "ざじずぜぞ", d: "だぢづでど", b: "ばびぶべぼ", p: "ぱぴぷぺぽ",
  };
  const m = {};
  for (const [c, ks] of Object.entries(rows))
    [...ks].forEach((k, i) => { if (k !== " ") m[k] = c + "aiueo"[i]; });
  Object.assign(m, { し: "shi", ち: "chi", つ: "tsu", ふ: "fu", じ: "ji", ぢ: "ji", づ: "zu",
    ゐ: "i", ゑ: "e", を: "o", ん: "n", ぁ: "a", ぃ: "i", ぅ: "u", ぇ: "e", ぉ: "o" });
  return m;
})();
const SMALL_Y = { ゃ: "a", ゅ: "u", ょ: "o" };
const toHira = (s) => s.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
function kanaRomaji(kana) {
  const h = toHira(kana).replace(/[.\-・]/g, "");
  let out = "", dbl = false;
  for (let i = 0; i < h.length; i++) {
    const c = h[i];
    if (c === "っ") { dbl = true; continue; }
    if (c === "ー") { out += out.slice(-1); continue; }
    let r = KANA[c];
    if (r == null) { out += c; continue; }
    const sm = SMALL_Y[h[i + 1]];
    if (sm && r.endsWith("i") && r !== "i") {     // きゃ kya, しゃ sha, じゃ ja
      r = /^(sh|ch|j)/.test(r) ? r.slice(0, -1) + sm : r.slice(0, -1) + "y" + sm;
      i++;
    }
    if (dbl) { out += r.startsWith("ch") ? "t" : r[0]; dbl = false; }
    out += r;
  }
  return dbl ? out + "-" : out;     // ガッ: a geminating form (gat-, gak-)
}
const isKata = (s) => /[ァ-ヶ]/.test(s) && !/[ぁ-ゖ]/.test(s);

// Hangul syllable → Revised Romanization (single syllables, so no assimilation)
const RR_I = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"];
const RR_V = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"];
const RR_F = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"];
const hangulParts = (syl) => {
  const c = syl.codePointAt(0) - 0xac00;
  return c >= 0 && c < 11172 && syl.length === 1 ? [Math.floor(c / 588), Math.floor((c % 588) / 28), c % 28] : null;
};
const hangulRR = (s) => [...s].map((ch) => { const p = hangulParts(ch); return p ? RR_I[p[0]] + RR_V[p[1]] + RR_F[p[2]] : ch; }).join("");
// 두음법칙: at the start of a word, ㄹ → ㅇ before i / y-vowels and ㄴ elsewhere;
// ㄴ → ㅇ before i / y-vowels (룡 → 용, 로 → 노, 녀 → 여)
const Y_VOWEL = new Set([2, 3, 6, 7, 12, 17, 20]);
function dueum(syl) {
  const p = hangulParts(syl);
  if (!p) return syl;
  let [i, v, f] = p;
  if (i === 5) i = Y_VOWEL.has(v) ? 11 : 2;
  else if (i === 2 && Y_VOWEL.has(v)) i = 11;
  else return syl;
  return String.fromCharCode(0xac00 + i * 588 + v * 28 + f);
}

// on'yomi strata: when (and from where) each was borrowed
const JA_TYPE = { goon: "呉音 go-on", "kan'on": "漢音 kan-on", "tōon": "唐音 tō-on",
  "kan'yōon": "慣用音 kan'yō-on", soon: "宋音 sō-on", on: "" };
function sinoRows(e) {
  const out = [];
  const g = (id) => e.v?.[D.colIdx(id)] || [];
  const ja = g("Japanese"), on = g("Japanese On"), kun = g("Japanese Kun");
  if (ja.length || on.length || kun.length) {
    const chip = (r) => {
      const kana = r.t.replace(/[.\-]/g, "");
      return readingHTML({ ...r, rom: kanaRomaji(r.t) }, { audio: ttsBtn(kana, "ja-JP", { small: true, label: `Play ${r.t}` }) });
    };
    const roRow = (rs) => `<div class="readings">${rs.map((r) => readingHTML(r)).join("")}</div>`;
    let onK = ja.filter((r) => isKata(r.t)), kunK = ja.filter((r) => !isKata(r.t));
    // Wiktionary's kanji categories say which on'yomi is go-on, kan-on…; a
    // reading only Unihan lists (末 ベキ, ミャク) goes behind a fold
    const jt = e.jt || {};
    let onRare = [], kunRare = [];
    if (jt.o) {
      const typ = (r) => jt.o[r.t.replace(/[.\-]/g, "")];
      const order = ["goon", "kan'on", "tōon", "kan'yōon", "soon", "on"];
      onRare = onK.filter((r) => !typ(r));
      onK = onK.filter(typ).map((r) => ({ ...r, tag: JA_TYPE[typ(r)] || "" }))
        .sort((a, b) => order.indexOf(typ(a)) - order.indexOf(typ(b)));
    }
    if (jt.k) {
      const have = new Set(kunK.map((r) => r.t.replace(/[.\-]/g, "")));
      const att = new Set(jt.k);
      kunRare = kunK.filter((r) => !att.has(r.t.replace(/[.\-]/g, "")));
      kunK = [...kunK.filter((r) => att.has(r.t.replace(/[.\-]/g, ""))),
              ...jt.k.filter((k) => !have.has(k)).map((t) => ({ t }))];
    }
    const rare = (rs) => rs.length ? `<details class="ja-rare"><summary>${rs.length} more listed only in Unihan</summary><div class="readings">${rs.map(chip).join("")}</div><div class="muted" style="font-size:12.5px">Wiktionary doesn't list ${rs.length > 1 ? "these" : "this"} for the character: often a rare, historical or name reading.</div></details>` : "";
    const onBody = onK.length || onRare.length ? `<div class="readings">${onK.map(chip).join("")}</div>${rare(onRare)}` : on.length ? roRow(on) : "";
    const kunBody = kunK.length || kunRare.length ? `<div class="readings">${kunK.map(chip).join("")}</div>${rare(kunRare)}` : kun.length ? roRow(kun) : "";
    const joyo = jt.j ? " · 常用 jōyō kanji" : "";
    if (onBody) out.push(simpleRow("Japanese on'yomi", "音読み", "Sino-Japanese · borrowed from Chinese" + joyo, onBody));
    if (kunBody) out.push(simpleRow("Japanese kun'yomi", "訓読み", "native Japanese word · not from Chinese", kunBody));
  }
  const ko = g("Korean (Hangul)");
  if (ko.length) {
    // a ㄹ/ㄴ reading whose 두음법칙 form is also listed is that same reading as it
    // sounds INSIDE a word (공룡 gongnyong): note it on the word-initial chip
    const texts = new Set(ko.map((r) => r.t));
    const inner = new Map();
    ko.forEach((r) => { const d = dueum(r.t); if (d !== r.t && texts.has(d)) inner.set(d, r.t); });
    const chips = ko.filter((r) => ![...inner.values()].includes(r.t)).map((r) => {
      return readingHTML({ ...r, rom: hangulRR(r.t) },
        { audio: ttsBtn(r.t, "ko-KR", { small: true, label: `Play ${r.t}` }) });
    }).join("");
    const note = inner.size ? `<div class="ipa-line" style="display:flex"><span>${[...inner].map(([d, w]) =>
      `<span class="han">${esc(w)}</span> (${esc(hangulRR(w))}) and <span class="han">${esc(d)}</span> are one reading: South Korean writes and says ${esc(d)} at the start of a word (두음법칙) and ${esc(w)} inside one.`).join(" ")}</span></div>` : "";
    out.push(simpleRow("Korean", "한국어", "Hangul · Revised Romanization", `<div class="readings">${chips}</div>${note}`));
  }
  const vi = g("Vietnamese");
  if (vi.length) {
    out.push(simpleRow("Vietnamese", "Tiếng Việt", "Hán-Việt", `<div class="readings">${vi.map((r) =>
      readingHTML(r, { audio: r.a ? urlBtn(A.keyUrl(r.a), { small: true, label: `Play ${r.t}` }) : ttsBtn(r.t, "vi-VN", { small: true, label: `Play ${r.t}` }) })).join("")}</div>`));
  }
  for (const id of ["Okinawan", "Zhuang"]) {
    const c = COL(id);
    if (c && g(id).length) out.push(rowHTML(c, e));
  }
  return out.join("");
}

// A reconstruction chip: the form, its respelling (from notation.js, so it
// follows the system's own symbols) and any scholarly note under it.
function reconHTML(r, sys) {
  const { respell } = N.analyse(r.form, sys);
  return `<span class="reading recon${r.m ? " ml" : ""}"><span class="t">${esc(r.form)}</span>`
    + (r.m ? `<span class="badge-ml" title="Machine-predicted: inferred by a model, not attested in a source">ML</span>` : "")
    + (respell ? `<span class="e" title="Rough respelling for an English reader; open “What the symbols mean” for the real sounds">${esc(respell)}</span>` : "")
    + (r.notes?.length ? `<span class="recon-note" title="The reconstruction's own annotation">Note: ${r.notes.map(esc).join(" · ")}</span>` : "") + `</span>`;
}
// "What the symbols mean": one block per form, every symbol explained.
function symbolsFold(groups) {
  const blocks = groups.flatMap(([sys, label, rs]) => rs.map((r) => {
    const { parts } = N.analyse(r.form, sys);
    if (!parts.length) return "";
    return `<div class="sym-block"><div class="sym-form">${label ? `<span class="pill">${esc(label)}</span>` : ""}<b>${esc(r.form)}</b></div>
      <div class="breakdown">${parts.map(([sym, t]) => `<div><b>${esc(sym)}</b>${esc(t)}</div>`).join("")}</div></div>`;
  })).filter(Boolean);
  return blocks.length ? `<details class="note sym"><summary>What the symbols mean</summary>${blocks.join("")}</details>` : "";
}

function histRows(e) {
  const out = [];
  const g = (id) => e.v?.[D.colIdx(id)] || [];
  const n = (id) => e.n?.[D.colIdx(id)] || [];
  const oc = g("Old Chinese"), ocz = g("Old Chinese (Zhengzhang)");
  if (oc.length || ocz.length) {
    const bs = N.mergeForms(oc), zz = N.mergeForms(ocz);
    const line = (lab, rs, sys) => rs.length ? `<div class="readings"><span class="pill">${lab}</span>${rs.map((r) => reconHTML(r, sys)).join("")}</div>` : "";
    out.push(simpleRow("Old Chinese", "上古漢語", "~1000 BCE · two rival reconstructions",
      line("Baxter–Sagart", bs, "bs") + line("Zhengzhang", zz, "zz")
      + symbolsFold([["bs", "Baxter–Sagart", bs], ["zz", "Zhengzhang", zz]])));
  }
  const pm = g("Proto-Min");
  if (pm.length) {
    const conf = n("Proto-Min")[0]?.conf;
    const chip = conf != null
      ? `<span class="conf" style="background:${confColor(conf)}22;color:${confColor(conf)}" title="How far the Min daughter languages agree on the reconstructed vowel. Onset, coda and tone are anchored on Middle Chinese.">vowel ${Math.round(conf * 100)}%</span>` : "";
    out.push(simpleRow("Proto-Min", "原始閩語", "★ reconstructed here from the Min languages",
      `<div class="readings">${N.mergeForms(pm).map((r) => reconHTML(r, "pm")).join("")}${chip}</div>`
      + symbolsFold([["pm", "", N.mergeForms(pm)]])));
  }
  const mc = g("Middle Chinese"), mci = g("Middle Chinese (Baxter)");
  if (mc.length || mci.length) {
    out.push(simpleRow("Middle Chinese", "中古漢語", "~600 CE · Qieyun",
      `<div class="readings">${mc.map((r) => readingHTML(r)).join("")}</div>`
      + (mci.length ? `<div class="ipa-line" style="display:flex"><span class="lbl">IPA</span>${N.mergeForms(mci).map((r) => `<span>${esc(r.form)} <span style="color:var(--jade)">≈ ${esc(N.analyse(r.form, "mc").respell)}</span></span>`).join("")}</div>`
        + symbolsFold([["mc", "", N.mergeForms(mci)]]) : "")));
  }
  const pos = g("Middle Chinese (position)");
  if (pos.length) {
    const notes = n("Middle Chinese (position)");
    const body = notes.length ? notes.map((x) => `<details class="note"><summary><b class="han">${esc(x.code)}</b>${x.syl ? ` — sounded roughly like “${esc(x.syl)}”` : ""}</summary>
      <div class="breakdown">${x.parts.map(([gl, t]) => `<div><b>${esc(gl)}</b>${esc(t)}</div>`).join("")}</div></details>`).join("")
      : `<div class="readings">${pos.map((r) => `<span class="han">${esc(r.t)}</span>`).join(" · ")}</div>`;
    out.push(simpleRow("Rime position", "音韻地位", "tap to see what each part means", body));
  }
  const fq = g("Fanqie");
  if (fq.length) {
    const notes = n("Fanqie");
    const how = notes.map((x) => `<div class="note"><b class="han">${esc(x.u)}</b> gives the initial <code>${esc(x.i)}-</code> + <b class="han">${esc(x.l)}</b> gives the final <code>-${esc(x.f)}</code> and the ${esc(x.tone)} tone → <code>${esc(x.c)}</code>${x.ok ? ' <span class="ok">= its Middle Chinese ✓</span>' : ""}</div>`).join("");
    out.push(simpleRow("Fanqie", "反切", "how the Guangyun spells it",
      `<div class="readings">${fq.map((r) => `<span class="han" style="font-size:19px">${esc(r.t)}</span>`).join('<span class="muted">·</span>')}</div>${how}`));
  }
  const tang = g("Tang");
  if (tang.length) {
    // Unihan lists a reading both with and without Stimson's * (common in
    // Tang poetry): show it once, starred
    const rs = N.tangReadings(tang);
    const c = COL("Tang");
    out.push(simpleRow(c.label, c.native, "Stimson's spelling (1976)",
      `<div class="readings">${rs.map((r) => reconHTML(r, "tang")).join("")}</div>` + symbolsFold([["tang", "", rs]])));
  }
  return out.join("");
}
const confColor = (c) => (c >= 0.8 ? "#3f9a5a" : c >= 0.6 ? "#c08a24" : "#c4574a");

function localityHTML(e) {
  if (!e.l) return "";
  const cols = D.cols();
  const groups = {};
  for (const [k, rs] of Object.entries(e.l)) {
    const c = cols[k];
    (groups[c.branch] ||= []).push([c.label, rs]);
  }
  const names = Object.keys(groups).sort();
  const total = names.reduce((s, b) => s + groups[b].length, 0);
  const body = names.map((b) => `<div class="loc-branch">${esc(b)}</div><div class="loc-grid">${groups[b]
    .sort((x, y) => x[0].localeCompare(y[0]))
    .map(([place, rs]) => `<div class="loc"><b>${esc(place)}</b><span><span class="t">${rs.map((r) => esc(r.t)).join(" · ")}</span>${rs[0]?.e ? ` <span class="e">≈ ${esc(rs[0].e)}</span>` : ""}</span></div>`).join("")}</div>`).join("");
  return fold("loc", "地", "Local varieties", `${total} towns and cities, from dialect surveys`, body);
}

function fold(id, ico, title, sub, body = "") {
  return `<details class="fold card" data-fold="${id}"><summary><span class="ico">${ico}</span><span><span>${esc(title)}</span><br><span class="sub">${esc(sub)}</span></span><span class="chev">${ICON.chev}</span></summary><div class="fold-body">${body}</div></details>`;
}

// ------------------------------------------------------------- char view ----
async function charView(ch) {
  document.title = `${ch} · 漢字音庫`;
  if (!D.isHan(ch)) {
    view.innerHTML = `<div class="empty"><span class="han">?</span>“${esc(ch)}” isn't a Chinese character. <a href="#/s/${enc(ch)}">Search for “${esc(ch)}” instead</a>.</div>`;
    return;
  }
  view.innerHTML = `<div class="hero fade-in"><div class="hero-glyph">${esc(ch)}</div><div class="hero-main"><div class="skeleton" style="height:26px;width:60%"></div><div class="skeleton" style="height:16px;width:85%;margin-top:12px"></div></div></div>`;
  const e = await D.entry(ch);
  if (!e || (!e.v && !e.i && !e.d)) {
    view.innerHTML = `<div class="empty"><span class="han">${esc(ch)}</span>No readings recorded for this character yet.<br><a class="btn" style="margin-top:14px" href="${W.pageUrl(ch)}" target="_blank" rel="noopener">${ICON.ext} Try Wiktionary</a></div>`;
    return;
  }
  pushRecent(ch);
  document.title = `${ch} · 漢字音庫`;
  const k = e.k || [];
  const man = e.v?.[D.colIdx("Mandarin")] || [];
  const can = e.v?.[D.colIdx("Cantonese")] || [];
  const simp = D.toSimp(ch) !== ch ? D.toSimp(ch) : null;
  const isSaved = saved().includes(ch);
  const rank = k[2];
  const pills = [
    k[0] ? `<span class="pill">${k[0]} strokes</span>` : "",
    k[1] ? `<span class="pill">radical <span class="han">${kangxi(k[1])}</span> ${k[1]}</span>` : "",
    rank ? `<span class="pill ${rank <= 3500 ? "accent" : ""}">${rank <= 3500 ? "Common" : "Standard"} · #${rank}</span>` : "",
    `<span class="pill">U+${ch.codePointAt(0).toString(16).toUpperCase()}</span>`,
  ].join("");
  const hiddenIds = new Set(settings.hidden);
  const sin = SINITIC();
  const shownRows = sin.filter((c) => !hiddenIds.has(c.id)).map((c) => rowHTML(c, e)).filter(Boolean);
  const hiddenCols = sin.filter((c) => hiddenIds.has(c.id) && rowHTML(c, e));
  const hiddenRows = hiddenCols.map((c) => rowHTML(c, e));
  const sino = sinoRows(e), hist = histRows(e);
  const variant = e.from
    ? `<div class="variant-note">Readings that are only recorded under the traditional form <a href="#/c/${enc(e.from)}" class="han">${esc(e.from)}</a> are included.</div>`
    : simp ? `<div class="variant-note">Simplified form: <a href="#/c/${enc(simp)}" class="han">${esc(simp)}</a></div>` : "";

  view.innerHTML = `
  <article class="fade-in">
    <div class="hero">
      <h1 class="hero-glyph" lang="zh-Hant">${esc(ch)}</h1>
      <div class="hero-main">
        <div class="hero-readings">
          ${man.slice(0, 3).map((r) => `<span class="r">${esc(r.t)}</span>`).join("")}
          ${can.length ? `<span class="r" style="font-size:19px;color:var(--ink-2)">${esc(can.slice(0, 2).map((r) => r.t).join(" / "))}<small>Cantonese</small></span>` : ""}
        </div>
        ${e.d ? `<p class="hero-def">${esc(e.d)}</p>` : ""}
        <div class="hero-meta">${pills}</div>
      </div>
      ${variant}
      <div class="hero-actions">
        ${(man[0]?.a ? urlBtn(A.keyUrl(man[0].a), { label: `Play ${man[0].t}` }) : ttsBtn(ch, "zh-CN", { label: "Play Mandarin" })).replace('class="play"', 'class="play" style="width:38px;height:38px"')}
        <button class="btn ${isSaved ? "on" : ""}" id="save-btn">${ICON.star}<span>${isSaved ? "Saved" : "Save"}</span></button>
        <button class="btn" id="copy-btn">${ICON.copy}<span>Copy</span></button>
        ${navigator.share ? `<button class="btn" id="share-btn">${ICON.share}<span>Share</span></button>` : ""}
        <a class="btn ghost" href="${W.pageUrl(ch)}" target="_blank" rel="noopener">${ICON.ext}<span>Wiktionary</span></a>
      </div>
    </div>

    <div class="view-toggle" role="group" aria-label="Layout">
      <div class="seg" id="view-toggle">${[["list", "Readings"], ["tree", "Family tree"]].map(([v, t]) =>
        `<button data-v="${v}" class="${(settings.view === "tree") === (v === "tree") ? "on" : ""}" aria-pressed="${(settings.view === "tree") === (v === "tree")}">${t}</button>`).join("")}</div>
    </div>

    <section class="section" id="rd-tree" ${settings.view === "tree" ? "" : "hidden"}>
      <div class="section-head"><h2>How the readings evolved</h2><span class="han">語音演變</span></div>
      <div class="card tree-card">${T.treeHTML(e, ch)}</div>
    </section>

    <div id="rd-list" ${settings.view === "tree" ? "hidden" : ""}>
    ${shownRows.length ? `<section class="section"><div class="section-head"><h2>Spoken today</h2><span class="han">現代漢語方言</span><span class="spacer"></span><span class="muted" style="font-size:12.5px">${shownRows.length} varieties</span></div>
      <div class="card rows two">${shownRows.join("")}</div>
      ${hiddenRows.length ? `<details class="fold card" style="margin-top:10px"><summary><span>Hidden in Settings: ${esc(hiddenCols.map((c) => c.label).join(", "))} · <u>show</u></span><span class="chev">${ICON.chev}</span></summary><div class="fold-body rows two">${hiddenRows.join("")}</div></details>` : ""}
    </section>` : ""}

    ${sino ? `<section class="section"><div class="section-head"><h2>Across East Asia</h2><span class="han">漢字文化圈</span></div><div class="card rows two">${sino}</div></section>` : ""}

    ${hist ? `<section class="section"><div class="section-head"><h2>Through history</h2><span class="han">歷史音韻</span></div><div class="card rows">${hist}</div></section>` : ""}
    </div>

    <section class="section">
      ${localityHTML(e)}
      ${fold("glyph", "字", "Glyph origin", "How the character was formed · Wiktionary")}
      ${fold("ety", "源", "Etymology", "Where the word comes from · Wiktionary")}
      ${fold("sources", "據", "Sources", "Where every reading on this page comes from")}
    </section>
    ${footer()}
  </article>`;

  $("#save-btn").onclick = (ev) => {
    const on = toggleSaved(ch);
    ev.currentTarget.classList.toggle("on", on);
    ev.currentTarget.querySelector("span").textContent = on ? "Saved" : "Save";
    toast(on ? `Saved ${ch}` : `Removed ${ch}`);
  };
  $("#copy-btn").onclick = async () => {
    toast(await copyText(ch) ? `Copied ${ch}` : "This browser blocked copying. Select the character and copy it yourself.");
  };
  if ($("#share-btn")) $("#share-btn").onclick = () =>
    navigator.share({ title: `${ch} · 漢字音庫`, text: `${ch} ${man[0]?.t || ""} — ${e.d || ""}`, url: location.href }).catch(() => {});
  T.bindTree($("#rd-tree"), e);
  $$("#view-toggle button").forEach((b) => b.addEventListener("click", () => {
    settings.view = b.dataset.v; saveSettings();
    const tree = settings.view === "tree";
    $$("#view-toggle button").forEach((x) => {
      const on = (x.dataset.v === "tree") === tree;
      x.classList.toggle("on", on); x.setAttribute("aria-pressed", on);
    });
    $("#rd-tree").hidden = !tree; $("#rd-list").hidden = tree;
  }));
  bindLazyFolds(ch);
}

function bindLazyFolds(ch) {
  const lazy = {
    glyph: async () => {
      const html = await W.glyphOrigin(ch);
      return html ? `<div class="wikt">${html}<div class="wikt-src">From English Wiktionary · CC BY-SA 4.0</div></div>`
        : `<div class="loading">Wiktionary has no glyph-origin notes for ${esc(ch)}.</div>`;
    },
    ety: async () => {
      const parts = await W.etymology(ch);
      let last = "";
      return parts.length
        ? `<div class="wikt">${parts.map((x) => {
            const head = x.lang !== last ? `<h3 class="ety-lang"><a href="${W.pageUrl(ch, x.lang)}" target="_blank" rel="noopener">${esc(x.lang)}</a></h3>` : "";
            last = x.lang;
            return head + (x.title ? `<h4>${esc(x.title)}</h4>` : "") + x.html;
          }).join("")}<div class="wikt-src">From English Wiktionary · CC BY-SA 4.0 · <a href="${W.pageUrl(ch)}" target="_blank" rel="noopener">open the full page</a></div></div>`
        : `<div class="loading">Wiktionary has no etymology notes for ${esc(ch)}.</div>`;
    },
    sources: async () => {
      const rows = await D.provenance(ch);
      if (!rows.length) return `<div class="loading">No source records.</div>`;
      const label = (id) => id.startsWith("dial:") ? id.slice(5).replace("-", " · ") : (COL(id)?.label && COL(id).id === id ? `${COL(id).label}${COL(id).scheme ? ` (${COL(id).scheme})` : ""}` : id);
      return `<div class="prov-wrap"><table class="prov"><thead><tr><th>Variety</th><th>Reading</th><th>Source</th></tr></thead><tbody>${rows
        .map(([c, r, s, conf]) => `<tr class="${s === "ml" ? "ml" : ""}"><td>${esc(label(c))}</td><td class="r">${esc(r)}</td><td>${esc(s)}${conf != null && s === "ml" ? ` · ${Math.round(conf * 100)}%` : ""}</td></tr>`).join("")}</tbody></table></div>`;
    },
  };
  $$("details.fold[data-fold]").forEach((d) => {
    const fn = lazy[d.dataset.fold];
    if (!fn) return;
    d.addEventListener("toggle", async () => {
      if (!d.open || d.dataset.loaded) return;
      d.dataset.loaded = "1";
      const body = d.querySelector(".fold-body");
      body.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;
      try { body.innerHTML = await fn(); }
      catch { body.innerHTML = `<div class="loading">Couldn't reach Wiktionary. Check your connection and try again.</div>`; delete d.dataset.loaded; }
    });
  });
}

// ------------------------------------------------- phrase / ruby rendering --
const MIN_LANGS = new Set(["Hokkien", "Teochew"]);
// Word-level readings stored on each word's first character, per variety
// (Mandarin from CC-CEDICT/pypinyin; Cantonese and Taiwanese Hokkien from
// Wiktionary): 銀行 ngan4 hong4, 行長 hong4 zoeng2, 長大 zoeng2 daai6.
const WORD_KEY = { Mandarin: "x", Cantonese: "xy", Hokkien: "xh" };
const nfc = (t) => (t || "").normalize("NFC").toLowerCase();

/** First reading for a column at each position: [{ch, r, han, pos, poly, how}].
 *  A word reading wins over the character's first reading; a reading the
 *  user picked (`overrides`, keyed by pos) wins over both. `poly` marks a
 *  character whose reading was a guess among several. With `literary`,
 *  Hokkien/Teochew take the literary (文讀) reading where one is marked, as
 *  classical poems are recited (and colloquial word readings are skipped). */
function perChar(list, ents, colId, { literary = false, overrides = null, base = "" } = {}) {
  const k = D.colIdx(colId);
  const lit = literary && MIN_LANGS.has(colId);
  const ctx = WORD_KEY[colId] && !lit ? wordReadings(list, ents, WORD_KEY[colId]) : [];
  return list.map((ch, i) => {
    const e = ents[i];
    const rs = e?.v?.[k] || [];
    let r = e ? ((lit && rs.find((x) => x.k === "l")) || rs[0] || e.i?.[k]?.[0] || null) : null;
    let how = "";
    if (ctx[i]) { r = rs.find((x) => nfc(x.t) === nfc(ctx[i])) || { t: ctx[i] }; how = "word"; }
    const pos = `${base}${i}`;
    const o = overrides?.get(pos);
    if (o) { r = rs.find((x) => x.t === o) || { t: o }; how = "picked"; }
    return { ch, r, han: D.isHan(ch), pos, poly: !how && rs.length > 1, how, known: !!e };
  });
}

/** Readings that depend on the word (長城 cháng chéng, 銀行 yín háng):
 *  longest match over the words stored on each character's entry. */
function wordReadings(list, ents, key = "x") {
  const out = new Array(list.length).fill(null);
  for (let i = 0; i < list.length;) {
    const x = ents[i]?.[key];
    let py = null;
    if (x) {
      for (let L = Math.min(8, list.length - i); L >= 2 && !py; L--) {
        const hit = x[list.slice(i, i + L).join("")];
        if (hit) py = hit.split(" ");
      }
    }
    if (py && py.length) { py.forEach((p, j) => { out[i + j] = p; }); i += py.length; } else i++;
  }
  return out;
}

const CLAUSE_END = /[，,、；;：:。！？!?]/;
function rubyCell({ ch, r, han, pos, poly, known }) {
  if (!han) return `<span class="ruby punct"><span class="rt">&nbsp;</span><span class="rb">${esc(ch)}</span></span>`;
  const rt = r ? `<span class="rt${r.m ? " ml" : ""}${poly ? " poly" : ""}">${esc(r.t)}</span>`
    : `<span class="rt none">—</span>`;
  const en = r?.e ? `<span class="en">≈ ${esc(r.e)}</span>` : "";
  const tip = !r ? (known ? "No reading recorded in this variety" : "This character isn't in the dictionary yet")
    : poly ? "This character has other readings here: tap to choose" : "";
  return `<button class="ruby" data-ch="${esc(ch)}"${pos != null ? ` data-pos="${esc(pos)}"` : ""}${tip ? ` title="${esc(tip)}"` : ""}>${rt}<span class="rb">${esc(ch)}</span>${en}</button>`;
}
/** Characters with readings above. Punctuation sticks to the character
 *  before it so a line never starts with a comma; with `clauses`, each
 *  clause (，。 …) gets its own line, as poems are usually set. */
function rubyLine(cells, { clauses = false } = {}) {
  const groups = [];
  for (const c of cells) {
    if (!c.han && groups.length) groups[groups.length - 1].push(c);
    else groups.push([c]);
  }
  const lines = [[]];
  for (const g of groups) {
    lines[lines.length - 1].push(g);
    if (clauses && CLAUSE_END.test(g[g.length - 1].ch)) lines.push([]);
  }
  return lines.filter((l) => l.length).map((l) => `<div class="ruby-line">${l.map((g) =>
    g.length === 1 ? rubyCell(g[0]) : `<span class="rg">${g.map(rubyCell).join("")}</span>`).join("")}</div>`).join("");
}

/** Play button for a whole line in one language. */
function lineAudio(colId, cells, text) {
  const han = cells.filter((c) => c.han);
  const tts = { Mandarin: "zh-CN", Cantonese: "zh-HK", "Korean (Hangul)": "ko-KR", Vietnamese: "vi-VN" }[colId];
  if (colId === "Mandarin" || colId === "Cantonese") return ttsBtn(text, tts, { label: `Play in ${langName(colId)}` });
  if (colId === "Korean (Hangul)" || colId === "Vietnamese") {
    const t = han.map((c) => c.r?.t).filter(Boolean).join(" ");
    return t ? ttsBtn(t, tts, { label: `Play in ${langName(colId)}` }) : "";
  }
  if (MIN_LANGS.has(colId)) {
    // one syllable at a time, citation tone: no tone sandhi (see MIN_NOTE)
    const urls = han.map((c) => A.keyUrl(c.r?.a)).filter(Boolean);
    return urls.length ? urlBtn(urls, { gap: 180, label: `Play each syllable in ${langName(colId)} (citation tones, no sandhi)` }) : "";
  }
  return "";
}

/** Shown wherever Hokkien or Teochew is read as a phrase. */
const MIN_NOTE = `<p class="min-note">Read syllable by syllable in citation tones. In connected speech Min tones change before another syllable (tone sandhi). The app doesn't model that, so a phrase sounds like a list of single syllables.</p>`;

async function phraseView(text) {
  const list = D.chars(text.trim()).slice(0, 80);
  view.innerHTML = `<div class="loading"><span class="spinner"></span>Looking up ${esc(text)}…</div>`;
  const ents = await D.entries(list);
  document.title = `${text} · 漢字音庫`;
  const hidden = new Set(settings.hidden);
  const langs = [...SINITIC().map((c) => c.id).filter((id) => !hidden.has(id)),
                 "Korean (Hangul)", "Vietnamese", "Japanese On", "Middle Chinese (Baxter)"];
  const blocks = langs.map((id) => {
    const cells = perChar(list, ents, id);
    if (!cells.some((c) => c.r)) return "";
    const c = COL(id);
    return `<div class="lang-line"><div class="head"><b>${esc(langName(id))}</b><span class="native">${esc(c?.native || "")}</span><span class="spacer"></span>${lineAudio(id, cells, text)}</div>${rubyLine(cells)}${MIN_LANGS.has(id) && list.length > 1 ? MIN_NOTE : ""}</div>`;
  }).join("");
  view.innerHTML = `<article class="fade-in">
    <div class="phrase-hero">${list.map((ch) => D.isHan(ch) ? `<a href="#/c/${enc(ch)}" class="han">${esc(ch)}</a>` : `<span class="han" style="font-size:40px;color:var(--muted)">${esc(ch)}</span>`).join("")}</div>
    <p class="page-sub">Tap any character for its full page. Mandarin, Cantonese and Hokkien use the word's own reading where the dictionary has the word; <span class="poly-key">dotted</span> readings are a guess among several.</p>
    <div class="card">${blocks || `<div class="empty">No readings found.</div>`}</div>
    ${list.length > 6 ? `<p style="margin-top:14px"><a class="btn" href="#/read" id="open-reader">${ICON.book}<span>Open in the reader</span></a></p>` : ""}
    ${footer()}
  </article>`;
  const or = $("#open-reader");
  if (or) or.onclick = () => D.store.set("readDraft", text);
}

// ----------------------------------------------------------- search view ----
async function searchView(q) {
  view.innerHTML = `<div class="loading"><span class="spinner"></span>Searching…</div>`;
  const [byReading, byEnglish] = await Promise.all([D.searchReading(q), D.searchEnglish(q)]);
  const all = [...new Set([...byReading.map((x) => x.ch), ...byEnglish])];
  const ents = await D.entries(all);
  const E = Object.fromEntries(all.map((c, i) => [c, ents[i]]));
  const card = (ch, sub = "") => {
    const e = E[ch]; if (!e) return "";
    const p = (e.v?.[D.colIdx("Mandarin")] || [])[0]?.t || "";
    return `<a class="res" href="#/c/${enc(ch)}"><span class="g han">${esc(ch)}</span><span class="p">${esc(p)}</span><span class="d">${esc(e.d || "")}</span>${sub ? `<span class="c">${esc(sub)}</span>` : ""}</a>`;
  };
  // first 24 of each list, the rest behind "Show all"
  const paged = (cards, id) => cards.length <= 24 ? cards.join("")
    : cards.slice(0, 24).join("") + `<div class="more-wrap" id="${id}" hidden>${cards.slice(24).join("")}</div>`
      + `<button class="btn more-btn" data-more="${id}">Show all ${cards.length}</button>`;
  const rd = paged(byReading.map((x) => card(x.ch, x.col ? `${x.col.label}${x.col.scheme && x.col.section !== "local" ? " · " + x.col.scheme : ""}` : "")).filter(Boolean), "more-rd");
  const en = paged(byEnglish.map((c) => card(c)).filter(Boolean), "more-en");
  document.title = `${q} · 漢字音庫`;
  view.innerHTML = `<div class="fade-in">
    <h1 class="page-title">“${esc(q)}”</h1>
    ${rd ? `<section class="section"><div class="section-head"><h2>Characters read “${esc(q)}”</h2><span class="muted" style="font-size:12.5px">${byReading.length}</span></div><div class="results">${rd}</div></section>` : ""}
    ${en ? `<section class="section"><div class="section-head"><h2>Meaning “${esc(q)}”</h2><span class="muted" style="font-size:12.5px">${byEnglish.length}</span></div><div class="results">${en}</div></section>` : ""}
    ${!rd && !en ? `<div class="empty"><span class="han">無</span>Nothing found. Try a single English word (“moon”), a reading (“tian”, “jat1”, “then”) or paste Chinese characters.</div>` : ""}
    ${footer()}
  </div>`;
  $$("[data-more]").forEach((b) => b.addEventListener("click", () => {
    const box = $("#" + b.dataset.more);
    box.hidden = false; box.style.display = "contents"; b.remove();
  }));
}

// ------------------------------------------------------------ bottom sheet --
async function peek(ch, pos = null) {
  const sheet = $("#sheet"), bd = $("#sheet-backdrop");
  sheet.innerHTML = `<div class="grab"></div><div class="loading"><span class="spinner"></span></div>`;
  sheet.hidden = bd.hidden = false;
  const e = await D.entry(ch);
  if (!e) { sheet.innerHTML = `<div class="grab"></div><div class="empty">No data for ${esc(ch)}</div>`; return; }
  const ids = ["Mandarin", "Cantonese", "Hokkien", "Teochew", "Hakka", "Wu", "Korean (Hangul)", "Vietnamese", "Japanese On"];
  const rows = ids.map((id) => {
    const r = D.first(e, id);
    if (!r) return "";
    const all = (e.v?.[D.colIdx(id)] || []).slice(0, 3).map((x) => x.t).join(" · ") || r.t;
    return `<div><b>${esc(langName(id))}</b><span class="t">${esc(all)}</span></div>`;
  }).join("");
  // on the Read page: let the reader pick which reading this character has here
  let choose = "";
  if (pos != null && readerCtx) {
    const rs = e.v?.[D.colIdx(readerCtx.lang)] || [];
    const curT = readerCtx.out.querySelector(`button.ruby[data-pos="${CSS.escape(pos)}"] .rt`)?.textContent;
    if (rs.length > 1) {
      choose = `<div class="peek-choose"><div class="eyebrow">Reading here in ${esc(langName(readerCtx.lang))}</div><div class="chips">${rs.map((r) =>
        `<button class="chip-btn${r.t === curT ? " on" : ""}" data-pick="${esc(r.t)}">${esc(r.t)}${r.k === "l" ? " 文" : r.k === "v" ? " 白" : ""}</button>`).join("")}</div></div>`;
    }
  }
  sheet.innerHTML = `<div class="grab"></div>
    <div class="peek-head"><span class="g">${esc(ch)}</span><div><div style="font-size:15px;color:var(--ink-2)">${esc(e.d || "")}</div>
    <div class="row-flex" style="margin-top:10px">${ttsBtn(ch, "zh-CN", { label: "Play Mandarin" })}<a class="btn primary" href="#/c/${enc(ch)}">Open full page</a></div></div></div>
    ${choose}<div class="peek-list">${rows}</div>`;
  sheet.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => {
    pickReading(pos, b.dataset.pick); closeSheet();
  }));
}
function closeSheet() { $("#sheet").hidden = true; $("#sheet-backdrop").hidden = true; }
$("#sheet-backdrop").addEventListener("click", closeSheet);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
document.addEventListener("click", (ev) => {
  const r = ev.target.closest("button.ruby[data-ch]");
  if (!r) return;
  if (r.closest(".recite, .recite-chars") && !r.classList.contains("peek")) { r.classList.add("peek"); return; }
  peek(r.dataset.ch, readerCtx?.out?.contains(r) ? r.dataset.pos : null);
});

// ------------------------------------------------------------------ reader --
// The reading on screen, so a tapped character can be given another reading.
let readerCtx = null;     // { lang, overrides: Map, E, literary, out }
const SENT_RE = /[^。！？；!?;\n]+[。！？；!?;]?/g;
function langSelect(id, value) {
  return `<select class="select" id="${id}">${READ_LANGS.filter((l) => COL(l)).map((l) =>
    `<option value="${esc(l)}" ${l === value ? "selected" : ""}>${esc(langName(l))}${COL(l)?.audio || ["Hokkien", "Teochew"].includes(l) ? "  🔊" : ""}</option>`).join("")}</select>`;
}

async function renderReading(text, lang, out, { big = false, literary = false } = {}) {
  const sentences = (text.match(SENT_RE) || []).map((s) => s.trim()).filter(Boolean);
  const all = [...new Set(D.chars(text).filter(D.isHan))];
  out.innerHTML = `<div class="loading"><span class="spinner"></span>Reading ${all.length} characters…</div>`;
  const ents = await D.entries(all);
  const E = Object.fromEntries(all.map((c, i) => [c, ents[i]]));
  const ctx = readerCtx = { lang, overrides: new Map(), E, literary, out };
  const sentenceHTML = (s, si) => {
    const list = D.chars(s);
    const cells = perChar(list, list.map((c) => E[c] || null), lang, { literary, overrides: ctx.overrides, base: `${si}:` });
    return `<div class="sentence"><div class="${big ? "big-ruby" : ""}">${rubyLine(cells, { clauses: big })}</div><div>${lineAudio(lang, cells, s)}</div></div>`;
  };
  const note = !MIN_LANGS.has(lang) ? ""
    : `<div class="sentence min">${literary
        ? MIN_NOTE.replace("</p>", " Literary (文讀) readings are used where known, as classical poems are recited.</p>")
        : MIN_NOTE}</div>`;
  if (!sentences.length) { out.innerHTML = `<div class="empty">Paste or type some Chinese text above.</div>`; return; }
  // long texts: draw the first part at once, the rest in batches, so a pasted
  // chapter doesn't freeze the page
  const BATCH = 60;
  out.innerHTML = note + sentences.slice(0, BATCH).map(sentenceHTML).join("");
  for (let i = BATCH; i < sentences.length; i += BATCH) {
    await new Promise((r) => setTimeout(r, 0));
    if (readerCtx !== ctx) return;                    // a newer reading replaced this one
    out.insertAdjacentHTML("beforeend", sentences.slice(i, i + BATCH).map((s, j) => sentenceHTML(s, i + j)).join(""));
  }
}

/** Give one character on the Read page another reading (from the peek sheet). */
function pickReading(pos, t) {
  const ctx = readerCtx;
  if (!ctx) return;
  ctx.overrides.set(pos, t);
  const btn = ctx.out.querySelector(`button.ruby[data-pos="${CSS.escape(pos)}"]`);
  if (!btn) return;
  const e = ctx.E[btn.dataset.ch];
  const rs = e?.v?.[D.colIdx(ctx.lang)] || [];
  const r = rs.find((x) => x.t === t) || { t };
  btn.outerHTML = rubyCell({ ch: btn.dataset.ch, r, han: true, pos, poly: false, known: !!e });
}

async function readView(fromUrl = "") {
  document.title = "Read · 漢字音庫";
  const draft = fromUrl || D.store.get("readDraft", "");
  const samples = await D.passages().catch(() => []);
  view.innerHTML = `<div class="fade-in">
    <h1 class="page-title">Read</h1>
    <p class="page-sub">Paste any Chinese text and read it in the variety you choose, with a reading over every character. Tap a character to look it up.</p>
    <div class="card pad reader-controls">
      <label class="field">Text<textarea class="input" id="rd-text" lang="zh" placeholder="今天天氣很好，我想去公園散步。">${esc(draft)}</textarea></label>
      <div class="stack">
        <label class="field">Read in${langSelect("rd-lang", settings.readLang)}</label>
        <label class="field">Sample passage<select class="select" id="rd-sample"><option value="">Choose a sample…</option>${samples.map((s, i) => `<option value="${i}">${esc(s.title)}</option>`).join("")}</select></label>
      </div>
    </div>
    <div class="card reader-out" id="rd-out"></div>
    ${footer()}
  </div>`;
  const ta = $("#rd-text"), sel = $("#rd-lang"), out = $("#rd-out");
  const go = () => {
    D.store.set("readDraft", ta.value);
    // keep the text in the address too, so a reload or a shared link reopens it
    const t = ta.value.trim();
    history.replaceState(null, "", t && t.length <= 1500 ? `#/read/${enc(t)}` : "#/read");
    settings.readLang = sel.value; saveSettings();
    renderReading(ta.value || "今天天氣很好，我想去公園散步。你要不要一起來？", sel.value, out);
  };
  let t;
  ta.addEventListener("input", () => { clearTimeout(t); t = setTimeout(go, 450); });
  sel.addEventListener("change", go);
  $("#rd-sample").addEventListener("change", (ev) => {
    const s = samples[+ev.target.value];
    if (s) { ta.value = s.text; go(); }
  });
  go();
}

// ------------------------------------------------------------------- poems --
// The poem source marks taboo-avoided characters (避諱) restored by the
// editors in brackets: [玄]宗. Show the character, marked, without brackets.
const TABOO_TIP = "Restored character: the source edition avoided it (避諱, a name taboo) and the editors put it back";
const tabooHTML = (t) => esc(t).replace(/\[([^\]]{1,4})\]/g, `<span class="taboo" title="${TABOO_TIP}">$1</span>`);
const unbracket = (t) => (t || "").replace(/\[([^\]]{1,4})\]/g, "$1");
const savedPoems = () => D.store.get("savedPoems", []);

const ANTH_ICON = { "唐詩三百首": "唐", "宋詞三百首": "宋", "詩經": "詩", "蒙學": "蒙" };
async function poemsView(anth) {
  document.title = "Poems · 漢字音庫";
  view.innerHTML = `<div class="loading"><span class="spinner"></span>Loading the library…</div>`;
  const poems = await D.poems();
  const anths = [...new Set(poems.map((p) => p.anthology))];
  const cur = anth && anths.includes(anth) ? anth : D.store.get("anth", anths[0]);
  view.innerHTML = `<div class="fade-in">
    <h1 class="page-title">Poems</h1>
    <p class="page-sub">Classical poetry to read aloud in any variety: the 300 Tang poems, 300 Song lyrics, the Book of Songs and the classic primers.</p>
    <div class="toolbar"><div class="seg" id="anth">${anths.map((a) => `<button data-a="${esc(a)}" class="${a === cur ? "on" : ""}"><span class="han">${esc(a)}</span></button>`).join("")}</div>
    <input class="input" id="poem-q" placeholder="Search title, author or a line: 李白, 静夜思…" style="max-width:320px" aria-label="Search poems">
    <select class="select" id="poem-author" style="max-width:220px" aria-label="Filter by author"></select>
    <select class="select" id="poem-sort" style="max-width:180px" aria-label="Sort poems"><option value="">Book order</option><option value="author">By author</option><option value="title">By title</option></select></div>
    <div class="card poem-list" id="plist" style="margin-top:14px"></div>
    ${footer()}
  </div>`;
  const list = $("#plist"), q = $("#poem-q"), au = $("#poem-author"), so = $("#poem-sort");
  let current = cur;
  const fillAuthors = () => {
    const n = {};
    poems.filter((p) => p.anthology === current).forEach((p) => { const a = unbracket(p.author); n[a] = (n[a] || 0) + 1; });
    const names = Object.keys(n).sort((a, b) => n[b] - n[a] || a.localeCompare(b, "zh-Hant"));
    au.innerHTML = `<option value="">All authors (${names.length})</option>` + names.map((a) => `<option value="${esc(a)}">${esc(a)} · ${n[a]}</option>`).join("");
  };
  const draw = () => {
    const raw = q.value.trim();
    // simplified input finds traditional titles (静夜思 → 靜夜思)
    const keys = [...new Set([raw, D.chars(raw).map(D.toTrad).join("")])].filter(Boolean);
    const hit = (t) => keys.some((k) => unbracket(t).includes(k));
    let pool = poems.filter((p) => p.anthology === current && (!au.value || unbracket(p.author) === au.value)
      && (!keys.length || hit(p.title) || hit(p.author) || p.lines.some(hit)));
    if (so.value) pool = [...pool].sort((a, b) => unbracket(a[so.value]).localeCompare(unbracket(b[so.value]), "zh-Hant"));
    list.innerHTML = pool.length ? pool.slice(0, 400).map((p) => `<a class="poem-item" href="#/poem/${p.id}"><b>${tabooHTML(p.title)}</b><span>${tabooHTML(p.author)}</span><small>${tabooHTML(p.lines[0] || "")}</small></a>`).join("")
      : `<div class="empty">No poems match.</div>`;
  };
  fillAuthors();
  au.addEventListener("change", draw);
  so.addEventListener("change", draw);
  $("#anth").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-a]"); if (!b) return;
    current = b.dataset.a; D.store.set("anth", current);
    $$("#anth button").forEach((x) => x.classList.toggle("on", x === b));
    fillAuthors(); draw();
  });
  q.addEventListener("input", draw);
  draw();
}

async function poemView(id) {
  const poems = await D.poems();
  const p = poems.find((x) => x.id === id);
  if (!p) { view.innerHTML = `<div class="empty">Poem not found.</div>`; return; }
  document.title = `${unbracket(p.title)} · 漢字音庫`;
  const isSaved = savedPoems().includes(p.id);
  const hasTaboo = /\[[^\]]{1,4}\]/.test([p.title, p.author, ...p.lines].join(""));
  view.innerHTML = `<article class="fade-in">
    <div class="row-flex" style="margin-bottom:6px"><a class="btn ghost" href="#/poems">← All poems</a><span class="spacer"></span>
      <button class="btn ${isSaved ? "on" : ""}" id="save-poem">${ICON.star}<span>${isSaved ? "Saved" : "Save"}</span></button></div>
    <div class="poem-head"><h1>${tabooHTML(p.title)}</h1><p class="han">${tabooHTML(p.author)} · ${esc(p.anthology)}</p></div>
    <div class="toolbar" style="justify-content:center">
      <div style="min-width:200px">${langSelect("pm-lang", settings.readLang)}</div>
      <div class="seg" id="recite"><button data-r="" class="on">Read</button><button data-r="recite">Hide readings</button><button data-r="recite-chars">Hide characters</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="pm-out"></div>
    ${p.note ? `<p class="note" style="margin-top:14px">${esc(p.note)}</p>` : ""}
    ${hasTaboo ? `<p class="note muted" style="margin-top:10px"><span class="taboo">Underlined</span> characters were avoided in the source edition (避諱, a name taboo) and restored by its editors.</p>` : ""}
    ${footer()}
  </article>`;
  const out = $("#pm-out"), sel = $("#pm-lang");
  const go = () => { settings.readLang = sel.value; saveSettings(); renderReading(p.lines.map(unbracket).join("\n"), sel.value, out, { big: true, literary: true }); };
  $("#save-poem").onclick = (ev) => {
    const list = savedPoems(), on = !list.includes(p.id);
    D.store.set("savedPoems", on ? [p.id, ...list] : list.filter((x) => x !== p.id));
    ev.currentTarget.classList.toggle("on", on);
    ev.currentTarget.querySelector("span").textContent = on ? "Saved" : "Save";
    toast(on ? `Saved ${unbracket(p.title)}` : `Removed ${unbracket(p.title)}`);
  };
  sel.addEventListener("change", go);
  $("#recite").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-r]"); if (!b) return;
    $$("#recite button").forEach((x) => x.classList.toggle("on", x === b));
    out.classList.remove("recite", "recite-chars");
    $$(".ruby.peek", out).forEach((r) => r.classList.remove("peek"));
    if (b.dataset.r) out.classList.add(b.dataset.r);
  });
  go();
}

// ----------------------------------------------------------- saved/settings --
async function savedView() {
  document.title = "Saved · 漢字音庫";
  const s = saved(), r = recent(), sp = savedPoems();
  const allPoems = sp.length ? await D.poems().catch(() => []) : [];
  const poemById = Object.fromEntries(allPoems.map((x) => [x.id, x]));
  const chip = (c) => `<a class="char-chip" href="#/c/${enc(c)}">${esc(c)}</a>`;
  const langs = SINITIC();
  const hidden = new Set(settings.hidden);
  view.innerHTML = `<div class="fade-in">
    <h1 class="page-title">Saved</h1>
    <div class="card pad"><div class="eyebrow" style="margin-bottom:10px">Saved characters</div>
      ${s.length ? `<div class="chips">${s.map(chip).join("")}</div>` : `<p class="muted" style="margin:0">Tap ★ Save on any character to keep it here.</p>`}</div>
    <div class="card pad" style="margin-top:14px"><div class="eyebrow" style="margin-bottom:10px">Saved poems</div>
      ${sp.length ? `<div class="poem-list">${sp.map((id) => poemById[id]).filter(Boolean).map((x) => `<a class="poem-item" href="#/poem/${x.id}"><b>${tabooHTML(x.title)}</b><span>${tabooHTML(x.author)}</span></a>`).join("")}</div>`
        : `<p class="muted" style="margin:0">Tap ★ Save on any poem to keep it here.</p>`}</div>
    <div class="card pad" style="margin-top:14px"><div class="eyebrow" style="margin-bottom:10px">Recently viewed</div>
      ${r.length ? `<div class="chips">${r.map(chip).join("")}</div>` : `<p class="muted" style="margin:0">Characters you look up appear here.</p>`}</div>
    <div class="row-flex" style="margin-top:12px;gap:8px">
      <button class="btn" id="export-btn">Export saved list</button>
      <label class="btn" style="cursor:pointer">Import…<input type="file" id="import-file" accept="application/json,.json" hidden></label>
    </div>

    <section class="section"><div class="section-head"><h2>Settings</h2></div>
    <div class="card settings">
      <div class="setting"><div class="txt"><b>Appearance</b><span>Follow the system, or pick one</span></div>
        <div class="seg" id="theme">${["auto", "light", "dark"].map((t) => `<button data-t="${t}" class="${settings.theme === t ? "on" : ""}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div></div>
      <label class="setting" for="set-ipa"><span class="txt"><b>Show IPA</b><span>Phonetic transcription under each romanised reading</span></span>
        <span class="switch"><input type="checkbox" role="switch" id="set-ipa" ${settings.ipa ? "checked" : ""}><span></span></span></label>
      <label class="setting" for="set-en"><span class="txt"><b>Show ≈ English hints</b><span>A rough English sounds-like for each reading</span></span>
        <span class="switch"><input type="checkbox" role="switch" id="set-en" ${settings.en ? "checked" : ""}><span></span></span></label>
      <div class="setting" style="display:block"><div class="txt"><b>Varieties shown first</b><span>Tap to hide the ones you don't need; hidden ones stay one tap away.</span></div></div>
      <div class="lang-toggles" id="langs">${langs.map((c) => `<button data-id="${esc(c.id)}" class="${hidden.has(c.id) ? "" : "on"}" aria-pressed="${!hidden.has(c.id)}">${esc(c.label)} <span class="han">${esc(c.native)}</span></button>`).join("")}</div>
      <div class="setting"><div class="txt"><b>Use offline</b><span id="off-txt">Save every reading on this device (about ${Math.round((D.meta().offlineBytes || 0) / 1e6)} MB) so lookups work with no connection. Audio and Wiktionary still need the internet.</span></div>
        <span class="row-flex" style="gap:6px;flex:none"><button class="btn" id="off-btn" ${navigator.serviceWorker?.controller ? "" : "disabled"}>Download</button>
        <button class="btn ghost" id="off-rm" hidden>Remove</button></span></div>
    </div></section>

    <section class="section"><div class="section-head"><h2>About</h2></div>
    <div class="card pad note">
      <p style="margin-top:0"><b>漢字音庫</b> brings together the pronunciations of ${D.meta().chars.toLocaleString()} Chinese characters across ${langs.length} Sinitic varieties, ${Object.keys(D.cols().reduce((a, c) => (c.section === "local" ? (a[c.id] = 1, a) : a), {})).length} local dialect points, Middle and Old Chinese, and Japanese, Korean and Vietnamese.</p>
      <p>Readings come from Unihan, Wiktionary, kaikki.org, MCPDict (漢字音典), Baxter–Sagart, ytenx and qieyun-data. Readings marked <span class="badge-ml">ML</span> are predicted by a model, not attested. Hokkien readings are Taiwanese and Teochew readings are Swatow (Shantou), from Wiktionary's place-tagged readings, with dialect surveys for characters it lacks. Teochew audio is from <a href="https://www.mogher.com" target="_blank" rel="noopener">mogher.com</a>, recorded by a Chaozhou-city speaker, so a few vowels differ from Swatow (Chaozhou -iêng / -uêng for Swatow -iang / -uang). Taiwanese Hokkien audio is ithuan.tw's <a href="https://ithuan.tw" target="_blank" rel="noopener">SuiSiann</a> voice. Both play one syllable at a time in citation tone: tone sandhi isn't applied. Mandarin syllables are recorded by Chen Wang (<a href="https://github.com/hugolpz/audio-cmn" target="_blank" rel="noopener">audio-cmn</a>, CC BY-SA). Vietnamese syllables are recorded by a Hanoi speaker on Lingua Libre (CC0), available for about one reading in five. Other voices are your device's own (<a href="https://github.com/zzz9269/hanzi-sound-library/blob/main/web/audio/CREDITS.md" target="_blank" rel="noopener">audio credits</a>).</p>
      <p style="margin-bottom:0">Data built ${esc(D.meta().built)} · <a href="https://github.com/zzz9269/hanzi-sound-library" target="_blank" rel="noopener">Source code and data credits</a></p>
    </div></section>
  </div>`;
  $("#theme").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-t]"); if (!b) return;
    settings.theme = b.dataset.t; saveSettings();
    $$("#theme button").forEach((x) => x.classList.toggle("on", x === b));
  });
  const offBtn = $("#off-btn");
  if (!navigator.serviceWorker?.controller) offBtn.title = "Available in the installed app (or after one reload)";
  const offV = D.store.get("offlineV", "");
  const offRm = $("#off-rm");
  if (offV === D.meta().v) { offBtn.textContent = "Downloaded ✓"; offRm.hidden = false; }
  else if (offV) { offBtn.textContent = "Update"; offBtn.title = "The dictionary has changed since you downloaded it"; offRm.hidden = false; }
  offRm.onclick = () => {
    navigator.serviceWorker?.controller?.postMessage({ type: "clear-offline" });
    D.store.set("offlineV", "");
    offBtn.textContent = "Download"; offRm.hidden = true;
    toast("Offline data removed");
  };
  offBtn.onclick = () => {
    const sw = navigator.serviceWorker?.controller;
    if (!sw) return;
    offBtn.disabled = true; offBtn.textContent = "Starting…";
    sw.postMessage({ type: "prefetch", urls: D.offlineUrls() });
  };
  $("#export-btn").onclick = () => {
    const blob = new Blob([JSON.stringify({ app: "hanzi-sound-library", saved: saved(), savedPoems: savedPoems(), recent: recent() }, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "hanzi-saved.json";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  $("#import-file").onchange = async (ev) => {
    const f = ev.target.files?.[0]; if (!f) return;
    try {
      const j = JSON.parse(await f.text());
      const merge = (key, list) => Array.isArray(list) && D.store.set(key, [...new Set([...D.store.get(key, []), ...list.filter((x) => typeof x === "string")])]);
      merge("saved", j.saved); merge("savedPoems", j.savedPoems);
      toast("Imported"); savedView();
    } catch { toast("That file isn't a saved-list export"); }
  };
  $("#set-ipa").onchange = (ev) => { settings.ipa = ev.target.checked; saveSettings(); };
  $("#set-en").onchange = (ev) => { settings.en = ev.target.checked; saveSettings(); };
  $("#langs").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-id]"); if (!b) return;
    const id = b.dataset.id;
    const h = new Set(settings.hidden);
    if (h.has(id)) h.delete(id); else h.add(id);
    settings.hidden = [...h]; saveSettings();
    b.classList.toggle("on", !h.has(id)); b.setAttribute("aria-pressed", !h.has(id));
  });
}

// ------------------------------------------------------------------- home ---
function homeView() {
  document.title = "漢字音庫 · Hanzi Sound Library";
  const common = D.meta().common || "";
  const day = Math.floor(Date.now() / 864e5);
  const daily = D.chars(common)[(day * 7919) % Math.max(1, D.chars(common).length)] || "音";
  const r = recent().slice(0, 16);
  view.innerHTML = `<div class="fade-in">
    <div class="home-hero">
      <div class="big-seal">音</div>
      <h1>漢字音庫</h1>
      <p>How every Chinese character sounds, in Mandarin, Cantonese, Hokkien, Teochew, Hakka, Wu and more, through Middle and Old Chinese, and in Japanese, Korean and Vietnamese.</p>
      <div class="try">
        ${["天", "葉", "行", "愛", "龍"].map((c) => `<a href="#/c/${enc(c)}"><span class="han">${c}</span></a>`).join("")}
        <a href="#/p/${enc("你好")}"><span class="han">你好</span></a>
        <a href="#/p/${enc("飲茶")}"><span class="han">飲茶</span></a>
        <a href="#/s/moon">moon</a><a href="#/s/tian">tian</a>
      </div>
    </div>
    <div class="home-grid">
      <a class="card pad daily" href="#/c/${enc(daily)}" id="daily">
        <span class="glyph">${esc(daily)}</span>
        <span><span class="eyebrow">Character of the day</span><br><span id="daily-r" class="ipa" style="font-size:20px"></span><br><span id="daily-d" class="muted"></span></span>
      </a>
      <div class="tiles">
        <a class="tile" href="#/read"><span class="han">讀</span><b>Read</b><span>Any text, with readings over every character</span></a>
        <a class="tile" href="#/poems"><span class="han">詩</span><b>Poems</b><span>Tang & Song poetry, recite mode</span></a>
        <a class="tile" href="#/s/water"><span class="han">英</span><b>Search English</b><span>Find characters by meaning</span></a>
        <a class="tile" href="#/saved"><span class="han">藏</span><b>Saved</b><span>Your characters and settings</span></a>
      </div>
    </div>
    ${r.length ? `<section class="section"><div class="section-head"><h2>Recently viewed</h2></div><div class="chips">${r.map((c) => `<a class="char-chip" href="#/c/${enc(c)}">${esc(c)}</a>`).join("")}</div></section>`
      : `<section class="section"><div class="section-head"><h2>Most common characters</h2><span class="muted" style="font-size:12.5px">a place to start</span></div><div class="chips">${D.chars(common).slice(0, 24).map((c) => `<a class="char-chip" href="#/c/${enc(c)}">${esc(c)}</a>`).join("")}</div></section>`}
    ${footer()}
  </div>`;
  D.entry(daily).then((e) => {
    if (!e) return;
    const p = D.first(e, "Mandarin"), c = D.first(e, "Cantonese");
    $("#daily-r") && ($("#daily-r").textContent = [p?.t, c?.t].filter(Boolean).join("  ·  "));
    $("#daily-d") && ($("#daily-d").textContent = e.d || "");
  });
}

function footer() {
  return `<p class="footer">漢字音庫 · data from Unihan, Wiktionary (CC BY-SA), MCPDict & more · <a href="https://github.com/zzz9269/hanzi-sound-library/blob/main/DATA_SOURCES.md" target="_blank" rel="noopener">credits</a></p>`;
}

// ------------------------------------------------------------------ router --
function setTab(tab) {
  $$("[data-tab]").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
}
function notFound(raw) {
  document.title = "Not found · 漢字音庫";
  view.innerHTML = `<div class="empty"><span class="han">迷</span>There's no page at “${esc(raw)}”.<br><a class="btn" style="margin-top:14px" href="#/">Go to the home page</a></div>`;
}
async function route() {
  A.stop(); closeSheet(); hideToast();
  if (!location.hash.startsWith("#/read")) readerCtx = null;
  const raw = location.hash.replace(/^#/, "") || "/";
  const [, kind = "", ...rest] = raw.split("/");
  const arg = decodeURIComponent(rest.join("/"));
  const qbox = $("#q");
  try {
    if (kind === "c" && arg) { setTab("home"); qbox.value = arg; await charView(D.chars(arg)[0]); }
    else if (kind === "p" && arg) { setTab("home"); qbox.value = arg; await phraseView(arg); }
    else if (kind === "s" && arg && D.chars(arg).some(D.isHan)) { location.replace(queryHash(arg)); return; }
    else if (kind === "s" && arg) { setTab("home"); qbox.value = arg; await searchView(arg); }
    else if (kind === "read") { setTab("read"); qbox.value = ""; await readView(arg); }
    else if (kind === "poems") { setTab("poems"); qbox.value = ""; await poemsView(arg); }
    else if (kind === "poem" && arg) { setTab("poems"); qbox.value = ""; await poemView(arg); }
    else if (kind === "saved") { setTab("saved"); qbox.value = ""; await savedView(); }
    else if (!kind) { setTab("home"); qbox.value = ""; homeView(); }
    else { setTab(""); qbox.value = ""; notFound(raw); }
  } catch (err) {
    console.error(err);
    view.innerHTML = `<div class="empty"><span class="han">斷</span>Something went wrong loading this page. Check your connection and try again.</div>`;
  }
  $("#q-clear").hidden = !qbox.value;
  window.scrollTo({ top: 0 });
}

/** Where a typed query goes: one character → its page, more Chinese
 *  characters (simplified or traditional) → the phrase view, else search. */
function queryHash(q) {
  const han = D.chars(q).filter(D.isHan);
  if (han.length === 1 && D.chars(q).length <= 2) return `#/c/${enc(han[0])}`;
  if (han.length) return `#/p/${enc(q)}`;
  return `#/s/${enc(q)}`;
}
function submitQuery(q) {
  q = q.trim();
  if (!q) return;
  location.hash = queryHash(q);
  $("#q").blur();
}

async function main() {
  applySettings();
  $("#search").addEventListener("submit", (ev) => { ev.preventDefault(); submitQuery($("#q").value); });
  // "Look up" searches whatever is typed (and focuses the box when it's empty)
  $$('a[data-tab="home"]').forEach((a) => a.addEventListener("click", (ev) => {
    const q = $("#q").value.trim();
    ev.preventDefault();
    if (q) submitQuery(q);
    else { location.hash = "#/"; $("#q").focus(); }
  }));
  $("#q").addEventListener("input", () => { $("#q-clear").hidden = !$("#q").value; });
  // "/" jumps to the search box from anywhere (not while typing)
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "/" || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (ev.target.closest?.("input, textarea, select, [contenteditable]")) return;
    ev.preventDefault(); $("#q").focus(); $("#q").select();
  });
  $("#q-clear").addEventListener("click", () => { $("#q").value = ""; $("#q-clear").hidden = true; $("#q").focus(); });
  view.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;
  try { await D.init(); }
  catch {
    view.innerHTML = `<div class="empty"><span class="han">斷</span>Couldn't load the dictionary. Check your connection and reload.</div>`;
    return;
  }
  window.addEventListener("hashchange", route);
  route();
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    // check for a new build on every open; when one takes over, reload once so
    // the page runs the new code instead of the copy it started with
    const hadController = !!navigator.serviceWorker.controller;
    let reloaded = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (hadController && !reloaded) { reloaded = true; location.reload(); }
    });
    navigator.serviceWorker.register("sw.js", { updateViaCache: "none" })
      .then((reg) => reg.update()).catch(() => {});
    navigator.serviceWorker.addEventListener("message", (ev) => {
      const m = ev.data || {};
      if (m.type !== "prefetch-progress") return;
      const b = $("#off-btn");
      const finished = m.done >= m.total;
      if (finished) { D.store.set("offlineV", D.meta().v); toast("Every reading is saved for offline use"); }
      if (b) { b.textContent = finished ? "Downloaded ✓" : `${Math.round((m.done / m.total) * 100)}%`; b.disabled = !finished; }
    });
  }
}
main();
