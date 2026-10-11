"""
Fix the 400 that breaks counting.

    An assistant message with 'tool_calls' must be followed by tool messages
    responding to each 'tool_call_id'.

The model asked for FOUR lookups in one turn. Something in run_tool_calls
answered fewer than four, and OpenAI rejects the whole thread when even one
request is left hanging. Counting is the question that triggers it, because
counting is what makes the model want several lookups at once.

Three changes, all inside streamlit_app.py, none of them touching tools.py:

  1. ensure_tool_replies()  walks the thread before it is sent and writes a
                            plain "did not run" reply for any tool call that
                            has none. The thread then always validates.
  2. round two declares the tools again, with tool_choice="none". Declaring
     them keeps the history consistent with the request; "none" stops a second
     round of calls that a stream cannot answer. My last patch dropped the
     declaration, which did not cause the error but did not help it either.
  3. if round two is still rejected, it retries once from the clean thread with
     no tool history at all. A learner gets an answer from the retrieved
     passages instead of a 400.

Run from the repo root, after patch_tonight.py:

    python patch_toolfix.py

It asserts every edit and writes a .backup first.
"""
import shutil
import sys

SRC = "streamlit_app.py"
EDITS = []


def edit(name, old, new):
    EDITS.append((name, old, new))


# ─── 1. the guard, added just above section 6 ────────────────────────────────
ANCHOR = '''# =============================================================================
# 6. APP
# ============================================================================='''

HELPER = '''# =============================================================================
# TOOL THREAD REPAIR
# =============================================================================
# OpenAI rejects a conversation in which an assistant message asked for tool
# calls and any single one of them has no reply:
#
#   "An assistant message with 'tool_calls' must be followed by tool messages
#    responding to each 'tool_call_id'."
#
# That is a 400 for the whole turn, and the learner sees an error instead of an
# answer. It showed up on "count from one to ten", because counting is the
# question that makes the model ask for several lookups at once: four requests
# went out, fewer came back answered, and the turn died.
#
# Rather than guess at why one went unanswered, this walks the thread and writes
# a plain reply for any request that has none. The model is told the lookup did
# not run, which is true, and answers from the retrieved passages instead. An
# honest gap beats a crash.


def _role_of(msg):
    return msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "")


def _tool_call_ids(msg):
    """Every tool_call_id an assistant message asked for. Dict or object."""
    calls = (msg.get("tool_calls") if isinstance(msg, dict)
             else getattr(msg, "tool_calls", None))
    out = []
    for c in calls or []:
        cid = c.get("id") if isinstance(c, dict) else getattr(c, "id", None)
        if cid:
            out.append(cid)
    return out


def ensure_tool_replies(messages):
    """
    Return the thread with a reply for every tool call that is missing one.

    Walks in order: an assistant message that asked for tools is followed by its
    tool replies, so anything still unanswered when the run of tool messages ends
    gets a stub.
    """
    out, i, repaired = [], 0, 0
    while i < len(messages):
        msg = messages[i]
        out.append(msg)
        i += 1
        wanted = _tool_call_ids(msg)
        if not wanted:
            continue
        answered = set()
        while i < len(messages) and _role_of(messages[i]) == "tool":
            reply_msg = messages[i]
            rid = (reply_msg.get("tool_call_id") if isinstance(reply_msg, dict)
                   else getattr(reply_msg, "tool_call_id", None))
            if rid:
                answered.add(rid)
            out.append(reply_msg)
            i += 1
        for cid in wanted:
            if cid not in answered:
                out.append({"role": "tool", "tool_call_id": cid,
                            "content": "No result: that lookup did not run. "
                                       "Answer from the passages you were given, "
                                       "and say plainly if something is missing."})
                repaired += 1
    if repaired:
        st.session_state.tool_replies_repaired = repaired
    return out


'''
edit("add ensure_tool_replies", ANCHOR, HELPER + ANCHOR)

# ─── 2. keep a clean copy of the thread ──────────────────────────────────────
edit("keep the pre-tool thread",
     '''        api_messages = ([{"role": "system", "content": STATIC_CONTEXT},
                         {"role": "system", "content": turn_context}] + history)''',
     '''        api_messages = ([{"role": "system", "content": STATIC_CONTEXT},
                         {"role": "system", "content": turn_context}] + history)
        # Kept aside before the tool round touches it, so a rejected tool thread
        # has something clean to fall back to instead of showing a 400.
        clean_messages = list(api_messages)''')

# ─── 3. round two: declare tools, forbid new calls, repair, fall back ────────
edit("round two: repair the thread and fall back",
     '''            else:
                # It asked for a lookup. Stream the real answer with the tool
                # output in view. Tools are NOT offered again: one lookup round is
                # enough, and leaving them on invites a second request mid-stream,
                # which a stream cannot answer.
                params["messages"] = api_messages
                stream = client.chat.completions.create(**params, stream=True)''',
     '''            else:
                # It asked for a lookup. Stream the real answer with the tool output
                # in view.
                #
                # The tools are DECLARED again but tool_choice is "none": declaring
                # them keeps the request consistent with a history that contains tool
                # calls, and "none" stops a second round of requests that a stream
                # cannot answer.
                #
                # ensure_tool_replies fills in any lookup that went unanswered. Without
                # it the API rejects the whole turn, which is what broke counting.
                params["messages"] = ensure_tool_replies(api_messages)
                try:
                    stream = client.chat.completions.create(
                        **params, stream=True,
                        tools=tools.TOOLS, tool_choice="none")
                except Exception:
                    # The tool thread was still refused. Answer from the clean one
                    # rather than show the learner an error code.
                    st.session_state.tool_thread_dropped = True
                    params["messages"] = clean_messages
                    stream = client.chat.completions.create(**params, stream=True)''')


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
                     f"  Did patch_tonight.py run first? If it did, send me the file.")

    shutil.copy(SRC, SRC + ".backup2")
    for name, old, new in EDITS:
        text = text.replace(old, new, 1)
    open(SRC, "w", encoding="utf-8").write(text)
    compile(text, SRC, "exec")
    print(f"backup written: {SRC}.backup2")
    for name, _o, _n in EDITS:
        print(f"  applied: {name}")
    print("\nsyntax OK. Now:  streamlit run streamlit_app.py")
    print("Then ask it to count from one to ten.")


if __name__ == "__main__":
    main()
