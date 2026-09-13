"""
Nɛpɛm — a Kenyang (Kɛ́nyāŋ) language tutor.

Built by Agbor Edouard Ransome, Bachou Ntai village.

  1. Config     — model, paths, budgets, trust tiers.
  2. Corpus     — reads every file in ./knowledge_base and cuts it into passages.
                  Nothing is thrown away any more: the whole corpus is searchable.
  3. Retrieval  — picks the passages that matter for the question actually asked.
  4. Prompt     — who Nɛpɛm is, what he must never say, and how he teaches.
  5. Look       — my chat bubbles, avatars, typing indicator (mobile first).
  6. App        — history, lesson tracking, streaming reply.

No database. The OpenAI key comes from Streamlit Secrets.
"""

import os
import re
import glob
import json
import math
import html
import numpy as np
import streamlit as st
from openai import OpenAI

# =============================================================================
# 1. CONFIG
# =============================================================================

MODEL = "gpt-4o-mini"                    # swap freely; temperature is guarded below
EMBED_MODEL = "text-embedding-3-small"   # ~$0.02 per million tokens, and indexed once
TEMPERATURE = 0.3
KB_ROOT = "knowledge_base"

# I no longer cram the whole library into every message. The verified file rides along
# always; everything else is searched, and only the passages that match come with it.
#
# Embeddings are ON now. I know the corpus: ~550k chars, 544 passages. That indexes in
# seconds and costs a fraction of a cent, and keyword search was demonstrably failing —
# "what is 1 in kenyang?" reduced to searching for the word "kenyang", which is in almost
# every passage. Set this False only to fall back to the keyword search below.
USE_EMBEDDINGS = True
MAX_CHUNKS = 8_000           # hard ceiling. Past this I want to be told, not to hang.
ALWAYS_ON_CHARS = 40_000     # ceiling for the verified tier, which travels every turn

# --- how much material goes in each message ---------------------------------
# "full" sends the ENTIRE corpus every turn. That is what I actually want — no retrieval,
# no chance of Nɛpɛm seeing only part of my files — but it is bounded by arithmetic, not
# by code: my corpus is ~550k characters, about 137k tokens, and gpt-4o-mini's whole
# window is 128k. It cannot be done on that model at any price.
#
#   "full"     — send everything. Needs a long-context model. Set MODEL first.
#   "retrieve" — search and send the best passages. Works on any model.
#   "auto"     — full when it fits under FULL_CONTEXT_CHARS, retrieve when it doesn't.
#
# The sidebar tells me which mode is actually live and why.
CONTEXT_MODE = "auto"
FULL_CONTEXT_CHARS = 350_000   # ~87k tokens, the most I'd push into a 128k window

EXACT_RESERVE = 20           # of those, held for literal word matches so that a
                             # passage containing the asked-for word always gets in
MAX_PASSAGES = 70            # retrieval mode: total passages per question, after merging
MAIN_PROBE_K = 18            # share for the whole question
SUB_PROBE_K = 4              # share for each word probe and each grammar probe
CHUNK_CHARS = 1_200          # passage size — roughly a page of a chapter
CHUNK_OVERLAP = 160          # bleed between passages so a sentence isn't cut in half
TIER_BOOST = {"verified": 0.10, "core": 0.05, "reference": 0.0}   # ties break toward trust

MAX_HISTORY_TURNS = 30       # messages Nɛpɛm can still see; older ones are marked on screen
STREAM_FLUSH_CHARS = 24
EMBED_BATCH = 96             # passages per embedding request when building the index

READABLE = (".md", ".txt", ".jsonl", ".json", ".pdf")
PDF_PAGE_LIMIT = 400

# --- Trust tiers -------------------------------------------------------------
# The PDFs are gone — everything is .txt, .md or .jsonl now, and the converted files
# carry _core / _ref in their names, so the suffix rule below does nearly all the work.
# These lists are only for files whose names say nothing about how much I trust them.
VERIFIED_FILES = {
    "kenyang_verified_speaker.md",         # the one file a speaker has actually checked
}
CORE_FILES = set()                         # unsuffixed .txt/.md default to core anyway
REFERENCE_FILES = {
    "kenyang_tone_orthography_1998.txt",
    "kenyang_hortatory_discourses.txt",
    "kenyang_discourse.md",
    "kenyang_noun_rameres.txt",
    "man_to_his_family_ml_plain_text (1).txt",
    "gemini-code-1789075633901.md",
}
EXCLUDE_FILES = {
    # The FULL.md is the proofreading dump of the lexicon — every entry in it is already
    # in kenyang_lexicon_core.jsonl, but messier. Loading both doubles the dictionary and
    # feeds the model two spellings of the same word. The .md stays in the folder so I can
    # read it; it just doesn't go to Nɛpɛm.
    "kenyang_lexicon_full.md",
}

# --- the grammar spine -------------------------------------------------------
# Word order, concord and tone are needed for EVERY sentence I ask him to build, and a
# search shaped like "where is my black dog" shares no words with a concord table — so
# retrieval was never reliably fetching them. These files ride along on every single turn,
# like the verified file does. If the order rule is always in view, he has no excuse.
#
# The teaching chapters belong here more than the scholarly files do: a chapter SHOWS the
# noun phrase built slot by slot, which is the pattern the model copies. Any file whose
# name contains one of these words is pinned to the spine, so I never have to rename a
# file to make it work — ch4_Relationship_chategories.txt matches on "relationship",
# CH_5_prepositions_adjectives_etc.txt on "preposition", and so on.
#
# Only the COMPOSITIONAL machinery goes here. The spine rides in every single message, so
# every character in it is paid for on every turn. Word lists (ch10 opposites, ch12 cheat
# sheet, the dictionaries) retrieve perfectly well on their own and stay out.
SPINE_KEYWORDS = ("possess", "relationship", "adjective", "conjugat", "negation",
                  "preposition", "demonstrative", "plural", "orthography", "noun_ram")
SPINE_FILES = {
    "kenyang_orthography_ref.jsonl",       # noun phrase order, AP, tone, tense, negation
}
SPINE_CHARS = 120_000        # total ceiling for the spine, shared across those files.
                             # Raised from 70k: the teaching chapters ARE the point of the
                             # spine now, and they must not be silently truncated away.

st.set_page_config(page_title="Nɛpɛm — Learn Kenyang", page_icon="🌿",
                   layout="centered", initial_sidebar_state="collapsed")

WELCOME = "Mma ne eta, welcome! I am Nɛpɛm your life-line to mastering Kenyang."


def api_key():
    """Secrets first (Streamlit Cloud), environment second (my Codespace)."""
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        key = ""
    return key or os.environ.get("OPENAI_API_KEY", "")


def rerun():
    """
    Restart the script. Same lesson as the st.status crash: don't assume a command
    exists on the version that's actually installed. st.rerun is recent; the
    experimental name is what older builds carry.
    """
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()


# =============================================================================
# 2. CORPUS — read everything, cut it up, discard nothing
# =============================================================================

def tier_of(filename):
    """How much I trust a file, from its name. None means skip it."""
    name = filename.lower()
    if name in EXCLUDE_FILES:
        return None
    if "_verified" in name:
        return "verified"
    if "_ref" in name:
        return "reference"
    if "_core" in name:
        return "core"
    if name in VERIFIED_FILES:
        return "verified"
    if name in CORE_FILES:
        return "core"
    if name in REFERENCE_FILES:
        return "reference"
    return "reference" if name.endswith(".pdf") else "core"


def in_spine(filename):
    """True if this file rides along on every turn (see SPINE_FILES / SPINE_KEYWORDS)."""
    name = filename.lower()
    return name in SPINE_FILES or any(k in name for k in SPINE_KEYWORDS)


def tidy(text):
    """Whitespace cleanup. Saves real tokens on the PDFs."""
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _english_score(s):
    """Crude 'is this English' signal — enough to tell repaired text from garbage."""
    s = " " + s.lower() + " "
    return sum(s.count(w) for w in (" the ", " and ", " of ", " in ", " is ", " to ",
                                    " a ", " for ", " that ", " with ", " are "))


def _shift(text):
    """Move every printable character up by one. Spaces and newlines stay put."""
    return "".join(chr(ord(c) + 1) if 33 <= ord(c) <= 125 else c for c in text)


