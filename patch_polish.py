"""
Six changes.

1. Four views instead of five. The eight steps move into Learn, where they
   belong beside the builder and the numbers. They are the best thing on the
   site, each one ending with something to go and say to a person, but they do
   not need a tab of their own.

2. Words of the week is gone. Somebody who knows a word can send it through
   Feedback, which is the same act with less machinery around it.

3. Teach becomes Feedback, which is what it actually is: teach a word, or say
   he got something wrong.

4. The top nav loses the section links, which the bar below already does. Share
   and Ask Nɛpɛm are left, because those are actions rather than places.
   The switcher becomes a row of pills under the header on a wide screen, and
   stays a bar along the bottom on a phone.

5. The button is no longer a Latin N in a circle, which looks like every other
   app. It is ɛ́, the letter at the heart of the name and the most distinctive
   letter in Kenyang.

6. Play becomes the place games are chosen from, with room for more.

Run from the repo root:

    python patch_polish.py
"""
import shutil
import sys

SRC = "index.html"
EDITS = []
def edit(name, old, new): EDITS.append((name, old, new))

# ── 1. four views, steps folded into Learn ───────────────────────────────────
edit("four views",
     """const PLAN = [
  ["learn", "Learn", "✦", [".hero", "#numbers"]],
  ["play",  "Play",  "🧩", ["#table"]],
  ["steps", "Steps", "↗",  ["#alone"]],
  ["teach", "Teach", "🌿", ["#family", "#help", "#wall"]],
  ["about", "About", "◇",  ["#honest", "#about", "#invent"]]
];""",
     """const PLAN = [
  ["learn",    "Learn",    "✦", [".hero", "#numbers", "#alone"]],
  ["play",     "Play",     "🧩", ["#table"]],
  ["feedback", "Feedback", "🌿", ["#help", "#wall"]],
  ["about",    "About",    "◇",  ["#honest", "#about", "#invent"]]
];""")

edit("old addresses point at the right view",
     """const WAS = {table:"play", alone:"steps", family:"teach", help:"teach",
             wall:"teach", honest:"about", numbers:"learn", invent:"about"};""",
     """const WAS = {table:"play", alone:"learn", steps:"learn", family:"feedback",
             teach:"feedback", help:"feedback", wall:"feedback",
             honest:"about", numbers:"learn", invent:"about"};""")

# ── 2. drop the words of the week, and the code that painted it ──────────────
edit("remove words of the week",
     """  PLAN.forEach(([id, , , sels]) => {""",
     """  /* words of the week is gone: a speaker who knows a word sends it through
     Feedback instead, which is the same act with less machinery round it */
  const week = wrap.querySelector("#family");
  if (week) week.remove();

  PLAN.forEach(([id, , , sels]) => {""")

edit("stop painting the week",
     """paintWeek(); loadWall();""",
     """if ($("wgrid")) paintWeek();
loadWall();""")

edit("guard the week repaint after a submission",
     """  if (en){ S.fam[en] = ken; save(); paintWeek(); }""",
     """  if (en){ S.fam[en] = ken; save(); if ($("wgrid")) paintWeek(); }""")

# ── 3. the top nav keeps only the two actions ────────────────────────────────
edit("strip the top nav",
     """      <a class="q" href="#table">Play together</a>
      <a class="q" href="#alone">Learn on your own</a>
      <a class="q" href="#family">Ask your family</a>
      <a class="q" href="games.html">Games</a>
      <button class="q" id="share" type="button">Share</button>""",
     """      <button class="q" id="share" type="button">Share</button>""")

# ── 4. the switcher, and the new button ──────────────────────────────────────
edit("switcher CSS",
     """/* the top nav does the same job on a wider screen */
.nav-r .q[aria-current="true"]{color:var(--place);background:rgba(255,201,77,.1)}""",
     """/* On a wide screen the switcher is a row of pills under the header rather
   than a bar stuck to the bottom, which is a phone idea. */
@media (min-width:881px){
  .tabs{position:static;display:flex;justify-content:flex-start;gap:7px;
    background:none;border:none;backdrop-filter:none;-webkit-backdrop-filter:none;
    padding:2px 0 0;margin:0 0 10px}
  .tabs button{flex:0 0 auto;flex-direction:row;gap:9px;font-size:14.5px;
    letter-spacing:0;padding:9px 17px;border:1px solid var(--edge);border-radius:99px}
  .tabs button:hover{border-color:var(--edge-hi);color:var(--text)}
  .tabs button[aria-current="true"]{border-color:var(--place);
    background:rgba(255,201,77,.1)}
  .tabs button .ti{font-size:15px}
}""")

