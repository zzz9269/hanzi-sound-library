// Family-tree view of one character's pronunciation: Old Chinese at the far
// left, the historical stages in the middle, every modern variety on the
// right, each hanging where its branch split off.
//
// The shape follows the mainstream classification (Norman 1988, Li Rong /
// Language Atlas of China): Min split from Old Chinese around the Han, before
// the Qieyun (601 CE), and divides into Coastal and Inland Min; every other
// variety descends through Early and Late Middle Chinese. Group nodes
// (Northern, Hakka–Gan, Coastal / Inland / Southern Min) carry no reading:
// they mark where branches part, not a language with recorded forms.
// Japanese, Korean and Vietnamese readings are borrowings, drawn dashed.
import * as D from "./data.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// id, name, Chinese name, column (0 = oldest), parent, data columns, kind,
// colour family, era line, what the node is
const NODES = [
  { id: "oc", name: "Old Chinese", han: "上古漢語", x: 0, cols: ["Old Chinese (Zhengzhang)", "Old Chinese"],
    tags: ["Zhengzhang", "Baxter–Sagart"], kind: "stage", fam: "old", era: "c. 1000–200 BCE",
    about: "The language of the Zhou classics. Nothing records its sounds directly, so it is reconstructed from rhymes in the Shijing, the phonetic parts of characters and later forms. Two leading systems are shown: Zhengzhang Shangfang (2003) and Baxter–Sagart (2014)." },

  { id: "pmin", name: "Proto-Min", han: "原始閩語", x: 1, parent: "oc", cols: ["Proto-Min"], kind: "stage", fam: "min",
    era: "split c. Han dynasty",
    about: "Min is the one branch that does not descend from Qieyun Middle Chinese: it split off around the Han dynasty and keeps distinctions Middle Chinese had already lost. This reconstruction is the app's own, worked out from the Min daughters by the comparative method; no published Proto-Min covers every character." },
  { id: "coastal", name: "Coastal Min", han: "沿海閩語", x: 2, parent: "pmin", kind: "group", fam: "min",
    about: "Norman's Coastal Min: Southern Min and Eastern Min (and Puxian, not shown)." },
  { id: "smin", name: "Southern Min", han: "閩南語", x: 3, parent: "coastal", kind: "group", fam: "min",
    about: "Southern Min. Besides the vernacular (白讀) layer inherited from Proto-Min, it has a literary (文讀) layer borrowed from the Tang–Song standard language for reading texts aloud: the dashed line from Late Middle Chinese." },
  { id: "hok", name: "Taiwanese Hokkien", han: "臺語", x: 4, parent: "smin", cols: ["Hokkien"], fam: "min",
    about: "Taiwanese Hokkien, a Quanzhou–Zhangzhou blend. Readings are read in citation tone; Hokkien changes tones before another syllable (sandhi)." },
  { id: "teo", name: "Teochew (Swatow)", han: "潮州話", x: 4, parent: "smin", cols: ["Teochew"], fam: "min",
    about: "Teochew of Swatow (Shantou), the Chaoshan branch of Southern Min." },
  { id: "hai", name: "Hainanese", han: "海南話", x: 4, parent: "smin", cols: ["Hainanese (Haikou)"], fam: "min",
    about: "Hainanese (Haikou). With Leizhou it forms the Qiong–Lei offshoot of Southern Min, which has drifted far from Hokkien (implosive ɓ- ɗ-, for example)." },
  { id: "emin", name: "Eastern Min", han: "閩東語", x: 4, parent: "coastal", cols: ["Eastern Min (Fuzhou)"], fam: "min",
    about: "Eastern Min (Fuzhou), known for initial assimilation and vowel alternation between syllables in connected speech." },
  { id: "inland", name: "Inland Min", han: "內陸閩語", x: 2, parent: "pmin", kind: "group", fam: "min",
    about: "Norman's Inland Min, spoken in the hills of north-western Fujian." },
  { id: "nmin", name: "Northern Min", han: "閩北語", x: 4, parent: "inland", cols: ["Northern Min (Jian'ou)"], fam: "min",
    about: "Northern Min (Jian'ou). Its 'softened' initials are key evidence for reconstructing Proto-Min." },

  { id: "emc", name: "Early Middle Chinese", han: "中古漢語", x: 1, parent: "oc", cols: ["Middle Chinese", "Middle Chinese (Baxter)"],
    tags: ["Baxter", "IPA"], kind: "stage", fam: "mid", era: "Qieyun 切韻, 601 CE",
    about: "The sound system of the Qieyun rhyme dictionary (601 CE), reconstructed from its fanqie spellings and the later rhyme tables. Every non-Min variety's sounds can be traced back to its categories." },
  { id: "lmc", name: "Late Middle Chinese", han: "晚期中古漢語", x: 2, parent: "emc", cols: ["Tang"], tags: ["Stimson"],
    kind: "stage", fam: "mid", era: "Tang, c. 8th–10th c.",
    about: "The Tang standard of Chang'an. Its innovations, such as f- from p- before certain rimes, are shared by every non-Min variety. Reading: Stimson's Tang reconstruction (1976, via Unihan), where one exists." },
  { id: "north", name: "Northern Chinese", han: "北方話", x: 3, parent: "lmc", kind: "group", fam: "north",
    about: "Mandarin descends through Early Mandarin (the Zhongyuan Yinyun 中原音韻 of 1324), which had already lost the entering tone. Jin, in Shanxi, is closely related but keeps it; some classify Jin as Mandarin." },
  { id: "man", name: "Mandarin", han: "普通話", x: 4, parent: "north", cols: ["Mandarin"], fam: "north", about: "Standard Mandarin (Beijing)." },
  { id: "jin", name: "Jin", han: "晉語", x: 4, parent: "north", cols: ["Jin"], fam: "north", about: "Jin (Taiyuan)." },
  { id: "wu", name: "Wu", han: "吳語", x: 4, parent: "lmc", cols: ["Wu"], fam: "other",
    about: "Wu (Shanghai): the only major group that still has Middle Chinese voiced initials (b- d- g- z-). Its colloquial layer keeps some older features too." },
  { id: "hui", name: "Hui", han: "徽語", x: 4, parent: "lmc", cols: ["Hui (Shexian)"], fam: "other",
    about: "Hui (Shexian), southern Anhui. Its classification is debated; it was once grouped with Wu." },
  { id: "xia", name: "Xiang", han: "湘語", x: 4, parent: "lmc", cols: ["Xiang"], fam: "other",
    about: "Xiang (Changsha, a New Xiang variety). Old Xiang varieties still keep voiced initials." },
  { id: "hg", name: "Hakka–Gan", han: "客贛", x: 3, parent: "lmc", kind: "group", fam: "other",
    about: "Hakka and Gan share a signature change: Middle Chinese voiced stops became aspirated in every tone. They are often grouped together." },
  { id: "gan", name: "Gan", han: "贛語", x: 4, parent: "hg", cols: ["Gan"], fam: "other", about: "Gan (Nanchang)." },
  { id: "hak", name: "Hakka", han: "客家話", x: 4, parent: "hg", cols: ["Hakka"], fam: "other",
    about: "Hakka. Its ancestors moved south in waves from the Song dynasty onwards." },
  { id: "yue", name: "Cantonese", han: "粵語", x: 4, parent: "lmc", cols: ["Cantonese"], fam: "other",
    about: "Cantonese (Guangzhou / Hong Kong) keeps all six Middle Chinese codas (-p -t -k -m -n -ŋ) and splits every tone by the old voicing of the initial." },

  { id: "sj", name: "Sino-Japanese", han: "音読み", x: 4, parent: "lmc", cols: ["Japanese On"], fam: "loan", loan: true,
    era: "go-on 5–6th c. · kan-on 7–9th c.",
    about: "On'yomi were borrowed, not inherited, in layers: go-on (5th–6th c., from southern China) and kan-on (7th–9th c., from Tang Chang'an). Hence the dashed line." },
  { id: "sk", name: "Sino-Korean", han: "漢字音", x: 4, parent: "lmc", cols: ["Korean (Hangul)", "Korean (romanized)"], fam: "loan", loan: true,
    era: "borrowed c. 8th–10th c.", about: "Sino-Korean readings, borrowed mainly from Late Middle Chinese." },
  { id: "sv", name: "Sino-Vietnamese", han: "漢越音", x: 4, parent: "lmc", cols: ["Vietnamese"], fam: "loan", loan: true,
    era: "borrowed c. 9th–10th c.", about: "Sino-Vietnamese readings, borrowed from Late Middle Chinese around the late Tang." },
];
const BY_ID = Object.fromEntries(NODES.map((n) => [n.id, n]));
// Southern Min's literary readings: a borrowed layer, not descent
const EXTRA_EDGES = [{ from: "lmc", to: "smin", label: "文讀 literary layer" }];

