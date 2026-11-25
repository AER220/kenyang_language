"""
recordings.py — speakers' recordings, for the review page. Server side only.

Everything here uses the SERVICE ROLE key, which bypasses every policy, so this
module must only ever run on the server (the Review page on Render). It never
goes near index.html.

The shape (the SQL is in Supabase; see the Job 2 notes):

    words       one row per spelling: kenyang, folded, english, status,
                kb_spelling (what was last pasted into the knowledge base)
    recordings  one row per file. The id is the filename, <id>.wav, for ever.
                A contributor can only add a pending, unlinked, non-primary row;
                everything after that happens here.

    recordings-pending   private bucket: what contributors send. Only this
                         module can read it, and only to play it to Ed.
    recordings           public bucket: approved files, plus the two files
                         this module writes after every change:
        manifest.json        folded spelling -> "<id>.wav", for say.js
        recorded_words.json  [{kenyang, english, voices}], text only, for the
                             Teach form's list. No file names, nothing pending.
        contributors.json    [{speaker, village, taught}], one per named person
                             with approved recordings, for the wall. The wall
                             adds these to the text contributors from the
                             `contributors` view, matching on tidy_name().

Nothing reaches a learner until approve() runs, and approve() runs only from
the Approve button, which the review page shows only after Ed has pressed
Listen. A file is never renamed: correcting a spelling edits a row and
rebuilds the two public files.

Nothing here writes to the knowledge base. paste_block() only produces text.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from build_audio_manifest import fold
from textnorm import clean

PENDING, PUBLIC = "recordings-pending", "recordings"
ID_OK = set("0123456789abcdef")


class Trouble(Exception):
    """Supabase said no, or could not be reached. The message says which."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _valid_id(rec_id):
    return isinstance(rec_id, str) and len(rec_id) == 24 and set(rec_id) <= ID_OK


class Store:
    """The service-key connection. `send` is swappable so tests need no network."""

    def __init__(self, url, service_key, send=None):
        if not url or not service_key:
            raise Trouble("SUPABASE_URL and SUPABASE_SERVICE_KEY must both be set")
        self.url = url.rstrip("/")
        self.key = service_key
        self.send = send or self._requests

    def _requests(self, method, path, *, params=None, json_body=None, data=None,
                  headers=None):
        import requests
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        h.update(headers or {})
        r = requests.request(method, self.url + path, params=params, json=json_body,
                             data=data, headers=h, timeout=30)
        return r.status_code, r.content

    def call(self, method, path, ok=(200, 201, 204), **kw):
        try:
            code, body = self.send(method, path, **kw)
        except Exception as e:                      # network, DNS, timeout
            raise Trouble(f"could not reach Supabase: {type(e).__name__}") from e
        if code not in ok:
            raise Trouble(f"Supabase said {code} to {method} {path.split('?')[0]}: "
                          f"{body[:200].decode('utf-8', 'replace')}")
        return body

    def rows(self, table, **params):
        return json.loads(self.call("GET", f"/rest/v1/{table}", params=params) or b"[]")

    def patch(self, table, match, values):
        self.call("PATCH", f"/rest/v1/{table}", params=match, json_body=values,
                  headers={"Content-Type": "application/json", "Prefer": "return=minimal"})

    def insert(self, table, values):
        body = self.call("POST", f"/rest/v1/{table}", json_body=values,
                         headers={"Content-Type": "application/json",
                                  "Prefer": "return=representation"})
        return json.loads(body)[0]

    def delete_row(self, table, match):
        self.call("DELETE", f"/rest/v1/{table}", params=match,
                  headers={"Prefer": "return=minimal"})

    def get_file(self, bucket, name):
        return self.call("GET", f"/storage/v1/object/{bucket}/{name}", ok=(200,))

    def put_file(self, bucket, name, data, content_type, cache):
        self.call("POST", f"/storage/v1/object/{bucket}/{name}", data=data,
                  headers={"Content-Type": content_type, "Cache-Control": cache,
                           "x-upsert": "true"})

    def delete_file(self, bucket, name):
        # a file that is already gone is what we wanted, so 400/404 are fine
        self.call("DELETE", f"/storage/v1/object/{bucket}/{name}", ok=(200, 204, 400, 404))


