import * as D from "./data.js";
import * as A from "./audio.js";
import * as W from "./wikt.js";

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
  { theme: "auto", ipa: true, en: true, hidden: [], readLang: "Mandarin" },
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
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
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
function ttsBtn(text, lang, { small = false, label = "Play" } = {}) {
  const ok = A.canSpeak(lang);
  return `<button class="play${small ? " small" : ""}" data-tts="${lang}" data-text="${esc(text)}"
    aria-label="${esc(label)}" ${ok ? "" : `disabled title="No ${lang} voice on this device"`}>${ICON.play}</button>`;
}
function urlBtn(urls, { small = false, label = "Play" } = {}) {
  const list = (Array.isArray(urls) ? urls : [urls]).filter(Boolean);
  if (!list.length) return "";
  return `<button class="play${small ? " small" : ""}" data-urls="${esc(JSON.stringify(list))}" aria-label="${esc(label)}">${ICON.play}</button>`;
}
document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest(".play");
  if (!btn || btn.disabled) return;
  ev.preventDefault(); ev.stopPropagation();
  if (btn.classList.contains("playing") || btn.classList.contains("busy")) { A.stop(); return; }
  try {
    if (btn.dataset.tts) await A.speak(btn.dataset.text, btn.dataset.tts, { btn, rate: +(btn.dataset.rate || 0.9) });
    else if (btn.dataset.urls) await A.playUrls(JSON.parse(btn.dataset.urls), btn);
  } catch {
    toast(btn.dataset.tts ? "No voice for this language on your device" : "No recording available for this reading");
  }
});
document.addEventListener("voices-ready", () => {
  $$("button.play[data-tts][disabled]").forEach((b) => {
    if (A.canSpeak(b.dataset.tts)) { b.disabled = false; b.removeAttribute("title"); }
  });
});

// -------------------------------------------------------------- readings ----
function readingHTML(r, { audio = "" } = {}) {
  return `<span class="reading${r.m ? " ml" : ""}"><span class="t">${esc(r.t)}</span>`
    + (r.m ? `<span class="badge-ml" title="Machine-predicted: inferred by a model, not attested in a source">ML</span>` : "")
    + (r.e ? `<span class="e">${esc(r.e)}</span>` : "") + audio + `</span>`;
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
  if (col.audio?.startsWith("tts:")) rowPlay = ttsBtn(e.ch, col.audio.slice(4), { small: true, label: `Play ${col.label}` });
  const ipaLine = roms.length && ipas.length
    ? `<div class="ipa-line"><span class="lbl">IPA</span>${ipas.map((r) =>
        `<span>${esc(r.t)}${r.m ? '<span class="badge-ml">ML</span>' : ""}</span>`).join("")}</div>` : "";
  const sandhi = e.h?.[k]
    ? `<div class="sandhi">Before another syllable the tone shifts <span class="ipa">${esc(e.h[k])}</span></div>` : "";
  return `<div class="rd-row">
    <div class="rd-label"><b>${esc(col.label)}</b><span class="native">${esc(col.native || "")}</span><span class="scheme">${esc(col.scheme || "")}</span></div>
    <div class="rd-vals"><div class="readings">${items}${rowPlay}</div>${ipaLine}${sandhi}${extra}</div>
  </div>`;
}

function simpleRow(label, native, scheme, inner) {
  return `<div class="rd-row"><div class="rd-label"><b>${esc(label)}</b><span class="native">${esc(native || "")}</span><span class="scheme">${esc(scheme || "")}</span></div>
    <div class="rd-vals">${inner}</div></div>`;
}