// ------------------------------------------------------------ sound laws --
// Regular changes that shaped THIS character in each branch, from its Middle
// Chinese position (音韻地位, e.g. 透開四先平). First-order regularities only:
// colloquial layers and sporadic exceptions are what the readings themselves show.
const MUDDY_STOP = new Set("並定澄羣群從崇床");      // 全濁 stops / affricates
const MUDDY_FRIC = new Set("奉邪匣船常禪俟");         // 全濁 fricatives (+ ambiguous 船 禪)
const SONORANT = new Set("明微泥孃娘疑來日云雲以喻");
const ZHI = new Set("知徹澄孃娘");
const BILABIAL = new Set("幫滂並明");
const NASAL_INI = new Set("明泥孃娘");
const R_M = new Set("侵覃談鹽添咸銜嚴凡");
const R_N = new Set("真眞諄臻文殷欣魂痕寒桓刪山先仙元");
const R_NG = new Set("東冬鍾江陽唐庚耕清青蒸登");
const QINGCHUN = new Set("東鍾微虞廢文元陽尤凡");    // 輕脣十韻
const TONES = "平上去入", HU = "開合", DIV = "一二三四";

function parsePos(code) {
  const cs = Array.from((code || "").trim());
  if (cs.length < 3) return null;
  const tone = TONES.includes(cs[cs.length - 1]) ? cs.pop() : "";
  const ini = cs.shift();
  let hu = "", div = "", rime = "";
  for (const c of cs) {
    if (HU.includes(c)) hu = c;
    else if (DIV.includes(c)) div = c;
    else if (!"ABC".includes(c)) rime += c;
  }
  return tone ? { ini, hu, div, rime, tone } : null;
}

