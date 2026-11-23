// Audio: the device's own speech voices (Mandarin, Cantonese, Japanese, Korean,
// Vietnamese), mogher.com dictionary recordings (Teochew) and ithuan.tw's
// SuiSiann neural voice (Taiwanese Hokkien). No server and no API key needed:
// recordings play straight from their source URLs. Min phrases are played one
// syllable at a time in citation tone: neither source applies tone sandhi
// reliably, so the app never claims to.
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

let utter = null;                // held so Chrome doesn't garbage-collect it mid-speech
export function speak(text, lang, { rate = 0.9, btn } = {}) {
  stop();
  const v = pickVoice(lang);
  if (!window.speechSynthesis || !v) return Promise.reject(new Error("no voice"));
  return new Promise((resolve, reject) => {
    const u = new SpeechSynthesisUtterance(text);
    utter = u;
    u.voice = v; u.lang = v.lang; u.rate = rate;
    // some voices are listed but never speak (an online voice while offline):
    // report that instead of leaving the button pulsing
    let started = false;
    const guard = setTimeout(() => {
      if (started || utter !== u) return;
      try { speechSynthesis.cancel(); } catch { /* */ }
      setBtn(btn, ""); if (current?.btn === btn) current = null; utter = null;
      reject(new Error("voice did not start"));
    }, 5000);
    u.onstart = () => { started = true; clearTimeout(guard); setBtn(btn, "playing"); };
    u.onend = u.onerror = () => { clearTimeout(guard); setBtn(btn, ""); if (current?.btn === btn) current = null; if (utter === u) utter = null; resolve(); };
    current = { stop: () => speechSynthesis.cancel(), btn };
    setBtn(btn, "busy");
    // Chrome can drop (or replay the previous) utterance queued in the same tick
    // as cancel(): give the engine a moment to clear before speaking.
    setTimeout(() => {
      if (utter !== u) { resolve(); return; }
      speechSynthesis.resume();
      speechSynthesis.speak(u);
    }, 80);
  });
}

function loadAudio(url) {
  const a = new Audio();
  a.preload = "auto";
  a.src = url;
  return a;
}

// Drop a file without the browser re-requesting the page as audio (src = ""
// resolves to the page URL and fires a spurious error).
function unload(a) { a.pause(); a.removeAttribute("src"); a.load(); }

function playOne(a, btn, signal, timeout = 6000) {
  return new Promise((resolve, reject) => {
    // a missing file can hang instead of failing: give up if it never starts
    const timer = setTimeout(() => { unload(a); done(false); }, timeout);
    const done = (ok) => {
      clearTimeout(timer);
      a.onended = a.onerror = a.onplaying = null;
      ok ? resolve() : reject(new Error("audio failed"));
    };
    a.onended = () => done(true);
    a.onerror = () => done(false);
    a.onplaying = () => { clearTimeout(timer); setBtn(btn, "playing"); };
    signal.stop = () => { clearTimeout(timer); unload(a); resolve(); };
    if (a.error) { done(false); return; }
    a.play().catch(() => done(false));
  });
}

function pause(ms, signal) {
  return new Promise((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.stop = () => { clearTimeout(t); resolve(); };
  });
}

/** Play URLs one after another: stitched Teochew recordings, or Min read
 *  syllable by syllable (`gap` ms of silence between them). The next
 *  `ahead` files load while the current one plays. Skips failures. */
export async function playUrls(urls, btn, { gap = 0, ahead = 2 } = {}) {
  stop();
  const signal = {};
  const me = { stop: () => { signal.cancelled = true; signal.stop?.(); }, btn };
  current = me;
  setBtn(btn, "busy");
  const loaded = [];
  const load = (i) => { if (i < urls.length && !loaded[i]) loaded[i] = loadAudio(urls[i]); };
  let played = 0;
  for (let i = 0; i < urls.length; i++) {
    if (signal.cancelled) break;
    for (let j = i; j <= i + ahead; j++) load(j);
    try { await playOne(loaded[i], btn, signal); played++; } catch { /* skip a missing syllable */ }
    loaded[i] = null;
    if (gap && i < urls.length - 1 && !signal.cancelled) await pause(gap, signal);
  }
  loaded.forEach((a) => { if (a) unload(a); });
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
  // recordings hosted with the app (see web/audio/CREDITS.md)
  if (key.startsWith("c:")) return `audio/cmn/cmn-${key.slice(2)}.mp3`;
  if (key.startsWith("v:")) return `audio/vie/${encodeURIComponent(key.slice(2))}`;
  return null;
}
