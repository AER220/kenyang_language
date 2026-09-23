"""
community.py — catching what speakers teach Nɛpɛm, so none of it is lost.

The problem this solves
-----------------------
People who speak Kenyang correct Nɛpɛm all the time. Until now those corrections
lived in a chat window that vanished when the tab closed. This catches them,
keeps them somewhere I can actually read, and turns the ones I approve into text
I can paste straight into kenyang_verified_speaker.md.

Where it stores things, and why
-------------------------------
Streamlit Cloud wipes the container's disk whenever the app sleeps, so a file on
disk is useless for anything I want to keep. There are three backends here and
the module uses whichever is configured, in this order:

  1. Google Sheet   the one I recommend. Survives everything, I can read it on
                    my phone, and it exports CSV in one click.
  2. GitHub file    appends to a file in my own repo. Version controlled and
                    permanent, but slower and it can hit rate limits.
  3. Local file     always written as well, as a cache. Useful when running on
                    my own machine. Do NOT rely on it in the cloud.

If nothing is configured it still works, writing locally, and warns me plainly
rather than pretending the submission was saved.

Nothing a contributor sends goes anywhere near what Nɛpɛm teaches until I have
read it and marked it approved. That gate is the whole point: the project's one
promise is that it does not teach unverified Kenyang.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

LOCAL_PATH = "community_submissions.jsonl"

KINDS = {
    "correction": "Nɛpɛm said something wrong",
    "new_word":   "A word or phrase Nɛpɛm does not have",
    "issue":      "Something else is wrong",
}


# ─────────────────────────────────────────────────────────────────────────────
# writing
# ─────────────────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make(kind, *, question="", answer="", correction="", note="",
         speaker="", village="", source="chat"):
    """Build one submission. Kept as a plain dict so every backend can take it."""
    return {
        "id": uuid.uuid4().hex[:12],
        "at": _now(),
        "kind": kind if kind in KINDS else "issue",
        "question": (question or "").strip()[:2000],
        "answer": (answer or "").strip()[:4000],
        "correction": (correction or "").strip()[:2000],
        "note": (note or "").strip()[:2000],
        "speaker": (speaker or "").strip()[:80],
        "village": (village or "").strip()[:80],
        "source": source,
        "status": "new",          # new · approved · rejected
    }


def _write_local(rec):
    try:
        with open(LOCAL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _write_supabase(rec, cfg):
    """
    Insert one row into a Supabase table over its REST endpoint.

    Needs, in Streamlit secrets:
        [supabase]
        url = "https://xxxx.supabase.co"
        key = "the anon public key"
        table = "submissions"          # optional, this is the default

    Only `requests` is needed, so there is no new dependency to install.

    On the key: it is the ANON key and it sits in the app, where somebody
    determined could read it. That is safe here because the table's row level
    security lets the anon key INSERT and nothing else. It cannot read the
    table back, so contributors' names and villages are not exposed. If that
    policy is ever loosened, this stops being true.
    """
    import requests

    url = cfg["url"].rstrip("/")
    table = cfg.get("table", "submissions")
    r = requests.post(
        f"{url}/rest/v1/{table}",
        headers={
            "apikey": cfg["key"],
            "Authorization": f"Bearer {cfg['key']}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={k: rec[k] for k in
              ("id", "kind", "question", "answer", "correction", "note",
               "speaker", "village", "source", "status")},
        timeout=20,
    )
    if r.status_code in (200, 201, 204):
        return True, None
    # the body carries the real reason, and it is usually the RLS policy
    return False, f"Supabase said {r.status_code}: {r.text[:200]}"


def _write_sheet(rec, cfg):
    """
    Append a row to a Google Sheet.

    Needs, in Streamlit secrets:
        [gsheet]
        sheet_id = "..."                  the id out of the sheet's URL
        service_account = '''{ ... }'''   the whole service-account JSON

    Then share the sheet with the service account's client_email, as an editor.
    """
    import gspread                                    # imported late: optional
    from google.oauth2.service_account import Credentials

    info = cfg["service_account"]
    if isinstance(info, str):
        info = json.loads(info)
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(cfg["sheet_id"])
    ws = sh.sheet1

    # write a header the first time, so the sheet is readable without a legend
    if not ws.get_all_values():
        ws.append_row(["id", "at", "kind", "question", "answer", "correction",
                       "note", "speaker", "village", "source", "status"])
    ws.append_row([rec[k] for k in ("id", "at", "kind", "question", "answer",
                                    "correction", "note", "speaker", "village",
                                    "source", "status")])
    return True, None


def _write_github(rec, cfg):
    """
    Append one JSON line to a file in my own repo.

    Needs, in Streamlit secrets:
        [github]
        token = "ghp_..."                 a token with contents write access
        repo  = "AER220/kenyang_language"
        path  = "community/submissions.jsonl"
    """
    import base64
    import requests

    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
    head = {"Authorization": f"Bearer {cfg['token']}",
            "Accept": "application/vnd.github+json"}

    got = requests.get(url, headers=head, timeout=20)
    if got.status_code == 200:
        body = got.json()
        old = base64.b64decode(body["content"]).decode("utf-8")
        sha = body["sha"]
    elif got.status_code == 404:
        old, sha = "", None
    else:
        return False, f"GitHub read failed: {got.status_code}"

    new = old + json.dumps(rec, ensure_ascii=False) + "\n"
    payload = {"message": f"community: {rec['kind']} {rec['id']}",
               "content": base64.b64encode(new.encode("utf-8")).decode("ascii")}
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=head, json=payload, timeout=25)
    if put.status_code in (200, 201):
        return True, None
    return False, f"GitHub write failed: {put.status_code}"


def save(rec, secrets=None):
    """
    Store a submission everywhere that is configured.

    Returns (kept_somewhere_durable, [notes]). The first value is the one that
    matters: if it is False the submission exists only on a disk that Streamlit
    will wipe, and the person should be told, not thanked.
    """
    notes = []
    durable = False

    ok, err = _write_local(rec)
    if not ok:
        notes.append(f"local copy failed ({err})")

    cfg = secrets or {}

    if "supabase" in cfg:
        try:
            ok, err = _write_supabase(rec, cfg["supabase"])
            if ok:
                durable = True
                notes.append("saved to the database")
            else:
                notes.append(err)
        except Exception as e:
            notes.append(f"database failed: {type(e).__name__}: {e}")

    if "gsheet" in cfg:
        try:
            _write_sheet(rec, cfg["gsheet"])
            durable = True
            notes.append("saved to the sheet")
        except Exception as e:
            notes.append(f"sheet failed: {type(e).__name__}: {e}")

    if "github" in cfg:
        try:
            ok, err = _write_github(rec, cfg["github"])
            if ok:
                durable = True
                notes.append("saved to the repo")
            else:
                notes.append(err)
        except Exception as e:
            notes.append(f"repo failed: {type(e).__name__}: {e}")

    if not durable:
        notes.append("nothing durable is configured, so this is only on the "
                     "container's disk and will be lost when the app sleeps")
    return durable, notes


# ─────────────────────────────────────────────────────────────────────────────
# reading, for the review page
# ─────────────────────────────────────────────────────────────────────────────

def _read_supabase(cfg):
    """
    Read the table back, for the review page.

    This needs the SERVICE ROLE key, not the anon one, because row level
    security deliberately stops the anon key reading. Put it in secrets as:

        [supabase]
        url = "https://xxxx.supabase.co"
        key = "anon public key"          # used by the app to insert
        service_key = "service role key" # used ONLY by the review page to read

    Streamlit secrets are server side and never sent to the browser, so the
    service key is safe there. It must never appear in index.html or anywhere
    else a visitor can reach, because it bypasses every policy on the table.

    If service_key is missing, reading just falls through to the local file and
    the review page says so. Insertion still works, so no contribution is lost.
    """
    import requests

    key = cfg.get("service_key")
    if not key:
        return None
    url = cfg["url"].rstrip("/")
    table = cfg.get("table", "submissions")
    r = requests.get(
        f"{url}/rest/v1/{table}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        params={"select": "*", "order": "at.desc"},
        timeout=20,
    )
    if r.status_code == 200:
        return r.json()
    return None


def _status_supabase(rec_id, status, cfg):
    """Mark one row approved or rejected. Also needs the service key."""
    import requests

    key = cfg.get("service_key")
    if not key:
        return False
    url = cfg["url"].rstrip("/")
    table = cfg.get("table", "submissions")
    r = requests.patch(
        f"{url}/rest/v1/{table}",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        params={"id": f"eq.{rec_id}"},
        json={"status": status},
        timeout=20,
    )
    return r.status_code in (200, 204)


def load(secrets=None):
    """Read everything back: database first, then sheet, then the local file."""
    cfg = secrets or {}

    if "supabase" in cfg:
        try:
            rows = _read_supabase(cfg["supabase"])
            if rows is not None:
                return rows, "database"
        except Exception:
            pass
    if "gsheet" in cfg:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            info = cfg["gsheet"]["service_account"]
            if isinstance(info, str):
                info = json.loads(info)
            creds = Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            ws = gspread.authorize(creds).open_by_key(cfg["gsheet"]["sheet_id"]).sheet1
            return ws.get_all_records(), "sheet"
        except Exception:
            pass

    rows = []
    if os.path.exists(LOCAL_PATH):
        for line in open(LOCAL_PATH, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows, "local file"


def set_status(rec_id, status, secrets=None):
    """Mark one submission approved or rejected."""
    cfg = secrets or {}

    if "supabase" in cfg:
        try:
            if _status_supabase(rec_id, status, cfg["supabase"]):
                return True
        except Exception:
            pass

    if "gsheet" in cfg:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            info = cfg["gsheet"]["service_account"]
            if isinstance(info, str):
                info = json.loads(info)
            creds = Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            ws = gspread.authorize(creds).open_by_key(cfg["gsheet"]["sheet_id"]).sheet1
            ids = ws.col_values(1)
            if rec_id in ids:
                ws.update_cell(ids.index(rec_id) + 1, 11, status)   # column K
                return True
        except Exception:
            return False

    if not os.path.exists(LOCAL_PATH):
        return False
    rows = []
    for line in open(LOCAL_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("id") == rec_id:
            r["status"] = status
        rows.append(r)
    with open(LOCAL_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# turning approved submissions into something I can paste
# ─────────────────────────────────────────────────────────────────────────────

def to_markdown(rows):
    """
    Take the approved submissions and write them in the shape the verified file
    uses, ready to paste. Credits are kept, because people who give their
    language deserve their name on it.
    """
    ok = [r for r in rows if str(r.get("status", "")).lower() == "approved"]
    if not ok:
        return "", 0

    out = ["---", "",
           "## From speakers in the community", "",
           f"Confirmed and added on {datetime.now().strftime('%d %B %Y')}. "
           "Each of these came from somebody who speaks Kenyang and took the",
           "time to correct or teach it.", ""]

    words = [r for r in ok if r.get("kind") == "new_word"]
    fixes = [r for r in ok if r.get("kind") == "correction"]

    if words:
        out += ["### Words and phrases people brought", ""]
        for r in words:
            ken = (r.get("correction") or "").strip()
            eng = (r.get("question") or "").strip()
            if not ken:
                continue
            out.append(f"    {ken:<24} {eng}")
        out.append("")
        for r in words:
            if r.get("note"):
                out += [f"{r.get('correction','').strip()}: {r['note'].strip()}", ""]

    if fixes:
        out += ["### Corrections", ""]
        for r in fixes:
            out += [f"Nɛpɛm said: {r.get('answer','').strip()[:220]}",
                    f"A speaker corrected it to: **{r.get('correction','').strip()}**"]
            if r.get("note"):
                out.append(f"Why: {r['note'].strip()}")
            out.append("")

    names = sorted({(r.get("speaker") or "").strip() for r in ok
                    if (r.get("speaker") or "").strip()})
    if names:
        out += ["With thanks to " + ", ".join(names) + ".", ""]

    return "\n".join(out), len(ok)
