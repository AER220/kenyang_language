"""
Turn the one long page into sections you move between, the way an app does.

Four changes.

1. Five views: Learn, Play, Steps, Teach, About. One at a time, with a bar at
   the bottom on a phone and the top nav on a desktop. The back button works,
   because each view is a real address.

2. The speaker count is removed. Figures like that go quietly out of date and
   this one is not worth defending.

3. The gold button now says what it is for. A circle with an N in it tells a
   first-time visitor nothing.

4. The numbers section moves up beside the sentence builder, where it belongs.
   Both are about how the language works.

The regrouping is done in JavaScript rather than by cutting the HTML about,
because moving a node keeps its event listeners. Nothing that already works
stops working.

Run from the repo root:

    python patch_views.py
"""
import shutil
import sys

SRC = "index.html"
EDITS = []
def edit(name, old, new): EDITS.append((name, old, new))

# ── 1. drop the speaker count ────────────────────────────────────────────────
edit("remove the count from the headline",
     """    <p class="hsub">A free tutor for <b>Kɛ́nyāŋ</b>, the language of about 65,000
      Bayangi people in Southwest Cameroon. Every word here was checked by a native
      speaker, and <b>when Nɛpɛm does not know something, he says so.</b></p>""",
     """    <p class="hsub">A free tutor for <b>Kɛ́nyāŋ</b>, the language of the Bayangi
      people of Southwest Cameroon. Every word here was checked by a native speaker,
      and <b>when Nɛpɛm does not know something, he says so.</b></p>""")

edit("remove the count from the closing section",
     """        <p>Kenyang is spoken by about 65,000 people in the Southwest Region of Cameroon.
          It has never had an app, a course, or a crossword. This is the first.</p>""",
     """        <p>Kenyang is spoken in the Southwest Region of Cameroon. It has never had an
          app, a course, or a crossword. This is the first.</p>""")

# ── 2. give the last section an id so it can be grouped ──────────────────────
edit("id on the closing section",
     """  <section class="sec">
    <div class="two">
      <h2 class="big" style="margin:0">It will not invent your language</h2>""",
     """  <section class="sec" id="invent">
    <div class="two">
      <h2 class="big" style="margin:0">It will not invent your language</h2>""")

# ── 3. the CSS ───────────────────────────────────────────────────────────────
edit("views CSS",
     """.hero{padding:22px 0 4px}""",
     """.hero{padding:22px 0 4px}

/* ── one section at a time ────────────────────────────────────────
   The page was a hero and ten sections. On a phone that is a very long way to
   scroll to reach a crossword. Each group is now its own view with its own
   address, so the back button takes you where you came from. */
.view{display:none;animation:viewin .26s cubic-bezier(.2,.9,.25,1) both}
.view.on{display:block}
@keyframes viewin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}

/* the switcher, as a bar along the bottom on a phone */
.tabs{position:fixed;left:0;right:0;bottom:0;z-index:55;display:none;
  justify-content:space-around;gap:2px;padding:7px 6px;
  padding-bottom:calc(7px + env(safe-area-inset-bottom,0px));
  background:rgba(6,9,16,.9);border-top:1px solid var(--edge);
  backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
.tabs button{flex:1;min-width:0;background:none;border:none;color:var(--mute);
  font-family:inherit;font-size:10.5px;letter-spacing:.02em;cursor:pointer;
  padding:6px 2px 4px;border-radius:12px;display:flex;flex-direction:column;
  align-items:center;gap:4px;transition:color .18s}
.tabs button .ti{font-size:19px;line-height:1}
.tabs button[aria-current="true"]{color:var(--place)}
.tabs button:focus-visible{outline:2px solid var(--place);outline-offset:-2px}

/* the top nav does the same job on a wider screen */
.nav-r .q[aria-current="true"]{color:var(--place);background:rgba(255,201,77,.1)}

@media (max-width:880px){
  .tabs{display:flex}
  .wrap{padding-bottom:84px}
  /* lift Nɛpɛm clear of the bar */
  .dock{bottom:calc(84px + env(safe-area-inset-bottom,0px))}
  footer{padding-bottom:20px}
}

/* ── the button says what it is for ───────────────────────────────
   A gold circle with an N in it means nothing to somebody who has just
   arrived. The label stays until they have opened the chat once, then gets
   out of the way for good. */
.saylabel{display:flex;align-items:center;padding:9px 15px;border-radius:99px;
  background:var(--lift2);border:1px solid var(--edge-hi);font-size:13.5px;
  white-space:nowrap;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  box-shadow:0 8px 26px rgba(0,0,0,.4);cursor:pointer;
  animation:saybob 3.4s ease-in-out infinite}
@keyframes saybob{0%,100%{transform:none}50%{transform:translateX(-3px)}}
.saylabel b{color:var(--place);font-weight:600}
.dock.used .saylabel{display:none}
@media (prefers-reduced-motion:reduce){.saylabel{animation:none}}""")

