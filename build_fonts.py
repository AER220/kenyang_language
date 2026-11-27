"""Gentium Book Plus, served from nepem.org itself.

The pages used to load Gentium from Google Fonts with a stylesheet in <head>. A
stylesheet in <head> holds the whole page back until it arrives, so where
fonts.googleapis.com did not answer (Cameroon, 27 November 2026) the page never painted:
a blank white screen, read by everyone as "the site cannot open". No other host should
be able to do that, so the font files live in fonts/ and go out with the site.

    python build_fonts.py          builds fonts/*.woff2 from SIL's full fonts
    python build_fonts.py check    every character the site shows is in both files

Only regular and bold. Italic was measured (27 November 2026, Chrome's own report of
which font draws every element, all five views, light and dark, phone and desktop):
Gentium drew no italic text anywhere. The italic English gloss is the phone's own face.

The subset is by Unicode range, not by the characters on the page today, so a word a
learner types or a speaker records next week is still drawn in Gentium: Latin, Latin
Extended A, B and Additional, IPA (ɛ ɔ ɨ ʉ ə), the spacing and combining tone marks,
general punctuation, plus the Greek ε the alphabet lesson sets beside ɛ. The OpenType
mark positioning is kept (pyftsubset keeps mark and mkmk by default), which is what
puts a tone mark in the right place over ɛ. Hinting is left out: 56 KB a face against
74, and it only sharpens small text on old Windows screens.

Needs: pip install fonttools brotli (to build only; nothing here runs on Render).
The full fonts are SIL's, Open Font License, fetched from Google's font repository.
"""
import glob
import pathlib
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).parent
OUT = HERE / "fonts"
SRC = OUT / "src"                     # the full fonts; git-ignored, fetched when missing
REPO = "https://raw.githubusercontent.com/google/fonts/main/ofl/gentiumbookplus/"
FACES = {"400": "GentiumBookPlus-Regular.ttf", "700": "GentiumBookPlus-Bold.ttf"}
UNICODES = ",".join([
    "U+0020-007E", "U+00A0-00FF",                 # Basic Latin, Latin-1
    "U+0100-017F", "U+0180-024F", "U+1E00-1EFF",  # Latin Extended A, B, Additional
    "U+0250-02AF", "U+02B0-02FF",                 # IPA, spacing modifiers (ʼ)
    "U+0300-036F", "U+1DC0-1DFF",                 # combining marks: the tones
    "U+03B5",                                     # Greek ε, shown beside ɛ in a lesson
    "U+2000-206F", "U+20AC", "U+2190-2195", "U+2212", "U+2713", "U+FE0F",
    "U+A700-A71F", "U+A78B-A78C",                 # tone letters, saltillo
])
# what the pages show: the pages themselves and every word list they read
SHOWN = ["index.html", "games.html", "audio_words.json", "audio/manifest.json",
         *sorted(glob.glob(str(HERE / "scenes" / "*.json")))]


def build():
    SRC.mkdir(parents=True, exist_ok=True)
    for name in [*FACES.values(), "OFL.txt"]:
        if not (SRC / name).exists():
            urllib.request.urlretrieve(REPO + name, SRC / name)
    (OUT / "OFL.txt").write_bytes((SRC / "OFL.txt").read_bytes())
    for weight, name in FACES.items():
        out = OUT / f"gentium-book-plus-{weight}.woff2"
        subprocess.run([sys.executable, "-m", "fontTools.subset", str(SRC / name),
                        f"--unicodes={UNICODES}", "--flavor=woff2", "--no-hinting",
                        f"--output-file={out}"], check=True)
        print(f"{out.name}: {out.stat().st_size:,} bytes")


def check():
    """Every letter, mark and punctuation sign the site shows is in both files.
    Symbols and emoji Gentium has never had (☀ ☾ ✓ 🌿, the box-drawing rules in the
    CSS comments) are drawn by the phone's own fonts, as they always were."""
    from fontTools.ttLib import TTFont
    import unicodedata
    shown = set()
    for f in SHOWN:
        shown.update(pathlib.Path(HERE / f).read_text(encoding="utf-8"))
    full = set(TTFont(SRC / FACES["400"])["cmap"].getBestCmap()) if (SRC / FACES["400"]).exists() else None
    bad = 0
    for weight in FACES:
        have = set(TTFont(OUT / f"gentium-book-plus-{weight}.woff2")["cmap"].getBestCmap())
        for ch in sorted(shown):
            cp = ord(ch)
            if cp < 0x20 or cp in have:
                continue
            if full is not None and cp not in full:
                continue                 # not in Gentium at all: never was drawn by it
            if full is None and unicodedata.category(ch)[0] in "SC":
                continue
            print(f"MISSING in {weight}: U+{cp:04X} {unicodedata.name(ch, '?')}")
            bad += 1
    print("check:", "every character the site shows is in both fonts" if not bad else f"{bad} missing")
    return bad


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:
        sys.exit(1 if check() else 0)
    build()
    sys.exit(1 if check() else 0)