def store_from(cfg):
    """cfg is community._with_env(...)['supabase']."""
    return Store(cfg.get("url"), cfg.get("service_key"))


# ── reading ──────────────────────────────────────────────────────────────────

def pending(st):
    return st.rows("recordings", status="eq.pending", order="created_at.asc", select="*")


def approved(st):
    return st.rows("recordings", status="eq.approved", order="created_at.asc", select="*")


def word_for(st, spelling):
    """The word row this spelling belongs to, or None."""
    got = st.rows("words", folded=f"eq.{fold(spelling)}", select="*")
    return got[0] if got else None


def words(st):
    return st.rows("words", select="*", order="created_at.asc")


def voice_counts(st, speaker_code):
    """How many recordings this browser's code has sent, and how many approved."""
    got = st.rows("recordings", speaker_code=f"eq.{speaker_code}", select="status")
    return len(got), sum(1 for r in got if r["status"] == "approved")


def pending_audio(st, rec_id):
    if not _valid_id(rec_id):
        raise Trouble("not a recording id")
    return st.get_file(PENDING, f"{rec_id}.wav")


# ── deciding ─────────────────────────────────────────────────────────────────

def approve(st, rec, kenyang, english):
    """
    Approve one recording under the spelling and English Ed settled on.

    In order, so a failure part way leaves nothing a learner can reach:
      1. find the word by folded spelling, or create it
      2. copy the file into the public bucket (unreachable until the manifest
         names it)
      3. mark the row approved and linked; primary if the word has none yet
      4. delete the pending copy
      5. rebuild the two public files
    """
    # A phone's curly apostrophe, dash or no-break space is stored as the files write it.
    kenyang, english = clean(kenyang, kenyang=True), clean(english)
    if not kenyang:
        raise Trouble("the Kenyang spelling is empty")
    if not _valid_id(rec["id"]):
        raise Trouble("not a recording id")
    name = f"{rec['id']}.wav"

    word = word_for(st, kenyang)
    if word is None:
        word = st.insert("words", {"kenyang": kenyang, "folded": fold(kenyang),
                                   "english": english, "status": "confirmed"})
    elif english and english != word["english"]:
        # the review page shows the word's English already there, so this only
        # differs when Ed changed it. Its spelling is left alone: a spelling
        # that folds the same is the same word.
        st.patch("words", {"id": f"eq.{word['id']}"},
                 {"english": english, "updated_at": _now()})

    audio = st.get_file(PENDING, name)
    st.put_file(PUBLIC, name, audio, "audio/wav", "public, max-age=31536000, immutable")

    has_primary = st.rows("recordings", word_id=f"eq.{word['id']}",
                          is_primary="is.true", select="id")
    st.patch("recordings", {"id": f"eq.{rec['id']}", "status": "eq.pending"},
             {"status": "approved", "word_id": word["id"],
              "is_primary": not has_primary, "decided_at": _now()})

    st.delete_file(PENDING, name)
    rebuild_public(st)
    return word


def edit_word(st, word, kenyang, english):
    """
    Correct a word's spelling or English after it exists. The row changes, the
    two public files are rebuilt, and no file is touched. A spelling that folds
    to another word's is refused: that would be two rows for one spelling.
    """
    kenyang, english = clean(kenyang, kenyang=True), clean(english)
    if not kenyang:
        raise Trouble("the Kenyang spelling is empty")
    other = word_for(st, kenyang)
    if other and other["id"] != word["id"]:
        raise Trouble(f"{other['kenyang']} is already a word of its own")
    st.patch("words", {"id": f"eq.{word['id']}"},
             {"kenyang": kenyang, "folded": fold(kenyang), "english": english,
              "updated_at": _now()})
    rebuild_public(st)