def repair_encoding(text):
    """
    Undo the one-character shift some PDFs extract with.

    My orthography guide came out of pypdf as "JDMX@MF NQSGNFQ@OGX" — that is
    "KENYANG ORTHOGRAPHY" with every character moved up by one. The PDF uses a custom
    font encoding and pypdf hands back the raw codes. The file looked like it had loaded
    fine: 20,000 characters of confident nonsense. Every grammar rule Nɛpɛm needed —
    noun phrase order, the associative marker, its tone — sat in there unreadable, which
    is exactly why he kept guessing at word order.

    Line by line, because the headings in that file came out plain while the body didn't.
    A backtick or @ is near proof on its own: they decode to 'a' and 'A', the commonest
    letters in English, so shifted prose is full of them.
    """
    if not text:
        return text, False
    # Does the file as a whole look shifted? Don't touch a healthy file.
    head = text[:6000]
    if _english_score(_shift(head)) <= _english_score(head):
        return text, False

    out, changed = [], 0
    for line in text.split("\n"):
        if not line.strip():
            out.append(line)
            continue
        marks = line.count("`") + line.count("@")
        dec = _shift(line)
        if marks >= 2 or _english_score(dec) > _english_score(line):
            out.append(dec)
            changed += 1
        else:
            out.append(line)
    return "\n".join(out), changed > 0


# Keys I strip out of every JSONL record before Nɛpɛm ever sees it. My converted files
# carry a "document_id" on every line — "Kenyang_Lexicon", "Kenyang_Orthography_Guide" —
# and that is a source name, repeated two thousand times, in direct contradiction of the
# rule that he never names where his Kenyang came from. I built opaque labels into the
# loader and then handed the names straight back in the file content.
DROP_KEYS = {"document_id", "source", "source_file", "document", "author"}


def parse_json_records(raw):
    """
    Turn JSON or JSONL text into readable lines, dropping the source-naming keys.

    Split out of read_file because several of my files are JSONL saved with a .txt
    extension, and routing on the extension alone meant those were fed to Nɛpɛm as raw
    JSON — braces, quotes, and a document_id naming the source on every single line.
    """
    try:
        blob = json.loads(raw)
        items = blob if isinstance(blob, list) else [blob]
    except Exception:
        items = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                items.append(line)
    rows = []
    for o in items:
        if not isinstance(o, dict):
            rows.append(str(o))
            continue
        o = {k: v for k, v in o.items() if k.lower() not in DROP_KEYS}
        if not o:
            continue
        # A flat record reads better as "key: value | key: value". A nested one — a
        # grammar rule with a table of concords inside it — loses its shape that way, so
        # keep the JSON. ensure_ascii=False matters: without it every ɛ, ɔ and tone mark
        # becomes \\u025b and stops matching anything a learner types.
        if all(not isinstance(v, (dict, list)) for v in o.values()):
            rows.append(" | ".join(f"{k}: {v}" for k, v in o.items()))
        else:
            rows.append(json.dumps(o, ensure_ascii=False))
    return "\n".join(rows)


def looks_like_json(raw):
    """True if the text is really JSON or JSONL, whatever the file is called."""
    head = raw.lstrip()[:1]
    if head not in "[{":
        return False
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            return True                  # a whole record on one line: JSONL
        except Exception:
            break
    try:
        json.loads(raw)                  # or one JSON document across many lines
        return True
    except Exception:
        return False


def read_file(path):
    """
    One reader for all four of my formats. Returns (text, problem).

    It used to swallow every error and hand back an empty string, so a PDF that pypdf
    couldn't open looked exactly like a PDF with nothing in it — and a missing pypdf
    looked like 24 healthy files. Failures are named now and shown in the sidebar.
    """
    ext = path.lower().rsplit(".", 1)[-1]
    try:
        if ext == "pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return "", "pypdf is not installed — run: pip install pypdf"
            reader = PdfReader(path)
            pages = reader.pages[:PDF_PAGE_LIMIT]
            raw = "\n".join((p.extract_text() or "") for p in pages)
            if len(raw.strip()) < 40:
                return "", (f"{len(reader.pages)} pages but almost no text — this is a "
                            f"scanned image and needs OCR")
            fixed, _ = repair_encoding(raw)
            return tidy(fixed), ""

        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read().strip()

        # Content, not extension. Several of my dictionaries are JSONL saved as .txt, and
        # trusting the name meant they went in as raw JSON with the source name attached
        # to every line. Sniff the content and route on what it actually is.
        if ext in ("jsonl", "json") or looks_like_json(raw):
            return tidy(parse_json_records(raw)), ""

        fixed, _ = repair_encoding(raw)               # .md conversions carry the shift too
        return tidy(fixed), ""
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"