export function soundLaws(code, man = "") {
  const p = parsePos(code);
  if (!p) return {};
  const { ini, div, rime, tone } = p;
  const stop = MUDDY_STOP.has(ini), fric = MUDDY_FRIC.has(ini), muddy = stop || fric;
  const son = SONORANT.has(ini), ent = tone === "入";
  const coda = R_M.has(rime) ? "m" : R_N.has(rime) ? "n" : R_NG.has(rime) ? "ŋ" : "";
  // 明 in the 東 and 尤 rimes stayed m- (夢 mèng, 謀 móu)
  const qingchun = BILABIAL.has(ini) && div === "三" && QINGCHUN.has(rime)
    && !(ini === "明" && (rime === "東" || rime === "尤"));
  // the character's Mandarin onset, so a note never claims a change it did not undergo
  const manOn = man.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const labialIni = BILABIAL.has(ini) || "非敷奉微".includes(ini);
  const N = {};
  const add = (id, s) => (N[id] = N[id] || []).push(s);

  // Late Middle Chinese: shared by every non-Min descendant
  if (qingchun) add("lmc", ini === "明" ? "輕脣化: m- became labiodental ʋ- here (later w- in Mandarin)"
    : "輕脣化: the bilabial became labiodental here (p- pʰ- b- → f-), so non-Min varieties have f-");
  if (ZHI.has(ini)) add("lmc", "知 series: the retroflex stop ʈ- became an affricate, merging with the 照 series (Mandarin zh- / ch-)");

  // Proto-Min: split before those changes
  if (qingchun) add("pmin", "stays bilabial p- / b- / m-: f- arose in Late Middle Chinese, after Min had split off");
  if (ZHI.has(ini)) add("pmin", "知 series stays a plain dental t- (Min split before it became retroflex)");
  if (ent) add("pmin", "entering tone kept with its stop coda; daughters show -p -t -k, a glottal -ʔ, or (Northern Min) only a separate tone");

  // Mandarin
  if (ent) {
    add("man", "entering tone lost: the -p/-t/-k coda dropped (already gone in Early Mandarin, 1324)");
    add("man", stop || fric ? "全濁 entering syllables mostly went to tone 2"
      : son ? "次濁 entering syllables mostly went to tone 4"
      : "清 entering syllables were scattered over all four tones (no single rule)");
  }
  if (stop) add("man", tone === "平" ? "voiced stop devoiced to an ASPIRATED one because the tone is 平 (b- → pʰ-)"
    : "voiced stop devoiced to a plain one because the tone is not 平 (b- → p-)");
  if (fric) add("man", {
    匣: "voiced ɦ- devoiced to x- (h-)", 邪: "voiced z- devoiced to s-", 奉: "voiced labiodental devoiced to f-",
  }[ini] || "voiced initial devoiced (in 平 these often became the affricate ch-)");
  if ("見溪羣群曉匣".includes(ini) && /^[jqx]/.test(manOn))
    add("man", "velar palatalised before i / ü in the Qing era (k- kʰ- x- → j- q- x-)");
  if ("精清從心邪".includes(ini) && /^[jqx]/.test(manOn))
    add("man", "dental sibilant palatalised before i / ü (ts- s- → j- x-), merging with the velars: 尖團合流");
  if ((ini === "微" || (qingchun && ini === "明")) && manOn.startsWith("w")) add("man", "labiodental ʋ- → w-");
  if (coda === "m" && !ent) add("man", "-m merged into -n");
  if (!ent) {
    if (tone === "平") add("man", muddy || son ? "陽平 → tone 2 (平 with a voiced initial)" : "陰平 → tone 1 (平 with a voiceless initial)");
    else if (tone === "上") add("man", muddy ? "全濁上 became 去: tone 4 (濁上變去)" : "上聲 → tone 3");
    else add("man", "去聲 → tone 4");
  }

  // Jin
  if (ent) add("jin", "keeps the entering tone as a short -ʔ syllable: the main trait separating Jin from Mandarin");
  if (stop) add("jin", tone === "平" ? "voiced stop → aspirated in 平, like Mandarin" : "voiced stop → plain in non-平 tones, like Mandarin");

  // Wu
  if (muddy) add("wu", "keeps the VOICED initial (murmured b- d- g- z- ɦ-)");
  if (ent) add("wu", "entering coda reduced to a glottal stop -ʔ (a short tone)");
  if (muddy || son) add("wu", "lower (陽) tone register, from the voiced or sonorant initial");

  // Cantonese
  if (ent) add("yue", "keeps the stop coda; the entering tone split into three by voicing and vowel length");
  if (coda === "m") add("yue", labialIni ? `after a labial initial -${ent ? "p" : "m"} dissimilated to -${ent ? "t" : "n"} (法 faat, 凡 faan)`
    : `keeps the labial -${ent ? "p" : "m"} coda`);
  if (stop) add("yue", tone === "平" || tone === "上" ? "voiced stop → aspirated, as usual in 平 and 上 (陽平 / 陽上)"
    : "voiced stop → plain, as usual in 去 and 入 (陽去 / 陽入)");
  if (muddy || son) add("yue", "lower (陽) tone register, from the voiced or sonorant initial");
  if (qingchun) add("yue", "f- from the Late Middle Chinese labiodental");

  // Hakka / Gan
  for (const id of ["hak", "gan"])
    if (stop) add(id, "voiced stop → ASPIRATED in every tone (b- → pʰ- even outside 平): the Hakka–Gan signature");
  if (ent && coda !== "m") add("hak", `keeps the stop coda (-${coda === "n" ? "t" : coda === "ŋ" ? "k" : "p / -t / -k"})`);
  if (coda === "m") add("hak", ent ? "keeps the labial -p" : "keeps the -m coda");

  // Xiang
  if (stop) add("xia", "voiced stop → plain voiceless in Changsha (Old Xiang varieties keep the voicing)");

  // Hui
  if (ent) add("hui", "entering coda lost or reduced; often still a separate tone");

  // Sino-Japanese
  if (ent) add("sj", "the stop coda became its own syllable: -p → -fu (now -u), -t → -tsu / -chi, -k → -ku / -ki");
  if (coda === "ŋ" && !ent) add("sj", "-ŋ became a vowel: modern long ō / ei / -u");
  if (coda === "m" && !ent) add("sj", "-m → -n");
  if (muddy) add("sj", "go-on keeps the voicing (b- d- g- z-), kan-on devoices it: hence doublets");
  if (NASAL_INI.has(ini)) add("sj", "kan-on reflects Chang'an's denasalised initials (m- → b-, n- → d-); go-on keeps the nasal");
  if (ini === "日") add("sj", "go-on n-, kan-on z- / j- (人 nin / jin)");

  // Sino-Korean
  if (ent && coda !== "m") add("sk", coda === "n" ? "-t became -l (ㄹ): the regular Sino-Korean shift" : "keeps the -k stop");
  if (coda === "m") add("sk", ent ? "keeps the -p" : "keeps the -m");

  // Sino-Vietnamese
  if (ent) add("sv", `keeps the stop coda; entering tone → ${muddy || son ? "nặng (voiced initial)" : "sắc (voiceless initial)"}`);
  else if (tone === "平") add("sv", muddy || son ? "平 with a voiced initial → huyền" : "平 with a voiceless initial → ngang");
  else if (tone === "上") add("sv", muddy || son ? "上 with a voiced initial → ngã (some 全濁 words nặng)" : "上 with a voiceless initial → hỏi");
  else add("sv", muddy || son ? "去 with a voiced initial → nặng" : "去 with a voiceless initial → sắc");
  return N;
}

