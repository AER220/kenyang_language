# Nɛpɛm

An AI tutor for Kenyang (Kɛ́nyāŋ), a language of about the Manyu and Meme
Divisions of Southwest Cameroon. Built by Agbor Edouard Ransome of Bachou Ntai,
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

## How to tell what is trusted

Trust is read from the file name, in `tier_of()` in `streamlit_app.py`:

| name contains | tier | what it means |
|---|---|---|
| `_verified` or `verified` | **verified** | a native speaker confirmed it. Outranks everything. |
| `_core` | core | course chapters, trusted but unchecked |
| `_ref` | reference | a published book, decoded but not speaker-checked |

**A new knowledge file must be named to match its tier.** A book's word list
dropped in as `words.jsonl` is silently treated as core, which is wrong and
hard to notice.

Verified material travels with **every** question, capped by `ALWAYS_ON_CHARS`.
Files whose names contain `speaker`, `rules` or `grammar` sort first within the
tier, so the grammar is never the thing that gets cut. If the sidebar shows the
red "verified material is being cut" warning, raise `ALWAYS_ON_CHARS`; do not
reorder or trim the rules.

---

## Where things live

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

Diagnostics that need no API key:

```bash
python check.py rules          # which grammar rules are reaching him
python check.py word <word>    # where a word came from, or that it is invented
python check.py numbers        # which files disagree about counting
python audit_corpus.py         # size, duplication, contradictions
```

---

## Things not to change without asking

**`requirements.txt` is pinned deliberately.** Streamlit is pinned to an exact
version because its asset filenames carry a build hash: unpinning it changes
the hashes on every deploy and breaks the page for anyone with it open. The
openai pin is `<2` because the code uses the 1.x API.

**`.python-version` is 3.12.** Render defaulted to 3.14 and the OpenAI client
failed to connect.

**`CNAME` contains `nepem.org`.** Deleting it breaks the custom domain.

**Tools are offered but `tool_choice` is `"none"`.** The tool round was making
two full API calls per question and crashing when the model asked for several
lookups at once. Retrieval was fixed instead. Do not turn it back on without
fixing `run_tool_calls` to answer every call it is given.

**Render runs on 512 MB and sits close to the limit.** Anything that grows the
corpus or holds more per session needs to be weighed against that.

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
