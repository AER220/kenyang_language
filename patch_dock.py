"""
Make Nɛpɛm's button movable, and make the chat work properly on a phone.

Three changes to index.html.

1. The gold N can be dragged anywhere and snaps to the nearest edge. Where you
   leave it is remembered. A fixed corner button always covers something; on a
   phone there is nowhere to scroll it out of the way.

2. On a phone the chat opens as a sheet from the bottom, with a handle to pull
   it to full screen or flick it closed. The old 400px corner pane was wider
   than most phones, so the small and large states looked identical.

3. viewport-fit=cover plus safe area padding, so the button does not sit under
   the iPhone home indicator.

Run from the repo root:

    python patch_dock.py
"""
import shutil
import sys

SRC = "index.html"
EDITS = []
def edit(name, old, new): EDITS.append((name, old, new))

# ── 1. viewport, so the safe areas work ──────────────────────────────────────
edit("viewport-fit",
     '<meta name="viewport" content="width=device-width, initial-scale=1">',
     '<meta name="viewport" content="width=device-width, initial-scale=1, '
     'viewport-fit=cover">')

# ── 2. the dock and pane CSS ─────────────────────────────────────────────────
OLD_CSS = """.dock{position:fixed;right:clamp(14px,2.4vw,26px);bottom:clamp(14px,2.4vw,26px);
  z-index:60;display:flex;align-items:flex-end;gap:12px;flex-direction:row-reverse}"""

NEW_CSS = """.dock{position:fixed;right:clamp(14px,2.4vw,26px);
  bottom:calc(clamp(14px,2.4vw,26px) + env(safe-area-inset-bottom,0px));
  z-index:60;display:flex;align-items:flex-end;gap:12px;flex-direction:row-reverse;
  touch-action:none}
/* dragged to the left half, so the greeting opens the other way */
.dock.left{flex-direction:row}
.dock.moving{transition:none}
.dock.settling{transition:left .26s cubic-bezier(.2,.9,.25,1),
                          top .26s cubic-bezier(.2,.9,.25,1)}
.drum{touch-action:none}
.drum.held{transform:scale(1.12);box-shadow:0 16px 44px rgba(255,201,77,.55)}

/* ── the chat on a phone ──────────────────────────────────────────────
   A 400px corner pane is wider than most phones, so small and large looked
   the same. On a narrow screen it becomes a sheet from the bottom instead:
   the shape people already know from every messaging app. */
@media (max-width:640px){
  .pane{right:0;left:0;bottom:0;top:auto;width:auto;
        height:min(82vh,calc(100vh - 70px));
        border-radius:22px 22px 0 0;border-bottom:none;
        padding-bottom:env(safe-area-inset-bottom,0px);
        animation:sheetup .32s cubic-bezier(.2,.9,.25,1) both}
  .pane.big{top:0;height:auto;border-radius:0;
            padding-top:env(safe-area-inset-top,0px)}
  @keyframes sheetup{from{transform:translateY(100%)}to{transform:none}}
  /* the grab handle, only on a phone */
  .phead::before{content:"";position:absolute;top:7px;left:50%;
    transform:translateX(-50%);width:38px;height:4px;border-radius:99px;
    background:var(--edge-hi)}
  .phead{position:relative;padding-top:18px;touch-action:none}
  .dock.hidden{display:none}
}"""
edit("dock and pane CSS", OLD_CSS, NEW_CSS)

# ── 3. the drag behaviour ────────────────────────────────────────────────────
OLD_JS = """$("drum").addEventListener("click", () => {
  const p = $("pane");
  if (p.classList.contains("open")) shutPane(); else openPane(false);
});"""