def reject(st, rec):
    """Set a recording aside: the audio is deleted, the text row is kept."""
    if not _valid_id(rec["id"]):
        raise Trouble("not a recording id")
    st.delete_file(PENDING, f"{rec['id']}.wav")
    st.patch("recordings", {"id": f"eq.{rec['id']}", "status": "eq.pending"},
             {"status": "rejected", "decided_at": _now()})


def remove(st, rec):
    """
    Take an approved recording down, when somebody asks for theirs to be
    removed. The public file and the row both go. If it was the word's
    primary, the oldest other approved recording of that word takes over.
    """
    if not _valid_id(rec["id"]):
        raise Trouble("not a recording id")
    st.delete_file(PUBLIC, f"{rec['id']}.wav")
    st.delete_row("recordings", {"id": f"eq.{rec['id']}"})
    if rec.get("is_primary") and rec.get("word_id"):
        others = st.rows("recordings", word_id=f"eq.{rec['word_id']}",
                         status="eq.approved", order="created_at.asc", select="id")
        if others:
            st.patch("recordings", {"id": f"eq.{others[0]['id']}"}, {"is_primary": True})
    rebuild_public(st)


# ── the two public files ─────────────────────────────────────────────────────

def public_files(word_rows, approved_rows):
    """
    Build manifest.json and recorded_words.json from the rows. Pure, so it can
    be checked without a network. Only confirmed words, only approved
    recordings; the manifest names only primaries.
    """
    by_word = {}
    for r in approved_rows:
        if r.get("status") == "approved" and r.get("word_id"):
            by_word.setdefault(r["word_id"], []).append(r)
    manifest, listed = {}, []
    for w in word_rows:
        recs = by_word.get(w["id"], [])
        if w.get("status") != "confirmed" or not recs:
            continue
        key = fold(w["kenyang"])
        primary = next((r for r in recs if r.get("is_primary")), None)
        if primary and _valid_id(primary["id"]) and key:
            manifest[key] = f"{primary['id']}.wav"
        listed.append({"kenyang": w["kenyang"], "english": w.get("english", ""),
                       "voices": len(recs)})
    return manifest, listed


def tidy_name(text):
    """
    How the wall decides two typed names are the same: capitals, spacing at the ends
    and in between, the Unicode form of a letter, and curly or straight apostrophes
    do not matter. Nothing looser. "Ed" and "Agbor Edouard" stay two people: one
    person shown twice is a mistake Ed can see and fix, two people merged into one
    is not. index.html's tidyName() must do exactly the same.
    """
    import re
    import unicodedata
    t = unicodedata.normalize("NFC", text or "").lower()
    for a in "’‘ʼʻ`´":
        t = t.replace(a, "'")
    return re.sub(r"\s+", " ", t).strip()


def hidden_villages():
    """
    Names whose village must never be published, from WALL_HIDE_VILLAGE on Render,
    separated by semicolons: "Agbor; Agbor Edouard Ransome". Matched with
    tidy_name(). Kept in the server's settings, not in code, so nothing public says
    whose village is withheld. The rows keep the village; only the file omits it.
    """
    import os
    return {tidy_name(n) for n in os.environ.get("WALL_HIDE_VILLAGE", "").split(";")
            if tidy_name(n)}


def credits(approved_rows, hide=None):
    """
    One entry per named person, counting approved recordings: one recording is one
    thing taught, as one approved text submission is. Name and village must both
    match after tidying; a blank village matches only a blank village. Recordings
    with no name are not credited. The name shown is the spelling used most.
    For a name in hidden_villages() the village is left out before grouping, so
    that person's entries merge as one with a blank village.
    """
    hide = hidden_villages() if hide is None else hide
    groups = {}
    for r in approved_rows:
        if r.get("status") != "approved" or not (r.get("speaker") or "").strip():
            continue
        sp, vi = r["speaker"].strip(), (r.get("village") or "").strip()
        if tidy_name(sp) in hide:
            vi = ""
        key = (tidy_name(sp), tidy_name(vi))
        g = groups.setdefault(key, {"n": 0, "names": {}, "villages": {}})
        g["n"] += 1
        g["names"][sp] = g["names"].get(sp, 0) + 1
        g["villages"][vi] = g["villages"].get(vi, 0) + 1
    most = lambda d: max(d.items(), key=lambda kv: kv[1])[0]
    out = [{"speaker": most(g["names"]), "village": most(g["villages"]), "taught": g["n"]}
           for g in groups.values()]
    return sorted(out, key=lambda c: (-c["taught"], c["speaker"]))


