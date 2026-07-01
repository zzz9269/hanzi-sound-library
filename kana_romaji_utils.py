# kana_romaji_utils.py
"""
Romaji → Hiragana helper for your Hanzi tool.

- If 'romkan' is installed, we use it.
  pip install romkan
- Otherwise we fall back to a lightweight manual converter that
  handles normal Hepburn-style readings (no crazy edge cases).
"""

try:
    import romkan as _romkan
    _HAS_ROMKAN = True
except Exception:
    _HAS_ROMKAN = False


def romaji_to_hiragana(romaji: str) -> str:
    s = (romaji or "").strip().lower()
    if not s:
        return ""

    # Best case: delegate to romkan
    if _HAS_ROMKAN:
        try:
            return _romkan.to_hiragana(s)
        except Exception:
            pass  # fall through to manual path

    # -------- Manual fallback (good enough for dictionary-style readings) --------
    table = {
        # digraphs with y
        "kya":"きゃ","kyu":"きゅ","kyo":"きょ",
        "gya":"ぎゃ","gyu":"ぎゅ","gyo":"ぎょ",
        "sha":"しゃ","shu":"しゅ","sho":"しょ",
        "ja":"じゃ","ju":"じゅ","jo":"じょ",
        "cha":"ちゃ","chu":"ちゅ","cho":"ちょ",
        "nya":"にゃ","nyu":"にゅ","nyo":"にょ",
        "hya":"ひゃ","hyu":"ひゅ","hyo":"ひょ",
        "bya":"びゃ","byu":"びゅ","byo":"びょ",
        "pya":"ぴゃ","pyu":"ぴゅ","pyo":"ぴょ",
        "mya":"みゃ","myu":"みゅ","myo":"みょ",
        "rya":"りゃ","ryu":"りゅ","ryo":"りょ",

        # specials
        "shi":"し","chi":"ち","tsu":"つ","fu":"ふ","ji":"じ","dzu":"づ","du":"づ",

        # consonant + vowel
        "ka":"か","ki":"き","ku":"く","ke":"け","ko":"こ",
        "ga":"が","gi":"ぎ","gu":"ぐ","ge":"げ","go":"ご",
        "sa":"さ","si":"し","su":"す","se":"せ","so":"そ",
        "za":"ざ","zi":"じ","zu":"ず","ze":"ぜ","zo":"ぞ",
        "ta":"た","ti":"ち","tu":"つ","te":"て","to":"と",
        "da":"だ","di":"ぢ","du":"づ","de":"で","do":"ど",
        "na":"な","ni":"に","nu":"ぬ","ne":"ね","no":"の",
        "ha":"は","hi":"ひ","hu":"ふ","he":"へ","ho":"ほ",
        "ba":"ば","bi":"び","bu":"ぶ","be":"べ","bo":"ぼ",
        "pa":"ぱ","pi":"ぴ","pu":"ぷ","pe":"ぺ","po":"ぽ",
        "ma":"ま","mi":"み","mu":"む","me":"め","mo":"も",
        "ya":"や","yu":"ゆ","yo":"よ",
        "ra":"ら","ri":"り","ru":"る","re":"れ","ro":"ろ",
        "wa":"わ","wo":"を",

        # vowels
        "a":"あ","i":"い","u":"う","e":"え","o":"お",
    }

    def _consume_small_tsu(rest: str, out: list) -> str:
        # double consonant → small つ (except vowels / n / y)
        if len(rest) >= 2 and rest[0] == rest[1] and rest[0] not in "aeiouyn":
            out.append("っ")
            return rest[1:]
        return rest

    res = []
    i = 0
    n = len(s)
    while i < n:
        # syllabic 'n'
        if s[i] == "n":
            if i == n - 1 or s[i+1] in "bcdfghjklmnpqrstvwxz":
                res.append("ん")
                i += 1
                continue

        # small tsu
        chunk = s[i:]
        before = len(chunk)
        chunk = _consume_small_tsu(chunk, res)
        if len(chunk) != before:
            i = n - len(chunk)
            continue

        # try 3-char
        if i + 3 <= n and s[i:i+3] in table:
            res.append(table[s[i:i+3]])
            i += 3
            continue
        # 2-char
        if i + 2 <= n and s[i:i+2] in table:
            res.append(table[s[i:i+2]])
            i += 2
            continue
        # 1-char (vowel)
        if s[i] in table:
            res.append(table[s[i]])
            i += 1
            continue

        # unknown char: just pass through
        res.append(s[i])
        i += 1

    return "".join(res)
