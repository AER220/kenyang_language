# Nɛpɛm - a Kenyang language tutor

Nɛpɛm is a conversational tutor for **Kenyang (Kɛ́nyāŋ)**, a language of the Manyu and
Meme Divisions of Southwest Cameroon. It teaches greetings, counting, vocabulary and
sentence-building from a curated body of Kenyang material, and is careful never to invent
words — everything it teaches is drawn from its own knowledge base.

Built by **Agbor Edouard Ransome**, of Bachou Ntai village.

---

## What it does

- Teaches Kenyang conversationally, one small step at a time.
- Answers "how do you say…", quizzes both directions, and builds phrases from known pieces.
- Draws every Kenyang word from a trusted knowledge base rather than from a model's memory,
  so it does not fabricate vocabulary or grammar.
- Flags any word in a reply that it could not find in its own material, so unverified
  Kenyang is visible rather than hidden.

## How it works, briefly

The app reads a folder of Kenyang material, splits it into passages, and — for each
question — searches that material and hands the relevant passages to the language model
along with the grammar rules. The model teaches only from what it is given.

- **Knowledge base** (`knowledge_base/`) — dictionaries, a grammar guide, phonology,
  numbers, and teaching chapters, as `.txt`, `.md` and `.jsonl` files.
- **Trust tiers** — material is ranked *verified* (checked by a native speaker) >
  *core* (course chapters, dictionary) > *reference* (scholarly). Higher tiers win when
  sources disagree. A file's tier comes from a `_verified` / `_core` / `_ref` marker in
  its name, or from the lists near the top of `streamlit_app.py`.
- **Grammar spine** — the chapters that teach sentence structure (possessives, adjectives,
  conjugation, negation, word order) travel with *every* question, because a learner's
  wording rarely overlaps a grammar table enough for search to find it on its own.
- **Retrieval** — a hybrid of exact-word matching, meaning-based (embedding) search, and
  rarity-weighted keywords, with near-duplicate passages filtered out.

## Running it locally

Requires Python 3.9+ and an OpenAI API key.

```bash
pip install -r requirements.txt

# provide the key, either as an environment variable:
export OPENAI_API_KEY="sk-..."
# ...or in .streamlit/secrets.toml (never commit this file):
#   OPENAI_API_KEY = "sk-..."

streamlit run streamlit_app.py
```

In GitHub Codespaces, open the app through the **PORTS** tab (port 8501), not the
`localhost` URLs the terminal prints — those are internal to the container.

## The knowledge base

Everything Nɛpɛm teaches lives in `knowledge_base/`. To add material, drop a `.txt`,
`.md` or `.jsonl` file into that folder. Formatting that helps:

- **One entry per line** for word lists, so each stays retrievable on its own.
- **Worked examples in blocks** for grammar — show the phrase built slot by slot; that
  is the pattern the tutor copies.
- **No source names in the content** — the app strips `document_id`-type fields, but
  don't add "from the X dictionary" headers, as the tutor is meant never to name a source.
- Put a tier marker (`_core`, `_ref`, `_verified`) in the filename so it lands in the
  right tier.

The single most valuable file is `kenyang_verified_speaker.md` — anything a native
speaker has personally confirmed. It outranks every other source, and expanding it
raises the quality of everything the tutor does.

## Rebuilding the search index (optional, for deployment)

The app embeds the corpus on first load and caches it. On a hosted deployment that cache
can be lost when the app sleeps, so a prebuilt index removes the wait for visitors:

```bash
python build_index.py            # writes index.npz
git add knowledge_base index.npz
git commit -m "rebuild index"
git push
```

Run this after any change to `knowledge_base/`. If you forget, nothing breaks — the app
just embeds on first load and the sidebar tells you the index was "built just now".

## Configuration

Near the top of `streamlit_app.py`:

- `MODEL` — the OpenAI model. Larger models handle sentence-building noticeably better.
- `CONTEXT_MODE` — `"auto"` (default), `"retrieve"`, or `"full"` (whole corpus every
  turn; needs a long-context model).
- `SPINE_KEYWORDS` — filename keywords that pin a file to the always-in-view grammar spine.

## A note on the data

Several source documents were recovered from PDFs whose fonts extracted as scrambled or
shifted text; the converter scripts and their `*_NEEDS_REVIEW.txt` companions record what
was decoded and what still needs a speaker's eye. Where two sources disagree — a tone mark
here, a spelling there — only a Kenyang speaker can settle it. Treat the tutor as a study
aid built on documented material, not as a final authority, and check anything important
with an elder or native speaker.

---

*Kɛ́nyāŋ — the language of home.*