NEW_JS = """/* ── dragging the button ────────────────────────────────────────────
   A tap and a drag start the same way, so the two are told apart by distance:
   under 6px is a tap and opens the chat, over 6px is a drag. Without that
   threshold every drag would also open the chat on release.                */
const dock = document.querySelector(".dock");
const PAD = 12;

function placeDock(x, y){
  const w = dock.offsetWidth, h = dock.offsetHeight;
  const topPad = PAD, botPad = PAD + 6;
  x = Math.max(PAD, Math.min(innerWidth - w - PAD, x));
  y = Math.max(topPad, Math.min(innerHeight - h - botPad, y));
  dock.style.left = x + "px";
  dock.style.top = y + "px";
  dock.style.right = "auto";
  dock.style.bottom = "auto";
  dock.classList.toggle("left", x + w / 2 < innerWidth / 2);
}

function rememberDock(){
  try {
    const r = dock.getBoundingClientRect();
    localStorage.setItem("nepem.dock", JSON.stringify({
      side: r.left + r.width / 2 < innerWidth / 2 ? "l" : "r",
      y: r.top / innerHeight
    }));
  } catch(e){}
}

function restoreDock(){
  let p = null;
  try { p = JSON.parse(localStorage.getItem("nepem.dock") || "null"); } catch(e){}
  if (!p) return;                       /* never moved: leave the CSS corner */
  const w = dock.offsetWidth;
  placeDock(p.side === "l" ? PAD : innerWidth - w - PAD, p.y * innerHeight);
}

function settleDock(){
  const r = dock.getBoundingClientRect();
  const toLeft = r.left + r.width / 2 < innerWidth / 2;
  dock.classList.add("settling");
  placeDock(toLeft ? PAD : innerWidth - r.width - PAD, r.top);
  setTimeout(() => dock.classList.remove("settling"), 280);
  rememberDock();
}

let dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0;

$("drum").addEventListener("pointerdown", e => {
  dragging = true; moved = false;
  sx = e.clientX; sy = e.clientY;
  const r = dock.getBoundingClientRect();
  ox = r.left; oy = r.top;
  dock.classList.add("moving");
  $("drum").classList.add("held");
  try { $("drum").setPointerCapture(e.pointerId); } catch(err){}
});

addEventListener("pointermove", e => {
  if (!dragging) return;
  const dx = e.clientX - sx, dy = e.clientY - sy;
  if (!moved && Math.hypot(dx, dy) > 6){ moved = true; hideGreet(); }
  if (moved){ placeDock(ox + dx, oy + dy); e.preventDefault(); }
}, {passive:false});

addEventListener("pointerup", () => {
  if (!dragging) return;
  dragging = false;
  dock.classList.remove("moving");
  $("drum").classList.remove("held");
  if (moved){ settleDock(); return; }
  const p = $("pane");                  /* it was a tap */
  if (p.classList.contains("open")) shutPane();
  else openPane(innerWidth <= 640);     /* a phone opens straight to the sheet */
});

/* a rotation or a resized window can leave it off screen */
addEventListener("resize", () => {
  if (dock.style.left) restoreDock();
});
restoreDock();

/* ── flick the sheet away on a phone ────────────────────────────────
   Dragging the header down closes it, the way a sheet should. Short drags
   spring back, so a mis-touch does not lose the conversation.            */
{
  const head = document.querySelector(".phead");
  let sheetY = 0, sheeting = false;
  head.addEventListener("pointerdown", e => {
    if (innerWidth > 640) return;
    if (e.target.closest("button, a")) return;   /* let the buttons work */
    sheeting = true; sheetY = e.clientY;
    $("pane").style.transition = "none";
  });
  addEventListener("pointermove", e => {
    if (!sheeting) return;
    const dy = Math.max(0, e.clientY - sheetY);
    $("pane").style.transform = "translateY(" + dy + "px)";
  });
  addEventListener("pointerup", e => {
    if (!sheeting) return;
    sheeting = false;
    const pane = $("pane");
    const dy = Math.max(0, e.clientY - sheetY);
    pane.style.transition = "transform .25s cubic-bezier(.2,.9,.25,1)";
    if (dy > 110){ pane.style.transform = "translateY(100%)";
      setTimeout(() => { shutPane(); pane.style.transform = ""; }, 240); }
    else pane.style.transform = "";
  });
}"""
edit("drag behaviour", OLD_JS, NEW_JS)

# ── 4. hide the button while the sheet is open on a phone ────────────────────
edit("hide dock behind the sheet",
     """function shutPane(){
  $("pane").classList.remove("open", "big");
  document.body.style.overflow = "";
}""",
     """function shutPane(){
  $("pane").classList.remove("open", "big");
  document.body.style.overflow = "";
  document.querySelector(".dock").classList.remove("hidden");
}""")

edit("hide dock on open",
     """function openPane(big){
  hideGreet();
  const p = $("pane");
  p.classList.add("open");
  if (big) p.classList.add("big");
  loadChat();
}""",
     """function openPane(big){
  hideGreet();
  const p = $("pane");
  p.classList.add("open");
  if (big) p.classList.add("big");
  /* on a phone the sheet covers the button, so take it out of the way */
  if (innerWidth <= 640){
    document.querySelector(".dock").classList.add("hidden");
    document.body.style.overflow = "hidden";
  }
  loadChat();
}""")


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")
    if "placeDock" in text:
        sys.exit("Already patched. Nothing to do.")
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
    print("\nNow:  git add -A && git commit -m 'Movable Nepem, mobile sheet' && git push")


if __name__ == "__main__":
    main()
