"""
Two things.

1. A light mode, and a switch beside Share.

   Flipping the background is the easy half. The harder half is that several
   colours were chosen for a dark page and fail on a pale one. --root, the verb
   in the sentence builder, is pure white: invisible on white. The mint, the
   purple and the gold all wash out. And the chat pane, the bar along the bottom
   and the crossword clue squares are hardcoded dark. All of that is handled
   here, not just the background.

   The theme is set before the page paints, so there is no flash of the wrong
   colours on arrival. First visit follows whatever the phone is set to.

2. The button says something permanently.

   The old label vanished after the first tap, which left a gold circle sitting
   there meaning nothing. It now cycles through real questions, so it both asks
   to be tapped and teaches what Nɛpɛm can actually be asked.

Run from the repo root:

    python patch_theme.py
"""
import shutil
import sys

SRC = "index.html"
EDITS = []
def edit(name, old, new): EDITS.append((name, old, new))

# ── 1. set the theme before anything paints ─────────────────────────────────
edit("theme bootstrap",
     """<!-- Cloudflare Web Analytics -->""",
     """<script>
/* Runs before the page paints, so nobody sees the wrong colours flash first.
   No preference saved means follow whatever the phone is already set to. */
(function(){
  try{
    var t = localStorage.getItem("nepem.theme");
    if(!t) t = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    document.documentElement.dataset.theme = t;
  }catch(e){ document.documentElement.dataset.theme = "dark"; }
})();
</script>
<!-- Cloudflare Web Analytics -->""")

# ── 2. the light palette ────────────────────────────────────────────────────
edit("light palette",
     """*{box-sizing:border-box}""",
     """/* ── the pale version ─────────────────────────────────────────────
   Not the dark values inverted. Mint, purple and gold that sing against near
   black turn to pastel mush on paper, so each one is darkened until it holds
   its own. --root matters most: it is the verb in the sentence builder and it
   was pure white, which on a white page is nothing at all. */
:root[data-theme="light"]{
  --base:#FAF7F0;
  --lift:rgba(16,34,28,.035); --lift2:rgba(16,34,28,.062);
  --edge:rgba(16,34,28,.13); --edge-hi:rgba(16,34,28,.28);
  --text:#15201B; --mute:#56665E;
  --who:#077A58; --not:#B2351C; --root:#15201B; --when:#5F31BC; --place:#96680A;
  --p1:#0A6A9E; --p2:#A82F6B;
  color-scheme:light;
}
:root[data-theme="dark"]{ color-scheme:dark; }

/* the things that were written as dark colours rather than as variables */
[data-theme="light"] .pane,
[data-theme="light"] .pbody{background:#FFFDF8}
[data-theme="light"] .tabs{background:rgba(250,247,240,.92)}
[data-theme="light"] .cell.clue{background:rgba(16,34,28,.05)}
[data-theme="light"] .nav-r .q:hover,
[data-theme="light"] .stButton>button:hover{background:rgba(16,34,28,.06)}
[data-theme="light"] .bubble.bot,
[data-theme="light"] .wcard,
[data-theme="light"] .hcard{background:#FFFDF8}
[data-theme="light"] .greet,
[data-theme="light"] .saylabel,
[data-theme="light"] .toast{background:rgba(255,253,248,.94);
  box-shadow:0 10px 34px rgba(16,34,28,.16)}
[data-theme="light"] .pbar,
[data-theme="light"] .weekbar,
[data-theme="light"] .track{background:rgba(16,34,28,.1)}
[data-theme="light"] .choice.right{background:rgba(7,132,95,.12)}
[data-theme="light"] .choice.wrong{background:rgba(178,53,28,.1)}
[data-theme="light"] .verdict.ok{background:rgba(7,132,95,.08);
  border-color:rgba(7,132,95,.26)}
[data-theme="light"] .verdict.no{background:rgba(178,53,28,.07);
  border-color:rgba(178,53,28,.24)}
[data-theme="light"] .pane{box-shadow:0 22px 70px rgba(16,34,28,.2)}

/* --place is darkened so it can be read as small text on paper, which makes it
   too dim to sit behind the near-black text on a button. Anything using gold as
   a background gets the bright gold back. */
[data-theme="light"] .cta{background:linear-gradient(135deg,#E8A61B,#FF9E2C)}
[data-theme="light"] .btn.solid{background:#E8A61B;border-color:#E8A61B}
[data-theme="light"] .btn.solid:hover{background:#F6B733}
[data-theme="light"] .lvl[aria-pressed="true"],
[data-theme="light"] .opt[aria-pressed="true"]{background:#E8A61B;
  border-color:#E8A61B;color:#1A1206}
[data-theme="light"] .pbar i{background:linear-gradient(90deg,#077A58,#E8A61B)}
[data-theme="light"] .hproof i{background:#E8A61B}

/* the drifting colour behind everything is built for a dark page. On paper it
   turns to mud, so it is quieter, and the floating letters are dropped. */
[data-theme="light"] .sky{opacity:.2;filter:blur(120px)}
[data-theme="light"] #field{display:none}
[data-theme="light"] .hero .built .m::after{opacity:.4}

/* the switch itself */
.modesw{display:inline-flex;align-items:center;justify-content:center;
  width:36px;height:36px;border-radius:99px;border:1px solid var(--edge);
  background:none;color:var(--mute);cursor:pointer;font-size:15px;line-height:1;
  font-family:inherit;transition:color .2s,border-color .2s,background .2s}
.modesw:hover{color:var(--place);border-color:var(--edge-hi);
  background:rgba(255,201,77,.08)}
.modesw:focus-visible{outline:2px solid var(--place);outline-offset:2px}

*{box-sizing:border-box}""")

