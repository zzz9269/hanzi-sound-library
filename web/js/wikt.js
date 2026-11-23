// Live Wiktionary panels (glyph origin, etymology), fetched only when
// the user opens them. The MediaWiki API allows cross-origin reads (origin=*).
const API = "https://en.wiktionary.org/w/api.php";
const memo = new Map();

async function api(params) {
  const u = new URL(API);
  for (const [k, v] of Object.entries({ ...params, format: "json", origin: "*" })) u.searchParams.set(k, v);
  const r = await fetch(u);
  if (!r.ok) throw new Error(`Wiktionary HTTP ${r.status}`);
  return r.json();
}

async function sections(ch) {
  if (!memo.has("s:" + ch)) {
    memo.set("s:" + ch, api({ action: "parse", page: ch, prop: "sections", redirects: 1 })
      .then((j) => j?.parse?.sections || [])
      .catch((e) => { memo.delete("s:" + ch); throw e; }));
  }
  return memo.get("s:" + ch);
}

async function sectionHtml(ch, index) {
  const j = await api({ action: "parse", page: ch, section: index, prop: "text", redirects: 1,
                        disablelimitreport: 1, disableeditsection: 1 });
  return j?.parse?.text?.["*"] || "";
}

// Whole-page parse: Wiktionary's etymology templates check which language
// section they sit in, and error out when one section is parsed alone.
async function pageHtml(ch) {
  if (!memo.has("p:" + ch)) {
    memo.set("p:" + ch, api({ action: "parse", page: ch, prop: "text", redirects: 1,
                              disablelimitreport: 1, disableeditsection: 1 })
      .then((j) => j?.parse?.text?.["*"] || "")
      .catch((e) => { memo.delete("p:" + ch); throw e; }));
  }
  return memo.get("p:" + ch);
}

const DROP = "script,style,link,meta,iframe,object,embed,form,input,button,noscript,"
  + ".mw-editsection,.noprint,sup.reference,.mw-empty-elt,.mw-heading2,.catlinks,"
  + ".maintenance-line,.checksense,.request-box,.audiotable,audio,video,.mw-references-wrap,#toc,.toc";

