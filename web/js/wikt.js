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

function clean(html) {
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  const root = doc.body.firstElementChild;
  root.querySelectorAll(DROP).forEach((n) => n.remove());
  // the section's own heading repeats the panel title
  const first = root.querySelector(":scope > .mw-parser-output > .mw-heading:first-child, :scope > .mw-heading:first-child");
  if (first) first.remove();
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

/** Only the etymology prose of the Chinese section: the text under each
 *  "Etymology" / "Etymology N" heading, without its Pronunciation /
 *  Definitions subsections. The whole Chinese section is parsed in one go
 *  (parsing a lone sub-section breaks Wiktionary's templates). Etymology
 *  headings that only split senses (no text) are skipped.
 *  Returns [{title, html}] (title "" when there is a single etymology). */
export async function etymology(ch) {
  const secs = await sections(ch);
  if (!find(secs, (x) => x.level === "2" && (x.line || "").trim() === "Chinese")) return [];
  // keep only the Chinese language section (before clean() drops the h2s)
  const raw = new DOMParser().parseFromString(`<div>${await pageHtml(ch)}</div>`, "text/html").body.firstElementChild;
  const rb = raw.querySelector(":scope > .mw-parser-output") || raw;
  let inZh = false;
  for (const n of [...rb.childNodes]) {
    const h2 = n.nodeType === 1 && (n.matches(".mw-heading2") || n.tagName === "H2");
    if (h2) inZh = (n.querySelector?.("h2") || n).textContent.trim() === "Chinese";
    if (!inZh || h2) n.remove();
  }
  const doc = new DOMParser().parseFromString(`<div>${clean(rb.innerHTML)}</div>`, "text/html");
  const root = doc.body.firstElementChild;
  root.querySelectorAll("table, .floatright, .sister-wikipedia, .sister-project").forEach((n) => n.remove());
  const box = root.querySelector(":scope > .mw-parser-output") || root;
  const isHead = (n) => n.nodeType === 1 && (n.matches(".mw-heading") || /^H[2-6]$/.test(n.tagName));
  const headText = (n) => (n.querySelector?.("h2,h3,h4,h5,h6") || n).textContent.trim();
  const groups = [];
  let cur = null;
  for (const n of [...box.childNodes]) {
    if (isHead(n)) { const t = headText(n); cur = /^etymology(\s+\d+)?$/i.test(t) ? { title: t, nodes: [] } : null; if (cur) groups.push(cur); continue; }
    if (cur) cur.nodes.push(n);
  }
  const out = groups.map((g) => {
    const d = doc.createElement("div");
    g.nodes.forEach((n) => d.appendChild(n));
    return { title: g.title, html: d.innerHTML, text: d.textContent.trim() };
  }).filter((g) => g.text);
  return out.map((g) => ({ title: groups.length > 1 ? g.title : "", html: g.html }));
}

export const pageUrl = (ch) => `https://en.wiktionary.org/wiki/${encodeURIComponent(ch)}#Chinese`;