# ── 4. the bottom bar and the label ──────────────────────────────────────────
edit("tab bar and label markup",
     """<div class="dock">
  <button class="drum" id="drum" aria-label="Talk to Nɛpɛm"><span>N</span></button>""",
     """<nav class="tabs" id="tabs" aria-label="Sections"></nav>

<div class="dock">
  <button class="drum" id="drum" aria-label="Talk to Nɛpɛm"><span>N</span></button>
  <span class="saylabel" id="saylabel">Ask <b>Nɛpɛm</b> anything</span>""")

# ── 5. the routing ───────────────────────────────────────────────────────────
edit("view routing",
     """/* the crossword squares are sized from the screen, so redraw when it changes */
{
  let rt;
  addEventListener("resize", () => {
    if (A.id !== "xw" || !X) return;
    clearTimeout(rt);
    rt = setTimeout(xRender, 180);
  });
}""",
     """/* the crossword squares are sized from the screen, so redraw when it changes */
{
  let rt;
  addEventListener("resize", () => {
    if (A.id !== "xw" || !X) return;
    clearTimeout(rt);
    rt = setTimeout(xRender, 180);
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   ONE SECTION AT A TIME

   The sections are gathered into five views and shown one at a time. This is
   done by moving the existing nodes rather than rewriting the HTML, because a
   node keeps its event listeners when it moves. Every game, form and button
   that worked before still works.

   Each view is a real address, so the phone's back button goes back a view
   instead of leaving the site.
   ═══════════════════════════════════════════════════════════════════════════ */
const PLAN = [
  ["learn", "Learn", "✦", [".hero", "#numbers"]],
  ["play",  "Play",  "🧩", ["#table"]],
  ["steps", "Steps", "↗",  ["#alone"]],
  ["teach", "Teach", "🌿", ["#family", "#help", "#wall"]],
  ["about", "About", "◇",  ["#honest", "#about", "#invent"]]
];

(function buildViews(){
  const wrap = document.querySelector(".wrap");
  const foot = wrap.querySelector("footer");
  const holder = document.createElement("div");
  holder.className = "views";
  wrap.insertBefore(holder, foot);

  PLAN.forEach(([id, , , sels]) => {
    const v = document.createElement("div");
    v.className = "view";
    v.id = "v-" + id;
    sels.forEach((sel, j) => {
      const el = wrap.querySelector(sel);
      if (!el) return;
      if (j){ const hr = document.createElement("hr"); hr.className = "rule";
              v.appendChild(hr); }
      v.appendChild(el);
    });
    holder.appendChild(v);
  });

  /* the dividers that used to sit between the old sections */
  [...wrap.children].forEach(el => {
    if (el.tagName === "HR" && el.classList.contains("rule")) el.remove();
  });

  /* the bar along the bottom */
  $("tabs").innerHTML = PLAN.map(([id, label, icon]) =>
    `<button data-view="${id}" aria-current="false">
       <span class="ti" aria-hidden="true">${icon}</span>${label}</button>`).join("");

  /* the links already in the top nav point at the same views */
  const nav = document.querySelector(".nav-r");
  [...nav.querySelectorAll("a.q")].forEach(a => {
    const map = {"#table":"play", "#alone":"steps", "#family":"teach"};
    const to = map[a.getAttribute("href")];
    if (!to) return;
    a.setAttribute("href", "#" + to);
    a.dataset.view = to;
  });
})();

/* the old section ids still live in the footer links, and in any address
   somebody has already bookmarked, so they are pointed at the right view
   rather than silently dropping back to the first one */
const WAS = {table:"play", alone:"steps", family:"teach", help:"teach",
             wall:"teach", honest:"about", numbers:"learn", invent:"about"};

function showView(id, push){
  if (WAS[id]) id = WAS[id];
  if (!PLAN.some(p => p[0] === id)) id = PLAN[0][0];
  document.querySelectorAll(".view").forEach(v =>
    v.classList.toggle("on", v.id === "v-" + id));
  document.querySelectorAll("[data-view]").forEach(b =>
    b.setAttribute("aria-current", b.dataset.view === id ? "true" : "false"));
  if (push && location.hash !== "#" + id) location.hash = id;
  scrollTo(0, 0);
  /* the crossword measures the screen, and cannot while it is hidden */
  if (id === "play" && A.id === "xw" && X) xRender();
}

document.addEventListener("click", e => {
  const b = e.target.closest("[data-view]");
  if (!b) return;
  e.preventDefault();
  showView(b.dataset.view, true);
});

addEventListener("hashchange", () => showView(location.hash.slice(1), false));
showView(location.hash.slice(1) || "learn", false);

/* The place the button was dragged to was saved before there was a bar along
   the bottom, so an old position can now sit on top of it. */
{
  const dock = document.querySelector(".dock");
  if (innerWidth <= 880 && dock.style.top){
    const r = dock.getBoundingClientRect();
    const highest = innerHeight - r.height - 92;
    if (r.top > highest) placeDock(r.left, highest);
  }
}

/* ── the label beside the button ──────────────────────────────────── */
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
}""")


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")
    if "buildViews" in text:
        sys.exit("Already patched. Nothing to do.")
    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.")
    shutil.copy(SRC, SRC + ".backup4")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)
    print(f"backup written: {SRC}.backup4")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nNow:  git add -A && git commit -m 'Sections as views' && git push")


if __name__ == "__main__":
    main()
