"""
pages/8_Teach.py — a page of its own, so nothing in streamlit_app.py has to change.

Why a separate page rather than a box under every reply
-------------------------------------------------------
Putting it inline would be better for a speaker who has just watched Nɛpɛ́m get
something wrong: they could fix it right there. But it means editing the middle
of a 1,700 line file that is currently working, and a broken tutor is worse than
a slightly less convenient correction form.

So this comes first. Once the storage is proven and I can see submissions
landing, moving it inline is a small change.

This page also catches words handed over from the website's Words of the Week,
which arrive as ?mode=teach&word=sleep.
"""

import html
import unicodedata
import streamlit as st

import community
from settings import all_secrets

st.set_page_config(page_title="Teach Nɛpɛ́m", page_icon="🌿", layout="centered")

INK, GOLD, LEAF, PINK = "#243029", "#B07D2B", "#1B6B4C", "#B0517D"

st.markdown(f"""
<style>
  #MainMenu, footer, [data-testid="stToolbar"]{{display:none !important;}}
  .block-container{{padding-top:2rem; max-width:760px;}}
  .lead{{font-size:1.02rem; line-height:1.65; color:#4A5A50;}}
  .callout{{padding:14px 18px;border-radius:14px;margin:0 0 1.2rem;
            background:rgba(176,81,125,.07);border:1px solid rgba(176,81,125,.25);}}
  .callout p{{margin:0;}}
  .eyebrow{{font-size:.76rem;letter-spacing:.09em;color:{PINK};margin:0 0 3px !important;}}
</style>
""", unsafe_allow_html=True)

st.title("Teach Nɛpɛ́m")
st.markdown(
    '<p class="lead">If you speak Kenyang, you know things Nɛpɛ́m does not. '
    'A word he is missing, or an answer he got wrong. Put it here and it comes '
    'to me. I read every one before he teaches it to anybody, which is why he '
    'can be trusted with a child.</p>',
    unsafe_allow_html=True)


# ── a word sent over from the website ────────────────────────────────────────
# The Words of the Week board links here with the word already chosen, so a
# speaker only has to type the Kenyang.
prefill_en = ""
q = st.query_params
if q.get("mode") == "teach" and q.get("word"):
    prefill_en = q.get("word")
    st.markdown(
        f'<div class="callout"><p class="eyebrow">ONE OF THIS WEEK\'S SIX</p>'
        f'<p>You said you know the Kenyang for '
        f'<b>{html.escape(prefill_en)}</b>.</p></div>',
        unsafe_allow_html=True)


kind = st.radio(
    "What are you telling me?",
    ["A word Nɛpɛ́m does not have", "Nɛpɛ́m said something wrong"],
    horizontal=False,
    index=0 if prefill_en else 0,
)
is_new = kind.startswith("A word")

with st.form("teach", clear_on_submit=True):
    if is_new:
        # The language comes first in each label, and each box holds an example:
        # Ed typed the Kenyang into the English box three times in a row.
        english = st.text_input("**ENGLISH** · what it means",
                                value=prefill_en, placeholder="for example: house")
        kenyang = st.text_input("**KENYANG** · how you say it",
                                placeholder="for example: ɛkɛt")
        answer = ""
        note = st.text_area(
            "Anything worth knowing about it?", height=90,
            placeholder="who says it, when you would use it, whether it "
                        "changes when there is more than one")
    else:
        english = st.text_input("What did you ask him?",
                                placeholder="for example: how do you say tell them "
                                            "I am going to church")
        answer = st.text_area("What did he say?", height=80,
                              placeholder="paste his answer here")
        kenyang = st.text_input("**KENYANG** · what he should have said",
                                placeholder="for example: ghati bho bɛ mme rong "
                                            "ekeré-Mandɛm")
        note = st.text_area(
            "Why is his version wrong? This is the part I most need.", height=90,
            placeholder="angati is only for passing a message through somebody "
                        "else. One telling needs just ghati.")

    st.caption("Spelling can be tidied up later. Getting it written down at all "
               "is the hard part.")

    a, b = st.columns(2)
    speaker = a.text_input("Your name, if you would like the credit")
    village = b.text_input("Your village, if you like")

    sent = st.form_submit_button("Send it to Ed", type="primary",
                                 use_container_width=True)

# Kenyang in the English box: ɛ, ɔ, ŋ or a tone mark are never English. The
# website checks more (recorded words, English glosses), and the Review page
# flags an English word in the Kenyang box before anything is approved.
def kenyang_letters(text):
    return any(c in "ɛɔŋƐƆŊ" or unicodedata.category(c) == "Mn"
               for c in unicodedata.normalize("NFD", text or ""))


if sent:
    if not kenyang.strip():
        st.warning("Nothing was sent. The Kenyang is the part I need.")
    elif is_new and kenyang_letters(english) and not kenyang_letters(kenyang):
        st.warning(
            f"Nothing was sent. **{english.strip()}** is in the English box, and it "
            f"looks like Kenyang. The English box is for what the word means; the "
            f"Kenyang box is for how you say it. Please put them in again, the "
            f"other way round.")
    else:
        rec = community.make(
            "new_word" if is_new else "correction",
            question=english, answer=answer, correction=kenyang, note=note,
            speaker=speaker, village=village,
            source="words of the week" if prefill_en else "teach page")
        durable, notes = community.save(rec, all_secrets())

        if durable:
            st.success(f"Thank you. **{kenyang.strip()}** is written down now. "
                       "I read every one of these myself before Nɛpɛ́m teaches it.")
            if prefill_en:
                st.caption("Go back to the website, there are five more this week.")
        else:
            # Do not thank somebody for a contribution that was thrown away.
            st.warning(
                "Saved, but only on this server, which forgets when the app "
                "sleeps. The database is not connected yet. Please also send it "
                "to agboredouard51@gmail.com so it is not lost.")
            with st.expander("what happened to it"):
                for n in notes:
                    st.caption(n)

st.divider()
st.caption("Nothing sent here changes what Nɛpɛ́m teaches until I have read it. "
           "That is deliberate. A tool that learns from everybody learns "
           "everybody's mistakes too.")
