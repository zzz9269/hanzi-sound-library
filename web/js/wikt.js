// Live Wiktionary panels (glyph origin, full Chinese entry), fetched only when
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

const DROP = "script,style,link,meta,iframe,object,embed,form,input,button,noscript,"
  + ".mw-editsection,.noprint,sup.reference,.mw-empty-elt,.mw-heading2,.catlinks,"
  + ".maintenance-line,.checksense,.request-box,.audiotable,audio,video,.mw-references-wrap";

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

/** Cleaned HTML of the whole "Chinese" language section, or "". */
export async function chineseEntry(ch) {
  const secs = await sections(ch);
  const s = find(secs, (x) => x.level === "2" && (x.line || "").trim() === "Chinese");
  return s ? clean(await sectionHtml(ch, s.index)) : "";
}

export const pageUrl = (ch) => `https://en.wiktionary.org/wiki/${encodeURIComponent(ch)}#Chinese`;
