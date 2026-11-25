"""
textnorm.py — what a phone types, made into what the files use. One place, so the
website (index.html has the same rules in JavaScript), the Review page and the chat all
store and compare the same characters.

Phones change what people type without telling them: a straight apostrophe becomes a
curly one (Eta'ya → Eta’ya), two hyphens become a dash, quotes curl, a space after a
full stop can become a no-break space, and a pasted word can carry invisible characters.
The verified files use the plain forms, so a curly Ma’ya would sit beside Ma'ya as if it
were a different word.

clean(text)                 for any field
clean(text, kenyang=True)   also for a field that holds Kenyang: dashes between letters
                            become the hyphen Kenyang words use (N-ném), and the Greek
                            ε, which looks like ɛ and is not, becomes ɛ.

Tone marks are never touched, beyond NFC: é stays é, ɛ́ stays ɛ́.
"""

import re
import unicodedata

# Curly and look-alike apostrophes. Not ` or ´ on their own: either could be someone
# typing a tone mark, and turning it into an apostrophe would hide that.
APOSTROPHES = "’‘ʼʻ′‛"
DOUBLE_QUOTES = "“”„‟″"
SPACES = "       　"
INVISIBLE = "​‌‍⁠﻿­"
HYPHENS = "‐‑‒−"          # look like "-" and always mean it
DASHES = "–—"                       # en and em: a hyphen only inside a word

_TRANSLATE = {ord(c): "'" for c in APOSTROPHES}
_TRANSLATE.update({ord(c): '"' for c in DOUBLE_QUOTES})
_TRANSLATE.update({ord(c): " " for c in SPACES})
_TRANSLATE.update({ord(c): None for c in INVISIBLE})
_TRANSLATE.update({ord(c): "-" for c in HYPHENS})

_LETTER = r"[^\W\d_]|[̀-ͯ]"
_DASH_IN_WORD = re.compile(rf"(?<={_LETTER})[{DASHES}](?={_LETTER})")


def clean(text, kenyang=False):
    """The text a person meant, in the characters the files use."""
    if not text:
        return text or ""
    t = unicodedata.normalize("NFC", text).translate(_TRANSLATE)
    if kenyang:
        t = _DASH_IN_WORD.sub("-", t)
        t = t.replace("ε", "ɛ")     # Greek ε → Kenyang ɛ
    t = re.sub(r"[ \t]+", " ", t)
    t = "\n".join(line.strip() for line in t.split("\n"))
    return unicodedata.normalize("NFC", t).strip()


def odd_characters(text):
    """What clean() would change, as readable names, for reports and tests."""
    seen = []
    for c in text or "":
        if c in APOSTROPHES + DOUBLE_QUOTES + SPACES + INVISIBLE + HYPHENS + DASHES + "ε":
            name = unicodedata.name(c, f"U+{ord(c):04X}")
            if name not in seen:
                seen.append(name)
    if unicodedata.normalize("NFC", text or "") != (text or ""):
        seen.append("DECOMPOSED ACCENTS (not NFC)")
    return seen