def rebuild_public(st):
    done = approved(st)
    manifest, listed = public_files(words(st), done)
    for name, body in (("manifest.json", manifest), ("recorded_words.json", listed),
                       ("contributors.json", credits(done))):
        st.put_file(PUBLIC, name, json.dumps(body, ensure_ascii=False, indent=1).encode(),
                    "application/json", "public, max-age=60")
    return manifest, listed


# ── into the knowledge base, by hand ─────────────────────────────────────────

def to_paste(word_rows, approved_rows):
    """Confirmed, recorded words whose current spelling is not what was last pasted."""
    recorded = {r["word_id"] for r in approved_rows if r.get("word_id")}
    return [w for w in word_rows
            if w.get("status") == "confirmed" and w["id"] in recorded
            and (w.get("kb_spelling") or "") != w["kenyang"]]


def paste_block(word_rows, approved_rows):
    """
    The words in to_paste(), written the way community.to_markdown writes
    approved submissions for kenyang_verified_speaker.md, but with no names.
    Only text; nothing here writes to the knowledge base.
    """
    todo = to_paste(word_rows, approved_rows)
    if not todo:
        return "", []
    # No names. Credit belongs on the site; this block is sent to OpenAI with
    # every question, which a contributor did not consent to for their name.
    out = ["---", "",
           "## From speakers in the community", "",
           f"Confirmed and added on {datetime.now().strftime('%d %B %Y')}. "
           "Each of these came from somebody who speaks Kenyang and took the",
           "time to record it.", "",
           "### Words and phrases people recorded", ""]
    for w in todo:
        out.append(f"    {w['kenyang']:<24} {w.get('english', '')}".rstrip())
    out.append("")
    fixed = [w for w in todo if w.get("kb_spelling")]
    for w in fixed:
        out += [f"{w['kenyang']}: corrected from {w['kb_spelling']}. "
                f"Use {w['kenyang']}.", ""]
    return "\n".join(out), todo


def mark_pasted(st, todo):
    for w in todo:
        st.patch("words", {"id": f"eq.{w['id']}"},
                 {"kb_spelling": w["kenyang"], "updated_at": _now()})


# ── checks before a spelling becomes truth ───────────────────────────────────
#
# An approved recording makes its spelling count as confirmed: the chat's flag stops
# warning about it. So a typo approved once becomes truth. That is how Neyi and Eh,
# Ed's own néyi and Éh with the marks lost, became confirmed misspellings. These checks
# run on the Review page before Approve; they warn and never block, because a genuinely
# new word is the normal case.

import difflib
import glob
import os
import re
import unicodedata

_KB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
_ROOT = os.path.dirname(os.path.abspath(__file__))
_WORD = re.compile(r"(?:[^\W\d_]|[̀-ͯ'’])+(?:-(?:[^\W\d_]|[̀-ͯ'’])+)*")
# a verified file's "book spelling: ..." line names forms that are NOT confirmed
_BOOK_LINE = re.compile(r"^\s+book spelling:", re.IGNORECASE)
_CACHE = {}


def _bare(w):
    """Without tone marks, for finding the word a typo was meant to be."""
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


