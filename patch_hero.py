"""
Three things the site was missing.

1. A headline. The h1 was class="sr", screen-reader only, so a visitor saw
   coloured words rearranging and had to infer what the site was. The argument
   for trusting it, that a speaker checked every word and it admits what it does
   not know, sat at the very bottom in About.

2. A share button. WhatsApp is where this actually spreads, and there was no way
   to send it on. Uses the phone's own share sheet where there is one, and falls
   back to copying the link.

3. A link to the games page, which was pushed but reachable only by typing the
   URL.

Run from the repo root:

    python patch_hero.py
"""
import shutil
import sys

SRC = "index.html"
EDITS = []
def edit(name, old, new): EDITS.append((name, old, new))

# ── 1. CSS for the headline, proof line and the copied toast ─────────────────
edit("hero CSS",
     """.hero{padding:22px 0 4px}""",
     """.hero{padding:22px 0 4px}
/* ── the headline ─────────────────────────────────────────────────
   Somebody arriving has about two seconds to work out what this is. The old
   page spent them on a sentence rebuilding itself, which is lovely once you
   know what you are looking at and meaningless before. */
.htitle{font-family:var(--serif);font-size:clamp(31px,5.6vw,58px);line-height:1.06;
  font-weight:700;letter-spacing:-.025em;margin:10px 0 16px;max-width:15em}
.hsub{font-size:clamp(16px,1.9vw,19px);color:var(--mute);max-width:38em;
  margin:0 0 18px;line-height:1.62}
.hsub b{color:var(--text);font-weight:500}
.hproof{display:inline-flex;align-items:center;gap:9px;font-size:13px;
  color:var(--mute);margin:0 0 30px;padding:7px 15px;border-radius:99px;
  border:1px solid var(--edge);background:var(--lift)}
.hproof i{width:7px;height:7px;border-radius:99px;background:var(--place);flex:none}
.toast{position:fixed;left:50%;bottom:26px;transform:translate(-50%,16px);
  z-index:80;padding:12px 20px;border-radius:99px;font-size:14.5px;
  background:var(--lift2);border:1px solid var(--edge-hi);color:var(--text);
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  box-shadow:0 12px 40px rgba(0,0,0,.5);opacity:0;pointer-events:none;
  transition:opacity .22s,transform .22s}
.toast.up{opacity:1;transform:translate(-50%,0)}
@media (max-width:880px){ .htitle{margin-top:4px} .hproof{margin-bottom:22px} }""")

# ── 2. the headline itself ───────────────────────────────────────────────────
edit("hero markup",
     """    <h1 class="sr" id="heroT">How a Kenyang sentence is built</h1>
    <p class="hlead"><b>A Kenyang sentence is built from parts, in a fixed order.</b>""",
     """    <h1 class="htitle" id="heroT">Kenyang, for the people it belongs to</h1>
    <p class="hsub">A free tutor for <b>Kɛ́nyāŋ</b>, the language of about 65,000
      Bayangi people in Southwest Cameroon. Every word here was checked by a native
      speaker, and <b>when Nɛpɛm does not know something, he says so.</b></p>
    <p class="hproof"><i aria-hidden="true"></i>2nd place, Syracuse University
      Libraries LaunchPad Ideas Fest 2026</p>

    <p class="hlead"><b>A Kenyang sentence is built from parts, in a fixed order.</b>""")

# ── 3. nav: games and share ──────────────────────────────────────────────────
edit("nav links",
     """      <a class="q" href="#family">Ask your family</a>
      <button class="cta" id="openChat"><span class="dot"></span>Ask Nɛpɛm</button>""",
     """      <a class="q" href="#family">Ask your family</a>
      <a class="q" href="games.html">Games</a>
      <button class="q" id="share" type="button">Share</button>
      <button class="cta" id="openChat"><span class="dot"></span>Ask Nɛpɛm</button>""")

# ── 4. the toast element ─────────────────────────────────────────────────────
edit("toast element",
     """<div class="dock">""",
     """<div class="toast" id="toast" role="status"></div>

<div class="dock">""")

# ── 5. sharing ───────────────────────────────────────────────────────────────
edit("share behaviour",
     """const CHAT_URL = $("newTab").href;""",
     """/* ── sharing ──────────────────────────────────────────────────────
   WhatsApp is where this actually travels, so the phone's own share sheet is
   the right thing to open. Desktop has no share sheet, so the link is copied
   instead and the person is told that is what happened. */
function toast(words){
  const t = $("toast");
  t.textContent = words;
  t.classList.add("up");
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.remove("up"), 2600);
}

$("share").addEventListener("click", async () => {
  const link = "https://nepem.org";
  const note = {
    title: "Nɛpɛm, Kenyang for the whole family",
    text: "A free tutor for Kenyang. It only teaches what a speaker has checked.",
    url: link
  };
  try {
    if (navigator.share){ await navigator.share(note); return; }
  } catch(e){ return; }          /* they closed the sheet; say nothing */
  try {
    await navigator.clipboard.writeText(link);
    toast("Link copied. Paste it anywhere.");
  } catch(e){
    toast(link);
  }
});

const CHAT_URL = $("newTab").href;""")


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")
    if "htitle" in text:
        sys.exit("Already patched. Nothing to do.")
    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.")
    shutil.copy(SRC, SRC + ".backup3")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)
    print(f"backup written: {SRC}.backup3")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nNow:  git add -A && git commit -m 'Headline, share, games link' && git push")


if __name__ == "__main__":
    main()