# ── 3. the switch, beside Share ─────────────────────────────────────────────
edit("mode switch markup",
     """      <button class="q" id="share" type="button">Share</button>""",
     """      <button class="q" id="share" type="button">Share</button>
      <button class="modesw" id="modesw" type="button"
              aria-label="Switch between light and dark"></button>""")

# ── 4. a permanent hint instead of one that vanishes ────────────────────────
edit("hint CSS",
     """.dock.used .saylabel{display:none}""",
     """/* The old label disappeared after the first tap, which left a gold circle
   sitting there meaning nothing to anybody who came back a week later. It
   stays now, and cycles through things Nɛpɛm can actually answer, so it asks
   to be tapped and teaches what to ask in the same breath. */
.saylabel{max-width:min(54vw,230px);overflow:hidden}
.saylabel span{display:block;transition:opacity .3s,transform .3s}
.saylabel.turning span{opacity:0;transform:translateY(-5px)}""")

# ── 5. the behaviour ────────────────────────────────────────────────────────
edit("theme and hint behaviour",
     """/* ── the label beside the button ──────────────────────────────────── */
{
  const dock = document.querySelector(".dock");
  try { if (localStorage.getItem("nepem.asked")) dock.classList.add("used"); }
  catch(e){}
  $("saylabel").addEventListener("click", () => $("drum").click());
  const quieten = () => {
    dock.classList.add("used");
    try { localStorage.setItem("nepem.asked", "1"); } catch(e){}
  };
  $("drum").addEventListener("pointerup", quieten);
  $("openChat").addEventListener("click", quieten);
}""",
     """/* ── light and dark ───────────────────────────────────────────────── */
{
  const root = document.documentElement;
  const paint = () => {
    const dark = root.dataset.theme !== "light";
    $("modesw").textContent = dark ? "☀" : "☾";
    $("modesw").title = dark ? "Switch to the pale version"
                             : "Switch to the dark version";
  };
  paint();
  $("modesw").addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
    try { localStorage.setItem("nepem.theme", root.dataset.theme); } catch(e){}
    paint();
    /* the crossword squares are drawn from measurements, so redraw them */
    if (A.id === "xw" && X) xRender();
  });
}

/* ── what the button says ─────────────────────────────────────────── */
{
  const ASKS = [
    "How do I greet my mother?",
    "Count to ten",
    "What is the word for house?",
    "How do I say I am going home?",
    "What does Ndɨ́ndɨ́ mean?",
    "How do I say two small houses?",
    "Teach me something new"
  ];
  const label = $("saylabel");
  label.innerHTML = "<span>Ask <b>Nɛpɛm</b> anything</span>";
  label.addEventListener("click", () => $("drum").click());

  let i = -1;
  const turn = () => {
    if (document.hidden) return;             /* do not churn in a hidden tab */
    if ($("pane").classList.contains("open")) return;
    i = (i + 1) % ASKS.length;
    label.classList.add("turning");
    setTimeout(() => {
      label.querySelector("span").textContent = ASKS[i];
      label.classList.remove("turning");
    }, 300);
  };
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches)
    setInterval(turn, 5200);
}""")


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")
    if "nepem.theme" in text:
        sys.exit("Already patched. Nothing to do.")
    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.")
    shutil.copy(SRC, SRC + ".backup6")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)
    print(f"backup written: {SRC}.backup6")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nNow:  git add -A && git commit -m 'Light mode, speaking button' && git push")


if __name__ == "__main__":
    main()
