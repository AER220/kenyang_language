"""
run_checks.py — the Testing table and the twenty-reply measurement, as one command.

    python run_checks.py            all twenty questions (the table's ten, plus ten more)
    python run_checks.py --table    the table's ten only

Run it before every push that touches the knowledge base, the prompt, or the code
between the model and the learner. Each question is asked in a fresh session of the
chat, run locally through Streamlit's test harness (it reads .streamlit/secrets.toml,
so it makes real calls to the model: about one per question).

It prints, for each question, PASS or FAIL against the table's expectation, and the
two kinds of flag the word check put under the reply.

THE GATE IS A REGRESSION CHECK (Ed, 26 November 2026). It exits non-zero if a row that
passes on the live code fails, or if more than one reply carries a "not found" flag. A
row in LIVE_FAILING, already failing on the live code, does not block a push, and is
named in the summary so it is never forgotten. When a push makes one of those rows
pass, take it out of LIVE_FAILING in the same commit; when a row starts failing on the
live code for a reason nobody can fix now, it goes in only with Ed's agreement.

The rows live here, not only in CLAUDE.md, so that nobody has to remember to read a
table: rows 6 and 7 were failing for some time while the table only sat in a file.
A row is a question and a check on the reply. A check tests only what a speaker has
confirmed; a reply can pass and still be poor in ways no check here sees (an example
sentence the model built from parts, for one). Read the replies too.
"""

import html
import json
import logging
import os
import re
import sys
import unicodedata
import warnings

ROOT = os.path.dirname(os.path.abspath(__file__))


def norm(text):
    """For comparing: NFC, one kind of apostrophe, lower case, single spaces."""
    t = unicodedata.normalize("NFC", text or "")
    t = re.sub(r"[’‘ʼʻ`´]", "'", t)
    return re.sub(r"\s+", " ", t).lower()


def has(*forms):
    return lambda r: all(norm(f) in norm(r) for f in forms)


def lacks(*forms):
    return lambda r: not any(norm(f) in norm(r) for f in forms)


def both(*checks):
    return lambda r: all(c(r) for c in checks)


REFUSES = lambda r: bool(re.search(r"\b(don't|do not|doesn't|does not) have\b|\bno word\b|"
                                   r"\bnot (been )?given\b", norm(r)))

# Rows that fail on the live code: the known baseline. 26 November 2026: 4 (drops
# nyaka) and 7 (an example sentence built from parts, QUESTIONS 34). Rows 6 (name order)
# and 5 (bépay for Ed's recorded bɛ́pay) also failed on live; both were fixed in code in
# the push that set this up, and taken out. Take a row out only when a change fixes it:
# row 7 passed in that push's run by chance (no sentence was built), so it stays.
#
# Row 1 (count 1 to 10), added 26 November 2026 with Ed's agreement, is NOT a code
# failure: Ed's own counting table (Ɛmɔ́t, Tándat nɛ amɔt) disagrees with his own
# recordings (ɛ́mɔt, tándrámɔt), and the swap rightly leaves his written forms alone, so
# a reply that draws on the table fails the row. QUESTIONS 38. Ed will settle it by
# saying the forms aloud; take row 1 out again as soon as he answers.
LIVE_FAILING = {1, 4, 7}

ONE_TO_TEN = ["ɛ́mɔt", "bɛ́pay", "bɛ́rát", "mɛ́nwi", "bɛ́tay", "bɛ́tandat", "tándrámɔt",
              "mɛ́nɛn", "mɛ́nɛn nɛ amɔt", "byó"]

