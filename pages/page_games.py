"""
Nɛpɛm Games — Kenyang word games for children.

Built by Agbor Edouard Ransome, Bachou Ntai village.

Design notes, so future-me remembers why this is shaped the way it is:

  * NO API CALLS. Every game is pure logic in the browser. The tutor costs money per
    conversation; the games cost nothing per play, however many children play them. That
    is deliberate — the fun part should be the free part.
  * NO DATABASE. Words live in words.jsonl, recordings in audio/. Both ship with the app.
    Nothing here needs to persist across devices, so a file is not a compromise, it is
    the right answer.
  * DIFFICULTY, NOT AGE. A curious six-year-old and a rusty adult both want "easy".
  * A GAME CANNOT HEDGE. The tutor can say "check with a speaker"; a game states things
    as fact to a child. So flagged words (see build_words.py) are left out by default.

    streamlit run games.py
"""

import base64
import json
import os
import random

import streamlit as st

# Resolve against the project root, so this works whether it is run directly
# (streamlit run games.py) or as a page inside pages/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = _HERE if os.path.exists(os.path.join(_HERE, "words.jsonl")) \
    else os.path.dirname(_HERE)
WORDS_FILE = os.path.join(_ROOT, "words.jsonl")
AUDIO_DIR = os.path.join(_ROOT, "audio")
ROUNDS = 8                      # questions in one round of a game

st.set_page_config(page_title="Nɛpɛm — Games", page_icon="🎮",
                   layout="centered", initial_sidebar_state="collapsed")

# =============================================================================
# LOOK — same palette as the tutor, bigger targets because children use phones
# =============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gentium+Book+Plus:wght@400;700&family=Inter:wght@400;600;700&display=swap');

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
.stDeployButton, [data-testid="stAppDeployButton"]{display:none !important;}
header[data-testid="stHeader"]{background:transparent;}

:root{
  --paper:#FAF6EC; --forest:#0C3B2E; --leaf:#1B6B4C; --ochre:#B07D2B;
  --ink:#243029; --edge:#E7E0CD; --right:#1B6B4C; --wrong:#B4462F;
}
html{color-scheme: light;}
html, body, [data-testid="stAppViewContainer"] *{
  font-family:'Inter','Gentium Book Plus',system-ui,sans-serif;}
[data-testid="stAppViewContainer"]{background:var(--paper); color-scheme:light;}
.block-container{max-width:640px;padding-top:.6rem;padding-bottom:3rem;}

