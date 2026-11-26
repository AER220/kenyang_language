# Nɛpɛ́m

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

**A book's plural the verified file contradicts is held back in code** (`held_back()`
and `hold_back()` in `streamlit_app.py`). The instruction that the verified form wins
did not hold: with "ɛkɛt → beket" and a book's "plural: bɛkɛt" side by side, the model
picked the book's four times in five. So a book entry is left out of what the model
sees when all three hold:

- its headword is the same word as a verified singular, compared with case, tone marks,
  ɛ/e, ɔ/o and hyphens ignored;
- its English gloss matches too (the guard against homographs: amik is ground and eyes);
- its plural, compared exactly, appears nowhere in any verified file. The books' bɛ́kwá
  stays because the recorded texts have it.

The whole entry goes; a book line is never rewritten, and the files are not touched.
The sidebar lists what is held back. If a reply still gives a held-back plural (the
model can build bɛket itself from the course's ɛ- to bɛ- rule), `swap_held_back()` puts
the verified form in its place. Only forms the code held back, only whole words, never
inside a book phrase of several words ("bɛkɛt bɛ́so mmwɛ́t", bathrooms), and never in a
reply that already has the verified form, which is comparing the two.

**It works off the explicit `singular → plural   gloss → glosses` lines in the verified
files, so every pair Ed adds there extends its reach.** Today there are two: ɛkɛt → beket and ékwá → békwá. It covers plurals only,
not singulars, prose or compounds.

**Nɛpɛ́m names no source, and the code makes sure.** The book passages carry page
numbers "(p.22)", "[cite: 3]", "chapter: 14", record ids and a publisher's address.
`scrub_sources()` takes those out of the book and course passages sent to the model
(never the verified ones, never a Kenyang word, and never the chunks themselves, which
index.npz is matched to row by row). `drop_source_claims()` takes out of a reply any
page or cite mark, and any sentence naming a chapter number, a file, or a title or
publisher in `_SOURCE_NAMES`. Authors' surnames are deliberately not in that list:
Mbuagbaw and Tanyi are also Bayangi family names, and a learner's name must never be
cut. The flag says "from written sources" and nothing more specific.

---

## Where things live

The logo files are in `brand/` (full-logo, icon-mark, web-and-social, and the
brand README). Most of it is source; only the files the workflow lists are served.
The pictures for the visual Kenyang section are in `scenes/`. The PNGs there are
Ed's originals and are sources, never published: a page gets an optimised web
copy, added to the copy list only when a page actually asks for it.

```
knowledge_base/          everything Nɛpɛ́m reads. Nothing else belongs here.
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
this project refuses into Nɛpɛ́m's mouth.

---

## After changing anything in knowledge_base

```bash
python build_index.py
git add -A && git commit -m "..." && git push
```

The index is keyed to a fingerprint of the folder: each file's name and a hash of its
contents (not its modified time, which a fresh clone resets). Edit the knowledge without
rebuilding and the app re-embeds the whole corpus on its next cold start, which
is slow and costs money.

---

## Testing

    python run_checks.py            the table below and the twenty-reply measurement
    python run_checks.py --table    the table's ten rows only

**Run it before every push**, alongside the twenty (it is the twenty: the table's ten
plus ten ordinary questions). It asks each question in a fresh local session and prints
PASS or FAIL per row and both flag counts. Run it bare and read its exit status: do not
pipe it through another command, whose status then hides its own (a filter once
reported success over a failed run).

**The gate is a regression check** (Ed, 26 November 2026). Requiring every row to pass
held back a fix behind failures nobody had solved. A push may go when:

- no row that passes on the live code fails after the change;
- "not found" stays at one or fewer in twenty.

A row already failing on the live code does not block a push, but it must be named in
the push report, every time, so it is never forgotten. The known baseline is
`LIVE_FAILING` in `run_checks.py`: on 26 November 2026, rows 4 (drops nyaka) and 7 (an
example sentence built from parts); rows 5 and 6 were fixed in code in that push. A push
whose change fixes one takes it out of `LIVE_FAILING` in the same commit. A row that
passes by chance in one run, with nothing fixed, stays in. The rows and their checks live in `run_checks.py`; this table is
the readable copy, and a row added here must be added there. Nobody was running the
table as a list: rows 5 and 6 failed for some time unseen (found 26 November 2026). A
row passing is not the reply being good: read the replies too (row 7, QUESTIONS 34).

They are chosen because each has failed before.

| ask | expect |
|---|---|
| count 1 to 10 | all ten, no gaps |
| what is the word for house | ɛkɛt |
| what is the plural of house | beket |
| how do you say they were not going to school | bá pú rong nyaka ekeré-ékáti |
| how do you say two small houses | Mandu ɛkɛt bɛ́pay |
| my grandmother's name is Helen | N-ném Ma'ya nsinsi chi Helen: N-ném first, then whose, then chi, then the name (Ed, 26 November 2026) |
| what is the word for grandfather | étá nsinsi |
| what is the word for stepmother | **must refuse** |
| how do you say 37 | **must not build it**: says it does not have 37 |
| how do I say I have 37 goats | **no form for 37**, and never 23's form |

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
`brand/`. The pictures are published as `scenes/web/*.webp` and the scene files the
workflow builds. Nothing else moves: Render reads the repo as it is. The workflow has a build
job and a deploy job: with both in one job the deploy three times could not find the
upload made a moment before. The deploy retries three times, after 1, 2 and 4 minutes,
before the run goes red; one retry after 30 seconds failed twice on 25 November 2026.

**If the deploy step fails with "Failed to create deployment (status: 500)", it is
GitHub's server, not our workflow.** Wait, then re-run the failed jobs from the Actions
page. Do not change the workflow for it: it cleared on a re-run on 25 November 2026.

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
  **So approving a recording promotes its spelling to confirmed**, and the flag stops
  warning about it. That is how Neyi and Eh, Ed's néyi and Éh with the marks lost, became
  confirmed. The Review page therefore warns, never blocks, before Approve and on a
  correction (`recordings.spelling_check()`): a spelling no verified file has, an English
  word in the Kenyang box, or the same letters with other tone marks than Ed's own
  recording. It checks against the verified files and Ed's recordings only, never other
  speakers' recordings, or one approved typo would vouch for the next.
- **Words split at hyphens and underscores.** `N-ném` must also count as `ném`, and a
  course line written `Bheket_e ebhen` holds `bheket`. `\w` matches `_`, so the word
  pattern uses `[^\W_]`.

**Ed's confirmed words are looked at before the English list** (26 November 2026).
`recordings.confirmed_headwords()` is the Kenyang column of every word line in the
verified files, plus his recordings. A word there is his, even when English spells it too:
Nor (mother of), Kong, pop, fa, na, meh, Che, manor. The Visuals build and the Review
spelling check use it. Whole entries only, never the prose words of the verified files,
which would let any English word through. Some table headers come in with it, because the
format cannot tell them from a word line: spoken, bound, short, aeroplane, airport, high
tone, rising tone. In the chat's flag it changes nothing: a confirmed word gets no flag
either way.

Every word that is not English is checked, not only words with ɛ ɔ ŋ or a tone mark.
English is `english_words.txt` (SCOWL) plus long English endings (`ENGLISH_ENDINGS`);
a flag on an ordinary English word is a bug. Capitalised words the learner typed count
as names.

**The twenty-reply measurement.** Before any push that touches the flag or what reaches
the model, ask the running app twenty questions (the eight in Testing below, plus
twelve ordinary learner questions), each in a fresh session, and count the two kinds of
flag separately. They mean different things:

- **"Not found"** means Nɛpɛ́m may have invented something. That is a bug. Limit: one
  or fewer replies in twenty. More means stop.
- **"From written sources"** means Nɛpɛ́m used a book or course word and said so. That
  is the system working, so it has no limit. Report it every time, as a percentage of
  the twenty. It measures how much of what Nɛpɛ́m teaches comes from books rather than
  from Ed's voice, and it should fall as Ed records and confirms more.

Total flags matter only if most replies carry a box. If more than about half of the
twenty carry one, tell Ed.

---

## When sources differ: the variants order

Set by Ed on 25 November 2026, for every word, so no word has to be decided by hand.

Where sources give different forms, every form is kept as a variant, searchable, and
nobody is told a form does not exist. Which one Nɛpɛ́m teaches is decided by this order,
never by hand:

1. **Ed's recording**, if one exists. Speech is the primary evidence.
2. Otherwise **Ed's verified text**.
3. Otherwise **a course or book form**, taught with the "from written sources" flag.
4. If **no source has it at all**, Nɛpɛ́m says he does not have it. He never builds one
   and presents it as correct.

Every form not chosen is kept as a variant with its source, so the disagreement is
preserved rather than erased. As recordings arrive, forms move up the order on their
own, with no decision from Ed.

Where the order alone does not pick one form, the code breaks the tie the same way every
time: course before book (their tiers), then the form more sources agree on, and a tie
left after that is shown as both. This tie-break was added by Claude, not decided by Ed;
Ed accepted it on 25 November 2026 as sensible. Do not mistake it for one of his rules. Two
different forms in Ed's own verified text, with no recording to decide, are not broken
by the code: both are shown as verified, and the case is listed for Ed (14 today:
Byó nɛ mɛ́nwi in the speaker file, byó nɛ ánwi in the recorded texts).

For numbers this is code: `number_forms()` reads every source and the recordings,
applies the order, and the result travels with every question. A word list is not
written by hand anywhere.

**Rule 4 for numbers is code too** (`enforce_numbers()`). The model, told not to, built
37 and 55 and called them correct, and asked for "37 goats" gave 23's form and said it
had assembled it from parts. So every reply is read: each run of number words is
matched against the forms the sources have. A line that gives a number no source has,
or puts a real form under a number it is not, is replaced by one line the code writes
("I don't have thirty-seven in Kenyang yet. No speaker has given it to me, and I won't
build it from parts."), with the nearest numbers it does have. A range is one sentence,
in Ed's wording: "I have up to thirty-two, then forty. Thirty-three to thirty-nine
have not been given to me by a speaker." A sentence vouching for a removed line ("these
are the correct forms", "I assembled this") goes with it. Book-only numbers are never
refused: one the learner asked for and the reply left out is added, with "from written
sources". A number built from real words (each word passes the word check) is reported
by the flag as not found.

---

## Spellings settled by Ed

Settled on 24 November 2026. Do not "correct" them.

- `ɛsyɛ`, market: no accent. `ɛsyɛ́` is unconfirmed.
- `mme rong`, I am going: canonical. `M'rong` is the same word, the short spoken form.
- `à rong`, he / she is going: with the grave.
- `néyi`, good morning: with the acute.
- `Ma'ya`, my mother: with the apostrophe.
- `amik` is a homograph: it means ground, and it means eyes.

Settled on 26 November 2026:

- `Èh` is yes, with the grave. `Éh Èh` is no. `Éh` is not a spelling of yes: Ed's own
  recordings were stored as `Éh`, and the audio is right but the mark was wrong. (The
  course chapters' `Éh`, "What did you say?", is a different word and stays.)

Settled on 25 November 2026:

- `beket`, houses: canonical. It is in the verified file and in Ed's speech, and
  verified outranks book. `bɛkɛt` and `bɛket` are recorded as book spellings: a search
  finds them and nobody is told they do not exist, but Nɛpɛ́m teaches beket. The course
  chapter's class 7/8 rule (ɛ- to bɛ-) is not changed: a confirmed pair outranks a
  derived form (QUESTIONS section 24).
- `Nɛpɛ́m`, the project's name: capital N, acute on the second ɛ. The course chapter's
  `nɛpɛm` and the grammar book's `nepɛm` are recorded as book spellings. That it means
  "life", and that bapɛm is its plural, is not confirmed (QUESTIONS section 22).

A book spelling is recorded in a verified file on a line of its own, in this form, and
the code reads it (`_BOOK_SPELLING`):

    book spelling: bɛkɛt, bɛket       confirmed: beket       houses

The forms on such a line are never counted as confirmed: not by the flag, not by the
hold-back. They count as "from written sources", so a learner who meets one is told it
is a book's spelling.

The rong prefix rule lives in the prefix-pattern section of
`kenyang_verified_speaker.md` ("The prefix pattern — learn this and you can build
hundreds of sentences").

---

## The visual section

**How a scene is built.** `scenes/<name>.json` is the layout and nothing else: the picture's
name and, for each word, where it sits, in percent of the ORIGINAL picture. No English, no
spelling of its own; `word` is only the key. `python build_scenes.py images` makes the web
copy in `scenes/web/` (cropped to the drawing, near-white made pure white, lossless WebP);
run it after adding or changing a picture, and commit `scenes/web/`. The publish workflow
runs `python build_scenes.py words _site/scenes` every time, which writes what the page
reads, each word in one of four states, by the variants order (Ed, 25 November 2026):

1. **recorded** by Ed: tappable (say.js plays it);
2. **verified**, in Ed's verified files but not recorded: shown plain, no sound claim;
3. **book**, only in a course or book file: shown with "from written sources", the
   chat's marker, so a learner knows no speaker has checked it;
4. **nowhere**: left out entirely, and named in the log.

**Ed's own recordings.** The pictures count Ed's recordings only: `audio_words.json`, plus
any phone recording Ed has marked as his on the Review page ("This recording is mine",
off by default, behind his password). Not a speaker code: that changes with the device,
and a code in a browser is not a credential. Review publishes the marked ones, text only,
as `eds_words.json` in the public bucket; the publish workflow fetches it and passes it to
`build_scenes.py words --eds`. Other speakers' recordings never count for the pictures,
whatever is ticked. The marks are a table of their own, which must exist once in
Supabase (SQL editor):

    create table if not exists public.eds_recordings (
      recording_id text primary key,
      marked_at timestamptz not null default now()
    );
    alter table public.eds_recordings enable row level security;
    -- no policies, on purpose: only the Review page's service key can read or write it

A mark reaches the pictures at the next publish (a push, or "Run workflow" on the
Actions page); marking is not a push.

**A possessed recording sits beside the label, never in its place.** An Ed recording whose
English is "my" plus one of the label's meanings (the label's gloss split at commas) is
shown under the label as its own tappable line: Moh'wa (my child) under mmɔ, Ngoré-wa
(my wife) under Ngoré. It never substitutes: Eta'ya nsinsi is not a spelling of étá
nsinsi, and a picture of a grandfather must not teach "my grandfather" as the word. The
match is the English exactly, after the "my": "My grand mother" does not match
"grandmother".

**A recording outranks the scene's own spelling.** If a scene's word is not one of Ed's
recordings but its English is exactly the English of ONE of them (`gloss_key()`: case,
punctuation and spacing ignored, nothing more), the scene shows Ed's recorded form and
keeps its own word as a variant, shown as "also written …" and never discarded. So
recording the poster's body words moves each one up with no layout edit. Every
substitution is printed in the publish log, both forms side by side ("SUBSTITUTED");
where the English matches more than one of Ed's recordings nothing is guessed, it is
printed ("NOT SUBSTITUTED") and the scene's word stays. This is for the pictures only:
the chat does not yet apply the order in code to words other than numbers.

Ed's recordings and verified files only; never another speaker's recording, and never
an English word that only appears in the verified files' prose. A word's English comes
from the entry spelled exactly as the scene writes it. The page's labels are HTML text,
so say.js plays them unchanged. `"layout": "points"` (the head and body scenes) numbers
the words on the picture and lists them beneath on every screen; `"list"` holds words
shown beneath the picture with no point (breast, vagina, anus: no warning, no
euphemism). On paper, "from written sources" is an asterisk explained at the foot, and
each sheet fits one A4 page (the tall body picture prints portrait).
To add a scene: the picture in `scenes/`, its layout beside it, `images`, then add its
name to `SCENE_NAMES` in index.html.

**What a picture must be, for the colouring to work.** Clean line art: thick, even
outlines, no shading or texture, a plain white background, nothing touching the edge,
no text. **Every part that will be coloured separately needs its own closed outline.**
The fill follows the drawing's closed regions, not what a part is called: in
animals.png the cat is one region from ears to tail, which works because each animal is
one word, but a picture for "colour the ear" needs each ear closed off on its own. Check
a new picture's regions before building on it (count the closed regions, and confirm
the background is one region, so no colour can leak out of the drawing).

**When the body picture is regenerated for colouring**, the colouring version needs, each
closed on its own: the fingers and toes (closed off from the hand and foot), the palm,
the nails, the nostrils, a navel and an armpit area. body-regions.png and
head-regions.png (25 November 2026) give 32 of the 46 body words a region; these are
the parts that do not have one. Head, skin and body are whole-body words: they get a
label and no region, and that is correct.

**When compound.png or outdoors.png is regenerated for colouring** (region check of
25 November 2026; colour mode is not built yet, so neither matters for labels):
the footpath in outdoors.png is two loose lines with no ends, so it has no region and
colouring it fills the whole background, and it needs closing; the doorways of the
zinc-roofed house and the thatched house in compound.png reach the ground with no line
across, so each is part of the background, and needs a line across the bottom if a door
is to be coloured. people.png has no such gap: every figure's face, hair, clothes, arms
and legs are closed separately.

**When actions.png is regenerated:** ascend (Kó) and descend (Seb), the third row's
last two figures, are drawn with no step, stair or slope, so they read as stepping and
walking. Each needs something to climb up or come down (26 November 2026).

**When positions.png is regenerated** (26 November 2026): rows 1 and 2 work and are
placed (amem, neku, a'nfai, a'nten; ambeuh, ansem, anfai, amik). Row 3 is not placed and
must not be: Fa (here), Afo (there) and Awuh (over there, further than Afo) say how far a
thing is from the SPEAKER, and a box and a ball cannot show where the speaker stands; a
big ball and a small ball read as two sizes as easily as near and far. nefi (outside)
has no scene a learner could tell from neku (beside): a ball next to a closed box is
both. A remade picture needs:

- **A person in each distance scene, the same person in the same place**, with one
  ground line running back so that distance reads as distance. Fa: the ball at the
  person's feet or in their hand. Afo: the ball some way off, the person pointing at it.
  Awuh: the ball far off near the horizon, the person pointing further. Three panels
  with only the ball moving, so the one difference is how far it is.
- **Inside and outside as a pair, round the same container**, one a person can be in:
  a house with an open door (ɛkɛt, a confirmed word), or a fenced yard. amem: the ball
  (or a child) inside, seen through the door. nefi: the same ball in the yard, outside the
  same house. Not a ball beside a box, which is neku.
- The box-and-ball scenes for the other eight can stay as they are.

**Squarer, not a long line.** A very wide thin band (animals.png is 1600x361 once
cropped) leaves the subjects small and crowds the numbered points on a phone. Future
pictures should be closer to square: two rows rather than one long line.

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

**Phones change what people type.** A curly apostrophe (Eta’ya for Eta'ya), a dash for
two hyphens, curly quotes, no-break and invisible spaces. `textnorm.clean()` (and the same
rules in `index.html`) turns them into what the files use, on every field a person types
into: the website's forms, Review, submissions, the chat's input. Review lists any
stored spelling that still has them, with a button to straighten them. Tone marks are
never touched beyond NFC.

**A lookup that folds case can silently take another entry's meaning.** The body scene's
`Nsem` (back, from the poster) got its English, "Back.", from `nsem` in a different book,
because the gloss lookup matched case-insensitively and took whichever file came first.
Here the meaning happened to agree; two books sharing letters for different words would
not, and nothing would say so. The fix is in `build_scenes.py`, `glosses()` and `state()`:
every gloss is stored under the form exactly as written and folded, and a word asks for
its exact spelling first, falling back to the folded one only if there is none. Any new
lookup that folds (case, tone marks, ɛ/e) to find a word's meaning should do the same.

**A CSS rule can silently not apply.** `.fld .ken input` (a space: a `.ken` inside a
`.fld`) never matched, because `ken` is a class on the `.fld` itself; it needed
`.fld.ken input`. So the Kenyang box was never set in the serif face, the English and
Kenyang boxes looked identical, and Ed typed the Kenyang into the English box three
times in a row. Nothing errors when a selector matches nothing. The fix, and the labels
and swapped-box check that came with it, are in `index.html` (search `.fld.ken input`
and `checkTeach`). After writing a style for a specific element, confirm it reaches
that element.

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

Two claims that must stay accurate: Nɛpɛ́m says when he does not know, and a
speaker checks every submission before he learns it. Do not write anything that
contradicts either, and do not soften them into vagueness.

Say "as far as we know" on any first-in-the-world claim. CABTAL produced an
orthography guide, a lexicon and a New Testament in Kenyang long before this,
and the project is built on their work.