// ---------------------------------------------------------------- layout --
const STRAT = { v: ["白", "vernacular (白讀)"], l: ["文", "literary (文讀)"] };
const COL_W = 188, CARD_W = 168, LEAF_W = 212, ROW_H = 70, PAD_Y = 56;

function readings(e, node) {
  const out = [];
  node.cols?.forEach((c, i) => {
    const k = D.colIdx(c);
    const rs = (e.v?.[k] || e.i?.[k] || []).slice(0, c === "Japanese On" ? 3 : 2);
    if (rs.length) out.push({ tag: node.tags?.[i] || "", rs });
  });
  if (node.id === "sk" && out.length === 2) {          // 천 (chen)
    out[0].rs = out[0].rs.map((r, i) => ({ ...r, t: out[1].rs[i] ? `${r.t} (${out[1].rs[i].t})` : r.t }));
    out.length = 1;
  }
  return out;
}

export function treeHTML(e, ch) {
  const R = Object.fromEntries(NODES.map((n) => [n.id, n.cols ? readings(e, n) : []]));
  // which nodes show: leaves with a reading, groups with a visible child,
  // stages always (structural), Proto-Min only when a Min daughter shows
  const kids = {};
  NODES.forEach((n) => n.parent && (kids[n.parent] = kids[n.parent] || []).push(n.id));
  const vis = {};
  const visit = (id) => {
    const n = BY_ID[id];
    const childVis = (kids[id] || []).map(visit).some(Boolean);
    vis[id] = n.kind === "stage" ? (id === "pmin" ? childVis : true)
      : n.kind === "group" ? childVis : R[id].length > 0;
    return vis[id];
  };
  visit("oc");

  // leaves top to bottom in tree order; parents centred on their children
  const pos = {};
  let row = 0;
  const place = (id) => {
    const ch2 = (kids[id] || []).filter((k) => vis[k]);
    if (!ch2.length) { pos[id] = row++ * ROW_H; return; }
    ch2.forEach(place);
    const ys = ch2.map((k) => pos[k]);
    pos[id] = (Math.min(...ys) + Math.max(...ys)) / 2;
  };
  place("oc");
  const H = (row - 1) * ROW_H + 2 * PAD_Y - 6, W = 4 * COL_W + LEAF_W + 8;
  const X = (n) => n.x * COL_W + 4, Y = (id) => pos[id] + PAD_Y;

  const curve = (a, b, cls, label = "") => {
    const x1 = X(a) + CARD_W, y1 = Y(a.id), x2 = X(b), y2 = Y(b.id), mx = (x1 + x2) / 2;
    return `<path class="${cls}" d="M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}"/>`
      // label runs vertically beside the near-vertical curve
      + (label ? `<text class="t-elabel" x="${mx - 5}" y="${(y1 + y2) / 2}" text-anchor="middle" transform="rotate(-90 ${mx - 5} ${(y1 + y2) / 2})">${esc(label)}</text>` : "");
  };
  const edges = NODES.filter((n) => vis[n.id] && n.parent && vis[n.parent])
    .map((n) => curve(BY_ID[n.parent], n, n.loan ? "t-edge loan" : "t-edge")).join("")
    + EXTRA_EDGES.filter((x) => vis[x.from] && vis[x.to])
      .map((x) => curve(BY_ID[x.from], BY_ID[x.to], "t-edge layer", x.label)).join("");

  const card = (n) => {
    const rd = R[n.id].map((g) => `<span class="t-rd">${g.tag && R[n.id].length > 1 ? `<i>${esc(g.tag)}</i>` : ""}${
      g.rs.map((r) => esc(r.t) + (STRAT[r.k] ? `<sup class="t-k ${r.k}" title="${STRAT[r.k][1]}">${STRAT[r.k][0]}</sup>` : "")
        + (r.m ? '<b class="badge-ml" title="Machine-predicted, not attested in a source">ML</b>' : "")).join(" · ")}</span>`).join("");
    const empty = n.kind === "stage" && !rd ? `<span class="t-rd none">no reading recorded</span>` : "";
    return `<button class="t-node ${n.kind || "leaf"} f-${n.fam}${n.loan ? " loan" : ""}" data-node="${n.id}"
      style="left:${X(n)}px;top:${Y(n.id)}px${n.x === 4 ? `;width:${LEAF_W}px` : ""}">
      <span class="t-name">${esc(n.name)}${n.kind === "group" ? "" : ` <span class="han">${esc(n.han)}</span>`}</span>
      ${rd}${empty}${n.era ? `<span class="t-era">${esc(n.era)}</span>` : ""}</button>`;
  };
  const head = ["Zhou", "Han – Sui", "Tang", "Song – Yuan", "Today"].map((t, i) =>
    t ? `<span class="t-col" style="left:${i * COL_W + 4}px">${t}</span>` : "").join("");

  return `<p class="tree-hint">Swipe sideways to follow each branch from Old Chinese to today →</p>
    <div class="tree-scroll"><div class="tree" style="width:${W}px;height:${H}px">
      ${head}
      <svg class="t-svg" width="${W}" height="${H}" aria-hidden="true">${edges}</svg>
      ${NODES.filter((n) => vis[n.id]).map(card).join("")}
    </div></div>
    <div class="tree-detail" id="tree-detail" aria-live="polite"><p class="muted">Tap any box to see what it is and which regular sound changes gave ${esc(ch)} its form there.</p></div>
    <p class="tree-legend"><span class="sw f-min"></span>Min (split before Middle Chinese)
      <span class="sw f-north"></span>Northern
      <span class="sw f-other"></span>other branches
      <span class="sw f-loan"></span>borrowed (dashed)
      · Groups without a reading mark where branches part; columns are rough periods, and the dates of the group splits are approximate. Simplified: Puxian, Pinghua, Leizhou and others are not shown.</p>`;
}

