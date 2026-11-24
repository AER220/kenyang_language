"""
Nɛpɛm — a Kenyang (Kɛ́nyāŋ) language tutor.

Built by Agbor Edouard Ransome, from the Manyu Division of Cameroon.

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
import unicodedata
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# ─── FUNCTION CALLING ────────────────────────────────────────────────────────
# tools.py sits beside this file. It gives the model four things it can ASK me to
# do, instead of me guessing what it needs:
#
#   look_up_kenyang    the MODEL picks the search term, not my code
#   is_this_real       checks a word against the whole corpus before it is taught
#   get_grammar_rule   hands back a speaker-verified rule word for word
#   build_verb_forms   assembles a verb by the fixed rule, so the order cannot
#                      come out wrong
#
# The gain that matters most: when a learner types "use it in a sentence", my
# retrieval code has no content words to search on — but the model knows what the
# sentence is about and can say so. Retrieval stops being a guess.
import tools
from settings import secret

# =============================================================================
# 1. CONFIG
# =============================================================================

MODEL = "gpt-4o-mini"               # swap freely; temperature is guarded below
# Back to mini now that retrieval is fixed. If sentence building gets sloppy,
# "gpt-4o" is a one-word change back: mini is weaker at holding several ordering
# rules in mind at once, which is where it failed last time.
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
ALWAYS_ON_CHARS = 125_000    # ceiling for the verified tier, which travels every turn

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
# Pinned to retrieve, not auto. On "auto" the app posts the whole corpus whenever
# it fits under FULL_CONTEXT_CHARS, and 350,000 characters is about 87k tokens —
# which would fit mini's 128k window on paper, then fail the moment the prompt and
# history are added on top. Retrieval is also what the fixes below repair.
CONTEXT_MODE = "retrieve"
FULL_CONTEXT_CHARS = 350_000   # ~87k tokens, the most I'd push into a 128k window

EXACT_RESERVE = 12           # a SLICE held for literal word matches, not the whole
                             # budget. It was 20 against MAX_PASSAGES 20, and the call
                             # site doubled it, so exact matching could take every slot
                             # and the meaning search never ran at all.
MAX_PASSAGES = 40            # retrieval mode: total passages per question, after merging.
                             # Back up from 20 now that the rate limit is lifted. More
                             # passages is the other half of "it does not know what it
                             # has", and on mini the extra tokens cost very little.
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
                  "preposition", "demonstrative", "plural")
SPINE_FILES = set()   # the speaker-verified file now covers word order better than the
                      # orthography guide did — the guide had only the colour half of the
                      # rule. It stays in knowledge_base and is retrieved when relevant.
SPINE_CHARS = 30_000        # total ceiling for the spine, shared across those files.
                             # Raised from 70k: the teaching chapters ARE the point of the
                             # spine now, and they must not be silently truncated away.

st.set_page_config(page_title="Nɛpɛm — Learn Kenyang", page_icon="brand/web-and-social/favicon-32x32.png",
                   layout="centered", initial_sidebar_state="collapsed")

# "Mma ne eta" is unconfirmed: QUESTIONS_for_Ed.md section 20. It stays until Ed
# confirms or replaces it. The rest is plain, and says what he does.
WELCOME = "Mma ne eta, welcome! I am Nɛpɛm. I teach Kenyang, and I say so when I do not know something."
START_HINT = "Tap one of the options below to begin, or type your own question."


def api_key():
    """Environment first (Render), secrets.toml second (my Codespace)."""
    return secret("OPENAI_API_KEY")


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
    verified = []

    for f in files:
        counters[f["tier"]] += 1
        label = f"{f['tier']} source {counters[f['tier']]}"

        pieces = chunk_text(f["text"])
        for piece in pieces:
            chunks.append({"tier": f["tier"], "label": label, "text": piece})

        if f["tier"] == "verified":
            verified.append((f, label))

        # Grammar rides along too — see SPINE_FILES for why.
        if in_spine(f["name"]) and spine_used < SPINE_CHARS:
            seg = f["text"][:SPINE_CHARS - spine_used]
            spine_parts.append(f"\n### {label}\n{seg}")
            spine_used += len(seg)

        manifest.append({"file": f["name"], "label": label, "tier": f["tier"],
                         "chars": len(f["text"]), "chunks": len(pieces),
                         "spine": in_spine(f["name"])})

    # The verified files ride along in full; they're the one thing I never want search to
    # accidentally miss. The grammar goes first, so if the ceiling ever bites it cuts the
    # recorded texts and never the rules. Only this block is reordered: the chunk order
    # above must stay as it is, because index.npz is matched to it row by row.
    rules_last = lambda n: not any(w in n.lower() for w in ("speaker", "rules", "grammar"))
    for f, label in sorted(verified, key=lambda v: rules_last(v[0]["name"])):
        if always_used >= ALWAYS_ON_CHARS:
            break
        seg = f["text"][:ALWAYS_ON_CHARS - always_used]
        always_parts.append(f"\n### {label}\n{seg}")
        always_used += len(seg)

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


def exact_hits(query, chunks, lexicon=None, per_term=3):
    """
    Find passages that literally contain the words asked about.

    This is the guarantee. If "million" is written anywhere in my files, the passage
    holding it goes into context — it cannot be outranked, outvoted or crowded out.
    Embeddings are good at "something like this" and bad at "this exact rare word", which
    is most of what a language tutor is actually asked for.

    Matching is on whole TOKENS now, not substrings, and that single change is the fix
    for "it says it cannot count". The old line was `if t in c["text"].lower()`, so the
    needle "one" matched money, stone, listen and someone, and "1" matched 1998 and 21.
    A counting question produced dozens of false hits, they filled the entire budget,
    and the passage actually holding the numbers never got in. The comment on TOKEN two
    hundred lines above says "one must not match money" — it was true of tokenize and
    never true here.

    Rarest needle first, so a specific word like ɛkɛt spends the budget before a common
    one like count.
    """
    needles = {t for t in expand(terms(query)) if len(t) >= 3 or t.isdigit()}
    if not needles:
        return []

    if lexicon:
        sets, df = lexicon
        picks = []
        for t in sorted(needles, key=lambda w: (df.get(w, 0), -len(w))):
            n = 0
            for i, toks in enumerate(sets):
                if t in toks:
                    picks.append(i)
                    n += 1
                    if n >= per_term:
                        break
        return picks

    # No lexicon: keyword-only fallback. Still whole-word, and the Kenyang letters
    # count as word characters so ɛkɛt is not cut at the ɛ.
    picks = []
    WORDCHAR = r"\wɛɔŋʉɨ"          # \w plus the Kenyang letters
    for t in sorted(needles, key=len, reverse=True):
        pat = re.compile(rf"(?<![{WORDCHAR}]){re.escape(t)}(?![{WORDCHAR}])", re.I)
        n = 0
        for i, c in enumerate(chunks):
            if pat.search(c["text"]):
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
    _merge(exact_hits(query, chunks, lexicon), picked, seen, min(room, EXACT_RESERVE))

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

THE ONE RULE ABOVE ALL THE OTHERS — it is absolute:
- You never write a Kenyang word, spelling or tone mark that is not in the material you were
  given. Not to be friendly, not to keep a conversation going, not because it sounds right.
- Your warmth lives in the English around the Kenyang. It never comes from making up Kenyang.

WHO YOU ARE:
- You are Nɛpɛm, a Kenyang tutor. That is your whole identity.
- You were created by Agbor Edouard Ransome, from the Manyu Division of Cameroon. If a learner asks who made
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
- Appearing in your material does not make a form settled. When a VERIFIED form exists, use it,
  even if another form appears lower down.
- A REFERENCE form has not been checked by a speaker. If it is all you have, you may give it,
  but say plainly that a speaker has not confirmed it yet. Never present it as settled.
- Anything marked [TO CONFIRM], or written as an open question, is unresolved. Do not teach a
  form from inside such a note, and do not state its answer as fact. If it bears on the
  question, say that this point is still waiting on a speaker.
- Being conversational never loosens any of this.
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
  or on one real question that continues the lesson, such as inviting them to reply.
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
- Never describe how a Kenyang word sounds with a made-up respelling ("eh-KET") or a likeness
  to an English word. The only way you show a sound is a speaker's recording, or a note on
  pronunciation written in your material, quoted as it is.
- Check every word you are about to output against the material. If it isn't there, it isn't
  Kenyang as far as you are concerned, however natural it feels.

WORD ORDER — THE RULE A SPEAKER CONFIRMED. THIS OVERRIDES EVERY OTHER SOURCE:
- Kenyang does NOT put every adjective in the same place. It depends on the adjective.
- SIZE, QUALITY and SHAPE come BEFORE the noun:
      Ereme ɛkɛt      big house          (big + house)
      Ereme nsok      big elephant
      Mandu mmú       small dog          (small + dog)
      Mandu mmɔ       small child
      erítí ɛkɛt      beautiful house    (beautiful + house)
      Erehti bhisi    beautiful face
      esaptí enok     long stick
- COLOUR and NUMBER come AFTER the noun:
      ɛkɛt Piór       white house        (house + white)
      beket bépay     two houses         (houses + two)
- A scholarly guide in your material describes this construction using only a COLOUR as
  its example, so it appears to say every adjective follows the noun. That is right for
  colours and numbers and WRONG for size and quality. Where that guide and this rule
  disagree, this rule wins — it came from a native speaker and it is how Kenyang is
  actually spoken.
- So before you build any phrase with an adjective, ask yourself first: is this a size or
  quality word, or a colour or number? That decides which side of the noun it goes.

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

WHEN A LEARNER GREETS YOU:
- Greet them back in Kenyang, using only a greeting confirmed in your material, exactly as it is
  written there:
      Neyi            good morning        (the reply is Neyi nkuo)
      Echina?         how are you?        (the reply is Abekubep, I am fine)
      Nnah            a general greeting, a way of asking how
  Then invite them to reply, in English. Keep it to one greeting.
- If they greet you with one of these, answer with its confirmed reply. Nnah has no confirmed
  reply in your material, so do not make one up. Greet them in English and teach them Neyi or
  Echina? instead.
- If they greet you in English, choose a greeting from the list that fits what they said.
  Do not add words to it.

KEEPING A SHORT EXCHANGE GOING:
- You may end with one short follow-up question in English that keeps the learner speaking:
  "Do you want to try replying?" or "Shall I teach you the answer to that?" This is the kind of
  question you are allowed to end on. A general menu of options is not.
- The follow-up is in English. If it leads to Kenyang, that Kenyang must still come from your
  material.
- When the learner tries a reply, say plainly whether it was right before anything else.

STAYING IN YOUR LANE:
- You only help with learning Kenyang. For genuinely unrelated things, warmly say that's outside
  what you do and offer the next step in the lesson.
- When you're unsure or something is contested, say so and suggest asking a native speaker or
  elder. Honesty is part of who you are. Never fake fluency.
"""