# The icon rules have to come AFTER the original .drum block or the original
# flat gradient wins. .drum.quiet::after is the last rule in that block.
edit("the new mark",
     """.drum.quiet::after{display:none}""",
     """.drum.quiet::after{display:none}

/* ── the mark ─────────────────────────────────────────────────────
   It was a Latin N on flat gold, which is what every other app looks like. It
   is now ɛ́: the letter at the heart of the name Nɛpɛ́m, and the one letter
   that says Kenyang at a glance. The gold is lit from the top left so it reads
   as a round object rather than a coloured disc. */
.drum{width:62px;height:62px;
  background:radial-gradient(125% 125% at 32% 22%,
    #FFEFBE 0%, #FFCF5E 30%, #EDA42B 62%, #B5701A 100%);
  box-shadow:0 10px 30px rgba(230,160,45,.42),
             inset 0 1.5px 0 rgba(255,255,255,.6),
             inset 0 -4px 10px rgba(110,55,0,.3)}
.drum span{font-size:31px;color:#4A2B06;
  text-shadow:0 1px 0 rgba(255,255,255,.34);padding-bottom:3px}
.drum::after{inset:-6px;border-color:rgba(255,201,77,.4)}
.drum:hover{transform:translateY(-3px) scale(1.05);
  box-shadow:0 16px 42px rgba(230,160,45,.58),
             inset 0 1.5px 0 rgba(255,255,255,.6),
             inset 0 -4px 10px rgba(110,55,0,.3)}
.phead .av{background:radial-gradient(125% 125% at 32% 22%,
    #FFEFBE 0%, #FFCF5E 30%, #EDA42B 62%, #B5701A 100%);
  color:#4A2B06;font-size:17px}

/* Play, as the place games are chosen from */
.pickc.more{background:linear-gradient(140deg,rgba(255,201,77,.12),
            rgba(185,139,255,.09));border-color:rgba(255,201,77,.3);
            text-decoration:none;display:block}
.pickc.more:hover{border-color:var(--place)}
.pickc.more h3{color:var(--place)}""")

# ── 5. the glyph itself, in both places ──────────────────────────────────────
edit("button glyph",
     """  <button class="drum" id="drum" aria-label="Talk to Nɛpɛm"><span>N</span></button>""",
     """  <button class="drum" id="drum" aria-label="Talk to Nɛpɛm"><span>ɛ́</span></button>""")

edit("chat avatar glyph",
     """      <span class="av" aria-hidden="true">N</span>""",
     """      <span class="av" aria-hidden="true">ɛ́</span>""")

# ── 6. the switcher moves inside the page, under the header ──────────────────
edit("switcher placement",
     """  /* the bar along the bottom */
  $("tabs").innerHTML = PLAN.map(([id, label, icon]) =>""",
     """  /* under the header on a wide screen, along the bottom on a phone */
  const navEl = wrap.querySelector("nav");
  if (navEl) wrap.insertBefore($("tabs"), navEl.nextSibling);

  $("tabs").innerHTML = PLAN.map(([id, label, icon]) =>""")

# ── 7. a card for the games page ─────────────────────────────────────────────
edit("games card",
     """  {id:"build",ic:"🔤", t:"Build the sentence", tag:"solo",
   d:"You get the English. Put the Kenyang words in the right order."}
];""",
     """  {id:"build",ic:"🔤", t:"Build the sentence", tag:"solo",
   d:"You get the English. Put the Kenyang words in the right order."},
  {id:"more", ic:"🎲", t:"More games", tag:"solo", href:"games.html",
   d:"Four levels that each ask you to do something new. Tells you the rule when you get one wrong."}
];""")

edit("render the games card as a link",
     """  $("picks").innerHTML = PICKS.map(p=>`
    <button class="pickc" data-pick="${p.id}" role="tab" aria-selected="${A.id===p.id}">
      <div class="ic" aria-hidden="true">${p.ic}</div>
      <h3>${p.t}</h3><p>${p.d}</p>
      <span class="tag ${p.tag}">${p.tag==="fam"?"BETTER WITH TWO":"ON YOUR OWN"}</span>
    </button>`).join("");""",
     """  $("picks").innerHTML = PICKS.map(p=>{
    const body = `<div class="ic" aria-hidden="true">${p.ic}</div>
      <h3>${p.t}</h3><p>${p.d}</p>
      <span class="tag ${p.tag}">${p.href?"OPENS A PAGE":
        p.tag==="fam"?"BETTER WITH TWO":"ON YOUR OWN"}</span>`;
    /* a card that goes somewhere is a link, so it can be opened in a new tab
       and read out as a link rather than a button */
    return p.href
      ? `<a class="pickc more" href="${p.href}">${body}</a>`
      : `<button class="pickc" data-pick="${p.id}" role="tab"
           aria-selected="${A.id===p.id}">${body}</button>`;
  }).join("");""")

edit("skip the link card when wiring the choosers",
     """  document.querySelectorAll(".pickc").forEach(c=>{
    c.addEventListener("click",()=>{A.id=c.dataset.pick; runActivity();});""",
     """  document.querySelectorAll(".pickc").forEach(c=>{
    if (!c.dataset.pick) return;          /* the games card is a plain link */
    c.addEventListener("click",()=>{A.id=c.dataset.pick; runActivity();});""")


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")
    if '"feedback", "Feedback"' in text:
        sys.exit("Already patched. Nothing to do.")
    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.")
    shutil.copy(SRC, SRC + ".backup5")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)
    print(f"backup written: {SRC}.backup5")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nNow:  git add -A && git commit -m 'Four views, games hub, new mark' && git push")


if __name__ == "__main__":
    main()
