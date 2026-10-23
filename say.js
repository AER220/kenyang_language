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

  const clear = () => {
    hits = [];
    if (canHighlight) CSS.highlights.delete("nepem-say");
    document.querySelectorAll(".say").forEach(el => el.classList.remove("say"));
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
        /* no highlight API: mark the element if the word is all of its text */
        if (!canHighlight && lookup(n.parentElement.textContent) === key)
          n.parentElement.classList.add("say");
      }
    }
    if (canHighlight && hits.length)
      CSS.highlights.set("nepem-say", new Highlight(...hits.map(h => h.range)));
  };
  const later = () => { if (!queued) { queued = true; requestAnimationFrame(scan); } };

  /* which recorded word is under the point, if any */
  const wordAt = (x, y) => {
    for (const h of hits) {
      if (!h.range.startContainer.isConnected) continue;
      for (const r of h.range.getClientRects())
        if (x >= r.left - 2 && x <= r.right + 2 && y >= r.top - 2 && y <= r.bottom + 2)
          return h.key;
    }
    return null;
  };

  const play = key => {
    player.src = BASE + encodeURIComponent(manifest[key]);
    player.currentTime = 0;
    player.play().catch(() => {});
  };

  /* capture, so the word is found before a click redraws the builder */
  document.addEventListener("click", e => {
    if (!manifest || !on || !hits.length) return;
    if (e.target.closest && e.target.closest(SKIP + ",#sound")) return;
    const key = wordAt(e.clientX, e.clientY);
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
    })
    .catch(() => {});
})();
