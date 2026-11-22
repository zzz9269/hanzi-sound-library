// Audio: the device's own speech voices (Mandarin, Cantonese, Japanese, Korean,
// Vietnamese), mogher.com dictionary recordings (Teochew) and ithuan.tw's
// SuiSiann neural voice (Taiwanese Hokkien). No server and no API key needed:
// recordings play straight from their source URLs.
const MOGHER = "https://www.mogher.com/sound/syllabes/";
const ITHUAN = "https://hapsing.ithuan.tw/bangtsam?taibun=";

const LANG_RE = {
  "zh-CN": /^(zh[-_](CN|Hans|SG)|cmn)/i,
  "zh-TW": /^zh[-_](TW|Hant)/i,
  "zh-HK": /^(zh[-_](HK|MO|yue)|yue)/i,
  "ja-JP": /^ja/i, "ko-KR": /^ko/i, "vi-VN": /^vi/i,
};

let voices = [];
function loadVoices() {
  try { voices = window.speechSynthesis ? speechSynthesis.getVoices() : []; } catch { voices = []; }
}
loadVoices();
if (window.speechSynthesis) speechSynthesis.addEventListener?.("voiceschanged", () => {
  loadVoices();
  document.dispatchEvent(new CustomEvent("voices-ready"));
});

function pickVoice(lang) {
  const re = LANG_RE[lang];
  if (!re) return null;
  const all = voices.filter((v) => re.test(v.lang));
  if (!all.length && lang === "zh-CN") return pickVoice("zh-TW");
  // prefer natural/neural/enhanced voices, then local ones
  const score = (v) => (/natural|neural|premium|enhanced|siri/i.test(v.name) ? 4 : 0)
    + (/google/i.test(v.name) ? 2 : 0) + (v.localService ? 1 : 0);
  return all.sort((a, b) => score(b) - score(a))[0] || null;
}

export function canSpeak(lang) {
  return !!window.speechSynthesis && !!pickVoice(lang);
}
export const voicesKnown = () => voices.length > 0;

let current = null;              // { stop(), btn }
function setBtn(btn, state) {
  if (!btn) return;
  btn.classList.toggle("busy", state === "busy");
  btn.classList.toggle("playing", state === "playing");
}
export function stop() {
  if (current) { try { current.stop(); } catch { /* */ } setBtn(current.btn, ""); current = null; }
  try { window.speechSynthesis?.cancel(); } catch { /* */ }
}

export function speak(text, lang, { rate = 0.9, btn } = {}) {
  stop();
  const v = pickVoice(lang);
  if (!window.speechSynthesis || !v) return Promise.reject(new Error("no voice"));
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    u.voice = v; u.lang = v.lang; u.rate = rate;
    u.onstart = () => setBtn(btn, "playing");
    u.onend = u.onerror = () => { setBtn(btn, ""); if (current?.btn === btn) current = null; resolve(); };
    current = { stop: () => speechSynthesis.cancel(), btn };
    setBtn(btn, "busy");
    speechSynthesis.speak(u);
  });
}

function playOne(url, btn, signal) {
  return new Promise((resolve, reject) => {
    const a = new Audio();
    a.preload = "auto";
    const done = (ok) => { a.onended = a.onerror = null; ok ? resolve() : reject(new Error("audio failed")); };
    a.onended = () => done(true);
    a.onerror = () => done(false);
    a.onplaying = () => setBtn(btn, "playing");
    signal.stop = () => { a.pause(); a.src = ""; resolve(); };
    a.src = url;
    a.play().catch(() => done(false));
  });
}

/** Play URLs back to back (stitched Teochew syllables). Skips failures. */
export async function playUrls(urls, btn) {
  stop();
  const signal = {};
  const me = { stop: () => { signal.cancelled = true; signal.stop?.(); }, btn };
  current = me;
  setBtn(btn, "busy");
  let played = 0;
  for (const u of urls) {
    if (signal.cancelled) break;
    try { await playOne(u, btn, signal); played++; } catch { /* skip a missing syllable */ }
  }
  if (current === me) { setBtn(btn, ""); current = null; }
  if (!played && !signal.cancelled) throw new Error("no recording");
}

export const mogherUrl = (file) => MOGHER + encodeURI(file);
export const ithuanUrl = (tailo) => ITHUAN + encodeURIComponent(tailo);

/** Resolve an export audio key ("m:file.mp3" | "h:tâi-lô") to a URL. */
export function keyUrl(key) {
  if (!key) return null;
  if (key.startsWith("m:")) return mogherUrl(key.slice(2));
  if (key.startsWith("h:")) return ithuanUrl(key.slice(2));
  return null;
}