def verified_vocabulary():
    """
    Every word in the verified files, folded, plus Ed's own recordings. Not the
    other speakers' recordings: checking against those would let one approved typo
    vouch for the next. Words in capitals are left out: the crossword section writes
    NEYI and ƐKATI without their marks on purpose, one letter per square.
    """
    if "vocab" not in _CACHE:
        words = set()
        for path in glob.glob(os.path.join(_KB, "*verified*")):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if _BOOK_LINE.match(line):
                        continue
                    for w in _WORD.findall(unicodedata.normalize("NFC", line)):
                        if len(w) > 1 and w.upper() == w and w.lower() != w:
                            continue
                        words.add(fold(w))
                        words.update(fold(p) for p in w.split("-") if p)
        eds = set()
        try:
            with open(os.path.join(_ROOT, "audio_words.json"), encoding="utf-8") as f:
                for e in json.load(f):
                    eds.update(fold(w) for w in _WORD.findall(e.get("kenyang", "")))
        except (OSError, ValueError):
            pass
        _CACHE["vocab"] = words | eds
        _CACHE["eds"] = eds
    return _CACHE["vocab"]


def _english():
    if "english" not in _CACHE:
        try:
            with open(os.path.join(_ROOT, "english_words.txt"), encoding="utf-8") as f:
                _CACHE["english"] = {l.strip() for l in f if l.strip() and not l.startswith("#")}
        except OSError:
            _CACHE["english"] = set()
    return _CACHE["english"]


def spelling_check(spelling):
    """
    [(word, why, [closest verified words])] for each word of the spelling that the
    verified files do not have. `why` is "not in the verified files", or "an English
    word" when it is also English (the English typed into the Kenyang box, as
    "Mine (my)" was). Empty when every word is there.
    """
    vocab, english = verified_vocabulary(), _english()
    eds = _CACHE.get("eds", set())
    out = []
    for w in _WORD.findall(clean(spelling, kenyang=True)):
        f = fold(w)
        parts = [f] + [p for p in f.split("-") if p and p != f]
        if f in eds:
            continue                    # Ed recorded exactly this
        # The same letters with other tone marks. Against Ed's recordings it always
        # warns: Neyi beside his recorded néyi is how the marks got lost. Against the
        # verified text only when the spelling itself is not there, since the verified
        # files keep some variants on purpose (Byó nɛ amɔt beside Nɛkú nɛ amɔ́t).
        same = {v for v in vocab if v != f and _bare(v) == _bare(f)}
        rec = sorted(v for v in same if v in eds)
        if rec:
            out.append((w, "your recording writes it with tone marks this lacks", rec[:3]))
            continue
        if same and f not in vocab:
            out.append((w, "your verified files write it with other tone marks", sorted(same)[:3]))
            continue
        if any(p in vocab for p in parts) and f not in english:
            continue
        why = "an English word" if f in english else "not in the verified files"
        bare = _bare(f)
        near = sorted(vocab, key=lambda v: (_bare(v) != bare,
                                            -difflib.SequenceMatcher(None, bare, _bare(v)).ratio()))
        near = [v for v in near[:5]
                if _bare(v) == bare or difflib.SequenceMatcher(None, bare, _bare(v)).ratio() >= 0.6]
        if f in vocab and why == "an English word":
            why = "also an English word"
        out.append((w, why, near[:3]))
    return out


def unclean_words(word_rows):
    """[(row, cleaned kenyang, cleaned english)] for each stored word that clean()
    would change: a phone's curly apostrophe, dash or invisible space."""
    out = []
    for w in word_rows:
        k = clean(w.get("kenyang", ""), kenyang=True)
        e = clean(w.get("english", "") or "")
        if (k, e) != (w.get("kenyang", ""), w.get("english", "") or ""):
            out.append((w, k, e))
    return out


def clean_stored(st, items):
    """Store the cleaned spellings, one edit_word() each, so every rule there (no two
    rows for one spelling, the public files rebuilt) still holds. Returns
    (done, [(spelling, why it was not saved)])."""
    done, failed = 0, []
    for w, k, e in items:
        try:
            edit_word(st, w, k, e)
            done += 1
        except Trouble as ex:
            failed.append((w.get("kenyang", ""), str(ex)))
    return done, failed
