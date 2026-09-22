"""
tools.py — function calling for Nɛpɛm.

Why these four, and not more
----------------------------
The lecture makes the cost point plainly: tool definitions are injected into the
system message, count against the context limit, and are billed as input tokens.
Nɛpɛm is already brushing a tokens-per-minute ceiling, so every tool has to earn
its place. These four each fix a failure I have actually watched happen.

    1. look_up_kenyang     — fixes "tell me more", "use it in a sentence"
    2. is_this_real        — turns fabrication from a warning into prevention
    3. get_grammar_rule    — lets the resident grammar block shrink
    4. build_verb_forms    — makes the verb grid arithmetic, not guesswork

Integration
-----------
    import tools
    resp = client.chat.completions.create(
        model=MODEL, messages=msgs, tools=tools.TOOLS, tool_choice="auto")
    msgs, used = tools.run_tool_calls(resp, msgs, chunks, vectors, lexicon)
    if used:                       # second call, now with the tool results
        resp = client.chat.completions.create(
            model=MODEL, messages=msgs, tools=tools.TOOLS, tool_choice="auto")
"""

import json
import os
import re
import unicodedata

# ─────────────────────────────────────────────────────────────────────────────
# 1 · THE TOOL DEFINITIONS
#     Descriptions matter more than names. The model reads these and nothing
#     else, so each says WHEN to call it, not just what it does.
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "look_up_kenyang",
            "description": (
                "Search the Kenyang material for a word, phrase or topic. Call this "
                "whenever you need Kenyang you do not already have in front of you. "
                "Call it especially when the learner's message has no searchable words "
                "of its own — 'tell me more', 'use it in a sentence', 'what about the "
                "plural', 'say that again with my mother instead'. In those cases work "
                "out from the conversation what the actual subject is and search for "
                "THAT, not for the learner's words. You may call this several times in "
                "one turn, once per thing you need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": (
                            "What to search for — an English meaning ('to go'), a "
                            "Kenyang word ('rong'), or a topic ('noun class concord'). "
                            "Be specific. One idea per call."
                        ),
                    },
                    "why": {
                        "type": "string",
                        "description": (
                            "One short phrase saying what you are trying to build or "
                            "answer. Helps rank the passages."
                        ),
                    },
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "is_this_real",
            "description": (
                "Check whether a Kenyang word actually appears anywhere in the trusted "
                "material, and in which tier. CALL THIS BEFORE TEACHING ANY KENYANG WORD "
                "YOU ARE NOT CERTAIN OF. If it comes back not found, say plainly that you "
                "do not have the word and tell the learner to ask a speaker. Never present "
                "an unfound word as though it were confirmed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "words": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "One or more Kenyang words to verify.",
                    }
                },
                "required": ["words"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_grammar_rule",
            "description": (
                "Fetch a speaker-verified grammar rule, in full, with its worked examples. "
                "Call this before building any sentence, so you apply the rule as written "
                "rather than from memory. If you are unsure which rule you need, ask for "
                "'index' to see what rules exist."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "index", "person", "negation", "past", "possession",
                            "adjective_order", "plural", "questions",
                            "reported_speech", "word_order", "commands", "ongoing",
                        ],
                        "description": (
                            "Which rule. 'person' = the mme/O'/à/sé/bá prefixes. "
                            "'adjective_order' = which adjectives go before the noun and "
                            "which after. 'index' lists everything available."
                        ),
                    }
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_verb_forms",
            "description": (
                "Build the correct Kenyang form of a verb from the confirmed rule "
                "(person prefix + pú for not + verb + nyaka for past). The ordering is "
                "fixed, so this is computed rather than guessed — call it instead of "
                "assembling a verb yourself. Works for any verb root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "verb": {
                        "type": "string",
                        "description": "The bare Kenyang verb root, e.g. rong, tuor, kong, ghati.",
                    },
                    "person": {
                        "type": "string",
                        "enum": ["I", "you", "he_she", "we", "they"],
                    },
                    "negative": {"type": "boolean", "description": "True for 'not'."},
                    "past": {"type": "boolean", "description": "True for past tense."},
                    "place": {
                        "type": "string",
                        "description": "Optional place, which goes after the verb.",
                    },
                },
                "required": ["verb", "person"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 2 · THE IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────────────────────

# Match on DECOMPOSED text. A precomposed letter like ǔ (U+01D4) is a single
# codepoint that no sensible character class catches, so normalising to NFD first
# turns it into u + combining caron — and both of those are matchable. Without
# this, "Ndǔ" tokenised as "Nd" and the word could never be found.
KENYANG_LETTER = re.compile(r"[A-Za-zɛɔŋɨʉƐƆŊƗɄ'\u0300-\u036f-]{1,}")


def _tokens(text):
    return KENYANG_LETTER.findall(unicodedata.normalize("NFD", text))

# the four persons, exactly as confirmed by a speaker
PERSON = {"I": "mme", "you": "O'", "he_she": "à", "we": "sé", "they": "bá"}
ENGLISH_BE = {
    "I":       ("I am", "I was"),
    "you":     ("you are", "you were"),
    "he_she":  ("he/she is", "he/she was"),
    "we":      ("we are", "we were"),
    "they":    ("they are", "they were"),
}


def _fold(s):
    """Compare words without tone marks or case, so ɛ́ and ɛ match."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def look_up_kenyang(args, chunks, vectors, lexicon, search_fn, cap=24):
    """
    Search the corpus. This is the model driving retrieval rather than the app
    guessing from the raw prompt — which is the whole point. Returns passages
    with their trust tier so the model can weigh them.
    """
    term = (args.get("term") or "").strip()
    if not term:
        return {"error": "no term given"}
    query = f"{term} {args.get('why','')}".strip()
    hits = search_fn(query, chunks, vectors, lexicon, cap=cap)
    return {
        "term": term,
        "found": len(hits),
        "passages": [
            {"tier": h.get("tier", "core"), "text": h["text"][:900]}
            for h in hits[:12]
        ],
    }


def is_this_real(args, full_index):
    """
    Check words against EVERY token in the corpus, not just what was retrieved
    this turn. That distinction matters: the old post-hoc flag compared against
    retrieved passages only, so it cried wolf on real words like Ndǔ and afú
    whose definitions had not happened to come back that turn.
    """
    out = []
    for w in args.get("words", []):
        key = _fold(w.strip())
        rec = full_index.get(key)
        if rec:
            out.append({
                "word": w,
                "found": True,
                "best_tier": rec["tier"],
                "sources": rec["count"],
                "note": ("confirmed by a speaker" if rec["tier"] == "verified"
                         else f"appears in {rec['count']} place(s) in the material"),
            })
        else:
            out.append({
                "word": w,
                "found": False,
                "note": ("NOT in the material. Do not teach this word. Say you do not "
                         "have it and suggest asking a speaker."),
            })
    return {"checked": out}


def get_grammar_rule(args, rules):
    """Return a verified rule verbatim. Verbatim matters — paraphrasing a rule is
    how the adjective-order error crept in the first time."""
    topic = (args.get("topic") or "index").lower()
    if topic == "index":
        return {"available": sorted(rules.keys()),
                "note": "Call again with one of these to get the rule in full."}
    rule = rules.get(topic)
    if not rule:
        return {"error": f"no rule stored for '{topic}'",
                "available": sorted(rules.keys())}
    return {"topic": topic, "rule": rule,
            "note": "Apply this exactly as written. Do not adapt it."}


def build_verb_forms(args):
    """
    Assemble the verb deterministically. The order is fixed and confirmed:
    person + pú + verb + nyaka + place. Code cannot get it in the wrong order;
    a model can, and has.
    """
    verb = (args.get("verb") or "").strip()
    person = args.get("person")
    if not verb or person not in PERSON:
        return {"error": "need a verb root and a person"}

    neg, past = bool(args.get("negative")), bool(args.get("past"))
    place = (args.get("place") or "").strip()

    parts = [PERSON[person]]
    if neg:
        parts.append("pú")
    parts.append(verb)
    if past:
        parts.append("nyaka")
    if place:
        parts.append(place)

    be = ENGLISH_BE[person][1 if past else 0]
    gloss = f"{be}{' not' if neg else ''} [{verb}]{' ' + place if place else ''}"

    return {
        "kenyang": " ".join(parts),
        "english_frame": gloss,
        "built_from": "person prefix + pú (not) + verb + nyaka (past) + place",
        "note": "Order is fixed and speaker-confirmed. Use exactly this.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3 · SUPPORT: build the two indexes the tools need, once, at startup
# ─────────────────────────────────────────────────────────────────────────────

def build_word_index(chunks):
    """
    Every Kenyang-looking token in the whole corpus → its best tier and how many
    places it appears. Built once; this is what makes is_this_real accurate.
    """
    rank = {"verified": 3, "core": 2, "reference": 1}
    idx = {}
    for c in chunks:
        tier = c.get("tier", "core")
        for tok in _tokens(c["text"]):
            if len(tok) < 2:
                continue
            key = _fold(tok)
            rec = idx.get(key)
            if rec is None:
                idx[key] = {"tier": tier, "count": 1}
            else:
                rec["count"] += 1
                if rank.get(tier, 0) > rank.get(rec["tier"], 0):
                    rec["tier"] = tier
    return idx


RULE_HEADINGS = {
    "person":          ("prefix", "who is doing", "person"),
    "negation":        ("pú", "not —", "negative"),
    "past":            ("past tense", "nyaka"),
    "possession":      ("possession", "my / your", "thing comes first"),
    "adjective_order": ("where each adjective goes", "adjective"),
    "plural":          ("boh — making things plural", "plural"),
    "questions":       ("asking", "question"),
    "reported_speech": ("reported speech",),
    "word_order":      ("going somewhere", "word order", "place goes at the end"),
    "commands":        ("do not", "kɛ́"),
    "ongoing":         ("be doing", "nɔkɔ"),
}


def load_rules(verified_path="knowledge_base/kenyang_verified_speaker.md"):
    """
    Slice the verified file into named rules by its own headings, so
    get_grammar_rule can hand back a rule verbatim.
    """
    if not os.path.exists(verified_path):
        return {}
    text = open(verified_path, encoding="utf-8", errors="replace").read()
    sections, current, buf = {}, None, []
    for line in text.split("\n"):
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(buf).strip()
            current, buf = line[3:].strip().lower(), []
        elif current:
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()

    rules = {}
    for topic, needles in RULE_HEADINGS.items():
        chunks = [body for head, body in sections.items()
                  if any(n in head for n in needles) and body]
        if chunks:
            rules[topic] = "\n\n".join(chunks)[:3500]
    return rules


# ─────────────────────────────────────────────────────────────────────────────
# 4 · THE DISPATCH LOOP
# ─────────────────────────────────────────────────────────────────────────────

def run_tool_calls(response, messages, chunks, vectors, lexicon,
                   search_fn, word_index, rules, max_calls=6):
    """
    Handle whatever the model asked for and append the results to `messages`.

    Returns (messages, did_call_anything). If True, call the model again with the
    updated messages so it can answer using what came back. Cap the calls —
    without a ceiling a confused model can loop on look_up_kenyang forever, and
    every call is billed.
    """
    choice = response.choices[0].message
    calls = getattr(choice, "tool_calls", None)
    if not calls:
        return messages, False

    messages.append({
        "role": "assistant",
        "content": choice.content or "",
        "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in calls
        ],
    })

    for call in calls[:max_calls]:
        name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except Exception:
            args = {}

        if name == "look_up_kenyang":
            result = look_up_kenyang(args, chunks, vectors, lexicon, search_fn)
        elif name == "is_this_real":
            result = is_this_real(args, word_index)
        elif name == "get_grammar_rule":
            result = get_grammar_rule(args, rules)
        elif name == "build_verb_forms":
            result = build_verb_forms(args)
        else:
            result = {"error": f"unknown tool '{name}'"}

        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": name,
            "content": json.dumps(result, ensure_ascii=False),
        })

    return messages, True


# ─────────────────────────────────────────────────────────────────────────────
# 5 · PROMPT LINES TO ADD, so the model actually uses these
# ─────────────────────────────────────────────────────────────────────────────

TOOL_INSTRUCTIONS = """
YOU HAVE TOOLS. USE THEM RATHER THAN GUESSING:
- Before you teach any Kenyang word you are not certain of, call is_this_real.
  If it comes back not found, say you do not have the word. Do not soften this.
- Before you build any sentence, call get_grammar_rule for the rule you need,
  and apply it exactly as written rather than from memory.
- To put a verb into a person or a tense, call build_verb_forms. The ordering is
  fixed, and the tool cannot get it wrong.
- When the learner says something with no searchable words in it — "tell me
  more", "use it in a sentence", "what about the plural" — work out from the
  conversation what they actually mean and call look_up_kenyang for THAT.
- You may call several tools in one turn. Do that rather than answering half a
  question.
"""