SPEAKERS_MANIFEST = ("https://xkrjlihldrrwyeglszyg.supabase.co"
                     "/storage/v1/object/public/recordings/manifest.json")


@st.cache_resource
def _speakers_last_good():
    """The last list of speakers' recorded words that loaded, shared by every session,
    so a Supabase hiccup does not drop words Nɛpɛm knew a minute ago."""
    return {"words": []}


@st.cache_data(ttl=300, show_spinner=False)
def _speakers_fetch():
    import requests
    from build_audio_manifest import fold
    r = requests.get(SPEAKERS_MANIFEST, timeout=4)
    if r.status_code != 200:
        raise RuntimeError(r.status_code)          # raising means it isn't cached
    good = re.compile(r"^[0-9a-f]{24}\.wav$")
    return [k for k, v in r.json().items()
            if isinstance(v, str) and good.match(v) and k and k == fold(k)]


def speakers_recorded():
    """Words other speakers recorded and Ed approved: the same public list say.js merges.
    Checked at most every five minutes. If Supabase can't be reached, the last list
    that loaded is used, and before any has loaded, none. Ed's own never depend on it."""
    keep = _speakers_last_good()
    try:
        keep["words"] = _speakers_fetch()
    except Exception:
        pass
    return keep["words"]


def recordings_block(path=os.path.join("audio", "manifest.json")):
    """The words a speaker has recorded, so Nɛpɛm can tell a learner which ones to tap.

    The chat's player (say.js on nepem.org) reads this same manifest, which Render deploys
    from the same repo, so a word listed here is a word that is underlined in the reply.
    The keys are written exactly as say.js matches them. Words other speakers recorded
    come after, from the list say.js also reads. Without either there is no list, and
    the rule against describing sounds still stands on its own above."""
    try:
        with open(path, encoding="utf-8") as f:
            words = [k for k in json.load(f) if k.strip()]
    except (OSError, ValueError):
        words = []
    mine = set(words)
    words += [k for k in speakers_recorded() if k not in mine]
    if not words:
        return ""
    return f"""
RECORDINGS — words a speaker has recorded. This list is for knowing what can be heard. It is
not a source of Kenyang: teach a word only from your material, never because it is listed here.
{", ".join(words)}

- NEVER tell a learner they can tap a word, or that a word has a recording. The page adds
  that line itself, under your reply, and only for words that really are recorded. Leave it
  to the page.
- Keep the spelling your material gives. Do not change a word to match this list.
- When a learner asks how a word is said or pronounced: if the word you are teaching is NOT
  on this list, letters and tone marks exactly, say plainly that it isn't recorded yet. If it
  is on the list, just teach it; the page will show them how to hear it. Either way, do not
  try to describe the sound.
"""

def recorded_keys():
    """Every folded word or phrase that has a recording, Ed's and the speakers': the
    same two lists say.js underlines from."""
    try:
        with open(os.path.join("audio", "manifest.json"), encoding="utf-8") as f:
            keys = {k for k in json.load(f) if k.strip()}
    except (OSError, ValueError):
        keys = set()
    return keys | set(speakers_recorded())


_APOS = "'’‘ʼʻ"


def _word_spans(text):
    """Where the words are, the way say.js finds them: letters, tone marks (category M,
    which \\w misses), apostrophes, and hyphens inside a word as in ekeré-ékáti."""
    isw = lambda c: unicodedata.category(c)[0] in "LM" or c in _APOS
    spans, i, n = [], 0, len(text)
    while i < n:
        if not isw(text[i]):
            i += 1
            continue
        j = i
        while j < n and (isw(text[j]) or (text[j] == "-" and j + 1 < n and isw(text[j + 1])
                                           and j > i)):
            j += 1
        spans.append((i, j))
        i = j
    return spans


def recorded_in(text, keys):
    """The recorded words in a reply, as they are written there, longest match first,
    each once. A phrase only spans plain spaces, as in say.js, so this names exactly
    what the page will underline."""
    from build_audio_manifest import fold
    if not keys:
        return []
    longest = max(len(k.split(" ")) for k in keys)
    toks, out, seen, i = _word_spans(text), [], set(), 0
    while i < len(toks):
        for n in range(min(longest, len(toks) - i), 0, -1):
            j = i + n - 1
            if any(text[toks[x][1]:toks[x + 1][0]].strip() for x in range(i, j)):
                continue
            raw = text[toks[i][0]:toks[j][1]]
            key = fold(raw)
            if key not in keys:
                key = key.strip("'")
            if key in keys:
                if key not in seen:
                    seen.add(key)
                    out.append(raw if fold(raw) == key else raw.strip("'"))
                i = j
                break
        i += 1
    return out


_TAP_CLAIM = re.compile(r"\btap(?:s|ped|ping)?\b", re.IGNORECASE)


def drop_tap_claims(reply):
    """Take out any sentence of the model's that talks about tapping. Whether a word can
    be tapped is the page's to say, in hear_line(); the model is told not to, and once
    said it of a word that had no recording. Removing the sentence makes the claim
    impossible rather than merely discouraged. Line breaks are kept."""
    if not _TAP_CLAIM.search(reply):
        return reply
    lines = []
    for line in reply.split("\n"):
        parts = re.split(r"(?<=[.!?])\s+", line)
        kept = [p for p in parts if not _TAP_CLAIM.search(p)]
        if kept or not line.strip():
            lines.append(" ".join(kept))
    return "\n".join(lines).strip()


def hear_line(words):
    """The one line under a reply that says what can be heard. Written by code, never by
    the model, so it is never wrong about which words are recorded."""
    if not words:
        return ""
    if len(words) == 1:
        return f"Tap {words[0]} to hear it said."
    if len(words) <= 3:
        return f"Tap {', '.join(words[:-1])} or {words[-1]} to hear them said."
    return "Tap any underlined word to hear it said."


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
6. ADJECTIVE ORDER, every time you build a phrase:
      size / quality / shape  ->  BEFORE the noun    (Ereme ɛkɛt = big house)
      colour / number         ->  AFTER the noun     (ɛkɛt Piór = white house)
   Decide which kind of word it is FIRST, then place it. A guide in your material shows
   only the colour case; a native speaker confirmed both. The speaker wins.