function sinoRows(e) {
  const out = [];
  const g = (id) => e.v?.[D.colIdx(id)] || [];
  const ja = g("Japanese"), on = g("Japanese On"), kun = g("Japanese Kun");
  if (ja.length || on.length || kun.length) {
    const chips = ja.map((r) => readingHTML(r, { audio: /[぀-ヿ]/.test(r.t) ? ttsBtn(r.t, "ja-JP", { small: true, label: `Play ${r.t}` }) : "" })).join("");
    const rom = [on.length ? `<span><span class="lbl">On</span> ${on.map((r) => esc(r.t)).join(" · ")}</span>` : "",
                 kun.length ? `<span><span class="lbl">Kun</span> ${kun.map((r) => esc(r.t)).join(" · ")}</span>` : ""].join("");
    out.push(simpleRow("Japanese", "日本語", "on'yomi · kun'yomi",
      `<div class="readings">${chips}</div>${rom ? `<div class="ipa-line" style="display:flex">${rom}</div>` : ""}`));
  }
  const ko = g("Korean (Hangul)"), yale = g("Korean (romanized)");
  if (ko.length) {
    const chips = ko.map((r, i) => readingHTML({ ...r, e: ko.length === yale.length ? yale[i].t : "" },
      { audio: ttsBtn(r.t, "ko-KR", { small: true, label: `Play ${r.t}` }) })).join("");
    out.push(simpleRow("Korean", "한국어", "Hangul · Yale", `<div class="readings">${chips}</div>`));
  }
  const vi = g("Vietnamese");
  if (vi.length) {
    out.push(simpleRow("Vietnamese", "Tiếng Việt", "Hán-Việt", `<div class="readings">${vi.map((r) =>
      readingHTML(r, { audio: ttsBtn(r.t, "vi-VN", { small: true, label: `Play ${r.t}` }) })).join("")}</div>`));
  }
  for (const id of ["Okinawan", "Zhuang"]) {
    const c = COL(id);
    if (c && g(id).length) out.push(rowHTML(c, e));
  }
  return out.join("");
}

