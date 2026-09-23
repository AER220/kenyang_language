"""
pages/9_🔍_Review.py — where I read what speakers have sent, and turn the good
ones into text I can paste into kenyang_verified_speaker.md.

This page is for me, not for learners. It is behind a password because the
submissions contain people's names and villages, and because approving a
correction changes what Nɛpɛm teaches everybody.

Put this in secrets:

    review_password = "something only I know"

Nothing here writes to the verified file automatically. I read, I decide, I
paste. A community loop that edits the knowledge base on its own would undo the
one promise this project makes.
"""

import streamlit as st
import community

st.set_page_config(page_title="Review · Nɛpɛm", page_icon="🔍", layout="wide")

st.markdown("""
<style>
  #MainMenu, footer, [data-testid="stToolbar"]{display:none !important;}
  .block-container{padding-top:2.2rem; max-width:1100px;}
</style>
""", unsafe_allow_html=True)


# ── the gate ─────────────────────────────────────────────────────────────────
def unlocked():
    want = st.secrets.get("review_password")
    if not want:
        st.error("Set review_password in secrets before using this page.")
        st.caption("Without it anybody could read contributors' names and "
                   "change what Nɛpɛm teaches.")
        return False
    if st.session_state.get("review_ok"):
        return True
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

rows, where = community.load(dict(st.secrets))
if not rows:
    st.info("Nothing yet. When somebody corrects Nɛpɛm or teaches it a word, "
            "it lands here.")
    st.caption(f"Reading from the {where}.")
    st.stop()


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
tab_new, tab_all, tab_out = st.tabs(["Waiting for me", "Everything", "Export"])

KIND_LABEL = {"correction": "Nɛpɛm was wrong",
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
            st.markdown("**Nɛpɛm answered:**")
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
                community.set_status(r["id"], "approved", dict(st.secrets))
                st.rerun()
            if nope.button("Set aside", key=f"n{tab}{r['id']}",
                           use_container_width=True):
                community.set_status(r["id"], "rejected", dict(st.secrets))
                st.rerun()


with tab_new:
    if not new:
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