Answer in English. Say the thing, show the parts, then stop. No recap of what you just
said — the learner can still see it. No "feel free to ask", no closing question except one
short invitation to reply or try the Kenyang. No "great job" or "keep practising". Warmth lives in how you
correct someone, not in exclamation marks.
"""

# ─── TELLING THE MODEL THE TOOLS ARE THERE ───────────────────────────────────
# Defining tools is not enough. A model will cheerfully ignore them and answer
# from memory, which is the exact behaviour I am trying to stop. These lines say
# plainly WHEN to call each one, and they are appended to the REMINDER rather
# than the static prompt because the reminder sits closest to the learner's
# question — and instructions placed there are followed noticeably better.
RULES_REMINDER = RULES_REMINDER + tools.TOOL_INSTRUCTIONS

# --- what has been taught so far ---------------------------------------------
# Kenyang words carry marks English words don't: ɛ ɔ ŋ ʉ ɨ, tone accents, or the
# apostrophe in forms like O'chi. That's enough to spot them without another API call.
# Tone marks are combining characters, which \w does not match: without \u0300-\u036f
# in the class, Bɛ́pay is read as Bɛ and an invented word with a tone mark slips through.
KENYANG_WORD = re.compile(r"[\w'’\u0300-\u036f]*[ɛɔŋƐƆŊʉɨáàâāéèêēíìîīóòôōúùûūǎǐǒǔ\u0300-\u036f]"
                          r"[\w'’\u0300-\u036f]*", re.UNICODE)
APOSTROPHE_WORD = re.compile(r"\b[A-Za-z]{1,6}['’][A-Za-z]{2,}\b")
ENGLISH_TAILS = {"s", "t", "re", "ve", "ll", "d", "m"}   # don't, it's, you're, we'll…


def kenyang_tokens(text):
    """Pull the Kenyang-looking words out of a piece of text, in order, deduped."""
    text = unicodedata.normalize("NFC", text)
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


def material(found, always_on=""):
    """The text behind an answer, folded for matching: the passages found plus the
    verified block that travels with every answer, NFC, single-spaced, lowercase."""
    text = " ".join([always_on] + [c["text"] for c in found or []])
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).lower()


def unsupported_words(reply, found, always_on=""):
    """
    Which Kenyang words in this reply appear nowhere in the material behind it.

    This is the fabrication detector. It can't prove a word is wrong — the material uses
    more than one spelling convention, so a real word may be written differently here —
    but a word that appears in NO passage was not read out of my files. It was produced.
    Given that people are using this to recover their mother tongue, they should be told.

    The verified block travels with every answer, so it counts as material behind it too.
    """
    if not found and not always_on:
        return []
    corpus = material(found, always_on)
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


def lesson_note(messages, found=None, always_on=""):
    """
    A briefing so he builds on the lesson instead of restarting it.

    This had a nasty bug. taught_so_far() scrapes Kenyang-looking words out of Nɛpɛm's OWN
    previous replies — so anything he invented got handed back to him next turn as
    established lesson content, and the mistake compounded inside a single session. Now a
    word only counts as taught if it actually appears in the passages retrieved or the
    verified block. Inventions don't survive the next turn.
    """
    words = taught_so_far(messages)
    if found or always_on:
        corpus = material(found, always_on)
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
# ɛ ɔ ŋ ʉ ɨ and stacked tone marks. The phone's own font handles the UI (no second
# download) and falls back to Gentium for any glyph it lacks — that fallback is why tone
# marks never render as boxes on a phone.

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gentium+Book+Plus:wght@400;700&display=swap');

/* I hide Streamlit's chrome, but NOT the status widget. That little "Running" marker is
   the only sign the app is alive while the knowledge loads, and hiding it turned a slow
   startup into what looked like a dead page. */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
.stDeployButton, [data-testid="stAppDeployButton"]{display:none !important;}
header[data-testid="stHeader"]{background:transparent;}

:root{
  /* the same palette as nepem.org, light theme: the brand's off-white, the logo
     green for everything structural, ink text, and the logo orange only for
     sound. --forest and --leaf are kept as names so nothing below breaks; both
     are the logo green now. */
  --paper:#FAF9F6;
  --forest:#135C3C;
  --leaf:#135C3C;
  --ink:#15201B;
  --mute:#56665E;
  --edge:rgba(19,92,60,.18);
  --sound:#9A5D1D;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Gentium Book Plus",sans-serif;
}

/* English in the phone's own font, as on nepem.org. One font for replies: a
   reply cannot say which of its words are Kenyang, and Gentium on some of them
   would be worse than on none. */
html, body, [data-testid="stAppViewContainer"] *{
  font-family:var(--sans);
}
/* The whole app is designed light — cream page, dark text. Declaring the colour scheme
   explicitly stops iOS Safari's dark mode from inverting bubbles, text or inputs on a
   phone, which is what made the typed text invisible. */
html{color-scheme: light;}
[data-testid="stAppViewContainer"]{background:var(--paper); color-scheme: light;}
.block-container{max-width:680px;padding-top:.6rem;padding-bottom:7rem;}

/* the header: the same heart-and-leaf and NƐPƐM wordmark as nepem.org, on the
   page, with one quiet line under it. No card, no gradient, no gold rule. */
.hero{display:flex;flex-direction:column;gap:8px;margin:6px 0 20px;}
.hero .lock{display:flex;align-items:center;gap:10px;}
.hero .mark{height:34px;width:auto;flex:none;}
.hero .mk-heart{fill:var(--forest);} .hero .mk-leaf{fill:#DC9246;}
.hero .wordmark{height:24px;width:auto;color:var(--forest);}
.hero .means{margin:0;color:var(--mute);font-size:.95rem;}
[data-testid="stAppViewContainer"] .hero .means .ken{font-family:'Gentium Book Plus',Georgia,serif;
  font-size:1.08em;color:var(--ink);}

.row{display:flex;align-items:flex-end;gap:9px;margin:12px 0;}
.row.me{flex-direction:row-reverse;}
.ava{flex:0 0 30px;width:30px;height:30px;border-radius:50%;display:flex;
  align-items:center;justify-content:center;margin-bottom:2px;}
.ava svg{width:17px;height:17px;}
.ava-bot{background:var(--forest);color:#FAF9F6;}
.ava-me{background:rgba(19,92,60,.07);color:var(--forest);border:1px solid var(--edge);}

.bubble{max-width:78%;padding:11px 15px;font-size:1.02rem;line-height:1.62;
  word-wrap:break-word;overflow-wrap:anywhere;}
.bubble.bot{background:#FFFFFF;color:var(--ink);border:1px solid var(--edge);
  border-radius:16px 16px 16px 4px;}
.bubble.me{background:var(--forest);color:#F1FBF6;border-radius:16px 16px 4px 16px;}
/* the line the code adds when a reply has recorded words in it */
.bubble .hear{display:block;margin-top:8px;font-size:.92em;color:var(--leaf);}
.bubble .li{display:block;padding-left:15px;text-indent:-15px;margin:3px 0;}
.bubble .li:before{content:"•";color:var(--leaf);padding-right:8px;}
.bubble.me .li:before{color:#8FD4B4;}
.bubble code{background:rgba(19,92,60,.09);padding:1px 5px;border-radius:5px;font-size:.95em;}

.thinking{display:flex;align-items:center;gap:8px;color:var(--mute);font-size:.95rem;}
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

.note{color:var(--mute);font-size:.84rem;margin:-8px 2px 14px;line-height:1.45;}
/* The fabrication flag: a word in the answer that is in none of the material it
   was built from. It is one of the two accuracy claims made visible, so it must
   never be quiet. It was amber, which now means sound, so it carries its weight
   by shape instead: a full ink border, a heavy rule down the side, and a drawn
   "!", on white like Nɛpɛm's own bubbles. Solid lines only: dotted and dashed
   mean "tap to hear" on this site, and the flag must not borrow that. */
.unchecked{margin:-6px 0 14px 39px;padding:10px 13px 10px 14px;
  border-radius:4px 10px 10px 4px;background:#FFFFFF;border:2px solid var(--ink);
  border-left-width:5px;color:var(--ink);font-size:.9rem;line-height:1.5;max-width:78%;
  display:flex;gap:10px;align-items:flex-start;}
.unchecked b{font-weight:700;color:var(--ink);}
.unchecked .mk{flex:none;width:20px;height:20px;border-radius:50%;background:var(--ink);
  color:#FFFFFF;font:700 13px/20px system-ui,sans-serif;text-align:center;margin-top:1px;}
.memmark{display:flex;align-items:center;gap:10px;margin:20px 2px 16px;
  color:var(--mute);font-size:.8rem;}
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

/* iOS Safari applies its own dark-mode colours to form fields, and it does so at a level
   that beat my textarea rule — so on an iPhone the typed text came out dark on a dark
   field and vanished. Three fixes together: force the dark ink colour on every element
   inside the input (not just the textarea), tell the browser this control is light-scheme
   so iOS stops recolouring it, and disable the -webkit text-fill that iOS uses to override
   `color` on inputs. */
[data-testid="stChatInput"]{
  background:#FFFFFF !important;
  border:1.5px solid #D6E3DA !important;
  border-radius:26px !important;
  box-shadow:0 2px 10px rgba(19,92,60,.06);
  transition:border-color .15s ease, box-shadow .15s ease;
  color-scheme: light;                 /* stop iOS painting this control dark */
}
[data-testid="stChatInput"]:focus-within{
  border-color:var(--leaf) !important;
  box-shadow:0 2px 14px rgba(19,92,60,.16);
}
/* Force typed text dark, wherever Streamlit puts the box. The narrow selector
   [data-testid="stChatInput"] textarea stopped matching on newer Streamlit, so this
   targets the textarea AND text inputs app-wide, plus the bottom container by name.
   Belt and braces on purpose — invisible input text is a total blocker on a phone. */
/* THE ONE THAT MATTERS: this Streamlit version names the box stChatInputTextArea (one
   word). Every earlier rule used "stChatInput textarea" with a space — a different
   selector that never matched, which is why the text stayed invisible. This hits it. */
textarea[data-testid="stChatInputTextArea"]{
  color:#15201B !important;
  -webkit-text-fill-color:#15201B !important;
  caret-color:#135C3C !important;
  font-size:16px !important;
  opacity:1 !important;
  background:transparent !important;
}
textarea[data-testid="stChatInputTextArea"]::placeholder{
  color:#9AAAA1 !important;
  -webkit-text-fill-color:#9AAAA1 !important;
}

textarea,
input[type="text"],
[data-testid="stChatInput"] textarea,
[data-baseweb="textarea"] textarea,
[data-baseweb="input"] input,
.stChatInput textarea,
[data-testid="stBottomBlockContainer"] textarea{
  color:#15201B !important;
  -webkit-text-fill-color:#15201B !important;
  caret-color:#135C3C !important;
  opacity:1 !important;
}
textarea::placeholder,
[data-testid="stChatInput"] textarea::placeholder{
  color:#9AAAA1 !important;
  -webkit-text-fill-color:#9AAAA1 !important;
}

[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] textarea *,
[data-testid="stChatInput"] input{
  font-size:16px !important;
  color:#15201B !important;            /* dark ink, spelled out so it can't be themed away */
  -webkit-text-fill-color:#15201B !important;   /* iOS overrides `color` with this; pin it */
  background:transparent !important;
  caret-color:#135C3C !important;      /* the blinking cursor, so it's visible too */
  opacity:1 !important;
}
[data-testid="stChatInput"] textarea::placeholder{
  color:#9AAAA1 !important;
  -webkit-text-fill-color:#9AAAA1 !important;
}
/* the send arrow. Empty, it is a green arrow on a pale button. Once something is typed,
   Streamlit fills the button with the theme green, so the arrow must turn white there,
   or it is green on green and the button reads as a solid block. */
[data-testid="stChatInput"] button{color:var(--leaf) !important;}
[data-testid="stChatInput"] button:disabled:hover{
  background:rgba(19,92,60,.10) !important;border-radius:50% !important;}
[data-testid="stChatInput"] button:not(:disabled){
  background:var(--leaf) !important;color:#FFFFFF !important;border-radius:50% !important;}
[data-testid="stChatInput"] button:not(:disabled) svg{fill:#FFFFFF !important;color:#FFFFFF !important;}
[data-testid="stChatInput"] button:not(:disabled):hover{background:var(--forest) !important;}

@media (max-width:640px){
  .block-container{padding-left:.75rem;padding-right:.75rem;}
  .hero .name{font-size:1.8rem;}
  .bubble{max-width:85%;font-size:1rem;}
}

/* Tap to hear, as on nepem.org: the sound orange, dotted, on a recorded word. */
::highlight(nepem-say){text-decoration:underline dotted var(--sound);
  text-decoration-thickness:2px;text-underline-offset:4px}
@media (pointer:coarse){ ::highlight(nepem-say){text-decoration-thickness:3px} }
/* the empty frame that loads it takes no room */
[data-testid="stElementContainer"]:has(iframe[srcdoc*="nepem-say"]){display:none !important;}
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


def bubble(role, text, streaming=False, hear=""):
    """One chat row, built as a single HTML line so Streamlit can't read it as a code block.
    `hear` is the line saying which words can be heard, written by hear_line(), not by
    the model; it sits inside the bubble, so its words are tappable too."""
    body = to_html(text) + ('<span class="caret"></span>' if streaming else "")
    if hear:
        body += f'<span class="hear">{html.escape(hear)}</span>'
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

# --- tap to hear --------------------------------------------------------------
# The player is say.js on nepem.org, the same file the main page runs, with the audio
# beside it. Streamlit won't run a script in st.markdown, so this empty frame (same
# origin as the page) adds say.js to the page itself, once. It marks words in my
# replies only. If nepem.org or the manifest can't be reached, nothing switches on.
components.html("""<script>
const doc = window.parent.document;
if (!doc.getElementById("nepem-say")) {
  const s = doc.createElement("script");
  s.id = "nepem-say";
  s.src = "https://nepem.org/say.js";
  s.dataset.base = "https://nepem.org/audio/";
  s.dataset.scope = ".bubble.bot";
  doc.head.appendChild(s);
}
</script>""", height=0)

# --- header FIRST ------------------------------------------------------------
# This used to sit below the knowledge loading, which meant that on a cold start the
# page was blank cream until every PDF had been parsed. Draw the app, then work.
st.markdown('<div class="hero"><div class="lock"><svg class="mark" viewBox="22 24 274 289" aria-hidden="true"><path class="mk-heart" fill-rule="evenodd" d="M 158.71,311.45 L 158.29,311.27 L 157.06,310.45 L 155.02,308.98 L 152.17,306.86 L 148.50,304.11 L 143.50,300.28 L 137.17,295.38 L 129.50,289.41 L 120.50,282.37 L 112.36,275.89 L 105.08,269.98 L 98.66,264.63 L 93.11,259.85 L 87.93,255.28 L 83.14,250.92 L 78.73,246.78 L 74.71,242.86 L 70.94,239.09 L 67.42,235.48 L 64.17,232.04 L 61.17,228.75 L 58.23,225.40 L 55.37,221.98 L 52.57,218.51 L 49.84,214.97 L 47.23,211.40 L 44.73,207.80 L 42.34,204.17 L 40.07,200.51 L 37.94,196.83 L 35.93,193.12 L 34.06,189.39 L 32.32,185.63 L 30.76,181.92 L 29.39,178.25 L 28.19,174.62 L 27.18,171.04 L 26.36,167.96 L 25.72,165.38 L 25.27,163.29 L 25.02,161.71 L 24.78,159.90 L 24.57,157.85 L 24.39,155.58 L 24.22,153.08 L 24.15,150.48 L 24.16,147.77 L 24.26,144.96 L 24.45,142.04 L 24.70,139.27 L 25.04,136.65 L 25.44,134.17 L 25.92,131.83 L 26.40,129.69 L 26.90,127.73 L 27.40,125.96 L 27.92,124.38 L 28.49,122.75 L 29.14,121.08 L 29.84,119.38 L 30.61,117.62 L 31.45,115.88 L 32.33,114.12 L 33.28,112.38 L 34.29,110.62 L 35.60,108.62 L 37.22,106.38 L 39.15,103.88 L 41.38,101.12 L 43.49,98.67 L 45.47,96.52 L 47.33,94.67 L 49.06,93.11 L 50.62,91.77 L 51.98,90.64 L 53.17,89.72 L 54.17,89.02 L 55.35,88.23 L 56.73,87.36 L 58.29,86.42 L 60.04,85.39 L 61.77,84.43 L 63.48,83.54 L 65.17,82.72 L 66.83,81.97 L 68.48,81.27 L 70.10,80.64 L 71.71,80.07 L 73.29,79.55 L 75.00,79.05 L 76.83,78.57 L 78.79,78.10 L 80.88,77.65 L 83.19,77.27 L 85.73,76.96 L 88.50,76.71 L 91.50,76.54 L 94.25,76.44 L 96.75,76.42 L 99.00,76.47 L 101.00,76.60 L 102.88,76.76 L 104.62,76.96 L 106.25,77.19 L 107.75,77.45 L 109.31,77.77 L 110.94,78.15 L 112.62,78.58 L 114.38,79.07 L 116.15,79.62 L 117.94,80.25 L 119.75,80.95 L 121.58,81.72 L 123.77,82.79 L 126.31,84.17 L 129.21,85.84 L 132.46,87.82 L 135.52,89.88 L 138.40,92.01 L 141.08,94.22 L 143.58,96.51 L 145.96,98.88 L 148.22,101.32 L 150.35,103.84 L 152.37,106.44 L 154.48,109.46 L 156.69,112.91 L 158.99,116.79 L 161.40,121.10 L 163.80,123.66 L 166.21,124.46 L 168.62,123.51 L 171.04,120.81 L 173.29,118.36 L 175.38,116.15 L 177.29,114.19 L 179.04,112.47 L 181.25,110.49 L 183.92,108.25 L 187.04,105.75 L 190.62,102.99 L 193.94,100.54 L 196.98,98.40 L 199.75,96.58 L 202.25,95.08 L 204.77,93.64 L 207.31,92.26 L 209.88,90.95 L 212.46,89.70 L 215.06,88.51 L 217.69,87.39 L 220.33,86.34 L 223.00,85.35 L 225.36,84.54 L 227.40,83.89 L 229.13,83.42 L 230.55,83.12 L 231.62,82.93 L 232.32,82.87 L 232.66,82.92 L 232.65,83.08 L 231.67,83.88 L 229.72,85.29 L 226.82,87.33 L 222.94,90.00 L 219.45,92.50 L 216.33,94.83 L 213.60,97.00 L 211.24,99.00 L 208.80,101.19 L 206.26,103.56 L 203.64,106.12 L 200.92,108.88 L 198.45,111.44 L 196.24,113.82 L 194.28,116.01 L 192.57,118.02 L 190.78,120.23 L 188.91,122.65 L 186.97,125.27 L 184.96,128.10 L 183.01,130.96 L 181.12,133.88 L 179.31,136.83 L 177.56,139.83 L 175.87,142.92 L 174.24,146.08 L 172.67,149.33 L 171.15,152.67 L 169.76,155.90 L 168.50,159.02 L 167.36,162.04 L 166.35,164.96 L 165.47,167.65 L 164.72,170.10 L 164.10,172.33 L 163.60,174.33 L 163.09,176.65 L 162.57,179.27 L 162.05,182.21 L 161.52,185.46 L 161.07,188.71 L 160.72,191.96 L 160.45,195.21 L 160.27,198.46 L 160.20,201.83 L 160.23,205.33 L 160.35,208.96 L 160.58,212.71 L 160.88,216.29 L 161.24,219.71 L 161.66,222.96 L 162.14,226.04 L 162.75,229.29 L 163.50,232.71 L 164.37,236.29 L 165.37,240.04 L 166.49,243.85 L 167.75,247.73 L 169.12,251.67 L 170.63,255.67 L 172.02,259.20 L 173.28,262.28 L 174.43,264.90 L 175.46,267.05 L 176.49,268.50 L 177.54,269.25 L 178.59,269.30 L 179.65,268.65 L 181.39,267.41 L 183.81,265.59 L 186.90,263.19 L 190.67,260.20 L 195.23,256.46 L 200.58,251.96 L 206.71,246.70 L 213.64,240.69 L 219.85,235.14 L 225.35,230.04 L 230.14,225.41 L 234.21,221.25 L 237.97,217.29 L 241.39,213.54 L 244.49,210.00 L 247.27,206.66 L 250.03,203.10 L 252.79,199.31 L 255.54,195.29 L 258.28,191.04 L 260.59,187.33 L 262.47,184.17 L 263.91,181.54 L 264.93,179.46 L 265.87,177.40 L 266.75,175.35 L 267.57,173.33 L 268.31,171.33 L 268.99,169.33 L 269.61,167.33 L 270.16,165.33 L 270.65,163.33 L 271.08,161.36 L 271.44,159.42 L 271.74,157.51 L 271.98,155.63 L 272.12,153.24 L 272.17,150.32 L 272.12,146.88 L 271.99,142.93 L 272.36,139.42 L 273.26,136.36 L 274.66,133.75 L 276.59,131.58 L 278.50,129.24 L 280.41,126.73 L 282.30,124.04 L 284.18,121.18 L 285.64,119.06 L 286.68,117.68 L 287.29,117.05 L 287.49,117.16 L 287.74,117.48 L 288.05,117.99 L 288.42,118.71 L 288.84,119.62 L 289.35,120.98 L 289.94,122.77 L 290.62,125.00 L 291.39,127.67 L 292.08,130.52 L 292.68,133.56 L 293.19,136.79 L 293.62,140.21 L 293.91,143.65 L 294.05,147.10 L 294.04,150.58 L 293.89,154.08 L 293.71,157.10 L 293.50,159.65 L 293.26,161.71 L 292.99,163.29 L 292.59,165.19 L 292.07,167.40 L 291.43,169.92 L 290.65,172.75 L 289.83,175.50 L 288.95,178.17 L 288.01,180.75 L 287.02,183.25 L 285.90,185.85 L 284.66,188.56 L 283.29,191.38 L 281.79,194.29 L 280.29,197.08 L 278.77,199.75 L 277.25,202.29 L 275.71,204.71 L 273.56,207.79 L 270.80,211.54 L 267.42,215.96 L 263.42,221.04 L 259.56,225.74 L 255.84,230.07 L 252.26,234.01 L 248.82,237.57 L 245.60,240.84 L 242.59,243.84 L 239.79,246.57 L 237.20,249.01 L 233.64,252.22 L 229.10,256.21 L 223.58,260.96 L 217.08,266.50 L 209.21,272.95 L 199.96,280.34 L 189.33,288.64 L 177.33,297.87 L 168.23,304.75 L 162.02,309.28 Z M 147.41,269.38 L 145.96,264.29 L 144.69,259.65 L 143.59,255.44 L 142.67,251.67 L 141.92,248.33 L 141.23,245.00 L 140.60,241.67 L 140.03,238.33 L 139.52,235.00 L 139.07,231.65 L 138.69,228.27 L 138.37,224.88 L 138.12,221.46 L 137.98,217.54 L 137.98,213.12 L 138.09,208.21 L 138.32,202.79 L 138.64,197.88 L 139.02,193.46 L 139.48,189.54 L 140.02,186.12 L 140.67,182.65 L 141.43,179.10 L 142.31,175.50 L 143.30,171.83 L 144.41,168.15 L 145.63,164.44 L 146.98,160.71 L 148.43,156.96 L 149.32,153.52 L 149.64,150.40 L 149.39,147.59 L 148.57,145.10 L 147.58,142.45 L 146.41,139.64 L 145.08,136.67 L 143.58,133.55 L 142.02,130.54 L 140.40,127.66 L 138.71,124.89 L 136.96,122.25 L 135.15,119.75 L 133.27,117.39 L 131.33,115.17 L 129.33,113.10 L 127.29,111.18 L 125.21,109.39 L 123.08,107.75 L 120.92,106.25 L 118.71,104.87 L 116.46,103.62 L 114.17,102.49 L 111.83,101.48 L 109.31,100.60 L 106.60,99.85 L 103.71,99.23 L 100.62,98.74 L 97.61,98.43 L 94.65,98.31 L 91.77,98.38 L 88.94,98.63 L 86.26,98.99 L 83.72,99.48 L 81.32,100.09 L 79.06,100.81 L 76.80,101.67 L 74.54,102.66 L 72.29,103.79 L 70.04,105.05 L 67.92,106.38 L 65.94,107.77 L 64.09,109.22 L 62.37,110.73 L 60.64,112.45 L 58.90,114.37 L 57.16,116.50 L 55.40,118.83 L 53.83,121.12 L 52.44,123.38 L 51.25,125.58 L 50.24,127.75 L 49.35,129.83 L 48.60,131.83 L 47.97,133.75 L 47.47,135.58 L 47.04,137.77 L 46.67,140.31 L 46.37,143.21 L 46.13,146.46 L 46.07,149.73 L 46.21,153.02 L 46.54,156.33 L 47.05,159.67 L 47.69,162.90 L 48.45,166.02 L 49.33,169.04 L 50.33,171.96 L 51.47,174.90 L 52.72,177.85 L 54.11,180.83 L 55.62,183.83 L 57.25,186.83 L 59.00,189.83 L 60.85,192.83 L 62.82,195.83 L 64.87,198.79 L 67.00,201.71 L 69.19,204.58 L 71.47,207.42 L 73.99,210.42 L 76.75,213.58 L 79.76,216.92 L 83.02,220.42 L 86.47,223.98 L 90.10,227.60 L 93.92,231.29 L 97.93,235.04 L 101.81,238.60 L 105.56,241.98 L 109.18,245.17 L 112.68,248.17 L 117.12,251.86 L 122.50,256.23 L 128.82,261.30 L 136.09,267.06 L 141.67,271.47 L 145.56,274.53 L 147.75,276.24 L 148.25,276.60 L 148.66,276.86 L 148.98,277.02 L 149.21,277.09 L 149.36,277.05 L 149.10,275.76 L 148.45,273.20 Z"/><path class="mk-leaf" fill-rule="evenodd" d="M 200.79,151.67 L 197.54,151.67 L 194.90,151.65 L 192.85,151.60 L 191.42,151.53 L 190.58,151.44 L 189.84,151.31 L 189.18,151.14 L 188.60,150.94 L 188.11,150.70 L 189.14,150.08 L 191.68,149.10 L 195.74,147.75 L 201.31,146.04 L 206.28,144.37 L 210.65,142.77 L 214.42,141.22 L 217.58,139.73 L 220.71,138.11 L 223.79,136.36 L 226.83,134.48 L 229.83,132.47 L 232.77,130.33 L 235.63,128.06 L 238.44,125.66 L 241.17,123.13 L 243.73,120.56 L 246.10,117.95 L 248.30,115.30 L 250.31,112.62 L 252.33,109.63 L 254.34,106.33 L 256.36,102.74 L 258.37,98.84 L 260.14,95.17 L 261.64,91.72 L 262.89,88.50 L 263.88,85.50 L 264.75,82.67 L 265.49,80.00 L 266.11,77.50 L 266.60,75.16 L 267.08,72.43 L 267.55,69.30 L 268.00,65.78 L 268.45,61.87 L 268.72,58.88 L 268.80,56.81 L 268.70,55.65 L 268.42,55.42 L 267.21,55.46 L 265.07,55.76 L 262.00,56.33 L 258.00,57.17 L 253.19,58.02 L 247.56,58.87 L 241.12,59.72 L 233.88,60.58 L 227.88,61.36 L 223.12,62.05 L 219.62,62.66 L 217.38,63.18 L 215.00,63.82 L 212.50,64.59 L 209.88,65.47 L 207.12,66.48 L 204.50,67.55 L 202.00,68.67 L 199.62,69.85 L 197.38,71.08 L 195.09,72.45 L 192.77,73.95 L 190.41,75.58 L 188.01,77.35 L 185.69,79.22 L 183.44,81.20 L 181.26,83.29 L 179.16,85.48 L 177.04,87.90 L 174.90,90.55 L 172.75,93.43 L 170.58,96.53 L 168.88,98.88 L 167.62,100.48 L 166.83,101.31 L 166.50,101.39 L 166.29,101.10 L 166.21,100.45 L 166.26,99.44 L 166.44,98.06 L 166.76,96.43 L 167.23,94.53 L 167.84,92.38 L 168.61,89.96 L 169.69,87.21 L 171.07,84.12 L 172.77,80.71 L 174.79,76.96 L 176.67,73.67 L 178.43,70.83 L 180.07,68.46 L 181.58,66.54 L 183.26,64.61 L 185.12,62.65 L 187.15,60.68 L 189.36,58.69 L 191.57,56.83 L 193.80,55.10 L 196.04,53.51 L 198.29,52.04 L 200.52,50.68 L 202.73,49.44 L 204.92,48.31 L 207.08,47.29 L 209.52,46.27 L 212.23,45.25 L 215.21,44.24 L 218.46,43.22 L 223.31,42.05 L 229.77,40.73 L 237.83,39.26 L 247.50,37.64 L 255.54,36.17 L 261.96,34.86 L 266.75,33.70 L 269.92,32.70 L 273.21,31.53 L 276.62,30.20 L 280.17,28.70 L 283.83,27.04 L 286.66,26.18 L 288.64,26.12 L 289.79,26.85 L 290.09,28.38 L 290.34,30.42 L 290.55,32.97 L 290.71,36.04 L 290.83,39.62 L 290.89,43.08 L 290.89,46.42 L 290.83,49.62 L 290.72,52.71 L 290.51,56.00 L 290.20,59.50 L 289.80,63.21 L 289.31,67.12 L 288.74,70.90 L 288.11,74.52 L 287.40,78.00 L 286.63,81.33 L 285.80,84.54 L 284.93,87.62 L 284.00,90.58 L 283.02,93.42 L 282.04,96.10 L 281.04,98.65 L 280.03,101.04 L 279.00,103.29 L 277.93,105.50 L 276.81,107.67 L 275.64,109.79 L 274.42,111.88 L 273.13,113.92 L 271.78,115.92 L 270.37,117.88 L 268.89,119.80 L 267.30,121.74 L 265.59,123.69 L 263.78,125.67 L 261.85,127.67 L 260.04,129.48 L 258.33,131.10 L 256.73,132.54 L 255.24,133.78 L 253.63,135.03 L 251.90,136.28 L 250.05,137.53 L 248.08,138.79 L 246.22,139.91 L 244.47,140.91 L 242.83,141.77 L 241.30,142.51 L 239.46,143.31 L 237.32,144.18 L 234.88,145.13 L 232.12,146.14 L 229.25,147.08 L 226.25,147.95 L 223.12,148.75 L 219.88,149.48 L 216.85,150.09 L 214.06,150.59 L 211.50,150.98 L 209.17,151.26 L 206.60,151.46 L 203.81,151.60 Z"/></svg><svg class="wordmark" viewBox="355 101 609 134" role="img" aria-label="Nɛpɛm"><path fill="currentColor" fill-rule="evenodd" d="M 537.83,230.70 L 535.50,230.72 L 533.17,230.67 L 530.83,230.55 L 528.50,230.36 L 526.17,230.11 L 523.71,229.74 L 521.12,229.24 L 518.42,228.63 L 515.58,227.89 L 512.92,227.08 L 510.42,226.21 L 508.08,225.27 L 505.92,224.27 L 503.88,223.21 L 501.96,222.09 L 500.17,220.91 L 498.50,219.68 L 496.94,218.38 L 495.48,217.02 L 494.12,215.60 L 492.88,214.12 L 491.75,212.65 L 490.75,211.19 L 489.88,209.74 L 489.12,208.30 L 488.44,206.67 L 487.82,204.85 L 487.27,202.84 L 486.79,200.64 L 486.42,198.67 L 486.17,196.95 L 486.03,195.46 L 486.02,194.21 L 486.07,192.90 L 486.18,191.52 L 486.37,190.09 L 486.62,188.59 L 487.00,187.01 L 487.52,185.34 L 488.16,183.59 L 488.94,181.76 L 489.70,180.13 L 490.45,178.71 L 491.19,177.50 L 491.91,176.50 L 492.65,175.56 L 493.40,174.69 L 494.18,173.88 L 494.97,173.12 L 495.84,172.38 L 496.79,171.62 L 497.81,170.88 L 498.92,170.12 L 500.10,169.40 L 501.35,168.69 L 502.67,168.00 L 504.06,167.33 L 504.73,166.60 L 504.69,165.81 L 503.93,164.96 L 502.45,164.04 L 501.12,163.17 L 499.96,162.33 L 498.95,161.54 L 498.09,160.79 L 497.21,159.92 L 496.31,158.93 L 495.38,157.81 L 494.43,156.57 L 493.59,155.39 L 492.86,154.26 L 492.25,153.18 L 491.75,152.15 L 491.30,151.14 L 490.91,150.13 L 490.58,149.14 L 490.29,148.15 L 490.05,146.95 L 489.85,145.54 L 489.70,143.92 L 489.58,142.08 L 489.54,140.33 L 489.56,138.67 L 489.65,137.08 L 489.81,135.58 L 490.05,134.08 L 490.38,132.58 L 490.79,131.08 L 491.28,129.58 L 491.77,128.22 L 492.27,127.01 L 492.76,125.93 L 493.26,124.99 L 493.82,124.04 L 494.44,123.08 L 495.12,122.11 L 495.87,121.14 L 496.68,120.17 L 497.56,119.21 L 498.50,118.25 L 499.50,117.31 L 500.52,116.43 L 501.56,115.59 L 502.62,114.81 L 503.70,114.09 L 505.07,113.28 L 506.74,112.40 L 508.70,111.44 L 510.95,110.40 L 513.45,109.43 L 516.21,108.55 L 519.21,107.74 L 522.46,107.00 L 525.52,106.43 L 528.40,106.02 L 531.08,105.76 L 533.58,105.66 L 536.08,105.62 L 538.58,105.62 L 541.08,105.66 L 543.58,105.75 L 545.83,105.89 L 547.83,106.06 L 549.58,106.28 L 551.08,106.53 L 552.65,106.84 L 554.27,107.21 L 555.96,107.64 L 557.71,108.12 L 559.48,108.68 L 561.27,109.31 L 563.08,110.01 L 564.92,110.77 L 566.60,111.54 L 568.15,112.29 L 569.54,113.05 L 570.79,113.79 L 572.12,114.67 L 573.54,115.66 L 575.04,116.78 L 576.62,118.02 L 577.98,119.11 L 579.09,120.04 L 579.98,120.81 L 580.63,121.42 L 581.14,121.94 L 581.51,122.37 L 581.74,122.71 L 581.83,122.96 L 581.26,123.96 L 580.02,125.73 L 578.11,128.24 L 575.53,131.52 L 573.41,134.20 L 571.75,136.28 L 570.54,137.77 L 569.79,138.66 L 569.17,139.37 L 568.67,139.88 L 568.29,140.21 L 568.04,140.35 L 567.41,140.10 L 566.41,139.48 L 565.03,138.47 L 563.27,137.08 L 561.52,135.79 L 559.77,134.60 L 558.02,133.50 L 556.28,132.51 L 554.62,131.63 L 553.04,130.88 L 551.54,130.25 L 550.12,129.74 L 548.58,129.29 L 546.92,128.89 L 545.12,128.55 L 543.21,128.26 L 541.27,128.06 L 539.31,127.95 L 537.33,127.93 L 535.33,128.00 L 533.40,128.17 L 531.52,128.44 L 529.71,128.82 L 527.96,129.30 L 526.32,129.89 L 524.80,130.58 L 523.39,131.39 L 522.09,132.30 L 520.93,133.27 L 519.91,134.31 L 519.04,135.42 L 518.31,136.58 L 517.72,137.71 L 517.28,138.79 L 516.99,139.83 L 516.85,140.83 L 516.77,141.83 L 516.76,142.83 L 516.80,143.83 L 516.90,144.83 L 517.11,145.83 L 517.41,146.83 L 517.82,147.83 L 518.32,148.83 L 518.90,149.77 L 519.56,150.65 L 520.30,151.47 L 521.11,152.24 L 521.99,152.94 L 522.94,153.60 L 523.96,154.20 L 525.04,154.75 L 526.12,155.22 L 527.20,155.64 L 528.28,155.98 L 529.36,156.25 L 531.63,156.49 L 535.09,156.69 L 539.73,156.86 L 545.57,156.98 L 550.00,157.15 L 553.00,157.36 L 554.59,157.61 L 554.76,157.90 L 554.89,158.55 L 554.98,159.57 L 555.02,160.96 L 555.02,162.71 L 555.02,164.71 L 555.02,166.96 L 555.02,169.46 L 555.02,172.21 L 554.97,174.35 L 554.89,175.89 L 554.76,176.83 L 554.59,177.16 L 552.86,177.43 L 549.56,177.64 L 544.71,177.78 L 538.29,177.87 L 533.15,178.01 L 529.27,178.21 L 526.67,178.47 L 525.33,178.79 L 524.02,179.20 L 522.73,179.72 L 521.46,180.35 L 520.21,181.07 L 519.06,181.88 L 518.03,182.76 L 517.10,183.73 L 516.27,184.77 L 515.60,185.70 L 515.06,186.51 L 514.67,187.21 L 514.43,187.79 L 514.22,188.40 L 514.06,189.02 L 513.93,189.67 L 513.83,190.33 L 513.79,191.17 L 513.80,192.17 L 513.87,193.33 L 513.98,194.67 L 514.26,195.98 L 514.70,197.27 L 515.31,198.54 L 516.07,199.79 L 517.01,200.98 L 518.11,202.10 L 519.39,203.17 L 520.83,204.17 L 522.31,205.04 L 523.83,205.79 L 525.38,206.41 L 526.96,206.91 L 528.58,207.32 L 530.25,207.63 L 531.96,207.86 L 533.71,207.99 L 535.56,208.06 L 537.52,208.07 L 539.58,208.01 L 541.75,207.88 L 543.83,207.67 L 545.83,207.36 L 547.75,206.96 L 549.58,206.47 L 551.24,205.97 L 552.73,205.47 L 554.04,204.96 L 555.18,204.44 L 556.44,203.80 L 557.81,203.04 L 559.30,202.16 L 560.92,201.16 L 562.50,200.09 L 564.06,198.96 L 565.58,197.76 L 567.08,196.50 L 569.15,196.61 L 571.78,198.07 L 574.97,200.89 L 578.73,205.07 L 581.43,208.35 L 583.10,210.73 L 583.71,212.21 L 583.28,212.79 L 582.58,213.54 L 581.62,214.46 L 580.39,215.54 L 578.89,216.79 L 577.12,218.11 L 575.08,219.49 L 572.78,220.93 L 570.20,222.44 L 567.54,223.83 L 564.79,225.10 L 561.96,226.25 L 559.04,227.27 L 556.02,228.16 L 552.90,228.90 L 549.67,229.51 L 546.33,229.98 L 543.25,230.33 L 540.42,230.58 Z M 765.25,230.68 L 762.75,230.68 L 760.33,230.62 L 758.00,230.50 L 755.75,230.33 L 753.58,230.09 L 751.25,229.74 L 748.75,229.25 L 746.08,228.64 L 743.25,227.90 L 740.58,227.09 L 738.08,226.21 L 735.75,225.26 L 733.58,224.23 L 731.56,223.16 L 729.69,222.04 L 727.96,220.88 L 726.38,219.68 L 724.88,218.43 L 723.49,217.14 L 722.18,215.80 L 720.97,214.41 L 719.88,213.02 L 718.89,211.62 L 718.02,210.21 L 717.26,208.79 L 716.57,207.21 L 715.94,205.46 L 715.38,203.54 L 714.89,201.46 L 714.53,199.33 L 714.30,197.17 L 714.21,194.96 L 714.25,192.71 L 714.39,190.60 L 714.63,188.65 L 714.98,186.83 L 715.43,185.17 L 715.90,183.67 L 716.39,182.33 L 716.90,181.17 L 717.43,180.17 L 718.01,179.19 L 718.62,178.23 L 719.28,177.29 L 719.98,176.38 L 720.70,175.50 L 721.44,174.67 L 722.20,173.88 L 722.98,173.12 L 723.84,172.38 L 724.78,171.62 L 725.81,170.88 L 726.91,170.12 L 728.07,169.40 L 729.30,168.69 L 730.58,168.00 L 731.93,167.33 L 732.57,166.60 L 732.50,165.81 L 731.73,164.96 L 730.25,164.04 L 728.90,163.15 L 727.70,162.29 L 726.64,161.45 L 725.72,160.63 L 724.77,159.66 L 723.80,158.54 L 722.80,157.26 L 721.78,155.82 L 720.89,154.45 L 720.14,153.15 L 719.52,151.92 L 719.04,150.75 L 718.61,149.52 L 718.23,148.23 L 717.90,146.88 L 717.62,145.46 L 717.41,144.08 L 717.27,142.75 L 717.20,141.46 L 717.20,140.21 L 717.26,138.92 L 717.38,137.58 L 717.56,136.21 L 717.79,134.79 L 718.10,133.38 L 718.47,131.96 L 718.92,130.54 L 719.43,129.12 L 720.11,127.60 L 720.98,125.98 L 722.02,124.25 L 723.24,122.42 L 724.40,120.81 L 725.50,119.43 L 726.54,118.27 L 727.53,117.35 L 728.53,116.46 L 729.57,115.61 L 730.62,114.80 L 731.71,114.03 L 732.90,113.27 L 734.19,112.51 L 735.58,111.75 L 737.08,111.00 L 738.56,110.31 L 740.02,109.69 L 741.46,109.13 L 742.88,108.64 L 744.62,108.14 L 746.71,107.64 L 749.12,107.13 L 751.88,106.62 L 754.52,106.21 L 757.06,105.91 L 759.50,105.72 L 761.83,105.63 L 764.15,105.59 L 766.44,105.58 L 768.71,105.63 L 770.96,105.71 L 773.08,105.85 L 775.08,106.03 L 776.96,106.26 L 778.71,106.55 L 780.46,106.88 L 782.21,107.25 L 783.96,107.68 L 785.71,108.15 L 787.47,108.70 L 789.26,109.32 L 791.05,110.03 L 792.87,110.82 L 794.54,111.60 L 796.07,112.37 L 797.45,113.12 L 798.70,113.88 L 799.97,114.69 L 801.26,115.56 L 802.58,116.50 L 803.93,117.50 L 805.18,118.50 L 806.35,119.50 L 807.42,120.50 L 808.39,121.50 L 808.62,122.92 L 808.11,124.75 L 806.84,127.00 L 804.83,129.67 L 802.94,132.10 L 801.17,134.30 L 799.51,136.27 L 797.97,138.01 L 796.38,138.97 L 794.74,139.13 L 793.04,138.52 L 791.29,137.11 L 789.54,135.82 L 787.79,134.62 L 786.04,133.53 L 784.29,132.55 L 782.60,131.68 L 780.98,130.92 L 779.42,130.28 L 777.92,129.75 L 776.35,129.29 L 774.73,128.89 L 773.04,128.56 L 771.29,128.29 L 769.48,128.10 L 767.60,127.98 L 765.67,127.95 L 763.67,127.99 L 761.71,128.14 L 759.79,128.40 L 757.91,128.78 L 756.06,129.27 L 754.37,129.84 L 752.83,130.50 L 751.44,131.25 L 750.20,132.08 L 749.08,132.98 L 748.09,133.95 L 747.21,134.98 L 746.46,136.08 L 745.84,137.19 L 745.36,138.32 L 745.01,139.46 L 744.79,140.61 L 744.68,141.78 L 744.67,142.98 L 744.77,144.21 L 744.97,145.46 L 745.30,146.67 L 745.76,147.83 L 746.35,148.96 L 747.07,150.04 L 747.85,151.03 L 748.70,151.92 L 749.60,152.72 L 750.56,153.42 L 751.45,154.02 L 752.26,154.52 L 753.00,154.91 L 753.67,155.21 L 754.48,155.50 L 755.44,155.79 L 756.54,156.08 L 757.79,156.37 L 760.18,156.62 L 763.72,156.83 L 768.39,157.00 L 774.21,157.13 L 778.59,158.42 L 781.53,160.86 L 783.03,164.46 L 783.10,169.21 L 783.09,172.85 L 783.02,175.39 L 782.87,176.83 L 782.66,177.16 L 780.87,177.43 L 777.51,177.64 L 772.58,177.78 L 766.08,177.86 L 760.92,178.00 L 757.08,178.19 L 754.58,178.43 L 753.42,178.73 L 752.29,179.07 L 751.21,179.47 L 750.17,179.92 L 749.17,180.42 L 748.27,180.91 L 747.48,181.40 L 746.79,181.87 L 746.21,182.35 L 745.64,182.87 L 745.10,183.43 L 744.57,184.04 L 744.05,184.69 L 743.60,185.32 L 743.21,185.94 L 742.87,186.54 L 742.60,187.12 L 742.35,187.79 L 742.13,188.54 L 741.93,189.38 L 741.77,190.29 L 741.69,191.33 L 741.70,192.50 L 741.81,193.79 L 742.00,195.21 L 742.32,196.54 L 742.77,197.79 L 743.36,198.96 L 744.07,200.04 L 744.74,200.98 L 745.37,201.76 L 745.96,202.40 L 746.51,202.88 L 747.14,203.38 L 747.86,203.88 L 748.67,204.38 L 749.56,204.90 L 750.63,205.41 L 751.88,205.91 L 753.31,206.41 L 754.92,206.91 L 756.59,207.31 L 758.31,207.62 L 760.08,207.83 L 761.92,207.95 L 763.79,208.01 L 765.71,208.02 L 767.67,207.97 L 769.67,207.86 L 771.65,207.66 L 773.60,207.36 L 775.54,206.96 L 777.46,206.46 L 779.18,205.95 L 780.69,205.45 L 782.01,204.94 L 783.13,204.43 L 784.36,203.80 L 785.70,203.04 L 787.16,202.17 L 788.72,201.17 L 790.22,200.12 L 791.66,199.03 L 793.04,197.89 L 794.36,196.70 L 795.41,195.80 L 796.19,195.19 L 796.71,194.86 L 796.96,194.81 L 798.07,195.81 L 800.04,197.86 L 802.87,200.96 L 806.56,205.11 L 809.20,208.39 L 810.79,210.79 L 811.31,212.33 L 810.79,212.99 L 810.05,213.78 L 809.10,214.69 L 807.94,215.74 L 806.57,216.91 L 805.16,218.04 L 803.70,219.13 L 802.20,220.17 L 800.65,221.17 L 799.12,222.11 L 797.59,222.99 L 796.08,223.80 L 794.58,224.55 L 792.85,225.31 L 790.90,226.07 L 788.71,226.84 L 786.29,227.63 L 783.62,228.33 L 780.71,228.96 L 777.54,229.50 L 774.12,229.97 L 770.94,230.33 L 767.98,230.56 Z M 457.46,228.34 L 452.21,228.32 L 448.15,228.27 L 445.27,228.17 L 443.58,228.04 L 443.08,227.86 L 439.21,223.27 L 431.96,214.24 L 421.33,200.80 L 407.33,182.93 L 396.80,169.60 L 389.75,160.82 L 386.16,156.58 L 386.05,156.88 L 385.96,161.50 L 385.91,170.45 L 385.88,183.71 L 385.88,201.29 L 385.83,214.52 L 385.72,223.39 L 385.55,227.91 L 385.33,228.06 L 383.62,228.18 L 380.43,228.27 L 375.75,228.31 L 369.58,228.31 L 364.92,228.29 L 361.75,228.25 L 360.08,228.17 L 359.92,228.08 L 359.77,227.78 L 359.64,227.28 L 359.53,226.58 L 359.44,225.68 L 359.39,217.73 L 359.39,202.73 L 359.44,180.68 L 359.53,151.57 L 360.89,129.73 L 363.52,115.14 L 367.42,107.81 L 372.58,107.75 L 376.61,107.72 L 379.51,107.73 L 381.26,107.78 L 381.88,107.87 L 385.48,112.03 L 392.07,120.27 L 401.63,132.59 L 414.18,148.98 L 423.91,161.67 L 430.82,170.67 L 434.91,175.98 L 436.18,177.59 L 437.21,178.83 L 438.00,179.71 L 438.55,180.23 L 438.87,180.39 L 439.10,175.99 L 439.27,167.03 L 439.35,153.52 L 439.37,135.44 L 439.44,121.85 L 439.56,112.72 L 439.74,108.07 L 439.98,107.90 L 441.70,107.77 L 444.90,107.68 L 449.58,107.64 L 455.75,107.63 L 460.43,107.65 L 463.61,107.70 L 465.31,107.77 L 465.51,107.86 L 465.68,115.39 L 465.80,130.35 L 465.89,152.75 L 465.94,182.58 L 465.94,205.02 L 465.87,220.07 L 465.76,227.72 L 465.59,227.97 L 464.15,228.16 L 461.44,228.28 Z M 618.08,228.38 L 611.92,228.38 L 607.19,228.31 L 603.92,228.17 L 602.08,227.98 L 601.69,227.72 L 601.41,220.09 L 601.22,205.09 L 601.15,182.71 L 601.17,152.96 L 601.28,130.60 L 601.47,115.64 L 601.75,108.06 L 602.12,107.88 L 605.81,107.75 L 612.83,107.67 L 623.17,107.64 L 636.83,107.65 L 647.69,107.75 L 655.73,107.91 L 660.96,108.16 L 663.38,108.47 L 665.79,108.90 L 668.21,109.43 L 670.62,110.07 L 673.04,110.82 L 675.31,111.62 L 677.44,112.48 L 679.42,113.40 L 681.25,114.38 L 683.02,115.43 L 684.72,116.56 L 686.36,117.78 L 687.93,119.07 L 689.39,120.37 L 690.74,121.68 L 691.99,123.00 L 693.13,124.33 L 694.23,125.81 L 695.30,127.44 L 696.34,129.21 L 697.34,131.12 L 698.21,133.00 L 698.96,134.83 L 699.58,136.62 L 700.08,138.38 L 700.51,140.40 L 700.87,142.69 L 701.17,145.25 L 701.40,148.08 L 701.51,150.75 L 701.50,153.25 L 701.36,155.58 L 701.10,157.75 L 700.84,159.65 L 700.59,161.27 L 700.34,162.62 L 700.09,163.71 L 699.78,164.83 L 699.41,166.00 L 698.98,167.21 L 698.49,168.46 L 697.88,169.81 L 697.13,171.27 L 696.26,172.83 L 695.25,174.50 L 694.18,176.09 L 693.05,177.61 L 691.84,179.05 L 690.57,180.42 L 689.17,181.77 L 687.65,183.11 L 686.00,184.42 L 684.22,185.72 L 682.33,186.94 L 680.33,188.09 L 678.22,189.17 L 676.00,190.17 L 673.85,191.05 L 671.76,191.80 L 669.75,192.42 L 667.80,192.92 L 665.87,193.34 L 663.95,193.70 L 662.05,193.97 L 660.16,194.18 L 657.02,194.34 L 652.62,194.47 L 646.96,194.57 L 640.04,194.62 L 634.79,194.68 L 631.21,194.76 L 629.29,194.85 L 629.04,194.95 L 628.84,197.01 L 628.67,201.05 L 628.55,207.06 L 628.48,215.04 L 628.35,221.10 L 628.19,225.27 L 627.98,227.52 L 627.72,227.87 L 625.98,228.13 L 622.77,228.30 Z M 949.67,228.37 L 943.67,228.36 L 939.12,228.32 L 936.04,228.23 L 934.41,228.10 L 934.23,227.92 L 934.09,223.39 L 933.96,214.51 L 933.86,201.26 L 933.78,183.66 L 933.64,170.54 L 933.44,161.92 L 933.18,157.78 L 932.86,158.14 L 930.72,161.82 L 926.75,168.83 L 920.96,179.17 L 913.35,192.83 L 907.56,203.21 L 903.60,210.29 L 901.46,214.08 L 901.14,214.58 L 900.82,214.99 L 900.50,215.31 L 900.17,215.54 L 899.83,215.69 L 898.92,215.80 L 897.42,215.88 L 895.33,215.91 L 892.67,215.91 L 890.58,215.89 L 889.08,215.83 L 888.17,215.75 L 887.83,215.64 L 885.54,212.02 L 881.29,204.89 L 875.08,194.25 L 866.92,180.11 L 860.76,169.59 L 856.62,162.69 L 854.49,159.43 L 854.38,159.79 L 854.29,164.27 L 854.24,172.87 L 854.22,185.58 L 854.22,202.42 L 854.17,215.09 L 854.06,223.61 L 853.90,227.97 L 853.67,228.17 L 852.02,228.31 L 848.95,228.41 L 844.46,228.45 L 838.54,228.44 L 834.07,228.40 L 831.03,228.35 L 829.44,228.26 L 829.28,228.16 L 829.14,228.04 L 829.02,227.90 L 828.92,227.75 L 828.83,227.58 L 828.78,220.00 L 828.77,205.00 L 828.81,182.58 L 828.89,152.75 L 830.34,130.35 L 833.17,115.38 L 837.38,107.85 L 842.96,107.75 L 847.23,107.69 L 850.19,107.69 L 851.84,107.75 L 852.17,107.85 L 854.90,112.35 L 860.03,121.26 L 867.55,134.58 L 877.46,152.30 L 884.98,165.72 L 890.09,174.85 L 892.81,179.67 L 893.12,180.20 L 893.43,180.64 L 893.72,180.99 L 894.00,181.24 L 894.27,181.41 L 897.02,176.92 L 902.25,167.80 L 909.96,154.03 L 920.16,135.62 L 927.95,121.78 L 933.32,112.53 L 936.28,107.85 L 936.84,107.75 L 938.59,107.69 L 941.53,107.67 L 945.67,107.70 L 951.00,107.77 L 955.03,115.29 L 957.77,130.26 L 959.20,152.67 L 959.34,182.54 L 959.39,205.00 L 959.35,220.06 L 959.22,227.73 L 959.00,227.99 L 957.33,228.18 L 954.22,228.31 Z M 657.14,171.26 L 658.42,170.98 L 659.65,170.66 L 660.83,170.28 L 661.97,169.86 L 663.07,169.38 L 664.13,168.84 L 665.18,168.22 L 666.19,167.53 L 667.18,166.78 L 668.11,165.96 L 668.98,165.08 L 669.79,164.14 L 670.54,163.13 L 671.23,162.05 L 671.87,160.89 L 672.45,159.64 L 672.96,158.32 L 673.38,157.01 L 673.70,155.73 L 673.91,154.46 L 674.02,153.21 L 674.07,151.90 L 674.06,150.52 L 674.00,149.08 L 673.87,147.58 L 673.65,146.15 L 673.34,144.77 L 672.94,143.46 L 672.44,142.21 L 671.90,141.06 L 671.31,140.02 L 670.68,139.08 L 670.01,138.24 L 669.28,137.43 L 668.48,136.64 L 667.62,135.87 L 666.71,135.12 L 665.77,134.44 L 664.81,133.83 L 663.83,133.28 L 662.83,132.80 L 661.85,132.37 L 660.87,131.99 L 659.92,131.67 L 658.97,131.40 L 657.87,131.17 L 656.62,130.97 L 655.22,130.81 L 653.67,130.68 L 651.10,130.60 L 647.53,130.56 L 642.96,130.58 L 637.38,130.65 L 633.15,130.73 L 630.29,130.84 L 628.78,130.97 L 628.63,131.11 L 628.53,133.72 L 628.47,138.80 L 628.44,146.33 L 628.46,156.33 L 628.55,163.86 L 628.71,168.93 L 628.93,171.52 L 629.23,171.65 L 631.04,171.73 L 634.39,171.77 L 639.25,171.77 L 645.64,171.73 L 650.76,171.63 L 654.59,171.47 Z"/></svg></div>'
            '<p class="means"><span class="ken" lang="ken">Nɛpɛ́m</span> means life.</p></div>',
            unsafe_allow_html=True)

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


# ─── INDEXES THE TOOLS NEED ──────────────────────────────────────────────────
# Two lookups, built once and cached on the corpus signature, so they refresh
# only when the knowledge folder actually changes.
#
# word_index  Every Kenyang-looking token in the WHOLE corpus, with the best
#             trust tier it appears under. This is what makes is_this_real
#             trustworthy. The amber flag under each reply compares the answer
#             against the passages retrieved THAT TURN — which is why it wrongly
#             flagged real words like Ndǔ and afú when I asked it to read Mark
#             1:9: their definitions simply had not come back that turn.
#             Checking the whole corpus ends that false alarm.
#
# rule_book   The verified file sliced up by its own "## " headings, so the model
#             can ask for "adjective_order" and get that rule verbatim. Verbatim
#             is the point — paraphrasing a rule is exactly how the wrong
#             adjective order got in the first time.
@st.cache_data(show_spinner=False)
def build_tool_indexes(sig):
    _always, ch, _man, _over, _tr = build_corpus(sig)
    return (tools.build_word_index(ch),
            tools.load_rules(os.path.join(KB_ROOT, "kenyang_verified_speaker.md")))


word_index, rule_book = {}, {}
try:
    if chunks:
        word_index, rule_book = build_tool_indexes(signature)
except Exception as e:
    # If this fails the tools degrade instead of breaking: is_this_real reports
    # nothing found, get_grammar_rule says no rules are stored. Better than
    # taking the whole app down over an index.
    st.warning(f"Tool indexes unavailable: {type(e).__name__}: {e}")

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

STATIC_CONTEXT = SYSTEM_PROMPT + recordings_block() + "\n\n" + always_on

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
        # ─── ARE THE TOOLS ACTUALLY BEING USED? ──────────────────────────
        # Models ignore tools more often than you would expect, and the four
        # definitions cost roughly 800 input tokens on EVERY request. So this
        # line tells me plainly whether I am paying for something that works.
        # If it keeps saying "answered without tools", the fix is sharper
        # instructions — not more tools.
        st.caption(f"tools: {len(tools.TOOLS)} offered · "
                   f"{len(word_index):,} words indexed · "
                   f"{len(rule_book)} rules available")
        if "last_tool_round" in st.session_state:
            st.caption("last answer: "
                       + ("used a tool" if st.session_state.last_tool_round
                          else "answered without tools"))

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
st.markdown('<p class="note">This conversation is kept on our side while you are away, for '
            'about half an hour. Refreshing the page starts a fresh one. Nɛpɛm does not keep '
            'a record of it after that. To answer, your messages are sent to OpenAI, which may '
            'keep them for up to 30 days.</p>',
            unsafe_allow_html=True)

# The how-to line only while the starters are on screen; after that it points at nothing.
opening = WELCOME if st.session_state.messages else WELCOME + "\n" + START_HINT
st.markdown(bubble("assistant", opening), unsafe_allow_html=True)

# Anything above the marker is on screen but past what Nɛpɛm can see. I draw the line
# rather than let him quietly forget and confuse someone.
horizon = max(0, len(st.session_state.messages) - MAX_HISTORY_TURNS)
for i, m in enumerate(st.session_state.messages):
    if i == horizon and horizon > 0:
        st.markdown('<div class="memmark">Nɛpɛm remembers from here on</div>',
                    unsafe_allow_html=True)
    st.markdown(bubble(m["role"], m["content"], hear=m.get("hear", "")),
                unsafe_allow_html=True)

# --- starters ----------------------------------------------------------------
starter = None
if not st.session_state.messages:
    c1, c2 = st.columns(2)
    if c1.button("Teach me a greeting"):
        starter = "Teach me a Kenyang greeting."
    if c2.button("Test me"):
        starter = "Test me with a quick Kenyang question."
    c3, c4 = st.columns(2)
    if c3.button("Teach me to count"):
        starter = "Teach me how to count in Kenyang, starting with one to five."
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
            knowledge, lesson_note(history, found, always_on),
            correction_note(last_user), RULES_REMINDER) if x)

        api_messages = ([{"role": "system", "content": STATIC_CONTEXT},
                         {"role": "system", "content": turn_context}]
                        + [{"role": m["role"], "content": m["content"]} for m in history])

        # GPT-5 and GPT-6 models reject `temperature` outright — the parameter being
        # present is the error, whatever value it holds. So I send it only where it's taken.
        # Note `stream` is NOT set here — it is added only on the final call below,
        # because the first call has to come back whole.
        params = dict(model=MODEL, messages=api_messages)
        if not MODEL.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
            params["temperature"] = TEMPERATURE

        # ─── THE TOOL ROUND ──────────────────────────────────────────────────
        # Streaming and tool calls do not mix. A tool request arrives in fragments
        # spread across the stream, and I cannot act on half a request. So a turn
        # now runs in two parts:
        #
        #   round 1  ask WITHOUT streaming, with the tools on offer. Either the
        #            model answers, or it asks me to look something up.
        #   round 2  if it asked, run the tools, append their results to the
        #            messages, then stream the real answer with that output in view.
        #
        # If it asks for nothing, round 1 is discarded and round 2 streams exactly
        # as before. The cost is one extra short call per turn — the price of the
        # model being able to look things up for itself instead of me guessing.
        client = OpenAI(api_key=api_key())
        reply, painted = "", 0
        try:
            # Round 1. Tools are on offer, so this one cannot stream.
            probe = client.chat.completions.create(
                **params, tools=tools.TOOLS, tool_choice="none")

            # run whatever it asked for; api_messages comes back with the results
            api_messages, used_tools = tools.run_tool_calls(
                probe, api_messages, chunks, vectors, lexicon,
                search, word_index, rule_book)
            st.session_state.last_tool_round = used_tools

            if not used_tools:
                # It asked for nothing, which means round 1 IS the answer. The old code
                # threw it away and generated the whole reply a second time, so every
                # ordinary question paid for two full calls and waited through both.
                # Most turns use no tool, so this halves the cost and the wait.
                # What it costs: no typing effect on those turns. The reply lands whole,
                # and it lands sooner than the first word used to.
                reply = (probe.choices[0].message.content or "").strip()
                if reply:
                    slot.markdown(bubble("assistant", reply), unsafe_allow_html=True)
                    painted = len(reply)
            else:
                # It asked for a lookup. Stream the real answer with the tool output in
                # view. Tools are NOT offered again: one lookup round is enough, and
                # leaving them on invites a second request mid-stream, which a stream
                # cannot answer.
                params["messages"] = api_messages
                stream = client.chat.completions.create(**params, stream=True)
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

            reply = drop_tap_claims(reply)
            if reply.strip():
                # Which words can be heard is a fact the code can check, so the code says
                # it. The model is told never to; it once claimed a recording that did not
                # exist. The line is kept beside the reply, not in it, so it is never sent
                # back to the model as something to imitate.
                hear = hear_line(recorded_in(reply, recorded_keys()))
                slot.markdown(bubble("assistant", reply, hear=hear), unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": reply,
                                                  "hear": hear})
                # Check the reply against the material it was built from, and say so.
                loose = unsupported_words(reply, found, always_on)
                if loose:
                    st.markdown(
                        '<div class="unchecked"><span class="mk" aria-hidden="true">!</span>'
                        '<span>Not found in the material behind this '
                        'answer: <b>' + ", ".join(html.escape(w) for w in loose[:12]) +
                        '</b>. These may be spelled differently in my sources — or they '
                        'may not be real Kenyang. Check with a speaker before learning '
                        'them.</span></div>', unsafe_allow_html=True)
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