function histRows(e) {
  const out = [];
  const g = (id) => e.v?.[D.colIdx(id)] || [];
  const n = (id) => e.n?.[D.colIdx(id)] || [];
  const oc = g("Old Chinese"), ocz = g("Old Chinese (Zhengzhang)");
  if (oc.length || ocz.length) {
    const line = (lab, rs) => rs.length ? `<div class="readings"><span class="pill">${lab}</span>${rs.map((r) => readingHTML(r)).join("")}</div>` : "";
    out.push(simpleRow("Old Chinese", "上古漢語", "~1000 BCE · two rival reconstructions",
      line("Baxter–Sagart", oc) + line("Zhengzhang", ocz)));
  }
  const pm = g("Proto-Min");
  if (pm.length) {
    const conf = n("Proto-Min")[0]?.conf;
    const chip = conf != null
      ? `<span class="conf" style="background:${confColor(conf)}22;color:${confColor(conf)}" title="How far the Min daughter languages agree on the reconstructed vowel. Onset, coda and tone are anchored on Middle Chinese.">vowel ${Math.round(conf * 100)}%</span>` : "";
    out.push(simpleRow("Proto-Min", "原始閩語", "★ reconstructed here from the Min languages",
      `<div class="readings">${pm.map((r) => readingHTML(r)).join("")}${chip}</div>`));
  }
  const mc = g("Middle Chinese"), mci = g("Middle Chinese (Baxter)");
  if (mc.length || mci.length) {
    out.push(simpleRow("Middle Chinese", "中古漢語", "~600 CE · Qieyun",
      `<div class="readings">${mc.map((r) => readingHTML(r)).join("")}</div>`
      + (mci.length ? `<div class="ipa-line" style="display:flex"><span class="lbl">IPA</span>${mci.map((r) => `<span>${esc(r.t)}${r.e ? ` <span style="color:var(--jade)">≈ ${esc(r.e)}</span>` : ""}</span>`).join("")}</div>` : "")));
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
  if (tang.length) out.push(rowHTML(COL("Tang"), e));
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
  const hiddenRows = sin.filter((c) => hiddenIds.has(c.id)).map((c) => rowHTML(c, e)).filter(Boolean);
  const sino = sinoRows(e), hist = histRows(e);
  const variant = e.from
    ? `<div class="variant-note">Readings that are only recorded under the traditional form <a href="#/c/${enc(e.from)}" class="han">${esc(e.from)}</a> are included.</div>`
    : simp ? `<div class="variant-note">Simplified form: <a href="#/c/${enc(simp)}" class="han">${esc(simp)}</a></div>` : "";

  view.innerHTML = `
  <article class="fade-in">
    <div class="hero">
      <div class="hero-glyph" lang="zh-Hant">${esc(ch)}</div>
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
        ${ttsBtn(ch, "zh-CN", { label: "Play Mandarin" }).replace('class="play"', 'class="play" style="width:38px;height:38px"')}
        <button class="btn ${isSaved ? "on" : ""}" id="save-btn">${ICON.star}<span>${isSaved ? "Saved" : "Save"}</span></button>
        <button class="btn" id="copy-btn">${ICON.copy}<span>Copy</span></button>
        ${navigator.share ? `<button class="btn" id="share-btn">${ICON.share}<span>Share</span></button>` : ""}
        <a class="btn ghost" href="${W.pageUrl(ch)}" target="_blank" rel="noopener">${ICON.ext}<span>Wiktionary</span></a>
      </div>
    </div>

    ${shownRows.length ? `<section class="section"><div class="section-head"><h2>Spoken today</h2><span class="han">現代漢語方言</span><span class="spacer"></span><span class="muted" style="font-size:12.5px">${shownRows.length} varieties</span></div>
      <div class="card rows two">${shownRows.join("")}</div>
      ${hiddenRows.length ? `<details class="fold card" style="margin-top:10px"><summary><span>${hiddenRows.length} more ${hiddenRows.length === 1 ? "variety" : "varieties"}</span><span class="chev">${ICON.chev}</span></summary><div class="fold-body rows two">${hiddenRows.join("")}</div></details>` : ""}
    </section>` : ""}

    ${sino ? `<section class="section"><div class="section-head"><h2>Across East Asia</h2><span class="han">漢字文化圈</span></div><div class="card rows two">${sino}</div></section>` : ""}

    ${hist ? `<section class="section"><div class="section-head"><h2>Through history</h2><span class="han">歷史音韻</span></div><div class="card rows">${hist}</div></section>` : ""}

    <section class="section">
      ${localityHTML(e)}
      ${fold("glyph", "字", "Glyph origin", "How the character was formed · Wiktionary")}
      ${fold("entry", "典", "Dictionary entry", "Meanings, etymology, compounds · Wiktionary")}
      ${fold("sources", "源", "Sources", "Where every reading on this page comes from")}
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
    try { await navigator.clipboard.writeText(ch); toast(`Copied ${ch}`); } catch { toast("Copy not allowed here"); }
  };
  if ($("#share-btn")) $("#share-btn").onclick = () =>
    navigator.share({ title: `${ch} · 漢字音庫`, text: `${ch} ${man[0]?.t || ""} — ${e.d || ""}`, url: location.href }).catch(() => {});
  bindLazyFolds(ch);
}

function bindLazyFolds(ch) {
  const lazy = {
    glyph: async () => {
      const html = await W.glyphOrigin(ch);
      return html ? `<div class="wikt">${html}<div class="wikt-src">From English Wiktionary · CC BY-SA 4.0</div></div>`
        : `<div class="loading">Wiktionary has no glyph-origin notes for ${esc(ch)}.</div>`;
    },
    entry: async () => {
      const html = await W.chineseEntry(ch);
      return html ? `<div class="wikt">${html}<div class="wikt-src">From English Wiktionary · CC BY-SA 4.0 · <a href="${W.pageUrl(ch)}" target="_blank" rel="noopener">open the full page</a></div></div>`
        : `<div class="loading">No Chinese entry on Wiktionary for ${esc(ch)}.</div>`;
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
/** First reading for a column at each position: [{ch, r}] (r null when none). */
function perChar(list, ents, colId) {
  const k = D.colIdx(colId);
  const ctx = colId === "Mandarin" ? wordReadings(list, ents) : [];
  return list.map((ch, i) => {
    const e = ents[i];
    let r = e ? (e.v?.[k]?.[0] || e.i?.[k]?.[0] || null) : null;
    if (ctx[i]) r = (e?.v?.[k] || []).find((x) => x.t === ctx[i]) || { t: ctx[i] };
    return { ch, r, han: D.isHan(ch) };
  });
}

/** Mandarin readings that depend on the word (長城 cháng chéng, 銀行 yín
 *  háng): longest match over the words stored on each character's entry. */
function wordReadings(list, ents) {
  const out = new Array(list.length).fill(null);
  for (let i = 0; i < list.length;) {
    const x = ents[i]?.x;
    let py = null;
    if (x) {
      for (let L = Math.min(8, list.length - i); L >= 2 && !py; L--) {
        const hit = x[list.slice(i, i + L).join("")];
        if (hit) py = hit.split(" ");
      }
    }
    if (py) { py.forEach((p, j) => { out[i + j] = p; }); i += py.length; } else i++;
  }
  return out;
}

const CLAUSE_END = /[，,、；;：:。！？!?]/;
function rubyCell({ ch, r, han }) {
  if (!han) return `<span class="ruby punct"><span class="rt">&nbsp;</span><span class="rb">${esc(ch)}</span></span>`;
  const rt = r ? `<span class="rt${r.m ? " ml" : ""}">${esc(r.t)}</span>` : `<span class="rt none">·</span>`;
  const en = r?.e ? `<span class="en">≈ ${esc(r.e)}</span>` : "";
  return `<button class="ruby" data-ch="${esc(ch)}">${rt}<span class="rb">${esc(ch)}</span>${en}</button>`;
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
  if (colId === "Hokkien") {
    const tl = han.map((c) => (c.r?.a || "").startsWith("h:") ? c.r.a.slice(2) : "").filter(Boolean);
    return tl.length ? urlBtn(A.ithuanUrl(tl.join("-")), { label: "Play in Taiwanese Hokkien" }) : "";
  }
  if (colId === "Teochew") {
    const urls = han.map((c) => A.keyUrl(c.r?.a)).filter(Boolean);
    return urls.length ? urlBtn(urls, { label: "Play in Teochew (stitched recordings)" }) : "";
  }
  return "";
}

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
    return `<div class="lang-line"><div class="head"><b>${esc(langName(id))}</b><span class="native">${esc(c?.native || "")}</span><span class="spacer"></span>${lineAudio(id, cells, text)}</div>${rubyLine(cells)}</div>`;
  }).join("");
  view.innerHTML = `<article class="fade-in">
    <div class="phrase-hero">${list.map((ch) => D.isHan(ch) ? `<a href="#/c/${enc(ch)}" class="han">${esc(ch)}</a>` : `<span class="han" style="font-size:40px;color:var(--muted)">${esc(ch)}</span>`).join("")}</div>
    <p class="page-sub">Tap any character for its full page. Readings are each character's main reading; context-dependent readings may differ.</p>
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
  const rd = byReading.map((x) => card(x.ch, x.col ? `${x.col.label}${x.col.scheme && x.col.section !== "local" ? " · " + x.col.scheme : ""}` : "")).join("");
  const en = byEnglish.map((c) => card(c)).join("");
  document.title = `${q} · 漢字音庫`;
  view.innerHTML = `<div class="fade-in">
    <h1 class="page-title">“${esc(q)}”</h1>
    ${rd ? `<section class="section"><div class="section-head"><h2>Characters read “${esc(q)}”</h2><span class="muted" style="font-size:12.5px">${byReading.length}</span></div><div class="results">${rd}</div></section>` : ""}
    ${en ? `<section class="section"><div class="section-head"><h2>Meaning “${esc(q)}”</h2><span class="muted" style="font-size:12.5px">${byEnglish.length}</span></div><div class="results">${en}</div></section>` : ""}
    ${!rd && !en ? `<div class="empty"><span class="han">無</span>Nothing found. Try a single English word (“moon”), a reading (“tian”, “jat1”, “then”) or paste Chinese characters.</div>` : ""}
    ${footer()}
  </div>`;
}

// ------------------------------------------------------------ bottom sheet --
async function peek(ch) {
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
  sheet.innerHTML = `<div class="grab"></div>
    <div class="peek-head"><span class="g">${esc(ch)}</span><div><div style="font-size:15px;color:var(--ink-2)">${esc(e.d || "")}</div>
    <div class="row-flex" style="margin-top:10px">${ttsBtn(ch, "zh-CN", { label: "Play Mandarin" })}<a class="btn primary" href="#/c/${enc(ch)}">Open full page</a></div></div></div>
    <div class="peek-list">${rows}</div>`;
}
function closeSheet() { $("#sheet").hidden = true; $("#sheet-backdrop").hidden = true; }
$("#sheet-backdrop").addEventListener("click", closeSheet);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
document.addEventListener("click", (ev) => {
  const r = ev.target.closest("button.ruby[data-ch]");
  if (!r) return;
  if (r.closest(".recite, .recite-chars") && !r.classList.contains("peek")) { r.classList.add("peek"); return; }
  peek(r.dataset.ch);
});

// ------------------------------------------------------------------ reader --
const SENT_RE = /[^。！？；!?;\n]+[。！？；!?;]?/g;
function langSelect(id, value) {
  return `<select class="select" id="${id}">${READ_LANGS.filter((l) => COL(l)).map((l) =>
    `<option value="${esc(l)}" ${l === value ? "selected" : ""}>${esc(langName(l))}${COL(l)?.audio || ["Hokkien", "Teochew"].includes(l) ? "  🔊" : ""}</option>`).join("")}</select>`;
}

async function renderReading(text, lang, out, { big = false } = {}) {
  const sentences = (text.match(SENT_RE) || []).map((s) => s.trim()).filter(Boolean);
  const all = [...new Set(D.chars(text).filter(D.isHan))];
  out.innerHTML = `<div class="loading"><span class="spinner"></span>Reading ${all.length} characters…</div>`;
  const ents = await D.entries(all);
  const E = Object.fromEntries(all.map((c, i) => [c, ents[i]]));
  out.innerHTML = sentences.map((s) => {
    const list = D.chars(s);
    const cells = perChar(list, list.map((c) => E[c] || null), lang);
    return `<div class="sentence"><div class="${big ? "big-ruby" : ""}">${rubyLine(cells, { clauses: big })}</div><div>${lineAudio(lang, cells, s)}</div></div>`;
  }).join("") || `<div class="empty">Paste or type some Chinese text above.</div>`;
}

async function readView() {
  document.title = "Read · 漢字音庫";
  const draft = D.store.get("readDraft", "");
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
    <input class="input" id="poem-q" placeholder="Search title or author: 李白, 靜夜思…" style="max-width:320px"></div>
    <div class="card poem-list" id="plist" style="margin-top:14px"></div>
    ${footer()}
  </div>`;
  const list = $("#plist"), q = $("#poem-q");
  let current = cur;
  const draw = () => {
    const s = q.value.trim();
    const pool = poems.filter((p) => p.anthology === current && (!s || p.title.includes(s) || p.author.includes(s)));
    list.innerHTML = pool.length ? pool.slice(0, 400).map((p) => `<a class="poem-item" href="#/poem/${p.id}"><b>${esc(p.title)}</b><span>${esc(p.author)}</span><small>${esc(p.lines[0] || "")}</small></a>`).join("")
      : `<div class="empty">No poems match.</div>`;
  };
  $("#anth").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-a]"); if (!b) return;
    current = b.dataset.a; D.store.set("anth", current);
    $$("#anth button").forEach((x) => x.classList.toggle("on", x === b));
    draw();
  });
  q.addEventListener("input", draw);
  draw();
}

async function poemView(id) {
  const poems = await D.poems();
  const p = poems.find((x) => x.id === id);
  if (!p) { view.innerHTML = `<div class="empty">Poem not found.</div>`; return; }
  document.title = `${p.title} · 漢字音庫`;
  view.innerHTML = `<article class="fade-in">
    <a class="btn ghost" href="#/poems" style="margin-bottom:6px">← All poems</a>
    <div class="poem-head"><h1>${esc(p.title)}</h1><p class="han">${esc(p.author)} · ${esc(p.anthology)}</p></div>
    <div class="toolbar" style="justify-content:center">
      <div style="min-width:200px">${langSelect("pm-lang", settings.readLang)}</div>
      <div class="seg" id="recite"><button data-r="" class="on">Read</button><button data-r="recite">Hide readings</button><button data-r="recite-chars">Hide characters</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="pm-out"></div>
    ${p.note ? `<p class="note" style="margin-top:14px">${esc(p.note)}</p>` : ""}
    ${footer()}
  </article>`;
  const out = $("#pm-out"), sel = $("#pm-lang");
  const go = () => { settings.readLang = sel.value; saveSettings(); renderReading(p.lines.join("\n"), sel.value, out, { big: true }); };
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
  const s = saved(), r = recent();
  const chip = (c) => `<a class="char-chip" href="#/c/${enc(c)}">${esc(c)}</a>`;
  const langs = SINITIC();
  const hidden = new Set(settings.hidden);
  view.innerHTML = `<div class="fade-in">
    <h1 class="page-title">Saved</h1>
    <div class="card pad"><div class="eyebrow" style="margin-bottom:10px">Saved characters</div>
      ${s.length ? `<div class="chips">${s.map(chip).join("")}</div>` : `<p class="muted" style="margin:0">Tap ★ Save on any character to keep it here.</p>`}</div>
    <div class="card pad" style="margin-top:14px"><div class="eyebrow" style="margin-bottom:10px">Recently viewed</div>
      ${r.length ? `<div class="chips">${r.map(chip).join("")}</div>` : `<p class="muted" style="margin:0">Characters you look up appear here.</p>`}</div>

    <section class="section"><div class="section-head"><h2>Settings</h2></div>
    <div class="card settings">
      <div class="setting"><div class="txt"><b>Appearance</b><span>Follow the system, or pick one</span></div>
        <div class="seg" id="theme">${["auto", "light", "dark"].map((t) => `<button data-t="${t}" class="${settings.theme === t ? "on" : ""}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div></div>
      <div class="setting"><div class="txt"><b>Show IPA</b><span>Phonetic transcription under each romanised reading</span></div>
        <label class="switch"><input type="checkbox" id="set-ipa" ${settings.ipa ? "checked" : ""}><span></span></label></div>
      <div class="setting"><div class="txt"><b>Show ≈ English hints</b><span>A rough English sounds-like for each reading</span></div>
        <label class="switch"><input type="checkbox" id="set-en" ${settings.en ? "checked" : ""}><span></span></label></div>
      <div class="setting" style="display:block"><div class="txt"><b>Varieties shown first</b><span>Tap to hide the ones you don't need; hidden ones stay one tap away.</span></div></div>
      <div class="lang-toggles" id="langs">${langs.map((c) => `<button data-id="${esc(c.id)}" class="${hidden.has(c.id) ? "" : "on"}">${esc(c.label)} <span class="han">${esc(c.native)}</span></button>`).join("")}</div>
      <div class="setting"><div class="txt"><b>Use offline</b><span id="off-txt">Save every reading on this device (about ${Math.round((D.meta().offlineBytes || 0) / 1e6)} MB) so lookups work with no connection. Audio and Wiktionary still need the internet.</span></div>
        <button class="btn" id="off-btn" ${navigator.serviceWorker?.controller ? "" : "disabled"}>Download</button></div>
    </div></section>

    <section class="section"><div class="section-head"><h2>About</h2></div>
    <div class="card pad note">
      <p style="margin-top:0"><b>漢字音庫</b> brings together the pronunciations of ${D.meta().chars.toLocaleString()} Chinese characters across ${langs.length} Sinitic varieties, ${Object.keys(D.cols().reduce((a, c) => (c.section === "local" ? (a[c.id] = 1, a) : a), {})).length} local dialect points, Middle and Old Chinese, and Japanese, Korean and Vietnamese.</p>
      <p>Readings come from Unihan, Wiktionary, kaikki.org, MCPDict (漢字音典), Baxter–Sagart, ytenx and qieyun-data. Readings marked <span class="badge-ml">ML</span> are predicted by a model, not attested. Teochew audio is from <a href="https://www.mogher.com" target="_blank" rel="noopener">mogher.com</a>; Taiwanese Hokkien from <a href="https://ithuan.tw" target="_blank" rel="noopener">ithuan.tw</a>; other voices are your device's own.</p>
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
  if (D.store.get("offlineV", "") === D.meta().v) { offBtn.textContent = "Downloaded ✓"; }
  offBtn.onclick = () => {
    const sw = navigator.serviceWorker?.controller;
    if (!sw) return;
    offBtn.disabled = true; offBtn.textContent = "Starting…";
    sw.postMessage({ type: "prefetch", urls: D.offlineUrls() });
  };
  $("#set-ipa").onchange = (ev) => { settings.ipa = ev.target.checked; saveSettings(); };
  $("#set-en").onchange = (ev) => { settings.en = ev.target.checked; saveSettings(); };
  $("#langs").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-id]"); if (!b) return;
    const id = b.dataset.id;
    const h = new Set(settings.hidden);
    if (h.has(id)) h.delete(id); else h.add(id);
    settings.hidden = [...h]; saveSettings();
    b.classList.toggle("on", !h.has(id));
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
    ${r.length ? `<section class="section"><div class="section-head"><h2>Recently viewed</h2></div><div class="chips">${r.map((c) => `<a class="char-chip" href="#/c/${enc(c)}">${esc(c)}</a>`).join("")}</div></section>` : ""}
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
async function route() {
  A.stop(); closeSheet();
  const raw = location.hash.replace(/^#/, "") || "/";
  const [, kind = "", ...rest] = raw.split("/");
  const arg = decodeURIComponent(rest.join("/"));
  const qbox = $("#q");
  try {
    if (kind === "c" && arg) { setTab("home"); qbox.value = arg; await charView(D.chars(arg)[0]); }
    else if (kind === "p" && arg) { setTab("home"); qbox.value = arg; await phraseView(arg); }
    else if (kind === "s" && arg) { setTab("home"); qbox.value = arg; await searchView(arg); }
    else if (kind === "read") { setTab("read"); qbox.value = ""; await readView(); }
    else if (kind === "poems") { setTab("poems"); qbox.value = ""; await poemsView(arg); }
    else if (kind === "poem" && arg) { setTab("poems"); qbox.value = ""; await poemView(arg); }
    else if (kind === "saved") { setTab("saved"); qbox.value = ""; await savedView(); }
    else { setTab("home"); qbox.value = ""; homeView(); }
  } catch (err) {
    console.error(err);
    view.innerHTML = `<div class="empty"><span class="han">斷</span>Something went wrong loading this page. Check your connection and try again.</div>`;
  }
  $("#q-clear").hidden = !qbox.value;
  window.scrollTo({ top: 0 });
}

function submitQuery(q) {
  q = q.trim();
  if (!q) return;
  const han = D.chars(q).filter(D.isHan);
  if (han.length === 1 && D.chars(q).length <= 2) location.hash = `#/c/${enc(han[0])}`;
  else if (han.length) location.hash = `#/p/${enc(q)}`;
  else location.hash = `#/s/${enc(q)}`;
  $("#q").blur();
}

async function main() {
  applySettings();
  $("#search").addEventListener("submit", (ev) => { ev.preventDefault(); submitQuery($("#q").value); });
  $("#q").addEventListener("input", () => { $("#q-clear").hidden = !$("#q").value; });
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
    navigator.serviceWorker.register("sw.js").catch(() => {});
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