export function bindTree(root, e) {
  const pos = (e.v?.[D.colIdx("Middle Chinese (position)")] || [])[0]?.t || "";
  const laws = soundLaws(pos, (e.v?.[D.colIdx("Mandarin")] || [])[0]?.t || "");
  const detail = root.querySelector("#tree-detail");
  root.querySelectorAll(".t-node").forEach((b) => b.addEventListener("click", () => {
    root.querySelectorAll(".t-node.sel").forEach((x) => x.classList.remove("sel"));
    b.classList.add("sel");
    const n = BY_ID[b.dataset.node];
    const notes = laws[n.id] || [];
    const lawHTML = notes.length
      ? `<h4>Regular sound changes for this character${pos ? ` <span class="han">(${esc(pos)})</span>` : ""}</h4><ul>${notes.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`
      : n.kind ? "" : pos ?`<p class="muted">No textbook sound change singles this character out here; its form follows the branch's regular correspondences.</p>` : "";
    const conf = n.id === "pmin" ? (e.n?.[D.colIdx("Proto-Min")] || [])[0]?.conf : null;
    const confHTML = conf != null
      ? `<p class="muted">For ${esc(e.ch || "")} the Min daughters agree on the reconstructed vowel ${Math.round(conf * 100)}%; onset, coda and tone are anchored on Middle Chinese categories.</p>` : "";
    detail.innerHTML = `<h3>${esc(n.name)} <span class="han">${esc(n.han)}</span></h3>${n.era ? `<p class="t-era">${esc(n.era)}</p>` : ""}
      <p>${esc(n.about)}</p>${confHTML}${lawHTML}`;
    const r = detail.getBoundingClientRect();
    if (r.bottom > innerHeight - 70 || r.top < 0) detail.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }));
}