def chunk_text(text, size=CHUNK_CHARS, overlap=CHUNK_OVERLAP):
    """
    Cut a file into passages along its own natural seams.

    Prose files break on blank lines. My dictionaries don't have blank lines — they're one
    entry per row — so paragraph splitting turned a whole dictionary into a single block
    that got sliced every 1,200 characters, cutting entries in half and giving every
    passage the same muddy meaning. Line-oriented files are now split by entry and packed
    into smaller passages, which makes each one about a handful of words instead of forty.
    """
    lines = text.split("\n")
    line_oriented = len(lines) > 40 and text.count("\n\n") < len(lines) / 10
    if line_oriented:
        units = [ln.strip() for ln in lines if ln.strip()]
        size = max(300, size // 2)       # tighter passages = sharper dictionary matches
    else:
        units = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks, buf, last = [], "", ""
    for u in units:
        if len(u) > size:                            # one huge block, usually an OCR'd page
            if buf:
                chunks.append(buf)
                buf = ""
            step = max(1, size - overlap)
            for i in range(0, len(u), step):
                chunks.append(u[i:i + size])
            last = ""
            continue
        if not buf:
            buf = (last + "\n" + u) if last else u    # carry one unit over the seam
        elif len(buf) + len(u) + 2 <= size:
            buf += "\n" + u if line_oriented else "\n\n" + u
        else:
            chunks.append(buf)
            last, buf = u, u
    if buf:
        chunks.append(buf)
    return chunks


def kb_signature():
    """
    Fingerprint of the folder: names, sizes, modified times.

    Passed into the cached builders purely as a cache key. Edit a knowledge file and
    the key changes, so corpus and search index both rebuild. Without it, a disk cache
    would serve last week's Kenyang forever.
    """
    marks = []
    for path in sorted(glob.glob(os.path.join(KB_ROOT, "**", "*"), recursive=True)):
        if os.path.isfile(path) and path.lower().endswith(READABLE):
            s = os.stat(path)
            marks.append(f"{os.path.basename(path)}:{s.st_size}:{int(s.st_mtime)}")
    return "|".join(marks)


@st.cache_data(show_spinner="Reading the knowledge…", persist="disk")
def build_corpus(signature):
    """
    Read the whole folder and return (always_on, chunks, manifest).

    `always_on` is the verified material, which travels with every single message.
    `chunks` is everything, searchable. Nothing is dropped for budget reasons any more.

    Note the labels: passages are tagged "verified source 1", "core source 4" and so on,
    never by filename. Nɛpɛm cannot leak a filename he was never shown.
    """
    _ = signature

    files, troubles = [], []
    for path in sorted(glob.glob(os.path.join(KB_ROOT, "**", "*"), recursive=True)):
        if not (os.path.isfile(path) and path.lower().endswith(READABLE)):
            continue
        name = os.path.basename(path)
        tier = tier_of(name)
        if tier is None:
            continue
        text, problem = read_file(path)
        if problem:
            troubles.append({"file": name, "problem": problem})
        if text:
            # Flag files that needed the shift repair, so I can see it happened.
            mended = "associative" in text.lower() or _english_score(text[:4000]) > 3
            files.append({"name": name, "tier": tier, "text": text, "readable": mended})

    order = {"verified": 0, "core": 1, "reference": 2}
    files.sort(key=lambda f: (order[f["tier"]], f["name"].lower()))

    counters = {"verified": 0, "core": 0, "reference": 0}
    chunks, manifest, always_parts, always_used = [], [], [], 0
    spine_parts, spine_used = [], 0

    for f in files:
        counters[f["tier"]] += 1
        label = f"{f['tier']} source {counters[f['tier']]}"

        pieces = chunk_text(f["text"])
        for piece in pieces:
            chunks.append({"tier": f["tier"], "label": label, "text": piece})

        # The verified file rides along in full. It's small, and it's the one thing I
        # never want search to accidentally miss.
        if f["tier"] == "verified" and always_used < ALWAYS_ON_CHARS:
            seg = f["text"][:ALWAYS_ON_CHARS - always_used]
            always_parts.append(f"\n### {label}\n{seg}")
            always_used += len(seg)

        # Grammar rides along too — see SPINE_FILES for why.
        if in_spine(f["name"]) and spine_used < SPINE_CHARS:
            seg = f["text"][:SPINE_CHARS - spine_used]
            spine_parts.append(f"\n### {label}\n{seg}")
            spine_used += len(seg)

        manifest.append({"file": f["name"], "label": label, "tier": f["tier"],
                         "chars": len(f["text"]), "chunks": len(pieces),
                         "spine": in_spine(f["name"])})

    always_on = ""
    if always_parts:
        always_on = ("===== VERIFIED KENYANG — checked by a native speaker. This outranks "
                     "every other source. If anything contradicts it, this wins. =====\n"
                     + "\n".join(always_parts))
    if spine_parts:
        always_on += ("\n\n===== KENYANG GRAMMAR — word order, noun classes, concord, tone. "
                      "This is in front of you on EVERY question. You have no excuse for "
                      "guessing at word order or concord: the rules are right here. Before "
                      "you output any assembled phrase, check it against the order given "
                      "below. =====\n" + "\n".join(spine_parts))

    # If the corpus is enormous I want a number on screen, not a hung page.
    overflow = max(0, len(chunks) - MAX_CHUNKS)
    if overflow:
        chunks = chunks[:MAX_CHUNKS]

    return always_on, chunks, manifest, overflow, troubles


# =============================================================================
# 3. RETRIEVAL — find the passages this question actually needs
# =============================================================================

STOP = set("""a an the is are was were be been being do does did to of in on at for with and or
but if then than that this these those it its as by from about into over under i you he she we
they me him her us them my your his our their can could would should will shall may might must
not no yes please thank""".split())
# Deliberately NOT stopwords, though every stoplist in the world includes them:
# what, which, who, how, when, where, why, say, word. In ordinary prose they carry
# nothing. In a dictionary they are HEADWORD GLOSSES — "fá | adv | where" — so binning
# them meant a learner asking "where is my black dog" could never retrieve fá.

# "one" must not match "money", and "1" must not be thrown away in a counting lesson.
# Digits are their own token; everything else is a word.
TOKEN = re.compile(r"[0-9]+|[\wɛɔŋʉɨ]+", re.UNICODE)

NUMBER_WORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
DIGIT_TO_WORD = {str(i + 1): w for i, w in enumerate(NUMBER_WORDS)}
WORD_TO_DIGIT = {w: str(i + 1) for i, w in enumerate(NUMBER_WORDS)}
COUNTING = {"count", "counting", "counts", "number", "numbers", "numeral", "numerals"}
# A learner types "1 million". My numbers file writes it "1.000.000" with dots as the
# thousand separator — a European convention — so every search for "1000000" or
# "1,000,000" missed an entry that was sitting right there. Bridge every written form.
BIG_NUMBERS = {
    "hundred": ("100",),
    "thousand": ("1000", "1.000", "1,000"),
    "million": ("1000000", "1.000.000", "1,000,000"),
    "billion": ("1000000000", "1.000.000.000", "1,000,000,000"),
    "100": ("hundred",),
    "1000": ("thousand", "1.000"),
    "1000000": ("million", "1.000.000"),
}


def tokenize(text):
    """Lowercase tokens. Digits survive — they were being filtered out by a length rule."""
    return TOKEN.findall(text.lower())


def terms(text):
    """Query terms: content words, plus any digit however short."""
    return {t for t in tokenize(text) if t.isdigit() or (len(t) > 2 and t not in STOP)}


def expand(qterms):
    """
    Widen the query where a learner's wording and the material's won't line up.

    A page of numbers is written "one, two, three"; a learner types "1 to 10". Without
    this bridge the counting lesson is unfindable, which is exactly what happened.
    """
    extra = set()
    for t in qterms:
        if t in DIGIT_TO_WORD:
            extra.add(DIGIT_TO_WORD[t])
        if t in WORD_TO_DIGIT:
            extra.add(WORD_TO_DIGIT[t])
        if t in COUNTING:
            extra.update(NUMBER_WORDS)
            extra.add("number")
        if t in BIG_NUMBERS:
            extra.update(BIG_NUMBERS[t])
    return qterms | extra


@st.cache_data(show_spinner=False, persist="disk")
def build_lexicon(signature):
    """
    Token set per passage, plus how many passages each token appears in.

    The document frequency is what makes the keyword search usable: a term in 500 of
    544 passages tells me nothing, a term in 3 of them tells me almost everything.
    """
    _a, chunks, _m, _o, _t = build_corpus(signature)
    sets = [set(tokenize(c["text"])) for c in chunks]
    df = {}
    for s in sets:
        for t in s:
            df[t] = df.get(t, 0) + 1
    return sets, df


INDEX_FILE = "index.npz"


@st.cache_data(show_spinner=False, persist="disk")
def build_index(signature):
    """
    The passage vectors, either loaded from a committed file or embedded fresh.

    On Streamlit Cloud the container is rebuilt whenever the app wakes from sleep, and the
    disk cache doesn't reliably survive that — so without this, the first visitor after
    every quiet spell waits ~30 seconds while the whole corpus re-embeds, and I pay for it
    again each time. build_index.py computes the vectors once and saves index.npz; I commit
    that next to the knowledge files. The signature guard is what stops a stale index
    outliving the folder it describes: edit the knowledge, the signature changes, and a
    mismatched file is ignored so the vectors rebuild.

    Returns None if there's no committed file AND no key; search then falls back to keywords.
    """
    if os.path.exists(INDEX_FILE):
        try:
            blob = np.load(INDEX_FILE, allow_pickle=False)
            if str(blob["signature"]) == signature:
                return blob["vectors"].astype(np.float32)
        except Exception:
            pass                          # unreadable or stale — fall through and rebuild

    key = api_key()
    if not key:
        return None
    _always, chunks, _man, _over, _tr = build_corpus(signature)
    if not chunks:
        return None
    try:
        client = OpenAI(api_key=key)
        rows = []
        for i in range(0, len(chunks), EMBED_BATCH):
            batch = [c["text"][:8000] for c in chunks[i:i + EMBED_BATCH]]
            resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
            rows.extend(d.embedding for d in resp.data)
        mat = np.asarray(rows, dtype=np.float32)
        # Normalise once, here. Then similarity is just a dot product at question time.
        mat /= np.clip(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9, None)
        return mat
    except Exception:
        return None


def embed_query(text):
    """One small embedding, normalised. Kept for anything that needs a single vector."""
    got = embed_many([text])
    return None if got is None else got[0]


def embed_many(texts):
    """
    Embed several probes in ONE request. Normalised rows, so scoring is a dot product.

    Batching matters: eight probes cost one round trip, not eight.
    """
    try:
        resp = OpenAI(api_key=api_key()).embeddings.create(
            model=EMBED_MODEL, input=[t[:8000] for t in texts])
        m = np.asarray([d.embedding for d in resp.data], dtype=np.float32)
        return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)
    except Exception:
        return None


# Grammar lives in different files from vocabulary, and a question like "translate this
# dialogue" is nowhere near a concord table in meaning — so a search for the question will
# never fetch one. These probes go and get the machinery explicitly.
GRAMMAR_PROBES = [
    "noun class prefix and concord agreement",
    "association particle linking noun and adjective",
    "word order in the noun phrase, adjective and possessive",
    "possessive pronoun agreement by class",
    "past tense marker and tone change on the verb",
    "question words, where, what, how",
    "plural formation and noun class pairs",
    "locative words, behind, inside, under",
]
COMPOSE_HINTS = {"translate", "translation", "sentence", "sentences", "dialogue", "phrase",
                 "grammar", "build", "construct", "conjugate", "class", "concord", "tone",
                 "order", "plural", "tense", "say", "write"}


def probes_for(query, max_word_probes=10):
    """
    Turn one question into many searches.

    This is the fix for "it only sees part of my data". Building "my black dog" needs the
    dictionary entry for dog, the entry for black, the class-9 possessive, the noun phrase
    order rule and the interrogative — five facts in four files. A single search finds
    whatever is nearest the sentence as a whole and misses the rest. So I search for the
    question, for each content word in it, and — when the question is compositional — for
    the grammar machinery by name.
    """
    out = [query]
    words = sorted(expand(terms(query)), key=len, reverse=True)
    out += words[:max_word_probes]
    low = query.lower()
    if any(h in low for h in COMPOSE_HINTS):
        out += GRAMMAR_PROBES
    seen, uniq = set(), []
    for p in out:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            uniq.append(p)
    return uniq


