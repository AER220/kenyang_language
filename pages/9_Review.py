"""
pages/9_🔍_Review.py — where I read what speakers have sent, and turn the good
ones into text I can paste into kenyang_verified_speaker.md.

This page is for me, not for learners. It is behind a password because the
submissions contain people's names and villages, and because approving a
correction changes what Nɛpɛ́m teaches everybody.

Set the password as the environment variable REVIEW_PASSWORD (Render), or in
.streamlit/secrets.toml (my Codespace):

    review_password = "something only I know"

With neither set, the page says review is not configured and lets nobody in.

Nothing here writes to the verified file automatically. I read, I decide, I
paste. A community loop that edits the knowledge base on its own would undo the
one promise this project makes.
"""

import json

import streamlit as st
import community
import recordings
from build_audio_manifest import fold
from settings import all_secrets, secret

st.set_page_config(page_title="Review · Nɛpɛ́m", page_icon="🔍", layout="wide")

st.markdown("""
<style>
  #MainMenu, footer, [data-testid="stToolbar"]{display:none !important;}
  .block-container{padding-top:2.2rem; max-width:1100px;}
</style>
""", unsafe_allow_html=True)


# ── the gate ─────────────────────────────────────────────────────────────────
def unlocked():
    want = secret("review_password", env="REVIEW_PASSWORD")
    if not want:
        st.error("Review is not configured on this server. Set REVIEW_PASSWORD "
                 "before using this page.")
        st.caption("Without it anybody could read contributors' names and "
                   "change what Nɛpɛ́m teaches.")
        return False
    if st.session_state.get("review_ok"):
        return True
    st.markdown("**Only for verified contributors.**")
    st.caption("Submissions carry people's names and villages, and approving "
               "one changes what Nɛpɛ́m teaches everybody. If you have taught "
               "Nɛpɛ́m something and would like to help review, write to "
               "agboredouard51@gmail.com.")
    got = st.text_input("Password", type="password")
    if got and got == want:
        st.session_state.review_ok = True
        st.rerun()
    elif got:
        st.error("Not that one.")
    return False


if not unlocked():
    st.stop()

st.title("What speakers have sent")

rows, where = community.load(all_secrets())


# ── what is in there ─────────────────────────────────────────────────────────
def status_of(r):
    return str(r.get("status", "new") or "new").lower()

new = [r for r in rows if status_of(r) == "new"]
ok = [r for r in rows if status_of(r) == "approved"]
no = [r for r in rows if status_of(r) == "rejected"]

a, b, c, d = st.columns(4)
a.metric("Waiting for me", len(new))
b.metric("Approved", len(ok))
c.metric("Set aside", len(no))
d.metric("All of it", len(rows))
# Only the local file is at risk. The database and the sheet both survive the
# app sleeping, and warning about them was my mistake.
if where in ("database", "sheet"):
    st.caption(f"Reading from the {where}. This survives the app sleeping.")
else:
    st.caption("⚠️ Reading from the container's disk, which Streamlit wipes "
               "when the app sleeps. Check the [supabase] block in secrets.")

st.divider()

# ── the queue ────────────────────────────────────────────────────────────────
tab_rec, tab_new, tab_all, tab_out = st.tabs(
    ["Recordings", "Waiting for me", "Everything", "Export"])

KIND_LABEL = {"correction": "Nɛpɛ́m was wrong",
              "new_word": "a word it did not have",
              "issue": "something else"}


def show(r, allow_decide=True, tab=""):
    """
    Render one submission.

    `tab` exists because the same row appears in both "Waiting for me" and
    "Everything". Streamlit keys widgets by their key string, so two buttons
    built from the same submission id crash the page with a duplicate key.
    Prefixing with the tab name makes them distinct.
    """
    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(f"**{KIND_LABEL.get(r.get('kind'), r.get('kind'))}**")
        top[1].caption(str(r.get("at", ""))[:16].replace("T", " "))

        if r.get("question"):
            st.markdown(f"**Asked:** {r['question']}")
        if r.get("answer"):
            st.markdown("**Nɛpɛ́m answered:**")
            st.code(r["answer"], language=None)
        if r.get("correction"):
            st.markdown(f"**A speaker says it is:** `{r['correction']}`")
        if r.get("note"):
            st.markdown(f"**Why:** {r['note']}")

        who = " · ".join(x for x in [r.get("speaker"), r.get("village")] if x)
        if who:
            st.caption(f"From {who}")

        if allow_decide:
            yes, nope = st.columns(2)
            if yes.button("Approve", key=f"y{tab}{r['id']}", type="primary",
                          use_container_width=True):
                community.set_status(r["id"], "approved", all_secrets())
                st.rerun()
            if nope.button("Set aside", key=f"n{tab}{r['id']}",
                           use_container_width=True):
                community.set_status(r["id"], "rejected", all_secrets())
                st.rerun()


