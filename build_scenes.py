"""
build_scenes.py — the pictures for the visual Kenyang section.

A scene is a LAYOUT, not a word store. scenes/<name>.json says which picture, and where
each word sits on it, in percent of the ORIGINAL picture, so a different crop never
moves a word:

    {"image": "animals", "title": "Animals",
     "points": [{"word": "mmú", "x": 13.7, "y": 51.4}, ...]}

The spelling, the English and the recording stay where they already live: the verified
files and audio_words.json. Correct a spelling once and every scene follows.

Two jobs, run separately:

    python build_scenes.py images        the web copy of each picture: cropped to the
                                         drawing, resized, WebP. Run it after adding or
                                         changing a picture in scenes/, and commit
                                         scenes/web/. Needs Pillow. The originals stay
                                         in scenes/ as sources and are never published.

    python build_scenes.py words OUT     what the page reads, into OUT (the publish
                                         workflow runs this on every publish). Standard
                                         library only. THE RULE, IN CODE, by the
                                         variants order: Ed's recording (tappable), else
                                         his verified text (shown, no sound claim), else
                                         a course or book file (shown, marked "from
                                         written sources"), else nowhere: left out and
                                         named in the log. Other speakers' recordings do
                                         not count, so one approved typo cannot vouch
                                         for itself on a picture.

Ed's recordings whose English is "my" plus one of a label's meanings ("my grandfather"
for a label meaning grandfather) are listed beside the label as "mine", each tappable,
and never replace it: a possessed form is not a spelling of the bare word.

A point may carry "sense": an English word that chooses among the word's OWN glosses in
the files, for a word listed with more than one (ansem is "after" in one list and
"behind" in another). It adds nothing: if none of the word's glosses contains it, the
build says so and shows the first.

A layout may also carry "layout": "points" (numbered points and a list on every screen,
for a picture with many words) and "list": [...] (words shown beneath the picture, with
no point on it).
"""

import glob
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SCENES = os.path.join(ROOT, "scenes")
WEB = os.path.join(SCENES, "web")
MARGIN = 0.03          # of the drawing's width, kept round it when cropping
WIDTH = 1600           # the web copy's width; enough for a printed page


def layouts():
    for path in sorted(glob.glob(os.path.join(SCENES, "*.json"))):
        with open(path, encoding="utf-8") as f:
            yield os.path.splitext(os.path.basename(path))[0], json.load(f)


def crop_box(img):
    """The drawing's edges plus a margin: these pictures come very wide, with the
    animals in a thin band and the rest blank."""
    from PIL import ImageOps
    grey = ImageOps.grayscale(img)
    box = grey.point(lambda v: 255 if v < 200 else 0).getbbox()
    if not box:
        return (0, 0) + img.size
    pad = int((box[2] - box[0]) * MARGIN)
    return (max(0, box[0] - pad), max(0, box[1] - pad),
            min(img.size[0], box[2] + pad), min(img.size[1], box[3] + pad))


def images():
    from PIL import Image
    os.makedirs(WEB, exist_ok=True)
    for name, scene in layouts():
        src = os.path.join(SCENES, scene["image"] + ".png")
        img = Image.open(src).convert("RGB")
        box = crop_box(img)
        out = img.crop(box)
        if out.size[0] > WIDTH:
            out = out.resize((WIDTH, round(out.size[1] * WIDTH / out.size[0])), Image.LANCZOS)
        # Paper is white: the generator's near-white becomes pure white, so a printed
        # sheet has no grey haze to colour over. Lossless, because lossy compression
        # leaves blotches round line art, and line art compresses well without it.
        out = out.point(lambda v: 255 if v > 232 else v)
        dest = os.path.join(WEB, scene["image"] + ".webp")
        out.save(dest, "WEBP", lossless=True, method=6)
        meta = {"source_size": img.size, "crop": box, "size": out.size}
        with open(os.path.join(WEB, scene["image"] + ".crop.json"), "w") as f:
            json.dump(meta, f)
        print(f"{dest}: {out.size[0]}x{out.size[1]}, {os.path.getsize(dest) // 1024} KB "
              f"(from {img.size[0]}x{img.size[1]}, cropped to {box})")