def _merge(order, picked, seen, cap):
    """Add ranked indices to the running selection, skipping ones already taken."""
    for i in order:
        i = int(i)
        if i not in seen:
            seen.add(i)
            picked.append(i)
        if len(picked) >= cap:
            return True
    return False


def exact_hits(query, chunks, per_term=4):
    """
    Find passages that literally contain the words asked about.

    This is the guarantee. If "million" is written anywhere in my files, the passage
    holding it goes into context — it cannot be outranked, outvoted or crowded out.
    Embeddings are good at "something like this" and bad at "this exact rare word", which
    is most of what a language tutor is actually asked for.
    """
    picks = []
    # expand() first: the material may write the number a different way than the learner
    # typed it ("1.000.000" vs "1 million"), and this pass is the guarantee.
    needles = {t for t in expand(terms(query)) if len(t) >= 3 or t.isdigit()}
    for t in sorted(needles, key=len, reverse=True):
        n = 0
        for i, c in enumerate(chunks):
            if t in c["text"].lower():
                picks.append(i)
                n += 1
                if n >= per_term:
                    break
    return picks


def drop_near_duplicates(chunks, picked, cap, threshold=0.72):
    """
    Remove passages that say the same thing as one already chosen.

    I ended up with seven overlapping word lists — four old partial dictionaries, a new
    one, the converted lexicon, and a proofreading dump. Ask for "dog" and retrieval would
    happily spend six of its seventy slots on six copies of the same entry, crowding out
    the grammar and the examples. This keeps the first copy and spends the freed slots on
    something the model hasn't already been told.

    Overlap is measured against the shorter passage, so a short dictionary line counts as
    a duplicate of a longer one that contains it.
    """
    kept, kept_sets = [], []
    for i in picked:
        toks = set(tokenize(chunks[i]["text"]))
        if len(toks) >= 8:
            dupe = False
            for s in kept_sets:
                shorter = min(len(toks), len(s))
                if shorter and len(toks & s) / shorter >= threshold:
                    dupe = True
                    break
            if dupe:
                continue
        kept.append(i)
        kept_sets.append(toks)
        if len(kept) >= cap:
            break
    return kept


def search(query, chunks, vectors, lexicon=None, cap=MAX_PASSAGES):
    """
    Hybrid, multi-probe retrieval: exact matches first, then meaning, then rarity.

    The keyword half used to be a fallback that only ran when embeddings failed, so on a
    working system it never ran at all — and a question like "1 million" got answered
    purely on vibes. All three now run every time and merge:

      1. exact   — passages literally containing the words asked about. Guaranteed in.
      2. semantic— the question and each of its parts, by meaning.
      3. lexical — rarity-weighted, to fill whatever budget is left.
    """
    qs = probes_for(query)
    picked, seen = [], set()
    boost = np.array([TIER_BOOST[c["tier"]] for c in chunks], dtype=np.float32)
    # Collect half again as many as I need, so that dropping duplicates further down
    # frees a slot for new material instead of just returning fewer passages.
    room = int(cap * 1.6)

    # 1. exact matches, reserved a slice of the budget so meaning can't crowd them out
    _merge(exact_hits(query, chunks), picked, seen, min(room, EXACT_RESERVE * 2))

    # 2. meaning
    if vectors is not None and len(vectors) == len(chunks):
        mat = embed_many(qs)
        if mat is not None:
            for n, row in enumerate(mat):
                per = MAIN_PROBE_K if n == 0 else SUB_PROBE_K
                sims = vectors @ row + boost
                if _merge(np.argsort(-sims)[:per], picked, seen, room):
                    return [chunks[i] for i in drop_near_duplicates(chunks, picked, cap)]

    # 3. rarity-weighted keywords, now running alongside rather than instead
    if lexicon:
        sets, df = lexicon
        total = max(1, len(sets))
        for n, q in enumerate(qs):
            qterms = expand(terms(q))
            if not qterms:
                continue
            weights = {t: math.log(1 + total / (1 + df.get(t, 0))) for t in qterms}
            scores = []
            for i, tokens in enumerate(sets):
                hit = sum(w for t, w in weights.items() if t in tokens)
                if hit:
                    scores.append((hit + TIER_BOOST[chunks[i]["tier"]], i))
            scores.sort(key=lambda s: s[0], reverse=True)
            per = MAIN_PROBE_K if n == 0 else SUB_PROBE_K
            if _merge([i for _s, i in scores[:per]], picked, seen, room):
                break
    return [chunks[i] for i in drop_near_duplicates(chunks, picked, cap)]


@st.cache_data(show_spinner=False, persist="disk")
def full_block(signature):
    """
    The entire corpus in one block, grouped by trust tier, for full-context mode.

    No search, no ranking, no chance of missing a file. Cached, and stable between turns
    so the whole thing sits in the model's prompt cache and costs the reduced rate.
    """
    _a, chunks, _m, _o, _t = build_corpus(signature)
    out = ["===== THE COMPLETE KENYANG MATERIAL — everything I have, nothing held back. "
           "If a word or rule is not in here, it is not something you know. ====="]
    for tier, note in (("verified", "native-speaker verified — outranks everything"),
                       ("core", "course chapters and dictionary — trusted"),
                       ("reference", "scholarly — working orthography, tone often "
                                     "inconsistent, never quote its tone as certain")):
        group = [c for c in chunks if c["tier"] == tier]
        if group:
            out.append(f"\n--- {tier.upper()} ({note}) ---")
            out += [c["text"] for c in group]
    return "\n\n".join(out)


def passages_block(found):
    """Group the retrieved passages under their trust headers, highest tier first."""
    if not found:
        return ""
    out = ["===== PASSAGES SELECTED FOR THIS QUESTION =====",
           "Drawn from the same material, chosen because they look relevant right now.",
           "The trust order still applies. If what you need is not here, say so plainly "
           "rather than inventing it."]
    for tier, note in (("verified", "native-speaker verified — outranks everything"),
                       ("core", "course chapters and dictionary — trusted"),
                       ("reference", "scholarly — working orthography, tone often "
                                     "inconsistent, never quote its tone as certain")):
        group = [c for c in found if c["tier"] == tier]
        if group:
            out.append(f"\n--- {tier.upper()} ({note}) ---")
            out += [f"\n[{c['label']}]\n{c['text']}" for c in group]
    return "\n".join(out)


# =============================================================================
# 4. PROMPT
# =============================================================================

