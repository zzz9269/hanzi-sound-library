// Data layer: lazy JSON shards built by `python -m hanzihub.build_web`.
const BASE = "data/";
const cache = new Map();

let VER = "";        // dataset hash from meta.json; keeps cached shards in step

function getJSON(path) {
  if (!cache.has(path)) {
    const url = BASE + path + (VER && path !== "meta.json" ? `?v=${VER}` : "");
    const p = fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json();
    });
    p.catch(() => cache.delete(path));     // a failed fetch can be retried
    cache.set(path, p);
  }
  return cache.get(path);
}

let META = null, COLS = null, COLIDX = null, S2T = null, T2S = null;

export async function init() {
  const meta = await getJSON("meta.json");
  VER = meta.v || meta.built || "";
  const s2t = await getJSON("s2t.json");
  META = meta;
  COLS = meta.columns;
  COLIDX = Object.fromEntries(COLS.map((c, i) => [c.id, i]));
  S2T = s2t;
  T2S = {};
  for (const [s, t] of Object.entries(s2t)) if (!(t in T2S)) T2S[t] = s;
  return META;
}
export const meta = () => META;
export const cols = () => COLS;
export const colIdx = (id) => COLIDX[id];
export const toTrad = (ch) => S2T[ch] || ch;
export const toSimp = (ch) => T2S[ch] || ch;

export const isHan = (c) => /\p{Script=Han}/u.test(c);
export const chars = (s) => Array.from(s || "");

function shardKey(ch) { return (ch.codePointAt(0) >> META.shardShift).toString(16); }

export async function rawEntry(ch) {
  const shard = await getJSON(`c/${shardKey(ch)}.json`).catch(() => ({}));
  return shard[ch] || null;
}

const MAPS = ["v", "i", "n", "h", "w", "l", "x"];   // x = word readings
/** Entry for a character with empty columns back-filled from its traditional
 *  form (the dataset is keyed by traditional characters). `from` = the
 *  traditional char used, when any back-fill happened. */
export async function entry(ch) {
  const own = await rawEntry(ch);
  const trad = S2T[ch];
  if (!trad || trad === ch) return own ? { ...own, ch } : null;
  const t = await rawEntry(trad);
  if (!t) return own ? { ...own, ch } : null;
  if (!own) return { ...t, ch, from: trad };
  const out = { ...own, ch };
  let used = false;
  for (const m of MAPS) {
    if (!t[m]) continue;
    out[m] = { ...(own[m] || {}) };
    for (const [k, v] of Object.entries(t[m])) {
      if (!(k in out[m])) { out[m][k] = v; used = true; }
      else if ((m === "v" || m === "i") && Array.isArray(v)) {
        // same column on both forms: add the readings only the traditional has
        const have = new Set(out[m][k].map((r) => r.t));
        const more = v.filter((r) => !have.has(r.t));
        if (more.length) { out[m][k] = [...out[m][k], ...more]; used = true; }
      }
    }
  }
  if (!out.d && t.d) { out.d = t.d; used = true; }
  if (used) out.from = trad;
  return out;
}

export function entries(list) {
  return Promise.all(list.map((c) => (isHan(c) ? entry(c) : Promise.resolve(null))));
}

export const provenance = async (ch) =>
  (await getJSON(`p/${shardKey(ch)}.json`).catch(() => ({})))[ch] || [];

/** First reading of a column for a character entry, or null. */
export function first(e, colId) {
  const k = COLIDX[colId];
  const r = e?.v?.[k]?.[0] || e?.i?.[k]?.[0];
  return r || null;
}

// --- search ---------------------------------------------------------------
export function fold(s) {
  return (s || "").replace(/ⁿ/g, "n").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

export async function searchReading(q) {
  const k = fold(q).replace(/\s+/g, "");
  if (!/^[a-z][a-z0-9'\-]*$/.test(k)) return [];
  const idx = await getJSON(`s/rd/${k[0]}.json`).catch(() => ({}));
  const hit = idx[k] || idx[k.replace(/[0-9]+$/, "")] || [];
  return hit.map(([ch, ci]) => ({ ch, col: COLS[ci] }));
}

export async function searchEnglish(q) {
  const words = fold(q).split(/[^a-z'\-]+/).filter((w) => w.length > 1);
  if (!words.length) return [];
  const lists = await Promise.all(words.map(async (w) => {
    const idx = await getJSON(`s/en/${w[0]}.json`).catch(() => ({}));
    return idx[w] || (w.endsWith("s") ? idx[w.slice(0, -1)] : null) || [];
  }));
  if (lists.length === 1) return lists[0];
  const [head, ...rest] = lists;
  const sets = rest.map((l) => new Set(l));
  const both = head.filter((c) => sets.every((s) => s.has(c)));
  return both.length ? both : [...new Set(lists.flat())].slice(0, 60);
}

/** Absolute, versioned URLs of every file needed to use the app offline. */
export const offlineUrls = () =>
  (META.offline || []).map((p) => new URL(`${BASE}${p}?v=${VER}`, location.href).href);

export const poems = () => getJSON("poems.json");
export const passages = () => getJSON("passages.json");

// --- tiny persistent store (localStorage, never required) ------------------
export const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem("hz." + key); return v == null ? fallback : JSON.parse(v); }
    catch { return fallback; }
  },
  set(key, val) { try { localStorage.setItem("hz." + key, JSON.stringify(val)); } catch { /* private mode */ } },
};
