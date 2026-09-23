"""
pages/8_Teach.py — a page of its own, so nothing in streamlit_app.py has to change.

Why a separate page rather than a box under every reply
-------------------------------------------------------
Putting it inline would be better for a speaker who has just watched Nɛpɛm get
something wrong: they could fix it right there. But it means editing the middle
of a 1,700 line file that is currently working, and a broken tutor is worse than
a slightly less convenient correction form.

So this comes first. Once the storage is proven and I can see submissions
landing, moving it inline is a small change.

This page also catches words handed over from the website's Words of the Week,
which arrive as ?mode=teach&word=sleep.
"""

import html
import streamlit as st

import community

st.set_page_config(page_title="Teach Nɛpɛm", page_icon="🌿", layout="centered")

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

st.title("Teach Nɛpɛm")
st.markdown(
    '<p class="lead">If you speak Kenyang, you know things Nɛpɛm does not. '
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
    ["A word Nɛpɛm does not have", "Nɛpɛm said something wrong"],
    horizontal=False,
    index=0 if prefill_en else 0,
)
is_new = kind.startswith("A word")

with st.form("teach", clear_on_submit=True):
    if is_new:
        english = st.text_input("What does it mean, in English?",
                                value=prefill_en, placeholder="tomorrow")
        kenyang = st.text_input("And in Kenyang?",
                                placeholder="write it the way you say it")
        answer = ""
        note = st.text_area(
            "Anything worth knowing about it?", height=90,
            placeholder="who says it, when you would use it, whether it "
                        "changes when there is more than one")
    else:
        english = st.text_input("What did you ask him?",
                                placeholder="how do you say tell them I am going to church")
        answer = st.text_area("What did he say?", height=80,
                              placeholder="paste his answer here")
        kenyang = st.text_input("What should it have been?",
                                placeholder="ghati bho bɛ mme rong ekeré-Mandɛm")
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

if sent:
    if not kenyang.strip():
        st.warning("Nothing was sent. The Kenyang is the part I need.")
    else:
        rec = community.make(
            "new_word" if is_new else "correction",
            question=english, answer=answer, correction=kenyang, note=note,
            speaker=speaker, village=village,
            source="words of the week" if prefill_en else "teach page")
        durable, notes = community.save(rec, dict(st.secrets))

        if durable:
            st.success(f"Thank you. **{kenyang.strip()}** is written down now. "
                       "I read every one of these myself before Nɛpɛm teaches it.")
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
st.caption("Nothing sent here changes what Nɛpɛm teaches until I have read it. "
           "That is deliberate. A tool that learns from everybody learns "
           "everybody's mistakes too.")