function clean(html, { keepFirstHeading = false } = {}) {
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  const root = doc.body.firstElementChild;
  root.querySelectorAll(DROP).forEach((n) => n.remove());
  // the section's own heading repeats the panel title
  const first = root.querySelector(":scope > .mw-parser-output > .mw-heading:first-child, :scope > .mw-heading:first-child");
  if (first && !keepFirstHeading) first.remove();
  root.querySelectorAll("*").forEach((el) => {
    for (const a of [...el.attributes]) {
      const n = a.name.toLowerCase();
      if (n.startsWith("on") || n === "style" || n === "bgcolor" || n === "color") el.removeAttribute(a.name);
    }
    if (el.tagName === "A") {
      const h = el.getAttribute("href") || "";
      if (h.startsWith("/")) el.setAttribute("href", (h.startsWith("//") ? "https:" : "https://en.wiktionary.org") + h);
      else if (h.startsWith("#")) el.removeAttribute("href");
      else if (!/^https?:/i.test(h)) el.removeAttribute("href");
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener noreferrer");
    }
    if (el.tagName === "IMG") {
      for (const att of ["src", "srcset"]) {
        const v = el.getAttribute(att);
        if (v) el.setAttribute(att, v.replace(/(^|\s|,)\/\//g, "$1https://"));
      }
      el.setAttribute("loading", "lazy");
    }
  });
  return root.innerHTML;
}

function find(secs, pred) { return secs.find(pred); }

/** Cleaned HTML of the "Glyph origin" section, or "" if the page has none. */
export async function glyphOrigin(ch) {
  const secs = await sections(ch);
  const s = find(secs, (x) => (x.line || "").trim().toLowerCase() === "glyph origin");
  return s ? clean(await sectionHtml(ch, s.index)) : "";
}

// Headings that carry senses (part of speech) vs. ones to skip entirely.
const SKIP_HEAD = /^(pronunciation|alternative forms?|compounds|derived terms|related terms|descendants|synonyms|antonyms|see also|references|further reading|usage notes|anagrams|conjugation|declension|inflection|idioms|proverbs|collocations|coordinate terms|hyponyms|hypernyms|kanji|han character|readings|glyph origin|notes)\b/i;
const LANG_ORDER = ["Chinese", "Japanese", "Korean", "Vietnamese"];
const MAX_SENSES = 8;

/** Senses of one part-of-speech block: the headword line plus the top-level
 *  definitions, without quotations, synonyms or sub-senses. */
function senses(nodes, doc) {
  const out = doc.createElement("div");
  for (const n of nodes) {
    if (n.nodeType !== 1) continue;
    if (n.tagName === "P" && n.querySelector(".headword-line, .headword, strong.Hani, strong.Jpan, strong.Kore")) {
      const p = n.cloneNode(true); p.classList.add("ety-head"); out.appendChild(p);
    } else if (n.tagName === "OL") {
      const ol = doc.createElement("ol");
      for (const li of [...n.children].slice(0, MAX_SENSES)) {
        const c = li.cloneNode(true);
        c.querySelectorAll("ol, ul, dl, .nyms, .nyms-toggle, .h-quotations, .citation-whole, .wiktQuote").forEach((x) => x.remove());
        if (c.textContent.trim()) ol.appendChild(c);
      }
      if (ol.children.length) out.appendChild(ol);
    }
  }
  return out.innerHTML;
}

/** "Mandarin mò · Cantonese mut6" from a Chinese pronunciation box. */
function zhReadings(nodes) {
  const box = document.createElement("div");
  nodes.forEach((n) => n.nodeType === 1 && box.appendChild(n.cloneNode(true)));
  const pick = (sel) => [...new Set([...box.querySelectorAll(sel)].map((x) => x.textContent.trim()).filter(Boolean))];
  // first .Latn in each pinyin span is the tone-marked form (yè); the second is ye4.
  // pinyin-ts- (one form) or pinyin-t- (traditional ≠ simplified, 葉/叶)
  const man = pick('[class*="pinyin-t"][class*="form-of"] > .Latn:first-child').slice(0, 3);
  // the Cantonese line: <li>Cantonese <small>(Jyutping)</small>: <span class="zhpron-monospace">…
  const yue = [...box.querySelectorAll("li")]
    // exactly "(Jyutping)": not Pinghua / Taishanese "(Nanning, Jyutping++)"
    .filter((li) => li.querySelector(":scope > small")?.textContent.trim().match(/^\(?Jyutping\)?$/))
    .flatMap((li) => [...li.querySelectorAll(":scope > .zhpron-monospace")].map((x) => x.textContent.trim()))
    .slice(0, 1)
    // drop changed-tone (變音) forms like jip6-2: no word context is given for them
    .map((t) => t.split(/\s*\/\s*/).filter((r) => !/\d-\d$/.test(r)).join(", "))
    .filter(Boolean);
  const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  return [man.length && `Mandarin <b>${esc(man.join(", "))}</b>`, yue.length && `Cantonese <b>${esc(yue.join(", "))}</b>`]
    .filter(Boolean).join(" · ");
}

/** Every etymology on the page, in every language (Chinese, Japanese, Korean,
 *  Vietnamese, then the rest). Each "Etymology" / "Etymology N" heading gives
 *  one entry: its prose, and when there is no prose (Wiktionary splits
 *  senses that way, e.g. 末 mò vs. 末 me = 麼) the headword and senses that
 *  follow it, so every etymology shows what it is about. The whole page is
 *  parsed in one go: parsing a lone section breaks Wiktionary's templates.
 *  Returns [{lang, title, html}]; title "" when a language has one etymology. */
export async function etymology(ch) {
  const raw = new DOMParser().parseFromString(`<div>${await pageHtml(ch)}</div>`, "text/html").body.firstElementChild;
  const rb = raw.querySelector(":scope > .mw-parser-output") || raw;
  // tag each top-level node with its language (h2) before clean() drops the h2s
  let lang = "";
  const byLang = new Map();
  for (const n of [...rb.childNodes]) {
    const h2 = n.nodeType === 1 && (n.matches(".mw-heading2") || n.tagName === "H2");
    if (h2) { lang = (n.querySelector?.("h2") || n).textContent.trim(); continue; }
    if (!lang) continue;
    if (!byLang.has(lang)) byLang.set(lang, []);
    byLang.get(lang).push(n);
  }
  const order = [...byLang.keys()].sort((x, y) =>
    (LANG_ORDER.indexOf(x) + 1 || 99) - (LANG_ORDER.indexOf(y) + 1 || 99));
  const out = [];
  for (const L of order) {
    const holder = document.createElement("div");
    byLang.get(L).forEach((n) => holder.appendChild(n));
    const doc = new DOMParser().parseFromString(`<div>${clean(holder.innerHTML, { keepFirstHeading: true })}</div>`, "text/html");
    const root = doc.body.firstElementChild;
    root.querySelectorAll("table, .floatright, .sister-wikipedia, .sister-project").forEach((n) => n.remove());
    const isHead = (n) => n.nodeType === 1 && (n.matches(".mw-heading") || /^H[3-6]$/.test(n.tagName));
    const headText = (n) => (n.querySelector?.("h3,h4,h5,h6") || n).textContent.trim();
    // group: an etymology heading, its prose, then sense blocks until the next etymology
    const groups = [];
    let cur = null, block = null;
    for (const n of [...root.childNodes]) {
      if (isHead(n)) {
        const t = headText(n);
        if (/^etymology(\s+\d+)?$/i.test(t)) { cur = { title: t, prose: [], blocks: [], pron: [] }; groups.push(cur); block = cur.prose; }
        else if (cur && /^pronunciation\b/i.test(t)) block = cur.pron;
        else if (cur && !SKIP_HEAD.test(t)) { block = []; cur.blocks.push(block); }
        else block = null;
        continue;
      }
      if (block) block.push(n);
    }
    const items = groups.map((g) => {
      const d = doc.createElement("div");
      g.prose.forEach((n) => d.appendChild(n));
      let html = d.textContent.trim() ? d.innerHTML : "";
      // senses tell several etymologies apart (末 sue / ura / ure); a lone
      // etymology with its own prose doesn't need them
      const sense = html && groups.length < 2 ? ""
        : g.blocks.map((b) => senses(b, doc)).filter(Boolean).join("");
      // which reading this Chinese etymology is (末 mò vs. 末 me)
      const read = L === "Chinese" && groups.length > 1 ? zhReadings(g.pron) : "";
      if (read) html = `<p class="ety-read">${read}</p>` + html;
      if (sense) html += `<div class="ety-senses">${sense}</div>`;
      return { title: g.title, html };
    }).filter((g) => g.html);
    items.forEach((g) => out.push({ lang: L, title: items.length > 1 ? g.title : "", html: g.html }));
  }
  return out;
}

export const pageUrl = (ch, lang = "Chinese") => `https://en.wiktionary.org/wiki/${encodeURIComponent(ch)}#${lang}`;