# ── recordings ───────────────────────────────────────────────────────────────
# Nothing a contributor recorded can be played by anybody but me until I press
# Approve, and Approve only appears once I have pressed Listen. I cannot be
# made to hear it to the end, but I cannot approve what I have not opened.

VOICE = {"man": "a man's voice", "woman": "a woman's voice", "unsaid": "voice not said"}


def rec_store():
    cfg = community._with_env(all_secrets()).get("supabase") or {}
    return recordings.store_from(cfg)


def my_own_words():
    """The folded words in my own manifest. Mine play wherever both have one."""
    try:
        with open("audio/manifest.json", encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def how_captured(r):
    c = r.get("capture") or {}
    off = lambda k: {False: "off", True: "ON"}.get(c.get(k), "not reported")
    rate = f"{(r.get('sample_rate') or 0) / 1000:g} kHz" if r.get("sample_rate") else "rate unknown"
    secs = f"{(r.get('duration_ms') or 0) / 1000:.1f} s"
    return (f"{secs} · {rate} · echo cancellation {off('echoCancellation')} · "
            f"noise suppression {off('noiseSuppression')} · "
            f"automatic volume {off('autoGainControl')}")


def spelling_warning(spelling):
    """Warn, never block: a spelling no verified file has, or with marks Ed's own
    recording does not use, becomes 'confirmed' the moment it is approved, and the
    chat's flag stops warning about it. A new word is the normal case; a typo approved
    once becomes truth. So: look before approving."""
    if not spelling.strip():
        return
    problems = recordings.spelling_check(spelling, st.session_state.get("own_words", ()))
    if not problems:
        return
    lines = []
    for word, why, near in problems:
        line = f"**{word}**: {why}."
        if near:
            line += " Closest: " + ", ".join(f"**{n}**" for n in near) + "."
        lines.append(line)
    st.warning("Look before approving: once approved, this spelling counts as confirmed "
               "and the chat stops flagging it.\n\n" + "\n\n".join(f"- {l}" for l in lines))


def show_recording(store, r, mine):
    rid = r["id"]
    heard = st.session_state.setdefault("heard", {})
    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(f"**{r['typed_kenyang']}**"
                        + (f" · {r['typed_english']}" if r.get("typed_english") else ""))
        top[1].caption(str(r.get("created_at", ""))[:16].replace("T", " "))

        who = " · ".join(x for x in [r.get("speaker"), r.get("village"),
                                     VOICE.get(r.get("voice"), "")] if x)
        st.caption(f"From {who}")
        st.caption("Speech tools: " + ("yes, they ticked the second box"
                   if r.get("consent_speech_tools") else "no") + " · " + how_captured(r))
        try:
            sent, ok = recordings.voice_counts(store, r["speaker_code"])
            if sent > 1:
                st.caption(f"This voice has sent {sent} recordings, {ok} approved.")
        except recordings.Trouble:
            pass
        if r.get("note"):
            st.markdown(f"**Their sentence:** {r['note']}")

        if rid not in heard:
            if st.button("Listen", key=f"listen{rid}", type="primary"):
                try:
                    heard[rid] = recordings.pending_audio(store, rid)
                except recordings.Trouble as e:
                    st.error(f"The recording could not be fetched: {e}")
                    return
                st.rerun()
            return

        st.audio(heard[rid], format="audio/wav")
        spelling = st.text_input("The Kenyang, spelled as it should be",
                                 value=r["typed_kenyang"], key=f"ken{rid}")
        try:
            word = recordings.word_for(store, spelling) if spelling.strip() else None
        except recordings.Trouble as e:
            st.error(f"Could not check the words table: {e}")
            return
        english = st.text_input(
            "The English", key=f"en{rid}",
            value=word["english"] if word else r.get("typed_english", ""))
        if word:
            st.info(f"**{word['kenyang']}** is already a word ({word['english'] or 'no English'}). "
                    "Approving adds this voice to it.")
            if english.strip() and english.strip() != word["english"]:
                st.warning(f"Approving will change its English from "
                           f"“{word['english']}” to “{english.strip()}”.")
        if fold(spelling) in mine:
            st.caption("You have recorded this word yourself. Yours stays the one "
                       "that plays; this one is kept beside it.")
        spelling_warning(spelling)

        # Off by default. Ticked, approving counts this as Ed's own recording for the
        # pictures; other speakers' recordings never count there, whatever is ticked.
        mine = st.checkbox("This recording is mine, in my own voice", value=False,
                           key=f"mine{rid}",
                           help="Only your own recordings move a word up on the pictures.")
        yes, nope = st.columns(2)
        if yes.button("Approve", key=f"ok{rid}", type="primary", use_container_width=True,
                      disabled=not spelling.strip()):
            try:
                recordings.approve(store, r, spelling, english)
                if mine:
                    recordings.mark_mine(store, r, True)
            except recordings.Trouble as e:
                st.error(f"Not approved: {e}")
                return
            heard.pop(rid, None)
            st.rerun()
        if nope.button("Set aside", key=f"no{rid}", use_container_width=True):
            try:
                recordings.reject(store, r)
            except recordings.Trouble as e:
                st.error(f"Not set aside: {e}")
                return
            heard.pop(rid, None)
            st.rerun()


def show_approved(store, r, own_ids=None):
    rid = r["id"]
    left, right = st.columns([4, 1])
    if own_ids is not None:
        was = rid in own_ids
        now = left.checkbox("Mine, in my own voice", value=was, key=f"own{rid}")
        if now != was:
            try:
                recordings.mark_mine(store, r, now)
                st.rerun()
            except recordings.Trouble as e:
                st.error(f"Not changed: {e}")
    left.markdown(f"**{r['typed_kenyang']}** "
                  + ("· primary " if r.get("is_primary") else "")
                  + f"· {r.get('speaker') or 'unnamed'} · "
                  + str(r.get("decided_at", ""))[:10])
    if not st.session_state.get(f"sure{rid}"):
        if right.button("Remove", key=f"rm{rid}"):
            st.session_state[f"sure{rid}"] = True
            st.rerun()
    else:
        st.warning("This deletes the recording for good and takes it off the site.")
        a, b = st.columns(2)
        if a.button("Remove it for good", key=f"rm2{rid}", type="primary"):
            try:
                recordings.remove(store, r)
            except recordings.Trouble as e:
                st.error(f"Not removed: {e}")
            st.session_state.pop(f"sure{rid}", None)
            st.rerun()
        if b.button("Keep it", key=f"keep{rid}"):
            st.session_state.pop(f"sure{rid}", None)
            st.rerun()


with tab_rec:
    try:
        store = rec_store()
        queue = recordings.pending(store)
    except recordings.Trouble as e:
        store = None
        st.error(f"The recordings could not be read: {e}")
    if store is not None:
        if not queue:
            st.success("No recordings waiting.")
        else:
            st.caption(f"{len(queue)} waiting. Press Listen to hear one; "
                       "Approve appears once you have.")
        mine = my_own_words()
        # the words of recordings marked as Ed's: the spelling check counts them as his
        try:
            ids = recordings.eds_ids(store)
            st.session_state.own_words = [w["kenyang"] for w in recordings.eds_words(
                recordings.words(store), recordings.approved(store), ids)] if ids else []
        except recordings.Trouble:
            st.session_state.own_words = []
        for r in queue:
            show_recording(store, r, mine)

        with st.expander("Approved recordings, and removing one"):
            st.caption("For when somebody asks for their recording to be removed.")
            try:
                done = recordings.approved(store)
            except recordings.Trouble as e:
                done = []
                st.error(f"Could not read them: {e}")
            if not done:
                st.caption("None approved yet.")
            try:
                own_ids = recordings.eds_ids(store)
            except recordings.Trouble as e:
                own_ids = None
                st.error(f"Could not read which recordings are yours: {e}")
            if own_ids is None:
                st.info("To mark recordings as your own, run the SQL in CLAUDE.md "
                        "(\"Ed's own recordings\") once in Supabase.")
            for r in reversed(done):
                show_approved(store, r, own_ids)

        with st.expander("Correct a word's spelling or English"):
            st.caption("The recordings stay as they are; only the word changes, and "
                       "the public files are rebuilt. A word already pasted into the "
                       "knowledge base comes back in Export, marked as corrected.")
            try:
                all_words = recordings.words(store)
            except recordings.Trouble as e:
                all_words = []
                st.error(f"Could not read the words: {e}")
            if all_words:
                pick = st.selectbox("Word", all_words, key="fixword",
                                    format_func=lambda w: f"{w['kenyang']} · {w['english']}")
                new_ken = st.text_input("Kenyang", value=pick["kenyang"], key=f"fk{pick['id']}")
                new_en = st.text_input("English", value=pick["english"], key=f"fe{pick['id']}")
                spelling_warning(new_ken)
                if st.button("Save", key="fixsave",
                             disabled=(new_ken, new_en) == (pick["kenyang"], pick["english"])):
                    try:
                        recordings.edit_word(store, pick, new_ken, new_en)
                        st.success("Saved, and the public files rebuilt.")
                    except recordings.Trouble as e:
                        st.error(f"Not saved: {e}")

        # A phone curls apostrophes whatever is typed, so a correction typed on one can
        # look identical to the old spelling. This finds every stored spelling with a
        # phone's characters in it and straightens them, only when the button is pressed.
        try:
            messy = recordings.unclean_words(recordings.words(store))
        except recordings.Trouble as e:
            messy = []
            st.error(f"Could not check the spellings: {e}")
        if messy:
            with st.expander(f"{len(messy)} stored spelling"
                             f"{'' if len(messy) == 1 else 's'} with a phone's characters"):
                st.caption("Curly apostrophes, curly quotes, dashes and invisible spaces, "
                           "which phones put in. Nothing changes until you press the button.")
                for w, k, e in messy:
                    changed = [x for x in (("Kenyang", w["kenyang"], k),
                                           ("English", w.get("english") or "", e)) if x[1] != x[2]]
                    st.markdown(" · ".join(f"{name}: `{old}` → `{new}`" for name, old, new in changed))
                if st.button(f"Straighten {'it' if len(messy) == 1 else 'all ' + str(len(messy))}",
                             key="straighten", type="primary"):
                    done, failed = recordings.clean_stored(store, messy)
                    if done:
                        st.success(f"Straightened {done}, and the public files rebuilt.")
                    for spelling, why in failed:
                        st.error(f"{spelling}: not saved. {why}")
                    if not failed:
                        st.rerun()

        st.divider()
        st.caption("The public list and manifest are rebuilt after every decision. "
                   "If one ever failed part way, this rebuilds them from the tables.")
        if st.button("Rebuild the public files"):
            try:
                m, listed = recordings.rebuild_public(store)
                st.success(f"Rebuilt: {len(m)} words in the manifest, "
                           f"{len(listed)} in the list.")
            except recordings.Trouble as e:
                st.error(f"Not rebuilt: {e}")


with tab_new:
    if not rows:
        st.info("Nothing yet. When somebody corrects Nɛpɛ́m or teaches it a word, "
                "it lands here.")
        st.caption(f"Reading from the {where}.")
    elif not new:
        st.success("Nothing waiting.")
    for r in reversed(new):
        show(r, tab="new")

with tab_all:
    only = st.multiselect("Show", ["new", "approved", "rejected"],
                          default=["new", "approved", "rejected"])
    for r in reversed(rows):
        if status_of(r) in only:
            show(r, allow_decide=status_of(r) == "new", tab="all")

with tab_out:
    # The recorded words first: every approved word not yet in the knowledge
    # base, or whose spelling has changed since it was pasted. This only makes
    # text. Nothing writes to the knowledge base but me.
    st.subheader("Recorded words to paste into the verified file")
    try:
        _st = rec_store()
        md_rec, todo = recordings.paste_block(recordings.words(_st), recordings.approved(_st))
    except recordings.Trouble as e:
        md_rec, todo = "", None
        st.error(f"The recorded words could not be read: {e}")
    if todo == []:
        st.info("Every recorded word is already in the knowledge base, as far as "
                "this page has been told.")
    elif todo:
        st.caption(f"{len(todo)} word(s). Paste this at the end of "
                   "knowledge_base/kenyang_verified_speaker.md, run build_index.py "
                   "and push. Then press the button below, so they are not offered again.")
        st.code(md_rec, language="markdown")
        if st.button("I have pasted these"):
            try:
                recordings.mark_pasted(_st, todo)
                st.rerun()
            except recordings.Trouble as e:
                st.error(f"Not marked: {e}")
    st.divider()

    st.subheader("Paste this into the verified file")
    md, n = community.to_markdown(rows)
    if not n:
        st.info("Approve something first and it will appear here, written the "
                "way kenyang_verified_speaker.md expects.")
    else:
        st.caption(f"{n} approved submission(s), written out below. Paste it at "
                   "the end of knowledge_base/kenyang_verified_speaker.md, then "
                   "run build_index.py and push.")
        st.code(md, language="markdown")
        st.download_button("Download it", md, file_name="community_additions.md",
                           mime="text/markdown")

    st.divider()
    st.subheader("Everything, as a spreadsheet")
    import io, csv
    buf = io.StringIO()
    cols = ["id", "at", "kind", "question", "answer", "correction", "note",
            "speaker", "village", "source", "status"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    st.download_button("Download the lot as CSV", buf.getvalue(),
                       file_name="community_submissions.csv", mime="text/csv")