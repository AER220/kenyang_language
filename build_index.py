"""
build_index.py — embed the whole corpus once and save it to disk.

Why: on Streamlit Cloud the container is rebuilt every time the app wakes from sleep, and
the in-app cache doesn't reliably survive that. Without a committed index, the first person
to visit after any quiet spell waits about half a minute while every passage re-embeds —
and I pay for that embedding call each time. This computes the vectors once, here, and
saves index.npz. The app loads that file and starts instantly, at no cost, even if the API
key is briefly unavailable.

Run it after ANY change to knowledge_base/, then commit the result:

    python build_index.py
    git add knowledge_base index.npz
    git commit -m "rebuild knowledge index"
    git push

If I forget, nothing breaks — the app just falls back to embedding on first load and the
sidebar tells me the index was "built just now". This only removes the wait, it isn't
load-bearing.
"""

import numpy as np
from openai import OpenAI

import streamlit_app as app          # reuse the app's own loader, so they can never drift


def main():
    key = app.api_key()
    if not key:
        raise SystemExit("No OPENAI_API_KEY found. Set it before building the index.")

    sig = app.kb_signature()
    _always, chunks, manifest, _over, _tr = app.build_corpus(sig)
    if not chunks:
        raise SystemExit(f"No readable files in ./{app.KB_ROOT} — nothing to index.")

    print(f"{len(manifest)} files, {len(chunks):,} passages to embed.")
    client = OpenAI(api_key=key)
    rows = []
    for i in range(0, len(chunks), app.EMBED_BATCH):
        batch = [c["text"][:8000] for c in chunks[i:i + app.EMBED_BATCH]]
        resp = client.embeddings.create(model=app.EMBED_MODEL, input=batch)
        rows.extend(d.embedding for d in resp.data)
        print(f"  {min(i + app.EMBED_BATCH, len(chunks)):>5}/{len(chunks)} embedded")

    mat = np.asarray(rows, dtype=np.float32)
    mat /= np.clip(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9, None)
    # allow_pickle stays off on load, so the signature is stored as a plain array of text.
    np.savez_compressed(app.INDEX_FILE, vectors=mat,
                        signature=np.array(sig))
    print(f"\nwrote {app.INDEX_FILE}: {mat.shape[0]} vectors, "
          f"{mat.nbytes // 1024:,} KB uncompressed")
    print("Now: git add knowledge_base index.npz && git commit && git push")


if __name__ == "__main__":
    main()
