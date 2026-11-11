# Fixes from the IST 692 class audit

Three student groups audited nepem.org. Their findings, in priority order.
Items 1 to 3 are bugs. Items 4 to 6 are real usability problems. Item 7 is a
feature request worth doing. Do them in order and show me each diff; do not
batch them into one commit.

---

## 1. Audio does not work on mobile for at least one student (BUG, highest)

A student reported: "it is not allowing me to click on words to listen to their
pronunciations when I try nepem.org on my phone." The same features work on
desktop, and work on my own iPhone.

Investigate before changing anything. Possible causes to check and report on:

- `::highlight()` support. The player marks words with the CSS Custom Highlight
  API. Confirm what the fallback path does when `CSS.highlights` is undefined,
  and whether that fallback actually makes words tappable or only styles them.
  If the fallback does not work, that is the bug.
- Whether the tap handler depends on anything that behaves differently on touch
  (click vs pointer events, the capture-phase listener, `closest()` on a text
  node's parent).
- Whether iOS requires a user gesture that the current flow does not satisfy on
  first tap.
- Whether the gold dotted underline is visible enough on a phone that a user
  knows a word is tappable at all. One student only learned audio existed when I
  told them, so discoverability may be the whole problem rather than the code.

Tell me the cause before you fix it. If it is the highlight fallback, replace the
fallback with one that genuinely works on older or stricter browsers, keeping the
Custom Highlight path where it is supported.

## 2. The same words are tappable in one answer but not another (BUG)

A student reported: asking "how to count to 10" gives numbers that can each be
tapped, but clicking the built-in "Teach me to count" starter gives numbers where
not all are tappable. The recordings exist for both. So the words are the same
and the behaviour differs.

Find out why. Likely candidates: the starter-button path renders the reply
differently (different DOM, different timing) so the mutation observer misses it;
or the reply arrives before say.js has loaded the manifest; or the observer only
watches a container that the starter path does not write into. Diagnose, then fix
so every Nepem reply is scanned regardless of how the question was asked.

## 3. The chat button covers content on mobile (BUG)

"The chatbot button blocks some of the bottom of the screen on mobile." The
floating button sits over the page. On a phone it overlaps content a user is
trying to read. Fix so it never covers text: add bottom padding to the page
equal to the button's height plus the safe-area inset, or move it clear. It must
stay draggable and must not sit over the bottom tab bar.

## 4. Phonetic pronunciation, asked for by all three groups (ACCESSIBILITY)

Every group asked for written pronunciation, and one gave the reason that matters:
"for those who may not have the ability to hear pronunciation." This is an
accessibility requirement, not a nicety, and it is also the honest answer to the
fact that I cannot record every word.

There is already a file `knowledge_base/kenyang_tone_ref.md` holding pronunciation
notes converted from a published phonological study, written as plain descriptions
rather than IPA symbols.

Before building anything, tell me: what is the smallest honest way to show written
pronunciation beside a Kenyang word on the page, using only what is in that file?
Do NOT invent pronunciation for any word that file does not cover, and do NOT
generate IPA or a phonetic respelling by rule. A word with no recorded
pronunciation note shows nothing. Propose the approach first.

## 5. The conversation resets with no warning

A student wrote: "I left the bot alone for about 10 minutes. When I sent another
message, the previous two messages were erased and the bot started a new
conversation and seemed to have forgotten the context."

The page already says the lesson lives in the browser only and refreshing starts
fresh. But an idle timeout that silently wipes history mid-conversation is
different and is not explained. Find what causes it (Streamlit session expiry on
Render, or the session state being cleared). Then either keep the history across
that event, or, if that is not possible, say plainly in the interface what will
happen and when. A silent reset that looks like amnesia is the worst of the
options.

## 6. Tab buttons are too small

"Would make the tab buttons at the top larger." On a wide screen the Learn, Play,
Feedback and About pills are small relative to everything else. Increase their
tap target and text size without changing the colours or the layout shape. Check
the mobile bottom bar still fits four items comfortably.

## 7. An alphabet section on the Learn page (FEATURE, do last)

"I believe an alphabet section on the Learn page would be quite helpful," and
separately: "what might confuse a beginner is the different letters from the
English alphabet such as the double letters like bh."

Add a step to the STEPS array in the Learn view teaching the alphabet: the five
letters English does not have (ɛ ɔ ŋ ɨ ʉ) and the digraphs that are one sound
(bh ch gb gh kp ny). Use the alphabet already recorded in the knowledge base;
add no new letters or claims. Follow the exact shape of the existing steps,
including the practice quiz. If any of those letters has a recording in
audio/manifest.json, it should be tappable like every other word.

---

## Rules for all of the above

- Fix one item at a time and show me the diff before moving on.
- Never invent Kenyang, a spelling, a tone mark or a pronunciation. Anything not
  in knowledge_base or audio/manifest.json does not get shown.
- Do not change any wording that states what Nepem can and cannot do. Three
  groups praised that transparency; it is the thing that is working.
- Items 1, 2 and 3 are on live behaviour I cannot reproduce. Tell me what you
  find before you change code, and say plainly if you cannot test something in
  this container.
