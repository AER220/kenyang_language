/* ═══════════════════════════════════════════════════════════════════════════
   TAP TO HEAR. audio/manifest.json maps each recorded word, folded the same
   way build_audio_manifest.py folds it, to its file. The page redraws itself
   constantly, so nothing here is attached to a word: one listener on the
   document finds what was tapped, and an observer re-finds the recorded words
   after every redraw. Without the manifest none of this switches on.

   index.html loads this as it is. The chat on Render loads it from nepem.org
   with two settings on the script tag: data-base, where the audio lives, and
   data-scope, the only elements whose words may be marked (Nɛpɛm's replies).
   With neither set it behaves as it always did on the main page.
   ═══════════════════════════════════════════════════════════════════════════ */
(() => {
  const APOS = /[’‘ʼʻ`´]/g;
  const fold = w => w.normalize("NFC").toLowerCase().replace(APOS, "'")
                     .replace(/\s+/g, " ").trim().replace(/[?.!,;:]+$/, "").trim();
  /* a Kenyang word: letters, their tone marks (category M, which \w misses),
     apostrophes, and hyphens inside it as in ekeré-ékáti */
  const WORD = /[\p{L}\p{M}'’‘ʼʻ]+(?:-[\p{L}\p{M}'’‘ʼʻ]+)*/gu;
  /* places a tap must not speak: typing, and the crossword squares and keys */
  const SKIP = "script,style,noscript,textarea,input,select,[contenteditable],.xgrid,.xkeys,[data-nosay]";
  const me = document.currentScript;
  const BASE = (me && me.dataset.base) || "audio/";
  const SCOPE = (me && me.dataset.scope) || null;

  let manifest = null, longest = 1, on = true, hits = [], queued = false;
  const player = new Audio();
  player.preload = "none";
  const btn = document.getElementById("sound");
  const canHighlight = !!(window.CSS && CSS.highlights && window.Highlight);
  /* without the highlight API the underlines are drawn in a layer of their own,
     laid over the page and taking no taps, so the page's text is still never
     wrapped. It hangs off <html>, outside the body the observer watches, above
     the page's text (z-index 1) and below the floating buttons (55 and up). */
  let marks = null, drawQueued = false;

  try { on = localStorage.getItem("nepem.sound") !== "off"; } catch (e) {}

  /* the key for a run of words, or for the same run with outer quotes taken off */
  const lookup = raw => {
    const k = fold(raw);
    if (manifest[k]) return k;
    const bare = k.replace(/^'+|'+$/g, "");
    return manifest[bare] ? bare : null;
  };

  /* every recorded word or phrase in one text node, longest match first */
  const scanText = node => {
    const t = node.nodeValue, toks = [];
    for (const m of t.matchAll(WORD)) toks.push([m.index, m.index + m[0].length]);
    const out = [];
    for (let i = 0; i < toks.length; i++) {
      for (let n = Math.min(longest, toks.length - i); n >= 1; n--) {
        const j = i + n - 1;
        let joined = true;            /* a phrase only spans plain spaces */
        for (let x = i; x < j; x++)
          if (/\S/.test(t.slice(toks[x][1], toks[x + 1][0]))) { joined = false; break; }
        if (!joined) continue;
        const key = lookup(t.slice(toks[i][0], toks[j][1]));
        if (key) { out.push([toks[i][0], toks[j][1], key]); i = j; break; }
      }
    }
    return out;
  };

  const draw = () => {
    drawQueued = false;
    if (canHighlight) return;
    if (!marks) {
      marks = document.createElement("div");
      marks.setAttribute("aria-hidden", "true");
      marks.style.cssText = "position:absolute;left:0;top:0;width:0;height:0;"
        + "pointer-events:none;z-index:2";
      document.documentElement.appendChild(marks);
    }
    marks.textContent = "";
    for (const h of hits) {
      if (!h.range.startContainer.isConnected) continue;
      for (const r of h.range.getClientRects()) {
        if (!r.width) continue;
        const u = document.createElement("div");
        u.style.cssText = `position:absolute;left:${r.left + scrollX}px;`
          + `top:${r.bottom + scrollY + 1}px;width:${r.width}px;`
          + "border-bottom:2px dotted var(--place, #96680A)";
        marks.appendChild(u);
      }
    }
  };
  const redraw = () => {
    if (!canHighlight && !drawQueued) { drawQueued = true; requestAnimationFrame(draw); }
  };

  const clear = () => {
    hits = [];
    if (canHighlight) CSS.highlights.delete("nepem-say");
    else if (marks) marks.textContent = "";
  };

  const scan = () => {
    queued = false;
    clear();
    if (!manifest || !on) return;
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: n => !n.nodeValue.trim() || n.parentElement.closest(SKIP)
          || (SCOPE && !n.parentElement.closest(SCOPE))
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
    });
    for (let n; (n = walk.nextNode());) {
      for (const [a, b, key] of scanText(n)) {
        const r = document.createRange();
        r.setStart(n, a); r.setEnd(n, b);
        hits.push({range: r, key});
      }
    }
    if (canHighlight && hits.length)
      CSS.highlights.set("nepem-say", new Highlight(...hits.map(h => h.range)));
    else draw();
  };
  const later = () => { if (!queued) { queued = true; requestAnimationFrame(scan); } };

  /* which recorded word is under the point, if any. A finger lands less
     exactly than a mouse, often on the underline below the word, so a touch
     is given more room, and the nearest word wins when two are in reach. The
     extra room never reaches into a button or link the word is not part of,
     so a tap meant for a builder chip does not speak the sentence above it. */
  const CONTROL = "button,a,label,summary,[role=button],[onclick]";
  let touch = false;
  const wordAt = (x, y, target) => {
    const ctl = target && target.closest ? target.closest(CONTROL) : null;
    const side = touch ? 8 : 2, above = touch ? 6 : 2, below = touch ? 12 : 2;
    let best = null, bestD = Infinity;
    for (const h of hits) {
      if (!h.range.startContainer.isConnected) continue;
      for (const r of h.range.getClientRects()) {
        if (x < r.left - side || x > r.right + side
            || y < r.top - above || y > r.bottom + below) continue;
        const dx = Math.max(r.left - x, 0, x - r.right),
              dy = Math.max(r.top - y, 0, y - r.bottom),
              d = dx * dx + dy * dy;
        if (d && ctl && !ctl.contains(h.range.startContainer)) continue;
        if (d < bestD) { bestD = d; best = h.key; }
      }
    }
    return best;
  };
  /* what pressed last, a finger or a mouse. Older iPhones send no pointer
     events, so a touchstart counts too. */
  document.addEventListener("pointerdown", e => { touch = e.pointerType !== "mouse"; }, true);
  document.addEventListener("touchstart", () => { touch = true; }, {capture: true, passive: true});

  const play = key => {
    player.src = BASE + encodeURIComponent(manifest[key]);
    player.currentTime = 0;
    player.play().catch(() => {});
  };

  /* capture, so the word is found before a click redraws the builder */
  document.addEventListener("click", e => {
    if (!manifest || !on || !hits.length) return;
    if (e.target.closest && e.target.closest(SKIP + ",#sound")) return;
    const key = wordAt(e.clientX, e.clientY, e.target);
    if (key) play(key);
  }, true);

  const show = () => {
    if (!btn) return;
    btn.textContent = on ? "Sound on" : "Sound off";
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  };
  if (btn) btn.addEventListener("click", () => {
    on = !on;
    try { localStorage.setItem("nepem.sound", on ? "on" : "off"); } catch (e) {}
    if (!on) player.pause();
    show(); scan();
  });

  fetch(BASE + "manifest.json", {cache: "no-cache"})
    .then(r => r.ok ? r.json() : null)
    .then(m => {
      if (!m || typeof m !== "object" || !Object.keys(m).length) return;
      manifest = m;
      longest = Math.max(...Object.keys(m).map(k => k.split(" ").length));
      if (btn) btn.hidden = false;
      show();
      scan();
      new MutationObserver(later).observe(document.body,
        {childList: true, subtree: true, characterData: true});
      /* the drawn underlines follow the words when anything moves them
         without changing the text: scrolling, resizing, fonts, animations */
      if (!canHighlight) {
        addEventListener("scroll", redraw, {capture: true, passive: true});
        addEventListener("resize", redraw);
        document.addEventListener("animationend", redraw, true);
        document.addEventListener("transitionend", redraw, true);
        if (window.ResizeObserver) new ResizeObserver(redraw).observe(document.body);
        if (document.fonts) document.fonts.ready.then(redraw);
      }
    })
    .catch(() => {});
})();
