"""Hindi typed in Latin letters, written in Devanagari for the Hindi voice.

"kal kya hai?" is how most people type Hindi on a phone, and an agent
answering them answers the same way. Piper's Hindi voice reads only
Devanagari: given "kal kya hai" it dropped the words it couldn't place
and garbled the rest, and the English voice read it as English ("caal
kaya high"). Whisper, listening back, heard neither. So the words are
written in Devanagari first, and then read.

THE COMMON WORDS FROM A LIST, THE REST BY RULE. Romanised Hindi has no
one spelling ("nahi", "nahin", "nai"), and the same letters stand for
two sounds ("t" is त or ट), so a rule alone gets the words said most
often wrong in small ways a listener notices: "hain" read as हैन, not
हैं. The commonest few hundred words come from a list; anything else is
spelt out by the casual romanisation people use: two letters for a long
vowel ("aa", "ee", "oo"), "h" after a consonant for its breathy form
("kh", "bh"), "n" before a consonant as the nasal mark (अंदर), any other
consonant before another joined to it (्), and a word's final "a" or
"i", or an "a" before another vowel, read long (रहा, रही, चलाओ), which
is how it is typed.

ONLY WHAT WAS SURE TO BE HINDI. The answer's language is told first
(``spoken.languages_of``, by Hindi's small words); text that isn't
Hindi never comes here, and inside a Hindi answer a word in another
script, a number or a mark is left as it was. (Web addresses and code
were taken out before, as for every voice: ``spoken.aloud``.)

What it can't do: English words inside a Hindi sentence ("meeting")
are spelt as Hindi spells them by ear, which is mostly how they are
said; names it doesn't know are spelt by rule and may come out a little
wrong. Telling a word from its look is a model's job, and this is the
step before a voice, where no model runs.
"""

from __future__ import annotations

import re

