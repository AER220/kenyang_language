"""
Three edits to index.html after the move to nepem.org.

  1. Cloudflare Web Analytics, above </head>
  2. og:url   was still the old github.io address
  3. og:image was too

Numbers 2 and 3 matter more than they look: they are what WhatsApp, LinkedIn
and Facebook read when somebody shares the link. Left alone, sharing nepem.org
would show the old address in the preview card.

Run from the repo root:

    python patch_domain.py

It writes index.html.backup first and checks every edit before changing
anything.
"""
import shutil
import sys

SRC = "index.html"

EDITS = [
    ("analytics above </head>",
     "</head>",
     "<!-- Cloudflare Web Analytics -->"
     "<script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
     "data-cf-beacon='{\"token\": \"befbccb9132f459eb44dd05e676d8832\"}'></script>"
     "<!-- End Cloudflare Web Analytics -->\n</head>"),

    ("og:url to nepem.org",
     '<meta property="og:url" content="https://aer220.github.io/kenyang_language/">',
     '<meta property="og:url" content="https://nepem.org/">'),

    ("og:image to nepem.org",
     '<meta property="og:image" content="https://aer220.github.io/kenyang_language/share.png">',
     '<meta property="og:image" content="https://nepem.org/share.png">'),
]


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")

    if "cloudflareinsights" in text:
        sys.exit("The analytics snippet is already in index.html. Nothing to do.")

    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.")

    shutil.copy(SRC, SRC + ".backup")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)

    print(f"backup written: {SRC}.backup")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nNow:  git add -A && git commit -m 'Analytics and nepem.org' && git push")


if __name__ == "__main__":
    main()
