"""Per-character sound-change notes for the evolution tree.

Given a character's Middle Chinese 音韻地位 (e.g. ``透開四先平``), derive which
of the *regular*, textbook sound laws actually applied to THIS character on the
way to each modern branch — 入聲 loss/retention, 全濁 devoicing (and each
branch's signature reflex of it), velar palatalisation, -m merger, 輕脣化 and
知-series retroflexion (which Min escaped), and the Sino-Xenic coda
adaptations. The app attaches them as hover tooltips on the tree nodes, keyed
by the node ids in ``app._EVO``.

These are first-order regularities (the comparative-method backbone), not
exhaustive per-character philology; exceptions (colloquial strata, sporadic
changes) are exactly what the attested readings above the tree show.
"""
from __future__ import annotations

from .appkit import parse_mc_position

# ---- Middle Chinese initial classes -------------------------------------
FULL_MUDDY = set("並奉定澄羣群從邪崇床俟船常禪匣")     # 全濁 voiced obstruents
SONORANTS = set("明微泥孃娘疑來日云雲以喻")           # 次濁
VELAR_LARYNGEAL = set("見溪羣群曉匣影疑")             # 牙喉音 (palatalise in Mandarin)
DENTAL_RETROFLEX = set("知徹澄孃娘")                  # 知系 (stays t- in Min)
BILABIAL = set("幫滂並明")                            # 幫組 (輕脣化 input)

# ---- rime → coda class (韻 grouped by 攝; mirrors reconstruct.py) --------
_RIME_LABIAL = set("侵覃談鹽添咸銜嚴凡")               # -m / -p
_RIME_CORONAL = set("真眞諄臻文殷欣魂痕寒桓刪山先仙元")  # -n / -t
_RIME_VELAR = set("東冬鍾江陽唐庚耕清青蒸登")          # -ŋ / -k
# 輕脣十韻: the 三等 rimes where 幫組 became f- (Late MC) — except in Min.
_QINGCHUN_RIMES = set("東鍾微虞廢文元陽尤凡")


def _coda_class(rime: str) -> str:
    if rime in _RIME_LABIAL:
        return "m"
    if rime in _RIME_CORONAL:
        return "n"
    if rime in _RIME_VELAR:
        return "ŋ"
    return ""


def edge_notes(mc_position: str) -> dict[str, list[str]]:
    """{tree-node-id: [notes]} for one 音韻地位 code. Empty dict if unparsable."""
    p = parse_mc_position(mc_position)
    if not p or not p.get("tone"):
        return {}
    ini, hu, div, rime, tone = (p["initial"], p["hu"], p["div"],
                                p["rime"], p["tone"])
    muddy = ini in FULL_MUDDY
    sonorant = ini in SONORANTS
    entering = tone == "入"
    coda = _coda_class(rime)
    notes: dict[str, list[str]] = {k: [] for k in
                                   ("man", "jin", "wu", "yue", "hak", "gan",
                                    "xia", "hui", "pmin", "sj", "sk", "sv")}

    # ---- Mandarin ----
    if entering:
        notes["man"].append("入聲 lost: the stop coda (-p/-t/-k) dropped and "
                            "the syllable was redistributed to another tone")
    if muddy:
        notes["man"].append("全濁 initial devoiced — "
                            + ("aspirated, because the tone is 平 (b→pʰ)"
                               if tone == "平" else "plain, in a non-平 tone (b→p)"))
    if ini in VELAR_LARYNGEAL and (div in "三四" or (div == "二" and hu != "合")):
        notes["man"].append("velar/guttural palatalised before the front "
                            "medial (k/kʰ/x → j/q/x)")
    if coda == "m" and not entering:
        notes["man"].append("-m coda merged into -n")
    if not entering:
        if tone == "平":
            notes["man"].append("陽平 → tone 2 (voiced-initial 平聲)"
                                if (muddy or sonorant)
                                else "陰平 → tone 1 (voiceless-initial 平聲)")
        elif tone == "上":
            notes["man"].append("濁上變去: 全濁 上聲 became tone 4"
                                if muddy else "上聲 → tone 3")
        elif tone == "去":
            notes["man"].append("去聲 → tone 4")

    # ---- Jin ----
    if entering:
        notes["jin"].append("keeps 入聲 as a short glottal-stop (ʔ) tone — "
                            "the main trait separating Jin from Mandarin")

    # ---- Wu ----
    if muddy:
        notes["wu"].append("keeps the VOICED initial (b- d- g- z- survive "
                           "only in Wu and Old Xiang)")
    if entering:
        notes["wu"].append("入聲 coda reduced to a glottal stop ʔ (short tone)")

    # ---- Cantonese (Yue) ----
    if entering:
        notes["yue"].append("keeps the full -p/-t/-k stop coda")
    if coda == "m" and not entering:
        notes["yue"].append("keeps the -m coda")
    if muddy:
        notes["yue"].append("全濁 devoiced → lower (陽) register tone")

    # ---- Hakka / Gan ----
    for node in ("hak", "gan"):
        if muddy:
            notes[node].append("全濁 devoiced to ASPIRATED in every tone "
                               "(b→pʰ even in 仄聲) — the Hakka–Gan signature")
        if entering and node == "hak":
            notes[node].append("keeps -p/-t/-k")

    # ---- Xiang ----
    if muddy:
        notes["xia"].append("全濁 devoiced, unaspirated (New Xiang / Changsha; "
                            "Old Xiang still voices them)")

    # ---- Hui ----
    if entering:
        notes["hui"].append("入聲 reduced to a glottal stop / lost, "
                            "but stays a separate tone")

    # ---- proto-Min: pre-MC split, so LATER innovations never applied ----
    if ini in DENTAL_RETROFLEX:
        notes["pmin"].append("知 series stays DENTAL t- (Min split off before "
                             "retroflexion — MC ʈ never formed here)")
    if ini in BILABIAL and div == "三" and rime in _QINGCHUN_RIMES:
        notes["pmin"].append("stays bilabial p-: 輕脣化 (p→f) happened after "
                             "the Min split, so Min never got f-")
    if entering:
        notes["pmin"].append("入聲 kept (daughters keep -p/-t/-k, -ʔ, or both)")

    # ---- Sino-Japanese ----
    if entering:
        notes["sj"].append("the stop coda became its own syllable: "
                           "-p→ふ/-t→つ·ち/-k→く·き")
    if coda == "ŋ" and not entering:
        notes["sj"].append("-ŋ became a vowel — modern long ō / ei")
    if coda == "m" and not entering:
        notes["sj"].append("-m → ん (n)")
    if muddy:
        notes["sj"].append("go-on (older layer) keeps the voice (b/d/g/z), "
                           "kan-on devoices — hence doublets")

    # ---- Sino-Korean ----
    if entering:
        notes["sk"].append("-t became -l (ㄹ) — the regular Sino-Korean shift"
                           if coda == "n" else "keeps the -p/-k stop coda")

    # ---- Sino-Vietnamese ----
    if entering:
        notes["sv"].append("keeps -p/-t/-k; entering-tone words get "
                           "sắc or nặng tone")
    elif muddy or sonorant:
        notes["sv"].append("voiced initial → lower-register tone "
                           "(huyền/nặng/ngã)")

    return {k: v for k, v in notes.items() if v}