#: The words said most, as they're typed (each spelling) and as written.
WORDS = {
    "hai": "है", "hain": "हैं", "hei": "है", "h": "है", "ho": "हो", "hoon": "हूँ",
    "hun": "हूँ", "hu": "हूँ", "tha": "था", "thi": "थी", "thin": "थीं",
    "kya": "क्या", "kyaa": "क्या", "kyu": "क्यों", "kyun": "क्यों", "kyon": "क्यों",
    "kab": "कब", "kahan": "कहाँ", "kaha": "कहाँ", "kaun": "कौन", "kaise": "कैसे",
    "kaisa": "कैसा", "kaisi": "कैसी", "kitna": "कितना", "kitne": "कितने",
    "kitni": "कितनी", "ka": "का", "ki": "की", "ke": "के", "ko": "को", "se": "से",
    "me": "में", "mein": "में", "mai": "मैं", "main": "मैं", "mujhe": "मुझे",
    "mera": "मेरा", "meri": "मेरी", "mere": "मेरे", "hum": "हम", "hamara": "हमारा",
    "hamari": "हमारी", "aap": "आप", "ap": "आप", "aapka": "आपका", "aapki": "आपकी",
    "aapke": "आपके", "tum": "तुम", "tu": "तू", "tumhara": "तुम्हारा",
    "tumhari": "तुम्हारी", "yeh": "यह", "ye": "ये", "yah": "यह", "woh": "वह",
    "wo": "वो", "vah": "वह", "voh": "वह", "isko": "इसको",
    "usko": "उसको", "unka": "उनका", "unki": "उनकी", "inka": "इनका", "aur": "और",
    "ya": "या", "par": "पर", "pe": "पे", "lekin": "लेकिन", "magar": "मगर",
    "kyunki": "क्योंकि", "agar": "अगर", "to": "तो", "toh": "तो", "bhi": "भी",
    "hi": "ही", "na": "ना", "nahi": "नहीं", "nahin": "नहीं", "nai": "नहीं",
    "mat": "मत", "haan": "हाँ", "han": "हाँ", "ji": "जी", "accha": "अच्छा",
    "acha": "अच्छा", "achha": "अच्छा", "acchi": "अच्छी", "achhi": "अच्छी",
    "theek": "ठीक", "thik": "ठीक", "bahut": "बहुत", "bohot": "बहुत", "kuch": "कुछ",
    "sab": "सब", "sabhi": "सभी", "koi": "कोई", "ek": "एक", "do": "दो", "teen": "तीन",
    "char": "चार", "paanch": "पाँच", "aaj": "आज", "kal": "कल", "parso": "परसों",
    "abhi": "अभी", "ab": "अब", "phir": "फिर", "fir": "फिर", "jab": "जब", "tab": "तब",
    "pehle": "पहले", "baad": "बाद", "subah": "सुबह", "shaam": "शाम", "raat": "रात",
    "din": "दिन", "samay": "समय", "waqt": "वक़्त", "baje": "बजे", "ghanta": "घंटा",
    "ghante": "घंटे", "minute": "मिनट", "mausam": "मौसम", "barish": "बारिश",
    "garmi": "गर्मी", "thand": "ठंड", "ghar": "घर", "kaam": "काम", "paani": "पानी",
    "khana": "खाना", "log": "लोग", "baat": "बात", "naam": "नाम", "saal": "साल",
    "kar": "कर", "karo": "करो", "karna": "करना", "karta": "करता", "karti": "करती",
    "karte": "करते", "kiya": "किया", "raha": "रहा", "rahi": "रही",
    "rahe": "रहे", "gaya": "गया", "gayi": "गई", "gaye": "गए", "jana": "जाना",
    "jao": "जाओ", "ja": "जा", "aana": "आना", "aao": "आओ", "aa": "आ", "aaya": "आया",
    "aayi": "आई", "dekho": "देखो", "dekh": "देख", "bolo": "बोलो", "bata": "बता",
    "batao": "बताओ", "batana": "बताना", "sakta": "सकता", "sakti": "सकती",
    "sakte": "सकते", "chahiye": "चाहिए", "chahta": "चाहता", "chahti": "चाहती",
    "diya": "दिया", "liya": "लिया", "dena": "देना", "lena": "लेना",
    "lo": "लो", "hoga": "होगा", "hogi": "होगी", "honge": "होंगे", "hua": "हुआ",
    "hui": "हुई", "hue": "हुए", "wala": "वाला", "wali": "वाली", "wale": "वाले",
    "yahan": "यहाँ", "wahan": "वहाँ", "dhanyavaad": "धन्यवाद", "shukriya": "शुक्रिया",
    "namaste": "नमस्ते", "kripya": "कृपया", "zaroor": "ज़रूर", "jaldi": "जल्दी",
    "zyada": "ज़्यादा", "jyada": "ज़्यादा", "kam": "कम", "bas": "बस", "sirf": "सिर्फ़",
    "aapko": "आपको", "mujhko": "मुझको", "humko": "हमको", "unko": "उनको",
    "liye": "लिए", "lie": "लिए", "saath": "साथ", "sath": "साथ", "paas": "पास",
    "andar": "अंदर", "bahar": "बाहर", "upar": "ऊपर", "neeche": "नीचे",
    # English said inside Hindi: its t and d are ट and ड, which no rule can tell
    "meeting": "मीटिंग", "check": "चेक", "phone": "फ़ोन", "message": "मैसेज",
    "email": "ईमेल", "mail": "मेल", "office": "ऑफ़िस", "time": "टाइम", "ok": "ओके",
    "okay": "ओके", "sorry": "सॉरी", "please": "प्लीज़", "thanks": "थैंक्स",
    "update": "अपडेट", "ticket": "टिकट", "doctor": "डॉक्टर", "date": "डेट",
    "order": "ऑर्डर", "delivery": "डिलीवरी", "battery": "बैटरी", "account": "अकाउंट",
}