# (question, what is expected, check). The ten rows of the Testing table in CLAUDE.md.
TABLE = [
    ("count 1 to 10", "all ten, no gaps", has(*ONE_TO_TEN)),
    ("what is the word for house", "ɛkɛt", has("ɛkɛt")),
    ("what is the plural of house", "beket", has("beket")),
    ("how do you say they were not going to school", "bá pú rong nyaka ekeré-ékáti",
     has("bá pú rong nyaka ekeré-ékáti")),
    ("how do you say two small houses", "Mandu ɛkɛt bɛ́pay", has("Mandu ɛkɛt bɛ́pay")),
    ("my grandmother's name is Helen", "N-ném Ma'ya nsinsi chi Helen (N-ném first)",
     both(has("N-ném Ma'ya nsinsi chi Helen"), lacks("Ma'ya nsinsi n-ném"))),
    ("what is the word for grandfather", "étá nsinsi", has("étá nsinsi")),
    ("what is the word for stepmother", "refuses", REFUSES),
    ("how do you say 37", "says it does not have 37, builds nothing",
     has("I don't have thirty-seven")),
    ("how do I say I have 37 goats", "no form for 37, never 23's form",
     both(has("don't have thirty-seven"), lacks("meso ɛ́rát", "ɛ̌ti"))),
]

# The other ten of the twenty: ordinary learner questions. No expectation is checked;
# they are here for the flag counts.
ORDINARY = [
    "what is the word for road", "how do I say path", "how do I say good morning",
    "how do I say thank you", "what is the word for sun", "how do you say I am going to church",
    "what is the word for dog", "how do I say my mother", "how do you say I am tired",
    "what is the word for river",
]


def ask(question):
    """One question in a fresh session: (reply text, not-found words, written words, errors)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(ROOT, "streamlit_app.py"), default_timeout=240).run()
    at.chat_input[0].set_value(question).run()
    md = [m.value for m in at.markdown]
    reply = ""
    for m in md:
        if 'class="bubble' in m or "assistant" in m[:200]:
            reply = m
    flag = next((m for m in md if 'class="unchecked"' in m), "")
    nf = re.search(r"Not found in the material behind this answer: <b>(.*?)</b>", flag)
    ws = re.search(r"From written sources, not yet checked by a speaker: <b>(.*?)</b>", flag)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", reply))).strip()
    return (text, html.unescape(nf.group(1)) if nf else "",
            html.unescape(ws.group(1)) if ws else "", [str(e.value) for e in at.exception])


def main():
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    rows = TABLE + ([] if "--table" in sys.argv else [(q, "", None) for q in ORDINARY])
    failed, not_found, written, results = [], 0, 0, []
    for i, (q, expect, check) in enumerate(rows, 1):
        reply, nf, ws, errors = ask(q)
        verdict = "    " if check is None else ("PASS" if check(reply) and not errors else "FAIL")
        if verdict == "FAIL":
            failed.append(i)
        not_found += bool(nf)
        written += bool(ws)
        print(f"{i:2d} {verdict}  {q}" + (f"   (expect: {expect})" if expect else ""))
        if verdict == "FAIL" or errors:
            print(f"        reply: {reply[-400:]}")
        for e in errors:
            print(f"        error: {e[:200]}")
        if nf:
            print(f"        NOT FOUND: {nf}")
        if ws:
            print(f"        from written sources: {ws}")
        results.append({"q": q, "verdict": verdict.strip(), "reply": reply,
                        "not_found": nf, "written": ws, "errors": errors})
    n = len(rows)
    print()
    regressed = [i for i in failed if i not in LIVE_FAILING]
    known = [i for i in failed if i in LIVE_FAILING]
    fixed = sorted(i for i in LIVE_FAILING if i not in failed and i <= len(TABLE))
    print(f"Testing table: {len(TABLE) - len(failed)} of {len(TABLE)} pass")
    if regressed:
        print(f"  REGRESSION: row {', '.join(map(str, regressed))} passes on live and fails now")
    if known:
        print(f"  Still failing, as on live (name these in the push report): "
              f"row {', '.join(map(str, known))}")
    if fixed:
        print(f"  Failing on live, passing now: row {', '.join(map(str, fixed))} "
              f"(take it out of LIVE_FAILING in this push)")
    print(f"'Not found' in {not_found} of {n} replies (limit: one in twenty)")
    print(f"'From written sources' in {written} of {n} replies ({round(100 * written / n)}%)")
    ok = not regressed and not_found <= 1
    print("GATE: PASS" if ok else "GATE: FAIL")
    out = os.path.join(ROOT, ".run_checks_last.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"Every reply in full: {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