SYSTEM_PROMPT = f"""You are Nɛpɛm, a warm, patient tutor for the Kenyang language (Kɛ́nyāŋ)
of Southwest Cameroon. Your learners are Bayangi people reconnecting with their mother tongue
and beginners who have never studied it. Teach in a friendly, conversational way and leave
every learner encouraged.

WHO YOU ARE:
- You are Nɛpɛm, a Kenyang tutor. That is your whole identity.
- You were created by Agbor Edouard Ransome of Bachou Ntai village. If a learner asks who made
  you, say so warmly and with pride. This is the ONLY fact about yourself you ever share.

WHAT YOU NEVER REVEAL — this is absolute:
- Never name or describe where your Kenyang comes from. No authors, compilers, scholars,
  dictionaries, lexicons, book or paper titles, institutions, filenames, or websites. Not one.
- Never confirm or deny a source a learner names at you. If someone asks "did you use X" or
  "who wrote your dictionary", you do not know and you do not speculate. You simply teach.
- Never discuss data, training, how you were built, how much material you hold, or what is or
  isn't inside you. There is no answer to give. Say warmly that you're here to teach Kenyang,
  and take the next step in the lesson in the same breath.
- If a learner claims the knowledge is theirs, or that their work was used, do not confirm,
  deny, argue, apologise or explain. Thank them for their care for Kenyang and return to the
  lesson immediately.
- If pressed a second or third time, add no new detail whatsoever. One short friendly line,
  then a concrete next step. Never let repetition draw more out of you than the first ask did.
- Never mention that you are an AI or language model, or refer to models, prompts or files.
- The learner has already seen your opening line ("{WELCOME}"), so don't repeat it word for word.

WHERE YOUR KENYANG COMES FROM:
- Every Kenyang word, meaning and tone mark you teach must appear in the material given to you.
  Nowhere else. You have no other Kenyang.
- Trust order: VERIFIED beats CORE beats REFERENCE. If they disagree, the higher tier wins.
- Never invent a Kenyang word and never guess a meaning. If a word isn't in your material, say
  so once, warmly and briefly, offer a related word you do have, and move on.
- The passages you're given are a SELECTION picked for the question just asked, not everything
  that exists. So when something isn't there, say you don't have it to hand and invite them to
  ask again in different words — not that it doesn't exist. "I don't have that in front of me;
  try asking me another way" is honest. "Kenyang has no word for that" is not yours to say.
- Before stating what a word means, check the meaning is actually written there. "I have that
  word but not a confirmed meaning" serves a learner far better than a confident guess.
- You MAY build phrases from words and grammar you have — that is teaching, not inventing. When
  you do, say you put known pieces together. Never attach a tone mark you haven't seen.
- Keep Kenyang spelling and special letters (ɛ ɔ ŋ ʉ ɨ) and tone marks exactly as written.

BE THE ONE DRIVING THE LESSON:
- Teach ONE thing per reply. Two new words at most. A wall of greeting pairs is how you lose a
  beginner in the first minute.
- Do not end every reply asking what they'd like to do. Vary it, and more often simply take the
  next step yourself. Never end two replies in a row with the same question.
- When a learner answers a quiz, say plainly whether they are right or wrong before anything
  else. Calling a wrong answer "very close" teaches them nothing — tell them what was wrong.
- When a learner says they are lost, do NOT repeat what you just said. Drop to something much
  smaller — a single word, no response pair — and rebuild from there.
- You will be shown what you have already taught in this lesson. Build on it. Don't restate it.
- Read their level from how they answer and adjust. Don't interrogate them.
- Say it once. Do not teach a word and then recap the same word in a summary two lines later.
  The learner can still see what you wrote. The recap is wasted space.
- Do not end on an offer. "Would you like to practise or learn something new?" is filler that
  ended nearly every one of your replies and taught no one anything. End on the Kenyang itself,
  or on one real question you need answered to continue the lesson.
- No cheerleading. "Great job!", "You're doing wonderfully!", "Keep it up!" are noise between
  the learner and the language. A plain "yes, that's right" does the encouraging.
- A reply can be one word, its meaning, and one line showing its use. That is a complete, good
  reply. It does not need a preamble, a recap, and an offer wrapped around it.

WHAT IS AND ISN'T YOUR JOB:
- Translating, building sentences, explaining noun classes, concord particles, tone and word
  order IS your job. It is the heart of it. NEVER refuse one of these as "outside what I do."
  That phrase belongs only to things that aren't Kenyang at all — weather, essays, homework in
  other subjects. A hard Kenyang question is not off-topic, it is the work.
- When a task is hard, do the part your material supports and name the part it doesn't. Never
  decline the whole thing because one piece is missing. "Here is the noun phrase; I don't have
  the tone rule for the verb" is a good answer. Refusing the dialogue is not.
- Show your working. Name the class, the particle, the order you used, so the learner can check
  you. If a piece isn't in your passages, say which piece, and stop at that piece.
- If a learner gives you a rule explicitly — a word order, a concord, a class — FOLLOW IT
  EXACTLY as written. Do not quietly reorder it. If you think it's wrong, say so and follow it
  anyway, marking your doubt.
- Never output a Kenyang word containing characters you have not seen in the material —
  underscores, stray punctuation, invented affixes. If you are reaching for those, you are
  assembling from nothing, and you should stop and say so instead.

BUILDING SENTENCES — THIS IS YOUR WORK, NOT A RISK TO AVOID:
- You may and should build phrases and sentences from the pieces in your material. A tutor who
  can only repeat whole attested sentences teaches nobody a language.
- But every piece must be traceable. Lay the parts out first, then assemble, then say you
  assembled it. Shape it like this:
      dog = m-mú (class 9) · black = pyo · my, class 9 = y-a · where = fá
      putting those together: m-mú …
      I built this from the parts above — a speaker should confirm it.
- If one piece is missing, NAME the missing piece and build as far as you can. "I have the
  words but not the class 9 particle" is a good answer. Refusing the whole task is not.
- Never invent a piece to complete a pattern. A gap named is worth more than a gap filled.
- ABSOLUTE: if you are about to write "not previously provided", "not in my material",
  "we can use it here", or anything of that shape about a Kenyang word — STOP. You have just
  caught yourself inventing. Do not write that word. Say you don't have it and build the rest
  around the gap. A learner skims past a parenthetical and takes the word as real Kenyang.
- Do not substitute an English pronunciation guide for Kenyang. "C as in cat" is not Kenyang
  and never belongs in a reply. If you don't have the alphabet or the sounds, say so.
- Check every word you are about to output against the material. If it isn't there, it isn't
  Kenyang as far as you are concerned, however natural it feels.

WORD ORDER IS NOT ENGLISH ORDER:
- Do NOT translate word by word and keep the English sequence. Swapping Kenyang words into an
  English sentence is the single most common mistake and it teaches people wrong Kenyang.
- Before you output any built phrase: state the order rule you are using from the grammar
  above, then lay your phrase against it and check each slot. Show that check.
- If the material's order and your instinct disagree, the material wins. Always.

WHEN A LEARNER SAYS THE ORDER IS WRONG:
- Stop. Do not move on to the next question, and do not repeat the same phrase back to them.
- Go to the grammar above, find the order rule, quote it, and rebuild the phrase against it.
- Say what you had wrong. "I put the possessive first; the rule puts it last" is what a
  learner needs. "Thank you for your patience!" followed by the same answer is useless.
- If a learner hands you a rule — a word order, a concord, a class — FOLLOW IT EXACTLY as
  written, and label the result as built from their rule rather than confirmed Kenyang. Do not
  quietly reorder what they gave you. If you think it's wrong, say so and follow it anyway.

UNDER PRESSURE:
- If a learner pushes back, never apologise your way into a new answer. Look again at the
  material. If it's there, say you found it. If it isn't, hold your position warmly.
- Changing your answer because someone insisted is a failure, not politeness. "I still don't
  have it, and I'd rather not guess at your language" is the right answer.

STAYING IN YOUR LANE:
- You only help with learning Kenyang. For genuinely unrelated things, warmly say that's outside
  what you do and offer the next step in the lesson.
- When you're unsure or something is contested, say so and suggest asking a native speaker or
  elder. Honesty is part of who you are. Never fake fluency.
"""

# This sits at the very END of everything, right against the learner's question. The rules
# at the top are thousands of tokens away by then, and models attend hardest to what comes
# first and last. Repeating the four that matter most is the cheapest accuracy fix I have.
RULES_REMINDER = """
===== BEFORE YOU ANSWER =====
1. Every Kenyang word, meaning and tone mark you give must appear in the material above. If it
   isn't there, say so. Do not guess, and do not fill the gap with something that merely sounds
   Kenyang.
2. Name no source, author, book or file. Confirm none. Deny none. Just teach.
3. One small step. Two new words at most. Say plainly whether their answer was right or wrong.
4. If you assembled a phrase from pieces, show the pieces, then say you assembled it.
5. Build no form that isn't in the material, and never change an answer just because you
   were pushed. Hold your ground warmly instead.
Answer in English. Say the thing, show the parts, then stop. No recap of what you just
said — the learner can still see it. No "feel free to ask", no closing question unless you
truly need an answer to go on. No "great job" or "keep practising". Warmth lives in how you
correct someone, not in exclamation marks.
"""

# --- what has been taught so far ---------------------------------------------
# Kenyang words carry marks English words don't: ɛ ɔ ŋ ʉ ɨ, tone accents, or the
# apostrophe in forms like O'chi. That's enough to spot them without another API call.
KENYANG_WORD = re.compile(r"[\w'’]*[ɛɔŋʉɨáàâāéèêēíìîīóòôōúùûūǎǐǒǔ][\w'’]*", re.UNICODE)
APOSTROPHE_WORD = re.compile(r"\b[A-Za-z]{1,6}['’][A-Za-z]{2,}\b")
ENGLISH_TAILS = {"s", "t", "re", "ve", "ll", "d", "m"}   # don't, it's, you're, we'll…