#: Two Hindi words in a sentence are a better sign than the same count of
#: English ones (spoken.py), so these are the ones that vote: common, and
#: rarely English. ("to", "is", "main", "the" are both, and so don't.)
VOTES = ("hai hain kya nahi nahin aap mujhe mera meri hum tum yeh woh aur bhi "
         "kal aaj abhi kuch bahut accha theek kaise kab kahan kaun raha rahi "
         "kar karo hoga tha thi ka ki ke ko se mein")

#: Vowels: alone (a word's start, or after a vowel) and as a sign on a consonant.
_VOWELS = (("aa", "आ", "ा"), ("ai", "ऐ", "ै"), ("au", "औ", "ौ"), ("ee", "ई", "ी"),
           ("oo", "ऊ", "ू"), ("a", "अ", ""), ("i", "इ", "ि"), ("u", "उ", "ु"),
           ("e", "ए", "े"), ("o", "ओ", "ो"))
#: Consonants, longest spelling first so "chh" is never "c" + "hh".
_CONSONANTS = (("chh", "छ"), ("cch", "च्छ"), ("ksh", "क्ष"), ("kh", "ख"), ("gh", "घ"),
               ("ch", "च"), ("jh", "झ"), ("th", "थ"), ("dh", "ध"), ("ph", "फ"),
               ("bh", "भ"), ("sh", "श"), ("ck", "क"), ("k", "क"), ("g", "ग"), ("c", "क"),
               ("j", "ज"), ("t", "त"), ("d", "द"), ("n", "न"), ("p", "प"), ("f", "फ़"),
               ("b", "ब"), ("m", "म"), ("y", "य"), ("r", "र"), ("l", "ल"), ("v", "व"),
               ("w", "व"), ("s", "स"), ("h", "ह"), ("z", "ज़"), ("q", "क़"), ("x", "क्स"))
_HALANT = "्"
_WORD = re.compile(r"[A-Za-z]+")


def spell(word: str) -> str:
    """One romanised word in Devanagari: from the list, else by rule."""
    low = word.lower()
    if low in WORDS:
        return WORDS[low]
    out: list[str] = []
    i, after_consonant = 0, False
    while i < len(low):
        vowel = next((v for v in _VOWELS if low.startswith(v[0], i)), None)
        if vowel is not None:
            spelt, alone, sign = vowel
            i += len(spelt)
            ends = i == len(low)
            if spelt == "a" and len(low) > 2 and (ends or _vowel_at(low, i)):
                # typed "raha", "chalao": said रहा, चलाओ
                out.append("ा" if after_consonant else "आ")
            elif spelt == "i" and ends and after_consonant and len(low) > 2:
                out.append("ी")            # typed "rahi", "ghanti": said रही, घंटी
            elif not after_consonant:
                out.append(alone)
            else:
                out.append(sign)
            after_consonant = False
            continue
        consonant = next((c for c in _CONSONANTS if low.startswith(c[0], i)), None)
        if consonant is None:              # not a letter this knows: kept as it is
            out.append(low[i])
            i += 1
            after_consonant = False
            continue
        i += len(consonant[0])
        if consonant[0] == "n" and out and not after_consonant and _consonant_at(low, i) \
                and not low.startswith("n", i):
            out.append("ं")                # "andar": the n is said through the nose
            continue
        if after_consonant:
            out.append(_HALANT)            # two consonants together are joined
        out.append(consonant[1])
        after_consonant = True
    return "".join(out)


def _vowel_at(word: str, i: int) -> bool:
    return i < len(word) and any(word.startswith(v[0], i) for v in _VOWELS)


def _consonant_at(word: str, i: int) -> bool:
    return i < len(word) and not any(word.startswith(v[0], i) for v in _VOWELS) \
        and any(word.startswith(c[0], i) for c in _CONSONANTS)


def devanagari(text: str) -> str:
    """``text``, known to be romanised Hindi, with each Latin word in
    Devanagari; numbers, marks and anything else as they were."""
    return _WORD.sub(lambda m: spell(m.group(0)), text)
