import json

wanted = {"vt", "vi", "v", "inf", "adv", "conj", "prep", "adj", "pron",
          "subj. pron.", "subj. pron", "det", "neg"}
seen, out = set(), []

for line in open("knowledge_base/dictionary.txt", encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    pos = str(o.get("part_of_speech", "")).strip().lower()
    k, e = o.get("kenyang"), o.get("english")
    if pos in wanted and k and e:
        key = k.lower()
        if key not in seen:
            seen.add(key)
            out.append({"kenyang": k, "english": e, "pos": pos})

with open("sentence_words.jsonl", "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"{len(out)} entries -> sentence_words.jsonl")
for p in ("vt", "vi", "adv", "conj", "prep", "adj", "pron"):
    print(f"  {p:<6} {sum(1 for r in out if r['pos'] == p)}")