.hero{background:linear-gradient(150deg,var(--forest) 0%,#144A38 55%,var(--leaf) 100%);
  color:#EAFFF5;border-radius:18px;padding:18px 22px 16px;margin:4px 0 14px;}
.hero .name{font-family:'Gentium Book Plus',Georgia,serif;font-size:1.9rem;
  font-weight:700;margin:0;line-height:1;}
.hero .rule{width:40px;height:3px;background:var(--ochre);border-radius:2px;margin:9px 0 8px;}
.hero .tag{color:#C6E9D8;margin:0;font-size:.92rem;}

/* the big Kenyang word or English prompt at the centre of a question */
.prompt{background:#fff;border:1px solid var(--edge);border-radius:16px;
  padding:26px 20px;text-align:center;margin:6px 0 14px;}
.prompt .big{font-family:'Gentium Book Plus',Georgia,serif;font-size:2.4rem;
  font-weight:700;color:var(--forest);line-height:1.15;word-break:break-word;}
.prompt .hint{color:#6B7C73;font-size:.95rem;margin-top:8px;line-height:1.45;}

.scorebar{display:flex;justify-content:space-between;align-items:center;
  color:#5C6D64;font-size:.9rem;margin:2px 2px 10px;}
.verdict{border-radius:14px;padding:13px 16px;margin:10px 0;font-size:1.02rem;
  line-height:1.5;}
.verdict.right{background:#EAF5EF;border:1px solid #B9DCC9;color:#14513A;}
.verdict.wrong{background:#FBEEEA;border:1px solid #E8C4B8;color:#8A3523;}
.verdict b{font-family:'Gentium Book Plus',Georgia,serif;font-size:1.15em;}

.finale{background:#fff;border:1px solid var(--edge);border-radius:16px;
  padding:26px 20px;text-align:center;margin:8px 0 14px;}
.finale .score{font-size:2.6rem;font-weight:700;color:var(--forest);line-height:1;}
.finale .msg{color:#5C6D64;margin-top:8px;}

/* buttons are answer targets here, so they need to be big and thumb-friendly */
.stButton>button{width:100%;border-radius:14px;border:1.5px solid var(--edge);
  background:#fff;color:var(--forest);font-weight:600;font-size:1.05rem;
  padding:.95rem .8rem;min-height:58px;line-height:1.3;}
.stButton>button:hover{border-color:var(--leaf);background:#F2F8F5;color:var(--forest);}
.stButton>button:focus-visible{outline:3px solid var(--leaf);outline-offset:2px;}

.card{background:#fff;border:1px solid var(--edge);border-radius:16px;
  padding:15px 17px;margin-bottom:11px;}
.card h4{margin:0 0 4px;color:var(--forest);font-size:1.06rem;}
.card p{margin:0;color:#5C6D64;font-size:.92rem;line-height:1.45;}
.note{color:#7A8A80;font-size:.85rem;line-height:1.5;}
@media (max-width:640px){
  .block-container{padding-left:.7rem;padding-right:.7rem;}
  .prompt .big{font-size:2rem;}
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# WORDS
# =============================================================================
@st.cache_data(show_spinner=False)
def load_words(include_flagged=False):
    """
    Read words.jsonl. Flagged words stay out unless I deliberately switch them on.

    A flagged word is one where two of my sources disagree, or a phrase whose word order
    contradicts the orthography guide. The tutor can say "a speaker should confirm this";
    a game just tells a child it is so. That difference is why the filter exists.
    """
    if not os.path.exists(WORDS_FILE):
        return [], "missing"
    words = []
    for line in open(WORDS_FILE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            w = json.loads(line)
        except Exception:
            continue
        if w.get("review") and not include_flagged:
            continue
        if w.get("kenyang") and w.get("english"):
            words.append(w)
    return words, "ok"


def pool(words, level):
    """Words at this level. 'Everything' mixes them all."""
    if level == "Everything":
        return list(words)
    got = [w for w in words if w.get("difficulty", "easy").lower() == level.lower()]
    return got or list(words)


def audio_html(filename):
    """
    An audio player for a recording, if the file exists.

    Embedded as base64 so it plays from a single file with no server route, which keeps
    the whole thing deployable as static content.
    """
    path = os.path.join(AUDIO_DIR, filename or "")
    if not filename or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    kind = "mpeg" if filename.lower().endswith(".mp3") else "mp4"
    return (f'<audio controls style="width:100%;margin-top:10px" '
            f'src="data:audio/{kind};base64,{b64}"></audio>')


def have_audio(words):
    return [w for w in words if os.path.exists(os.path.join(AUDIO_DIR, w.get("audio", "")))]


# =============================================================================
# GAME STATE
# =============================================================================
def reset_game():
    for k in ("q", "score", "asked", "answered", "choice", "pairs", "picked", "solved"):
        st.session_state.pop(k, None)


def go(screen, game=None, level=None):
    st.session_state.screen = screen
    if game:
        st.session_state.game = game
    if level:
        st.session_state.level = level
    reset_game()
    st.rerun()


def new_question(words, kind):
    """Pick the answer and three distractors for a multiple-choice question."""
    answer = random.choice(words)
    others = [w for w in words if w["kenyang"] != answer["kenyang"]]
    wrong = random.sample(others, min(3, len(others)))
    options = wrong + [answer]
    random.shuffle(options)
    st.session_state.q = {"answer": answer, "options": options, "kind": kind}
    st.session_state.answered = False
    st.session_state.choice = None


def scorebar():
    asked = st.session_state.get("asked", 0)
    score = st.session_state.get("score", 0)
    st.markdown(f'<div class="scorebar"><span>Question {min(asked + 1, ROUNDS)} '
                f'of {ROUNDS}</span><span>{score} right</span></div>',
                unsafe_allow_html=True)


def finish_screen():
    score = st.session_state.get("score", 0)
    if score == ROUNDS:
        msg = "Every one correct."
    elif score >= ROUNDS * 0.6:
        msg = "Well played."
    else:
        msg = "Play again and these will stick."
    st.markdown(f'<div class="finale"><div class="score">{score} / {ROUNDS}</div>'
                f'<div class="msg">{msg}</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Play again"):
        reset_game()
        st.rerun()
    if c2.button("Choose another game"):
        go("home")


# =============================================================================
# THE GAMES
# =============================================================================
def multiple_choice(words, kind):
    """
    Two games share this shape:
      'meaning'  — show the Kenyang, tap the English.
      'kenyang'  — show the English, tap the Kenyang.
    Asking both directions is what makes a word stick rather than just look familiar.
    """
    st.session_state.setdefault("asked", 0)
    st.session_state.setdefault("score", 0)

    if st.session_state.asked >= ROUNDS:
        finish_screen()
        return
    if "q" not in st.session_state or st.session_state.q.get("kind") != kind:
        new_question(words, kind)

    q = st.session_state.q
    answer = q["answer"]
    scorebar()

    if kind == "meaning":
        shown, hint = answer["kenyang"], "What does this mean?"
    else:
        shown, hint = answer["english"], "How do you say this in Kenyang?"
    st.markdown(f'<div class="prompt"><div class="big">{shown}</div>'
                f'<div class="hint">{hint}</div></div>', unsafe_allow_html=True)

    if not st.session_state.answered:
        for i in range(0, len(q["options"]), 2):
            cols = st.columns(2)
            for col, opt in zip(cols, q["options"][i:i + 2]):
                label = opt["english"] if kind == "meaning" else opt["kenyang"]
                if col.button(label, key=f"{kind}{st.session_state.asked}_{opt['kenyang']}"):
                    st.session_state.choice = opt
                    st.session_state.answered = True
                    st.session_state.asked += 1
                    if opt["kenyang"] == answer["kenyang"]:
                        st.session_state.score += 1
                    st.rerun()
    else:
        chosen = st.session_state.choice
        right = chosen["kenyang"] == answer["kenyang"]
        if right:
            st.markdown(f'<div class="verdict right">Yes. <b>{answer["kenyang"]}</b> '
                        f'is {answer["english"]}.<br>{answer.get("description","")}</div>',
                        unsafe_allow_html=True)
        else:
            # Say plainly what was wrong, then what is right. No "close!".
            st.markdown(f'<div class="verdict wrong">Not that one. '
                        f'<b>{answer["kenyang"]}</b> is {answer["english"]}.<br>'
                        f'You chose {chosen["kenyang"]}, which is '
                        f'{chosen["english"]}.</div>', unsafe_allow_html=True)
        clip = audio_html(answer.get("audio"))
        if clip:
            st.markdown(clip, unsafe_allow_html=True)
        if st.button("Next"):
            st.session_state.pop("q", None)
            st.rerun()


def listen_game(words):
    """Play the recording, tap the meaning. Needs clips in audio/."""
    ready = have_audio(words)
    if len(ready) < 4:
        st.markdown('<div class="card"><h4>No recordings yet</h4><p>This game switches on '
                    'as soon as there are voice clips in the <code>audio</code> folder — '
                    'one per word, named as in the word list. Until then, try the other '
                    'games.</p></div>', unsafe_allow_html=True)
        if st.button("Back"):
            go("home")
        return

    st.session_state.setdefault("asked", 0)
    st.session_state.setdefault("score", 0)
    if st.session_state.asked >= ROUNDS:
        finish_screen()
        return
    if "q" not in st.session_state or st.session_state.q.get("kind") != "listen":
        new_question(ready, "listen")

    q = st.session_state.q
    answer = q["answer"]
    scorebar()
    st.markdown('<div class="prompt"><div class="big">🎧</div>'
                '<div class="hint">Listen, then tap what it means.</div></div>',
                unsafe_allow_html=True)
    st.markdown(audio_html(answer.get("audio")), unsafe_allow_html=True)

    if not st.session_state.answered:
        for i in range(0, len(q["options"]), 2):
            cols = st.columns(2)
            for col, opt in zip(cols, q["options"][i:i + 2]):
                if col.button(opt["english"],
                              key=f"listen{st.session_state.asked}_{opt['kenyang']}"):
                    st.session_state.choice = opt
                    st.session_state.answered = True
                    st.session_state.asked += 1
                    if opt["kenyang"] == answer["kenyang"]:
                        st.session_state.score += 1
                    st.rerun()
    else:
        chosen = st.session_state.choice
        if chosen["kenyang"] == answer["kenyang"]:
            st.markdown(f'<div class="verdict right">Yes. That was '
                        f'<b>{answer["kenyang"]}</b> — {answer["english"]}.</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="verdict wrong">That was '
                        f'<b>{answer["kenyang"]}</b> — {answer["english"]}, '
                        f'not {chosen["english"]}.</div>', unsafe_allow_html=True)
        if st.button("Next"):
            st.session_state.pop("q", None)
            st.rerun()


def memory_game(words):
    """Tap a Kenyang word, then its English. Six pairs, no timer, no pressure."""
    st.session_state.setdefault("score", 0)
    if "pairs" not in st.session_state:
        chosen = random.sample(words, min(6, len(words)))
        cards = ([{"id": f"k{i}", "pair": i, "face": w["kenyang"], "w": w}
                  for i, w in enumerate(chosen)]
                 + [{"id": f"e{i}", "pair": i, "face": w["english"], "w": w}
                    for i, w in enumerate(chosen)])
        random.shuffle(cards)
        st.session_state.pairs = cards
        st.session_state.picked = []
        st.session_state.solved = []

    cards = st.session_state.pairs
    solved = st.session_state.solved
    picked = st.session_state.picked

    st.markdown(f'<div class="scorebar"><span>Match each word to its meaning</span>'
                f'<span>{len(solved)//2} of {len(cards)//2} found</span></div>',
                unsafe_allow_html=True)

    if len(solved) == len(cards):
        st.markdown('<div class="finale"><div class="score">All found</div>'
                    '<div class="msg">Every pair matched.</div></div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("Play again"):
            reset_game()
            st.rerun()
        if c2.button("Choose another game"):
            go("home")
        return

    # two picks that don't match are cleared on the next tap, so a child sees both
    if len(picked) == 2:
        a, b = picked
        if a["pair"] == b["pair"] and a["id"] != b["id"]:
            st.markdown(f'<div class="verdict right"><b>{a["w"]["kenyang"]}</b> '
                        f'is {a["w"]["english"]}. {a["w"].get("description","")}</div>',
                        unsafe_allow_html=True)
            st.session_state.solved = solved + [a["id"], b["id"]]
        else:
            st.markdown(f'<div class="verdict wrong">{a["face"]} and {b["face"]} '
                        f'are not a pair. Try again.</div>', unsafe_allow_html=True)
        st.session_state.picked = []

    for i in range(0, len(cards), 2):
        cols = st.columns(2)
        for col, card in zip(cols, cards[i:i + 2]):
            if card["id"] in st.session_state.solved:
                col.button("✓", key=f"done{card['id']}", disabled=True)
            else:
                if col.button(card["face"], key=f"card{card['id']}"):
                    st.session_state.picked = st.session_state.picked + [card]
                    st.rerun()


# =============================================================================
# NAVIGATOR
# =============================================================================
GAMES = [
    ("meaning", "What does it mean?",
     "See a Kenyang word, tap what it means in English."),
    ("kenyang", "Say it in Kenyang",
     "See an English word, tap the Kenyang for it."),
    ("listen", "Listen and choose",
     "Hear the word spoken, then tap what it means."),
    ("memory", "Find the pairs",
     "Match each Kenyang word to its meaning."),
]
LEVELS = ["Easy", "Medium", "Hard", "Everything"]

st.markdown('<div class="hero"><p class="name">Nɛpɛm Games</p><div class="rule"></div>'
            '<p class="tag">Kɛ́nyāŋ — play and learn</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### For the builder")
    include = st.checkbox("Include words still under review", value=False,
                          help="Words where two sources disagree, or phrases whose order "
                               "contradicts the orthography guide. Off by default: a game "
                               "states things as fact, so it should only use confirmed words.")
    words, status = load_words(include)
    st.caption(f"{len(words)} words in play")
    for d in ("easy", "medium", "hard"):
        n = sum(1 for w in words if w.get("difficulty", "").lower() == d)
        st.caption(f"  {d}: {n}")
    clips = len(have_audio(words))
    st.caption(f"{clips} with a recording")
    if clips == 0:
        st.caption("Add .mp3 clips to ./audio to switch on Listen and choose.")

words, status = load_words(include if "include" in dir() else False)

if status == "missing" or not words:
    st.markdown('<div class="card"><h4>No words yet</h4><p>Put <code>words.jsonl</code> '
                'beside this file and reload. Run <code>python build_words.py</code> to '
                'create it from the raw lists.</p></div>', unsafe_allow_html=True)
    st.stop()

st.session_state.setdefault("screen", "home")
st.session_state.setdefault("level", "Easy")

if st.session_state.screen == "home":
    st.markdown('<p class="note">Pick a game, then how hard you want it.</p>',
                unsafe_allow_html=True)
    st.session_state.level = st.radio("How hard?", LEVELS,
                                      index=LEVELS.index(st.session_state.level),
                                      horizontal=True, label_visibility="collapsed")
    for key, title, blurb in GAMES:
        st.markdown(f'<div class="card"><h4>{title}</h4><p>{blurb}</p></div>',
                    unsafe_allow_html=True)
        if st.button(f"Play — {title}", key=f"go{key}"):
            go("play", game=key, level=st.session_state.level)
else:
    level = st.session_state.get("level", "Easy")
    playing = pool(words, level)
    title = dict((k, t) for k, t, _ in GAMES)[st.session_state.game]
    st.markdown(f'<div class="scorebar"><span><b>{title}</b></span>'
                f'<span>{level}</span></div>', unsafe_allow_html=True)

    if len(playing) < 4:
        st.markdown('<div class="card"><h4>Not enough words at this level</h4>'
                    '<p>Add more words, or pick a different level.</p></div>',
                    unsafe_allow_html=True)
    elif st.session_state.game == "listen":
        listen_game(playing)
    elif st.session_state.game == "memory":
        memory_game(playing)
    else:
        multiple_choice(playing, st.session_state.game)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to the games"):
        go("home")
