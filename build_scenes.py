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
                                         library only. THE RULE, IN CODE: a word shows
                                         only if Ed confirmed it, in a verified file or
                                         by recording it himself. Other speakers'
                                         recordings do not count, so one approved typo
                                         cannot put itself on a picture. A word that
                                         fails is left out and named in the log.
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


def confirmed():
    """{folded word: english or ""} for every word Ed confirmed: his recordings, then
    the words of his verified files. The same rule as the Review page's check."""
    sys.path.insert(0, ROOT)
    from build_audio_manifest import fold
    from recordings import verified_vocabulary
    ed = {}
    with open(os.path.join(ROOT, "audio_words.json"), encoding="utf-8") as f:
        for e in json.load(f):
            if e.get("kenyang", "").strip():
                ed[fold(e["kenyang"])] = e.get("english", "")
    vocab = verified_vocabulary()
    return fold, ed, vocab


def words(out_dir):
    fold, ed, vocab = confirmed()
    from recordings import _english
    english = _english()
    os.makedirs(out_dir, exist_ok=True)
    word_rx = re.compile(r"(?:[^\W\d_]|[̀-ͯ'’])+(?:-(?:[^\W\d_]|[̀-ͯ'’])+)*")
    failed = 0
    for name, scene in layouts():
        with open(os.path.join(WEB, scene["image"] + ".crop.json")) as f:
            meta = json.load(f)
        (sw, sh), (x0, y0, x1, y1) = meta["source_size"], meta["crop"]
        points = []
        for p in scene["points"]:
            key = fold(p["word"])
            recorded = key in ed
            parts = [fold(w) for w in word_rx.findall(p["word"])]
            in_text = bool(parts) and all(w in vocab for w in parts)
            # The verified files hold English prose too, so "in a verified file" alone
            # would let an English word onto a picture. Unless Ed recorded it, it must
            # not be English.
            english_word = any(w in english for w in parts)
            if not (recorded or (in_text and not english_word)):
                why = ("is an English word" if english_word and in_text
                       else "is in no verified file and has no recording of Ed's")
                print(f"LEFT OUT of {name}: {p['word']!r} {why}")
                failed += 1
                continue
            # percent of the original picture -> percent of the cropped web copy
            x = (p["x"] / 100 * sw - x0) / (x1 - x0) * 100
            y = (p["y"] / 100 * sh - y0) / (y1 - y0) * 100
            points.append({"word": unicodedata.normalize("NFC", p["word"]),
                           "english": ed.get(key, ""),
                           "x": round(x, 2), "y": round(y, 2)})
        page = {"title": scene.get("title", name), "image": f"scenes/web/{scene['image']}.webp",
                "size": meta["size"], "points": points}
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False, indent=1)
        print(f"{name}: {len(points)} of {len(scene['points'])} words shown")
    return failed


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else ""
    if job == "images":
        images()
    elif job == "words" and len(sys.argv) > 2:
        words(sys.argv[2])
    else:
        sys.exit(__doc__)