EDS_FILE = None      # set by --eds: eds_words.json from the Review page's public bucket


def confirmed():
    """{folded word: english or ""} for every word Ed confirmed: his recordings, then
    the words of his verified files. The same rule as the Review page's check."""
    sys.path.insert(0, ROOT)
    from build_audio_manifest import fold
    from recordings import verified_vocabulary
    ed, by_gloss = {}, {}
    entries = []
    with open(os.path.join(ROOT, "audio_words.json"), encoding="utf-8") as f:
        entries += json.load(f)
    # Ed's phone recordings, the ones he marked as his own on the Review page (behind his
    # password). Other speakers' recordings are not in this file, and never count here.
    if EDS_FILE:
        try:
            with open(EDS_FILE, encoding="utf-8") as f:
                own = json.load(f)
            if isinstance(own, list):
                entries += [e for e in own if isinstance(e, dict)]
                print(f"Ed's own phone recordings: {len(own)}")
        except (OSError, ValueError) as e:
            print(f"Ed's own phone recordings: none read ({type(e).__name__})")
    if True:
        for e in entries:
            if e.get("kenyang", "").strip():
                ed[fold(e["kenyang"])] = e.get("english", "")
                by_gloss.setdefault(gloss_key(e.get("english", "")), {}).setdefault(
                    fold(e["kenyang"]), unicodedata.normalize("NFC", e["kenyang"].strip()))
    vocab = verified_vocabulary()
    return fold, ed, vocab, by_gloss