def kenyang_tokens(text):
    """Pull the Kenyang-looking words out of a piece of text, in order, deduped."""
    found = KENYANG_WORD.findall(text)
    for w in APOSTROPHE_WORD.findall(text):
        if re.split(r"['’]", w)[-1].lower() not in ENGLISH_TAILS:
            found.append(w)
    seen, out = set(), []
    for w in found:
        w = w.strip("'’.,;:!?()[]")
        if w and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out


def unsupported_words(reply, found):
    """
    Which Kenyang words in this reply appear nowhere in the material behind it.

    This is the fabrication detector. It can't prove a word is wrong — the material uses
    more than one spelling convention, so a real word may be written differently here —
    but a word that appears in NO passage was not read out of my files. It was produced.
    Given that people are using this to recover their mother tongue, they should be told.
    """
    if not found:
        return []
    corpus = " ".join(c["text"] for c in found).lower()
    return [w for w in kenyang_tokens(reply) if w.lower() not in corpus]


def taught_so_far(messages, cap=40):
    """Kenyang words Nɛpɛm has already put in front of this learner, in order."""
    seen, lowered = [], set()
    for m in messages:
        if m["role"] != "assistant":
            continue
        for w in kenyang_tokens(m["content"]):
            if w.lower() not in lowered:
                lowered.add(w.lower())
                seen.append(w)
    return seen[-cap:]


CORRECTION_HINTS = ("order", "wrong", "not right", "incorrect", "supposed to be", "check well",
                    "thats not", "that's not", "it's not", "its not", "actually",
                    "different", "mistake", "another way")


def correction_note(message):
    """
    Spot a learner correcting me, and make it impossible to skate past.

    Twice a learner told Nɛpɛm the word order was wrong and he answered "thank you for your
    patience" and repeated the same phrase unchanged. A correction has to stop the lesson,
    not get absorbed into the next pleasantry.
    """
    low = (message or "").lower()
    if not any(h in low for h in CORRECTION_HINTS):
        return ""
    return ("===== THE LEARNER IS CORRECTING YOU =====\n"
            "Deal with this before anything else. Go to the grammar rules above, find the rule "
            "that applies, quote it back, and rebuild the phrase against it slot by slot. Say "
            "specifically what you had wrong. Do not thank them and repeat the same answer. Do "
            "not move on to a new topic. If the material doesn't settle it, say so plainly and "
            "ask them for the correct order.")


def lesson_note(messages, found=None):
    """
    A briefing so he builds on the lesson instead of restarting it.

    This had a nasty bug. taught_so_far() scrapes Kenyang-looking words out of Nɛpɛm's OWN
    previous replies — so anything he invented got handed back to him next turn as
    established lesson content, and the mistake compounded inside a single session. Now a
    word only counts as taught if it actually appears in the passages retrieved. Inventions
    don't survive the next turn.
    """
    words = taught_so_far(messages)
    if found:
        corpus = " ".join(c["text"] for c in found).lower()
        words = [w for w in words if w.lower() in corpus]
    asked = sum(1 for m in messages if m["role"] == "user")
    lines = [f"===== THIS LESSON SO FAR — {asked} question(s) from the learner ====="]
    if words:
        lines.append("Kenyang already shown to them, and attested in the material above: "
                     + ", ".join(words))
        lines.append("Build on these. Anything you said earlier that is NOT in this list may "
                     "have been a mistake — do not repeat it as fact.")
    else:
        lines.append("Nothing confirmed taught yet. Start with one small thing.")
    return "\n".join(lines)


# =============================================================================
# 5. LOOK
# =============================================================================
# Gentium Book Plus is an SIL face built for African orthographies, so it carries
# ɛ ɔ ŋ ʉ ɨ and stacked tone marks. Inter handles the UI and falls back to Gentium for
# any glyph it lacks — that fallback is why tone marks never render as boxes on a phone.

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gentium+Book+Plus:wght@400;700&family=Inter:wght@400;500;600&display=swap');

/* I hide Streamlit's chrome, but NOT the status widget. That little "Running" marker is
   the only sign the app is alive while the knowledge loads, and hiding it turned a slow
   startup into what looked like a dead page. */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
.stDeployButton, [data-testid="stAppDeployButton"]{display:none !important;}
header[data-testid="stHeader"]{background:transparent;}

:root{
  --paper:#FAF6EC;      /* warm cream, the page */
  --forest:#0C3B2E;     /* deep green, my anchor */
  --leaf:#1B6B4C;       /* mid green, accents */
  --ochre:#B07D2B;      /* clay-gold, used once */
  --ink:#243029;
  --edge:#E7E0CD;
}

html, body, [data-testid="stAppViewContainer"] *{
  font-family:'Inter','Gentium Book Plus',system-ui,sans-serif;
}
[data-testid="stAppViewContainer"]{background:var(--paper);}
.block-container{max-width:680px;padding-top:.6rem;padding-bottom:7rem;}

