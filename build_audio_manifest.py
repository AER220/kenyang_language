"""
Write audio/manifest.json from audio_words.json.

audio_words.json is the only mapping between a Kenyang word and its recording.
This keeps the entries whose .mp3 is actually in audio/, keys them by the folded
word, and reports any recording that has no entry.

    python build_audio_manifest.py
"""
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(ROOT, "audio")

APOSTROPHES = "’‘ʼʻ`´"


def fold(word):
    """Lowercase, one kind of apostrophe, single spaces, no end punctuation.
    Tone marks are kept: they are part of the word."""
    w = unicodedata.normalize("NFC", word).lower()
    for a in APOSTROPHES:
        w = w.replace(a, "'")
    w = re.sub(r"\s+", " ", w).strip()
    return w.rstrip("?.!,;:").strip()


def main():
    with open(os.path.join(ROOT, "audio_words.json"), encoding="utf-8") as f:
        entries = json.load(f)
    present = {n for n in os.listdir(AUDIO) if n.lower().endswith(".mp3")}

    manifest, clash = {}, []
    for e in entries:
        if e["file"] not in present:
            continue
        key = fold(e["kenyang"])
        if key in manifest and manifest[key] != e["file"]:
            clash.append((key, manifest[key], e["file"]))
            continue
        manifest[key] = e["file"]

    listed = {e["file"] for e in entries}
    unlisted = sorted(present - listed)

    with open(os.path.join(AUDIO, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"{len(present)} recordings, {len(entries)} entries, {len(manifest)} in the manifest.")
    for name in unlisted:
        print(f"  not in audio_words.json: {name}")
    for key, a, b in clash:
        print(f"  two files for '{key}': {a} kept, {b} left out")
    return 1 if clash else 0


if __name__ == "__main__":
    sys.exit(main())
