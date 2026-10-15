"""
Two faults in the corner.

1. A long question pushed the button out of place.

   The label and the button sat in the same flex row, so the row was as wide as
   whatever the label happened to be saying. Once the dock has been dragged it
   is anchored by its left edge, so a long question pushed the button rightward
   and a short one pulled it back. The button wandered every five seconds.

   The label is taken out of the flow and hung off the button instead. The dock
   is now exactly the size of the button, whatever the label says.

2. On a first visit the greeting and the label both appeared, two speech
   bubbles elbowing each other in the same corner. The label now waits until
   the greeting has been dismissed.

Run from the repo root:

    python patch_dockfix.py
"""
import shutil
import sys

SRC = "index.html"
EDITS = []
def edit(name, old, new): EDITS.append((name, old, new))

edit("take the label out of the flow",
     """.saylabel{max-width:min(54vw,230px);overflow:hidden}""",
     """/* Hung off the button rather than sitting beside it in the row. The dock is
   now the size of the button alone, so the button cannot be pushed about by
   however long the current question happens to be. */
.saylabel{position:absolute;top:50%;transform:translateY(-50%);
  right:calc(100% + 12px);max-width:min(52vw,220px);overflow:hidden}
.dock.left .saylabel{right:auto;left:calc(100% + 12px)}
.dock{position:fixed;width:62px;height:62px}
.dock .greet{position:absolute;bottom:calc(100% + 12px);right:0;left:auto}
.dock.left .greet{right:auto;left:0;border-radius:18px 18px 18px 4px}
/* while the greeting is up, the label stays quiet */
.dock.greeting .saylabel{display:none}""")

edit("hold the label back during the greeting",
     """  const label = $("saylabel");
  label.innerHTML = "<span>Ask <b>Nɛpɛm</b> anything</span>";""",
     """  const label = $("saylabel");
  const dock = document.querySelector(".dock");
  label.innerHTML = "<span>Ask <b>Nɛpɛm</b> anything</span>";

  /* the greeting and the label are both bubbles in the same corner, so only
     one of them talks at a time */
  const greetUp = () => {
    const g = $("greet");
    return g && g.style.display !== "none" && !!g.offsetParent;
  };
  const watch = () => dock.classList.toggle("greeting", greetUp());
  watch();
  new MutationObserver(watch).observe($("greet"),
    {attributes:true, attributeFilter:["style"]});""")

edit("do not rotate while the greeting is up",
     """    if (document.hidden) return;             /* do not churn in a hidden tab */
    if ($("pane").classList.contains("open")) return;""",
     """    if (document.hidden) return;             /* do not churn in a hidden tab */
    if ($("pane").classList.contains("open")) return;
    if (dock.classList.contains("greeting")) return;""")


def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")
    if "dock.greeting" in text:
        sys.exit("Already patched. Nothing to do.")
    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.")
    shutil.copy(SRC, SRC + ".backup7")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)
    print(f"backup written: {SRC}.backup7")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nNow:  git add -A && git commit -m 'Steady the corner' && git push")


if __name__ == "__main__":
    main()