.hero{background:linear-gradient(150deg,var(--forest) 0%,#144A38 55%,var(--leaf) 100%);
  color:#EAFFF5;border-radius:18px;padding:20px 22px 18px;margin:4px 0 18px;}
.hero .name{font-family:'Gentium Book Plus',Georgia,serif;font-size:2.1rem;font-weight:700;
  margin:0;line-height:1;letter-spacing:.01em;}
.hero .rule{width:44px;height:3px;background:var(--ochre);border-radius:2px;margin:10px 0 9px;}
.hero .tag{color:#C6E9D8;margin:0;font-size:.94rem;line-height:1.45;}

.row{display:flex;align-items:flex-end;gap:9px;margin:12px 0;}
.row.me{flex-direction:row-reverse;}
.ava{flex:0 0 30px;width:30px;height:30px;border-radius:50%;display:flex;
  align-items:center;justify-content:center;margin-bottom:2px;}
.ava svg{width:17px;height:17px;}
.ava-bot{background:var(--forest);color:#BFE9D6;}
.ava-me{background:#EFE7D3;color:#6B5E43;border:1px solid var(--edge);}

.bubble{max-width:78%;padding:11px 15px;font-size:1.02rem;line-height:1.62;
  word-wrap:break-word;overflow-wrap:anywhere;}
.bubble.bot{background:#FFFFFF;color:var(--ink);border:1px solid var(--edge);
  border-radius:16px 16px 16px 4px;}
.bubble.me{background:var(--forest);color:#F1FBF6;border-radius:16px 16px 4px 16px;}
.bubble .li{display:block;padding-left:15px;text-indent:-15px;margin:3px 0;}
.bubble .li:before{content:"•";color:var(--leaf);padding-right:8px;}
.bubble.me .li:before{color:#8FD4B4;}
.bubble code{background:rgba(27,107,76,.09);padding:1px 5px;border-radius:5px;font-size:.95em;}

.thinking{display:flex;align-items:center;gap:8px;color:#5C6D64;font-size:.95rem;}
.dots span{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--leaf);
  margin-right:4px;animation:hop 1.15s infinite;}
.dots span:nth-child(2){animation-delay:.16s;}
.dots span:nth-child(3){animation-delay:.32s;}
@keyframes hop{0%,75%,100%{opacity:.25;transform:translateY(0);}
  35%{opacity:.95;transform:translateY(-3px);}}
.caret{display:inline-block;width:6px;height:1em;background:var(--leaf);margin-left:2px;
  vertical-align:-2px;border-radius:1px;animation:blink 1s steps(1) infinite;}
@keyframes blink{50%{opacity:0;}}
@media (prefers-reduced-motion:reduce){.dots span,.caret{animation:none;}}

.note{color:#7A8A80;font-size:.84rem;margin:-8px 2px 14px;line-height:1.45;}
/* Shown under a reply when a Kenyang word in it appears in none of the material the
   answer was built from. Amber, not red: it's a flag to check, not a verdict. */
.unchecked{margin:-6px 0 14px 39px;padding:9px 13px;border-radius:10px;
  background:#FDF6E3;border:1px solid #E8D9A8;color:#7A6320;font-size:.86rem;
  line-height:1.5;max-width:78%;}
.unchecked b{color:#5E4B12;}
.memmark{display:flex;align-items:center;gap:10px;margin:20px 2px 16px;
  color:#8A9891;font-size:.8rem;}
.memmark:before,.memmark:after{content:"";flex:1;height:1px;background:var(--edge);}

.stButton>button{width:100%;border-radius:12px;border:1px solid var(--edge);background:#fff;
  color:var(--forest);font-weight:500;font-size:.94rem;padding:.7rem .9rem;}
.stButton>button:hover{border-color:var(--leaf);background:#F2F8F5;color:var(--forest);}
.stButton>button:focus-visible{outline:2px solid var(--leaf);outline-offset:2px;}

/* --- the input bar ---------------------------------------------------------
   Streamlit's default is a grey slab that sits on my cream like a foreign object.
   White field, soft green border, deepening on focus. 16px on the textarea is not a
   style choice — anything smaller makes iOS Safari zoom the whole page on tap. */
[data-testid="stBottomBlockContainer"], [data-testid="stBottom"] > div,
.stChatFloatingInputContainer{background:var(--paper) !important;}

[data-testid="stChatInput"]{
  background:#FFFFFF !important;
  border:1.5px solid #D6E3DA !important;
  border-radius:26px !important;
  box-shadow:0 2px 10px rgba(12,59,46,.06);
  transition:border-color .15s ease, box-shadow .15s ease;
}
[data-testid="stChatInput"]:focus-within{
  border-color:var(--leaf) !important;
  box-shadow:0 2px 14px rgba(27,107,76,.16);
}
[data-testid="stChatInput"] textarea{
  font-size:16px !important;
  color:var(--ink) !important;
  background:transparent !important;
}
[data-testid="stChatInput"] textarea::placeholder{color:#9AAAA1 !important;}
/* the send arrow */
[data-testid="stChatInput"] button{color:var(--leaf) !important;}
[data-testid="stChatInput"] button:hover{
  background:rgba(27,107,76,.10) !important;border-radius:50% !important;}

@media (max-width:640px){
  .block-container{padding-left:.75rem;padding-right:.75rem;}
  .hero .name{font-size:1.8rem;}
  .bubble{max-width:85%;font-size:1rem;}
}
</style>
""", unsafe_allow_html=True)

# Inline SVG rather than emoji: crisp on every phone, no dependency on the device's
# emoji font. A leaf for Nɛpɛm, a figure for the learner.
AVA_LEAF = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 20.5c0-8.5 5-13.5 15-14.5'
            ' 0 9.5-5 14.5-15 14.5z"/><path d="M4.5 20.5c2.8-4 6-6.4 9.5-7.6"/></svg>')
AVA_YOU = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
           'stroke-linecap="round"><circle cx="12" cy="8.2" r="3.3"/>'
           '<path d="M5 20c0-3.7 3.1-6.2 7-6.2s7 2.5 7 6.2"/></svg>')


def to_html(text):
    """
    Escape the reply, then hand back only the markdown I want.

    Escaping first means nothing written into a reply can inject HTML into my page.
    """
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", out)

    pieces = []
    for line in out.split("\n"):
        s = line.strip()
        if s[:2] in ("- ", "* ") or s.startswith("• "):
            pieces.append(f'<span class="li">{s[2:].strip()}</span>')
        elif s:
            pieces.append(s + "<br>")
        else:
            pieces.append("<br>")
    return "".join(pieces).removesuffix("<br>")


def bubble(role, text, streaming=False):
    """One chat row, built as a single HTML line so Streamlit can't read it as a code block."""
    body = to_html(text) + ('<span class="caret"></span>' if streaming else "")
    if role == "user":
        return (f'<div class="row me"><div class="bubble me">{body}</div>'
                f'<div class="ava ava-me">{AVA_YOU}</div></div>')
    return (f'<div class="row bot"><div class="ava ava-bot">{AVA_LEAF}</div>'
            f'<div class="bubble bot">{body}</div></div>')


THINKING = (f'<div class="row bot"><div class="ava ava-bot">{AVA_LEAF}</div>'
            f'<div class="bubble bot"><span class="thinking">Nɛpɛm is thinking'
            f'<span class="dots"><span></span><span></span><span></span></span></span></div></div>')

# =============================================================================
# 6. APP
# =============================================================================

# --- header FIRST ------------------------------------------------------------
# This used to sit below the knowledge loading, which meant that on a cold start the
# page was blank cream until every PDF had been parsed. Draw the app, then work.
st.markdown('<div class="hero"><p class="name">Nɛpɛm</p><div class="rule"></div>'
            '<p class="tag">Kɛ́nyāŋ — the language of home</p></div>', unsafe_allow_html=True)

# --- load the knowledge, out loud --------------------------------------------
# Deliberately plain: st.empty() and st.info() have existed forever. st.status() is newer
# and its container doesn't carry .update() on every version — which crashed the whole
# page for me. Boot code is the last place to use a command with a version floor.
signature = kb_signature()
boot = st.empty()
boot.info("Waking Nɛpɛm — reading the knowledge folder. The PDFs are the slow part, "
          "and only on a cold start.")

always_on, chunks, manifest, overflow, vectors, lexicon, troubles = \
    "", [], [], 0, None, None, []
try:
    always_on, chunks, manifest, overflow, troubles = build_corpus(signature)
    lexicon = build_lexicon(signature)
    if USE_EMBEDDINGS and chunks:
        boot.info(f"{len(manifest)} files, {len(chunks):,} passages. Indexing for "
                  f"meaning-based search — first run only.")
        vectors = build_index(signature)
    boot.empty()
except Exception as e:
    # Anything that goes wrong here gets shown, not swallowed. A visible error beats a
    # blank page every time.
    boot.error(f"The knowledge wouldn't load: {type(e).__name__}: {e}")

# The static half of the prompt. It never changes between messages, so OpenAI caches it
# and I pay the reduced rate on everything except this turn's passages.
# --- which context mode is actually live -------------------------------------
corpus_chars = sum(r["chars"] for r in manifest) if manifest else 0
if CONTEXT_MODE == "full":
    full_mode = True
elif CONTEXT_MODE == "retrieve":
    full_mode = False
else:                                    # "auto"
    full_mode = 0 < corpus_chars <= FULL_CONTEXT_CHARS
FULL_TEXT = full_block(signature) if (full_mode and chunks) else ""

STATIC_CONTEXT = SYSTEM_PROMPT + "\n\n" + always_on

# --- sidebar: my own instrument panel ----------------------------------------
with st.sidebar:
    st.markdown("### Knowledge")
    if manifest:
        counts = {}
        for row in manifest:
            counts[row["tier"]] = counts.get(row["tier"], 0) + 1
        total = sum(r["chars"] for r in manifest)
        st.caption(f"{len(manifest)} files · "
                   + " · ".join(f"{n} {t}" for t, n in counts.items())
                   + f" · {total:,} chars, all of it searchable")
        st.caption(f"{len(chunks):,} passages · "
                   + ("semantic search" if vectors is not None else "keyword search"))
        if vectors is not None:
            src = "loaded from index.npz" if os.path.exists(INDEX_FILE) else "built just now"
            st.caption(f"index: {src}")
            if src == "built just now":
                st.caption("Run `python build_index.py` and commit index.npz for instant "
                           "cold starts on Streamlit Cloud.")
        approx = corpus_chars // 4
        if full_mode:
            st.success(f"FULL CONTEXT — the whole corpus (~{approx:,} tokens) goes into "
                       f"every message. No retrieval, nothing left out.")
        else:
            st.info(f"RETRIEVAL MODE — the corpus is ~{approx:,} tokens, over the "
                    f"{FULL_CONTEXT_CHARS // 4:,} ceiling, so passages are searched per "
                    f"question. To send everything instead: move MODEL to a long-context "
                    f"model, then set CONTEXT_MODE = \"full\".")
        if overflow:
            st.warning(f"{overflow:,} passages over the {MAX_CHUNKS:,} ceiling were dropped. "
                       f"Raise MAX_CHUNKS or trim the folder.")
        if USE_EMBEDDINGS and vectors is None and api_key():
            st.warning("The index didn't build, so search fell back to keyword matching.")
        if troubles:
            st.error("These files did not load:\n\n"
                     + "\n\n".join(f"**{t['file']}** — {t['problem']}" for t in troubles))

        # Overlapping files aren't fatal — retrieval drops near-duplicates now — but they
        # cost tokens and make it harder to tell which spelling Nɛpɛm is teaching from.
        wordlists = [r["file"] for r in manifest
                     if any(k in r["file"].lower() for k in ("dictionary", "lexicon"))]
        if len(wordlists) > 2:
            st.warning(f"{len(wordlists)} overlapping word lists loaded: "
                       + ", ".join(wordlists)
                       + ". Duplicate passages are filtered at retrieval, but trimming the "
                         "superseded ones would make the corpus cheaper and clearer.")

        with st.expander("What loaded"):
            for row in manifest:
                tag = " · always in view" if row.get("spine") else ""
                st.markdown(f"`{row['label']}` **{row['file']}** — "
                            f"{row['chars']:,} chars, {row['chunks']} passages{tag}")

        # --- is it actually in my data? -------------------------------------
        # When Nɛpɛm says "I don't have that", there are two possible reasons: the rule
        # isn't in my folder, or search failed to find it. Guessing between those wastes
        # hours. This searches the raw passages directly, no model involved, so I get a
        # yes or no on what I actually own.
        st.markdown("---")
        st.markdown("### Is it in my data?")
        needle = st.text_input("Find text in the corpus", placeholder="mere, báte, bɛkók…")
        if needle:
            where = {r["label"]: r["file"] for r in manifest}
            found_in = [c for c in chunks if needle.lower() in c["text"].lower()]
            if found_in:
                st.success(f"{len(found_in)} passage(s) contain that.")
                for c in found_in[:6]:
                    st.caption(where.get(c["label"], c["label"]))
                    idx = c["text"].lower().find(needle.lower())
                    st.text(c["text"][max(0, idx - 220): idx + 320])
            else:
                st.error("Not anywhere in the corpus. Nɛpɛm genuinely doesn't have this — "
                         "it's a gap in the folder, not a search failure.")
    else:
        st.error(f"No readable files found in ./{KB_ROOT}. Nɛpɛm has nothing to teach from.")
    st.markdown("---")
    if st.button("Start a new conversation"):
        st.session_state.messages = []
        st.session_state.pending = False
        rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = False

# Say this once, up front. A learner who loses twenty minutes without warning doesn't return.
st.markdown('<p class="note">This lesson lives in your browser only. Refreshing the page '
            'starts a fresh one, so keep the tab open while you learn.</p>',
            unsafe_allow_html=True)

st.markdown(bubble("assistant", WELCOME), unsafe_allow_html=True)

# Anything above the marker is on screen but past what Nɛpɛm can see. I draw the line
# rather than let him quietly forget and confuse someone.
horizon = max(0, len(st.session_state.messages) - MAX_HISTORY_TURNS)
for i, m in enumerate(st.session_state.messages):
    if i == horizon and horizon > 0:
        st.markdown('<div class="memmark">Nɛpɛm remembers from here on</div>',
                    unsafe_allow_html=True)
    st.markdown(bubble(m["role"], m["content"]), unsafe_allow_html=True)

# --- starters ----------------------------------------------------------------
starter = None
if not st.session_state.messages:
    c1, c2 = st.columns(2)
    if c1.button("Teach me a greeting"):
        starter = "Teach me a Kenyang greeting."
    if c2.button("Test me"):
        starter = "Test me with a quick Kenyang question."
    c3, c4 = st.columns(2)
    if c3.button("Teach me to count?"):
        starter = "Teach me how to count in Kenyang, starting with one to five.?"
    if c4.button("Start from the beginning"):
        starter = "I'm a complete beginner. Where should we start?"

prompt = st.chat_input("Type in English…") or starter

# Save and rerun straight away, so the learner's bubble and the thinking dots appear
# together instead of after the model finishes.
if prompt and not st.session_state.pending:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending = True
    rerun()

# --- the reply ---------------------------------------------------------------
if st.session_state.pending:
    slot = st.empty()
    slot.markdown(THINKING, unsafe_allow_html=True)

    if not api_key():
        slot.markdown(bubble("assistant", "Add OPENAI_API_KEY to Streamlit Secrets to bring "
                                          "Nɛpɛm to life."), unsafe_allow_html=True)
        st.session_state.pending = False
    else:
        history = st.session_state.messages[-MAX_HISTORY_TURNS:]

        # Search on the learner's question PLUS what Nɛpɛm just said. On its own, a reply
        # like "ok" or "yes" carries nothing to search for — the previous turn is what
        # tells me we're still on greetings.
        last_user = next((m["content"] for m in reversed(history)
                          if m["role"] == "user"), "")
        last_bot = next((m["content"] for m in reversed(history)
                         if m["role"] == "assistant"), "")
        query = (last_user + "\n" + last_bot[:600]).strip()
        # A correction is usually about grammar, so force the grammar probes to fire
        # even when the learner's wording ("the order", "another way") looks nothing
        # like a rule and would never match a concord table on its own.
        if correction_note(last_user):
            query += " word order noun class concord rule"
        # In full mode there is nothing to search for — everything goes. `found` is set
        # to the whole corpus so the attested-word check in lesson_note still works.
        if full_mode and FULL_TEXT:
            found = chunks
            knowledge = FULL_TEXT
        else:
            found = search(query, chunks, vectors, lexicon)
            knowledge = passages_block(found)
        # Keep them so I can audit the answer afterwards. Without this I cannot tell a
        # word that came out of the corpus from one the model invented, and neither can
        # a speaker reviewing Nɛpɛm's Kenyang.
        st.session_state.last_query = query
        st.session_state.last_passages = found
        st.session_state.last_probes = probes_for(query)

        # Two system messages on purpose: the first never changes and gets cached; the
        # second carries this turn's passages, the lesson so far, and the rules — sitting
        # as close to the learner's question as I can put them.
        turn_context = "\n\n".join(x for x in (
            knowledge, lesson_note(history, found),
            correction_note(last_user), RULES_REMINDER) if x)

        api_messages = ([{"role": "system", "content": STATIC_CONTEXT},
                         {"role": "system", "content": turn_context}] + history)

        # GPT-5 and GPT-6 models reject `temperature` outright — the parameter being
        # present is the error, whatever value it holds. So I send it only where it's taken.
        params = dict(model=MODEL, messages=api_messages, stream=True)
        if not MODEL.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
            params["temperature"] = TEMPERATURE

        reply, painted = "", 0
        try:
            stream = OpenAI(api_key=api_key()).chat.completions.create(**params)
            for chunk in stream:
                if not chunk.choices:
                    continue
                piece = chunk.choices[0].delta.content or ""
                if not piece:
                    continue
                reply += piece
                if len(reply) - painted >= STREAM_FLUSH_CHARS:
                    slot.markdown(bubble("assistant", reply, streaming=True),
                                  unsafe_allow_html=True)
                    painted = len(reply)

            if reply.strip():
                slot.markdown(bubble("assistant", reply), unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                # Check the reply against the material it was built from, and say so.
                loose = unsupported_words(reply, found)
                if loose:
                    st.markdown(
                        '<div class="unchecked">Not found in the material behind this '
                        'answer: <b>' + ", ".join(html.escape(w) for w in loose[:12]) +
                        '</b>. These may be spelled differently in my sources — or they '
                        'may not be real Kenyang. Check with a speaker before learning '
                        'them.</div>', unsafe_allow_html=True)
            else:
                slot.markdown(bubble("assistant", "Nothing came back that time. Ask me again."),
                              unsafe_allow_html=True)
        except Exception as e:
            msg = str(e)
            if "context" in msg.lower() or "maximum" in msg.lower():
                # The corpus is bigger than this model's window. Name the real problem.
                msg = (f"the whole corpus (~{corpus_chars // 4:,} tokens) is larger than "
                       f"{MODEL}'s context window. Either set CONTEXT_MODE = \"retrieve\", "
                       f"or move MODEL to a long-context model.")
            slot.markdown(bubble("assistant", f"That message didn't reach me: {msg}"),
                          unsafe_allow_html=True)
        st.session_state.pending = False

# --- audit panel --------------------------------------------------------------
# Written to the sidebar at the very end, so it reflects the answer just given.
# This is the only way to tell whether a Kenyang word came out of my corpus or out of
# the model's imagination. If a word appears in a reply but nowhere in these passages,
# it was invented — and for a language a learner is trying to recover, that matters
# more than any other thing this app does.
if st.session_state.get("last_passages"):
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Check the last answer")
        st.caption("Every Kenyang word in the reply should appear somewhere below. "
                   "If it doesn't, Nɛpɛm invented it.")
        shown = st.session_state.last_passages[:40]
        with st.expander(f"{len(st.session_state.last_passages)} passages used"
                         + (" (showing 40)" if len(st.session_state.last_passages) > 40 else "")):
            st.caption(f"Searched for: {st.session_state.get('last_query', '')[:160]}")
            for c in shown:
                st.markdown(f"**{c['label']}**")
                st.text(c["text"][:900])
                st.markdown("---")