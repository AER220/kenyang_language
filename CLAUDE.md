# Nɛpɛm

An AI tutor for Kenyang (Kɛ́nyāŋ), a language of about the Manyu and Meme
Divisions of Southwest Cameroon. Built by Agbor Edouard Ransome, from the Manyu Division,
who is a native speaker and checks every word himself.

Live at **nepem.org** (landing page, GitHub Pages) and **nepem.onrender.com**
(the chat, Streamlit on Render).

---

## The rule that matters more than any other

**Never write Kenyang that a speaker has not confirmed.**

Not a guessed spelling, not a plural built from a pattern, not a word inferred
from a related one, not a tone mark that looked likely. If the Kenyang is not in
a file already, it does not go in.

This is not a style preference. People are using this to recover their mother
tongue, and a child who learns an invented word has been given something false
about who they are. A gap named is worth more than a gap filled.

When unsure: leave it out and add a line to `QUESTIONS_for_Ed.md`.

The same applies to *removing* Kenyang. Do not correct a spelling that looks
wrong. The speaker's form and a book's form are often both right, and several
are recorded deliberately as variants.

---

## Never leave a checkable fact to an instruction

If the code can check it, the code does it. The model is told many things and does
not always do them: it once claimed a recording that did not exist, and it picks a
book's spelling over a verified one while being told the verified one wins. So the
code says which words can be heard (`hear_line`, and `drop_tap_claims` removes the
model's own claims), and the code checks every word against the tiers (the flag).
When a rule can be enforced in code, enforce it there; an instruction is the fallback,
never the guarantee.

---

## How to tell what is trusted

Trust is read from the file name, in `tier_of()` in `streamlit_app.py`:

| name contains | tier | what it means |
|---|---|---|
| `_verified` or `verified` | **verified** | a native speaker confirmed it. Outranks everything. |
| `_core` | core | course chapters, trusted but unchecked |
| `_ref` | reference | a published book, decoded but not speaker-checked |

**A file's tier comes from its name, and a new knowledge file must be named to
match it.** An unmarked file defaults to core. That is how a published dictionary
(`dictionary.txt`) was read as course material for months, its spellings ranked above
the books' and competing with the speaker's. On 24 November 2026 all 21 unmarked files
were renamed (`_core` for the 14 course chapters, `_ref` for the books, including
`dictionary_ref.txt`); every file in `knowledge_base/` now carries its tier. The name
lists in `streamlit_app.py` are empty and should stay that way: a name is visible in
the folder, a list in the code is not.

Verified material travels with **every** question, capped by `ALWAYS_ON_CHARS`.
Files whose names contain `speaker`, `rules` or `grammar` sort first within the
tier, so the grammar is never the thing that gets cut. If the sidebar shows the
red "verified material is being cut" warning, raise `ALWAYS_ON_CHARS`; do not
reorder or trim the rules.

---

## Where things live

The logo files are in `brand/` (full-logo, icon-mark, web-and-social, and the
brand README). Most of it is source; only the files the workflow lists are served.
The pictures for the visual Kenyang section are in `scenes/`. The PNGs there are
Ed's originals and are sources, never published: a page gets an optimised web
copy, added to the copy list only when a page actually asks for it.

```
knowledge_base/          everything Nɛpɛm reads. Nothing else belongs here.
  kenyang_verified_speaker.md    the grammar rules, speaker-confirmed
  kenyang_texts_verified.md      nine recorded speeches, line by line
  kenyang_sentences_verified.md  181 confirmed sentences
  *_ref.jsonl                    published books, unconfirmed
QUESTIONS_for_Ed.md      open questions. MUST NOT go in knowledge_base.
index.npz                the search vectors, built from knowledge_base
audio/                   recordings, one file per word, plus manifest.json
audio_words.json         the canonical word-to-filename list
english_words.txt        English words (SCOWL), so the chat's word check can tell
                         English from Kenyang. Not Kenyang: never in knowledge_base.
```

**`QUESTIONS_for_Ed.md` must never be moved into `knowledge_base/`.** It holds
guesses and unresolved readings. Indexing it would put exactly the material
this project refuses into Nɛpɛm's mouth.

---

## After changing anything in knowledge_base

```bash
python build_index.py
git add -A && git commit -m "..." && git push
```

The index is keyed to a fingerprint of the folder. Edit the knowledge without
rebuilding and the app re-embeds the whole corpus on its next cold start, which
is slow and costs money.

---

## Testing

Ask the running app these. They are chosen because each has failed before.

| ask | expect |
|---|---|
| count 1 to 10 | all ten, no gaps |
| what is the word for house | ɛkɛt |
| what is the plural of house | beket |
| how do you say they were not going to school | bá pú rong nyaka ekeré-ékáti |
| how do you say two small houses | Mandu ɛkɛt bɛ́pay |
| my grandmother's name is Helen | N-ném first, owner second |
| what is the word for grandfather | étá nsinsi |
| what is the word for stepmother | **must refuse** |

The last one matters most. It is in none of the books, so a confident answer
means something has started inventing. If it is ever confirmed and added, pick
a new refusal word and check with grep that it appears nowhere in
knowledge_base first.

---

## Colour means something

**Bright colour is reserved for meaning.** The grammar colours (`--who`, `--not`,
`--root`, `--when`, `--where`) and `--sound` own it; everything structural is
`--accent`, `--head`, `--line` or `--mute`, which are ink and the logo's green.
Green is ink and structure, never a bright accent.
`--sound` is the only warm colour on the site and means one thing: this word has
a recording, tap it. Do not give any other element a warm colour, and do not make
the dotted underline thinner than it is.

**One deliberate exception: right and wrong.** Quiz answers use `--who`'s green for
right and `--not`'s red for wrong. That borrows grammar colours, which the rule
forbids, and it is kept on purpose: green for right and red for wrong is understood
everywhere without being taught, and a learner checking an answer should not have to
learn a new code. Do not "fix" it.

**A second deliberate exception: the logo's leaf.** The heart-and-leaf in the header
keeps the logo's orange leaf (`#DC9246`), the same orange as `--sound`. A logo is a
fixed object, not page chrome, and a rule about page colour does not repaint the brand
mark; nobody taps a header logo expecting sound. The heart and the wordmark take the
structure colour (the logo green on paper, `#6FB58E` on dark, where `#135C3C` is only
2.2:1). Do not make the leaf green, and do not use the logo as a reason to give any
other element a warm colour.

## Things not to change without asking

**`requirements.txt` is pinned deliberately.** Streamlit is pinned to an exact
version because its asset filenames carry a build hash: unpinning it changes
the hashes on every deploy and breaks the page for anyone with it open. The
openai pin is `<2` because the code uses the 1.x API.

**`.python-version` is 3.12.** Render defaulted to 3.14 and the OpenAI client
failed to connect.

**`CNAME` contains `nepem.org`.** Deleting it breaks the custom domain.

**nepem.org publishes only a list of files.** `.github/workflows/pages.yml` copies
index.html, games.html, say.js, audio_words.json, CNAME, ed-portrait.jpg, audio/,
and five files from brand/web-and-social/ (the favicons, the apple-touch-icon and
the social card, plus favicon.ico again at the root) and publishes those alone, so the knowledge base,
QUESTIONS_for_Ed.md, this file and the Python files are not downloadable. A new file
the site needs (a page, an image, a script) must be added to that list, or it will
not be served. Source files stay off it: the scene originals in `scenes/`, the rest of
`brand/`. Nothing else moves: Render reads the repo as it is. The workflow has a build
job and a deploy job, with one retry: with both in one job the deploy three times
could not find the upload made a moment before.

**Tools are offered but `tool_choice` is `"none"`.** The tool round was making
two full API calls per question and crashing when the model asked for several
lookups at once. Retrieval was fixed instead. Do not turn it back on without
fixing `run_tool_calls` to answer every call it is given.

**Render runs on 512 MB and sits close to the limit.** Anything that grows the
corpus or holds more per session needs to be weighed against that.

**The chat's audio loader uses `st.components.v1.html`, which is deprecated.**
It works on the pinned Streamlit 1.66.0, and Streamlit says it will be removed.
Before Streamlit is ever upgraded, move the loader to `st.iframe`, and check that
the frame can still reach the page around it, which is how it adds say.js. If
`components.v1` is gone, the import at the top of `streamlit_app.py` fails and the
whole chat stops, not just the audio.

---

## The word flag under each chat reply

`check_words()` sorts every word in a reply that could be Kenyang into confirmed,
from written sources (in the passages behind the answer, not speaker-checked), or not
found. Two things it must keep doing, because each caused false flags:

- **Confirmed means verified text AND recordings.** `confirmed_words()` reads the
  verified files in full plus `audio_words.json` (Ed's recordings), and
  `speakers_recorded()` adds approved speaker recordings. A word Ed recorded is
  confirmed even if no verified file spells it.
- **Words split at hyphens and underscores.** `N-ném` must also count as `ném`, and a
  course line written `Bheket_e ebhen` holds `bheket`. `\w` matches `_`, so the word
  pattern uses `[^\W_]`.

Every word that is not English is checked, not only words with ɛ ɔ ŋ or a tone mark.
English is `english_words.txt` (SCOWL) plus long English endings (`ENGLISH_ENDINGS`);
a flag on an ordinary English word is a bug. Capitalised words the learner typed count
as names. Before any push that touches the flag, run the twenty-reply measurement: more
than two flagged replies in twenty means stop.

---

## Spellings settled by Ed

Settled on 24 November 2026. Do not "correct" them.

- `ɛsyɛ`, market: no accent. `ɛsyɛ́` is unconfirmed.
- `mme rong`, I am going: canonical. `M'rong` is the same word, the short spoken form.
- `à rong`, he / she is going: with the grave.
- `néyi`, good morning: with the acute.
- `Ma'ya`, my mother: with the apostrophe.
- `amik` is a homograph: it means ground, and it means eyes.

The rong prefix rule lives in the prefix-pattern section of
`kenyang_verified_speaker.md` ("The prefix pattern — learn this and you can build
hundreds of sentences").

---

## The visual section

Scenes are layouts onto words that already exist. A picture never brings a word with
it: pictures are generated to fit confirmed words, never the reverse, and a scene waits
until its words are confirmed (and, where it plays sound, recorded). Labels go in HTML
over the picture, never inside the SVG, so they stay text that can be checked, read
aloud, tapped for sound and corrected without redrawing anything.

---

## Watch out for

**`\w` does not match combining tone marks.** They are category Mn. A regex over
Kenyang needs `\u0300-\u036f` in the character class, or `bɛ́tandat` silently
becomes `bɛ`. This has caused real bugs.

**Kenyang letters are not their Latin look-alikes.** `ɛ` is U+025B, not Greek
epsilon. `ɔ` is U+0254. Mixing them up makes words unsearchable.

**The page rebuilds itself constantly.** The sentence builder redraws on every
tap, the crossword on every letter. Anything that marks up words must survive a
redraw, which is why the audio player uses a delegated listener and a mutation
observer rather than wrapping words in tags.

**Audio filenames are ASCII and numbered on purpose.** `audio_words.json` is the
only mapping between a Kenyang word and its recording.

---

## Writing for the site

Plain, direct, in the owner's voice. Short sentences. No marketing register, no
exclamation marks, no "revolutionary" or "empowering". The site's strength is
that it sounds like a person who loves his language.

Two claims that must stay accurate: Nɛpɛm says when he does not know, and a
speaker checks every submission before he learns it. Do not write anything that
contradicts either, and do not soften them into vagueness.

Say "as far as we know" on any first-in-the-world claim. CABTAL produced an
orthography guide, a lexicon and a New Testament in Kenyang long before this,
and the project is built on their work.