def gloss_key(english):
    """An English gloss, compared plainly: case, punctuation and spacing ignored, and
    nothing more. "Back." and "back" match; "back" and "back of the head" do not."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z' ]", " ", (english or "").lower().replace("’", "'"))).strip()


_PAIR_COLS = re.compile(r"\s{2,}|\t+")
_BOOK_LINE = re.compile(r"^\s+book spelling:\s*(?P<forms>\S.*?)\s{2,}confirmed:\s*(?P<canon>\S+)"
                        r"\s{2,}(?P<gloss>\S.*?)\s*$", re.IGNORECASE)
HEAD_KEYS = ("kenyang", "k", "kenyang_word", "kenyang_translation", "kenyang_phrase")
GLOSS_KEYS = ("english", "e", "english_word", "english_translation")


def glosses(fold, verified):
    """{folded form: English} from the knowledge files of one kind: the verified files
    (verified=True) or the course and book files. Indented "form   gloss" columns, JSON
    records, and (verified only) the confirmed form on a book-spelling line.
    Each is kept twice: under the form exactly as written, and folded. A scene asks for
    the exact spelling first, so a word takes its gloss from the entry it was copied
    from, not from another book that happens to share the letters."""
    out = {}
    def put(form, gloss):
        exact = unicodedata.normalize("NFC", form.strip())
        out.setdefault(("exact", exact), gloss)
        out.setdefault(fold(form), gloss)
        # every gloss of the form, in file order, so a layout's "sense" can choose
        # among them (ansem is "after" in one list and "behind" in another)
        for k in (("all", exact), ("allfold", fold(form))):
            if gloss not in out.setdefault(k, []):
                out[k].append(gloss)
    for path in sorted(glob.glob(os.path.join(ROOT, "knowledge_base", "*"))):
        n = os.path.basename(path)
        if ("verified" in n) != verified or n.lower().endswith(".pdf"):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                m = _BOOK_LINE.match(line)
                if m:
                    if verified:
                        put(m["canon"], m["gloss"])
                    continue
                if s.startswith("{"):
                    try:
                        d = json.loads(s)
                    except Exception:
                        continue
                    if isinstance(d, dict):
                        h = next((d[k] for k in HEAD_KEYS if isinstance(d.get(k), str)), "")
                        g = next((d[k] for k in GLOSS_KEYS if isinstance(d.get(k), str)), "")
                        if h.strip() and g.strip():
                            put(h, g.strip().rstrip("."))
                    continue
                if not line.startswith((" ", "\t")):
                    continue
                cols = [c for c in _PAIR_COLS.split(s) if c]
                for k in range(0, len(cols) - 1, 2):
                    if not cols[k][:1].isdigit():
                        put(cols[k], cols[k + 1])
    return out


def words(out_dir):
    """
    What each scene's page shows, by the variants order (CLAUDE.md, "When sources
    differ"), in four states:

      recorded   Ed recorded it: shown, tappable (say.js plays it)
      verified   in Ed's verified files, not recorded: shown, no sound claim
      book       only in a course or book file: shown with "from written sources"
      (dropped)  nowhere at all: left out, and named in this log
    """
    fold, ed, vocab, by_gloss = confirmed()
    from recordings import _english, confirmed_headwords
    english = _english()
    heads = confirmed_headwords()
    vgloss, bgloss = glosses(fold, True), glosses(fold, False)
    book_text = " ".join(
        fold(open(p, encoding="utf-8", errors="replace").read())
        for p in glob.glob(os.path.join(ROOT, "knowledge_base", "*"))
        if "verified" not in os.path.basename(p) and not p.lower().endswith(".pdf"))
    os.makedirs(out_dir, exist_ok=True)
    word_rx = re.compile(r"(?:[^\W\d_]|[\u0300-\u036f'’])+(?:-(?:[^\W\d_]|[\u0300-\u036f'’])+)*")
    failed = 0

    def pick(table, word, sense):
        """The gloss to show: with no sense, the first; with one, the first of the
        word's own glosses that contains the sense as whole words. None if none does:
        a sense chooses among what the files say, and never adds to it."""
        w = unicodedata.normalize("NFC", word.strip())
        if not sense:
            return table.get(("exact", w), table.get(fold(w), ""))
        rx = re.compile(r"(?<![a-z])" + re.escape(sense.lower()) + r"(?![a-z])")
        for g in table.get(("all", w), []) + table.get(("allfold", fold(w)), []):
            if rx.search(g.lower()):
                return g
        return None

    def base(word, sense=""):
        key = fold(word)
        exact = ("exact", unicodedata.normalize("NFC", word.strip()))
        if key in ed:
            return "recorded", ed[key]
        parts = [fold(w) for w in word_rx.findall(word)]
        in_text = bool(parts) and all(w in vocab for w in parts)
        # The verified files hold English prose too, so "in a verified file" alone
        # would let an English word onto a picture: it must not be English.
        # His confirmed words first, then the English list: Nor (mother of) is spelled
        # like the English nor, and is his word (Ed, 26 November 2026)
        if in_text and (key in heads or not any(w in english and w not in heads for w in parts)):
            g = pick(vgloss, word, sense)
            if g is None:
                bad_sense.append((word, sense, vgloss.get(("all", exact[1]), [])))
                g = pick(vgloss, word, "")
            return "verified", g
        if key in bgloss or re.search(r"(?<![^\W_])" + re.escape(key) + r"(?![^\W_])", book_text):
            g = pick(bgloss, word, sense)
            if g is None:
                bad_sense.append((word, sense, bgloss.get(("all", exact[1]), [])))
                g = pick(bgloss, word, "")
            return "book", g
        return None, ""

    def state(name, word, sense=""):
        """
        (state, English, the word to show, the variant it replaced or "").

        A recording outranks everything, so when the scene's word is not one of Ed's
        recordings but its English is exactly the English of ONE of them, the scene
        shows Ed's recorded form, and keeps its own word as a variant. Every such
        substitution is listed below with both forms side by side. Where the English
        matches more than one of Ed's recordings, nothing is guessed: it is listed, and
        the scene's own word stays.
        """
        st, gloss = base(word, sense)
        if st not in ("verified", "book") or not gloss:
            return st, gloss, word, ""
        mine = by_gloss.get(gloss_key(gloss), {})
        if len(mine) == 1:
            form = next(iter(mine.values()))
            substituted.append((name, gloss, word, st, form))
            return "recorded", ed[fold(form)], form, word
        if len(mine) > 1:
            ambiguous.append((name, gloss, word, sorted(mine.values())))
        return st, gloss, word, ""

    substituted, ambiguous, bad_sense = [], [], []

    # Ed's recordings whose English is "my" + something: {that something: [(form, english)]}
    owned = {}
    for k, forms in by_gloss.items():
        if k.startswith("my ") and len(k) > 3:
            for form in forms.values():
                owned.setdefault(k[3:], []).append((form, ed[fold(form)]))

    def possessed(gloss, shown):
        """Ed's recordings that are "my" + one of the label's meanings, the label's
        gloss split at commas: Ngoré is "woman, wife", so Ngoré-wa, "my wife", is
        one. Added beside the label, never instead of it."""
        out, seen = [], set()
        for part in [gloss] + re.split(r"[,;]", gloss or ""):
            for form, english in owned.get(gloss_key(part), []):
                if fold(form) != fold(shown) and form not in seen:
                    seen.add(form)
                    out.append({"word": unicodedata.normalize("NFC", form), "english": english})
        return out

    for name, scene in layouts():
        with open(os.path.join(WEB, scene["image"] + ".crop.json")) as f:
            meta = json.load(f)
        (sw, sh), (x0, y0, x1, y1) = meta["source_size"], meta["crop"]
        points, listed = [], []
        for p in scene.get("points", []) + [{"word": w} for w in scene.get("list", [])]:
            st, gloss, shown, variant = state(name, p["word"], p.get("sense", ""))
            if st is None:
                print(f"LEFT OUT of {name}: {p['word']!r} is in no file of any kind and has "
                      f"no recording of Ed's")
                failed += 1
                continue
            entry = {"word": unicodedata.normalize("NFC", shown), "english": gloss,
                     "state": st}
            # Ed's possessed recordings ("my grandfather") beside the label, never in
            # its place: Eta'ya nsinsi is not a spelling of étá nsinsi.
            mine = possessed(gloss, shown)
            if mine:
                entry["mine"] = mine
            if variant:
                # never discarded: the form the scene was written with, kept beside Ed's
                entry["variant"] = unicodedata.normalize("NFC", variant)
            if "x" in p:
                # percent of the original picture -> percent of the cropped web copy
                entry["x"] = round((p["x"] / 100 * sw - x0) / (x1 - x0) * 100, 2)
                entry["y"] = round((p["y"] / 100 * sh - y0) / (y1 - y0) * 100, 2)
                points.append(entry)
            else:
                listed.append(entry)
        page = {"title": scene.get("title", name), "image": f"scenes/web/{scene['image']}.webp",
                "size": meta["size"], "layout": scene.get("layout", "labels"),
                "points": points, "list": listed}
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False, indent=1)
        counts = {k: sum(1 for e in points + listed if e["state"] == k)
                  for k in ("recorded", "verified", "book")}
        print(f"{name}: {len(points) + len(listed)} of "
              f"{len(scene.get('points', [])) + len(scene.get('list', []))} words shown "
              f"({counts['recorded']} recorded, {counts['verified']} verified, "
              f"{counts['book']} from written sources)")
    for name, gloss, was, st, form in substituted:
        print(f"SUBSTITUTED in {name}: {gloss!r}  {was}  ->  {form}   "
              f"(Ed's recording; {was} was {'verified text' if st == 'verified' else 'a book form'}, "
              f"kept as a variant)")
    for word, sense, have in bad_sense:
        print(f"SENSE NOT FOUND: {word!r} has no gloss containing {sense!r} "
              f"(its glosses: {have}); the first is shown. Fix the layout.")
        failed += 1
    for name, gloss, was, forms in ambiguous:
        print(f"NOT SUBSTITUTED in {name}: {gloss!r} matches {len(forms)} of Ed's recordings "
              f"({', '.join(forms)}); {was} stays until the layout names one")
    return failed


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else ""
    if job == "images":
        images()
    elif job == "words" and len(sys.argv) > 2:
        if "--eds" in sys.argv:
            EDS_FILE = sys.argv[sys.argv.index("--eds") + 1]
        words(sys.argv[2])
    else:
        sys.exit(__doc__)
