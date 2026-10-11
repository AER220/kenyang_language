"""
Tonight's three fixes for streamlit_app.py.

  1. retrieval  exact matching was done on substrings, so "one" matched money,
                stone, listen and someone, and "1" matched 1998 and 21. Those
                false hits then ate the whole retrieval budget, so the meaning
                search never ran. This is why Nɛpɛm said it could not count
                while the numbers sat in the folder.
  2. speed      every turn made TWO full model calls. When the model asked for
                no tool, which is most turns, the first answer was thrown away
                and the whole reply generated again. Now the first answer is
                used.
  3. model      down to gpt-4o-mini, with the context mode pinned so the app
                cannot try to post a corpus larger than mini's window.

Run it from the repo root. It asserts every edit, so if your file differs from
what I read it stops without changing anything.

    cd /workspaces/kenyang_language
    python patch_tonight.py

It writes streamlit_app.py.backup first. To undo:

    cp streamlit_app.py.backup streamlit_app.py
"""
import shutil
import sys

SRC = "streamlit_app.py"
EDITS = []


def edit(name, old, new):
    EDITS.append((name, old, new))


# ─── 1. model ────────────────────────────────────────────────────────────────
edit("model -> gpt-4o-mini",
     'MODEL = "gpt-4o"                    # swap freely; temperature is guarded below',
     'MODEL = "gpt-4o-mini"               # swap freely; temperature is guarded below\n'
     '# Back to mini now that retrieval is fixed. If sentence building gets sloppy,\n'
     '# "gpt-4o" is a one-word change back: mini is weaker at holding several ordering\n'
     '# rules in mind at once, which is where it failed last time.')

# ─── 2. context mode ─────────────────────────────────────────────────────────
edit("context mode -> retrieve",
     'CONTEXT_MODE = "auto"',
     '# Pinned to retrieve, not auto. On "auto" the app posts the whole corpus whenever\n'
     '# it fits under FULL_CONTEXT_CHARS, and 350,000 characters is about 87k tokens —\n'
     '# which would fit mini\'s 128k window on paper, then fail the moment the prompt and\n'
     '# history are added on top. Retrieval is also what the fixes below repair.\n'
     'CONTEXT_MODE = "retrieve"')

# ─── 3. the budget ───────────────────────────────────────────────────────────
edit("retrieval budget",
     'EXACT_RESERVE = 20           # of those, held for literal word matches so that a\n'
     '                             # passage containing the asked-for word always gets in\n'
     'MAX_PASSAGES = 20            # retrieval mode: total passages per question, after merging',
     'EXACT_RESERVE = 12           # a SLICE held for literal word matches, not the whole\n'
     '                             # budget. It was 20 against MAX_PASSAGES 20, and the call\n'
     '                             # site doubled it, so exact matching could take every slot\n'
     '                             # and the meaning search never ran at all.\n'
     'MAX_PASSAGES = 40            # retrieval mode: total passages per question, after merging.\n'
     '                             # Back up from 20 now that the rate limit is lifted. More\n'
     '                             # passages is the other half of "it does not know what it\n'
     '                             # has", and on mini the extra tokens cost very little.')

# ─── 4. exact_hits: token matching, rarest needle first ──────────────────────
OLD_EXACT = '''def exact_hits(query, chunks, per_term=4):
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
    return picks'''

NEW_EXACT = '''def exact_hits(query, chunks, lexicon=None, per_term=3):
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
    WORDCHAR = r"\\wɛɔŋʉɨ"          # \\w plus the Kenyang letters
    for t in sorted(needles, key=len, reverse=True):
        pat = re.compile(rf"(?<![{WORDCHAR}]){re.escape(t)}(?![{WORDCHAR}])", re.I)
        n = 0
        for i, c in enumerate(chunks):
            if pat.search(c["text"]):
                picks.append(i)
                n += 1
                if n >= per_term:
                    break
    return picks'''
edit("exact_hits -> token matching", OLD_EXACT, NEW_EXACT)

# ─── 5. the call site ────────────────────────────────────────────────────────
edit("exact_hits call site",
     '    _merge(exact_hits(query, chunks), picked, seen, min(room, EXACT_RESERVE * 2))',
     '    _merge(exact_hits(query, chunks, lexicon), picked, seen, min(room, EXACT_RESERVE))')

# ─── 6. one model call instead of two ────────────────────────────────────────
OLD_ROUND = '''            probe = client.chat.completions.create(
                **params, tools=tools.TOOLS, tool_choice="auto")

            # run whatever it asked for; api_messages comes back with the results
            api_messages, used_tools = tools.run_tool_calls(
                probe, api_messages, chunks, vectors, lexicon,
                search, word_index, rule_book)

            st.session_state.last_tool_round = used_tools
            if used_tools:
                params["messages"] = api_messages     # point at the enriched thread

            stream = client.chat.completions.create(
                **params, stream=True, tools=tools.TOOLS, tool_choice="auto")
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
                    painted = len(reply)'''

NEW_ROUND = '''            # Round 1. Tools are on offer, so this one cannot stream.
            probe = client.chat.completions.create(
                **params, tools=tools.TOOLS, tool_choice="auto")

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
                        painted = len(reply)'''
edit("two model calls -> one when no tool is used", OLD_ROUND, NEW_ROUND)


# ─── apply ───────────────────────────────────────────────────────────────────
def main():
    try:
        text = open(SRC, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit(f"{SRC} not found. Run this from the repo root.")

    for name, old, _new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"STOPPED, nothing changed.\n"
                     f"  '{name}' matched {n} times, expected exactly 1.\n"
                     f"  Your file differs from the one I read. Send it to me again.")

    shutil.copy(SRC, SRC + ".backup")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)

    compile(text, SRC, "exec")          # syntax check before we claim success
    print(f"backup written: {SRC}.backup")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nsyntax OK. Now:  streamlit run streamlit_app.py")


if __name__ == "__main__":
    main()
