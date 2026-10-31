"""Swap-owner stress set: an answerable dev question about the USER is rewritten to ask about another person who is
never mentioned in the packed evidence. Evidence is unchanged, so the correct outcome is INSUFFICIENT_EVIDENCE.
Tests whether a softer abstention policy answers with the user's own fact. Synthetic; not challenge data."""
import json, re, sys
from pathlib import Path
ROOT = Path("/home/alex/code/personal/memory-challenge")
OUT = ROOT / "artifacts/stress-20261031"
gold = {json.loads(l)["question_id"]: json.loads(l) for l in open(ROOT / "dev/gold.jsonl")}
PEOPLE = ["brother", "neighbor", "coworker", "cousin", "roommate"]
RULES = [(re.compile(r"\bdid I\b"), "did my {p}"), (re.compile(r"\bmy\b"), "my {p}'s")]
picked, hist_ids = [], set()
for line in open(ROOT / "artifacts/tune-final.jsonl"):
    r = json.loads(line)
    g = gold[r["question_id"]]
    if g["abstain"] or g["question_type"] not in ("single-session-user", "single-session-assistant", "knowledge-update"):
        continue
    q = r["question"]
    rule = next((rx for rx in RULES if len(rx[0].findall(q)) == 1), None)
    others = re.findall(r"\b(I|I'm|I've|me|my|mine)\b", q)
    if rule is None or len(others) != 1:
        continue
    text = " ".join(p["text"].lower() for p in r["passages"])
    person = next((p for p in PEOPLE if p not in text), None)
    if person is None:
        continue
    new_q = rule[0].sub(rule[1].format(p=person), q, count=1)
    chars = r["retrieval"]["chars"] + len(new_q) - len(q)
    if chars > 14500:
        continue
    picked.append({**r, "question_id": r["question_id"] + "x", "question": new_q, "original_question": q,
                   "retrieval": {**r["retrieval"], "chars": chars}})
    hist_ids.add(r["history_id"])
    if len(picked) == 10:
        break
split = OUT / "split"; split.mkdir(exist_ok=True)
with open(split / "histories.jsonl", "w") as f:
    for line in open(ROOT / "dev/histories.jsonl"):
        if json.loads(line)["history_id"] in hist_ids:
            f.write(line)
qs = {json.loads(l)["question_id"]: json.loads(l) for l in open(ROOT / "dev/questions.jsonl")}
with open(split / "questions.jsonl", "w") as f:
    for r in picked:
        f.write(json.dumps({**qs[r["question_id"][:-1]], "question_id": r["question_id"], "question": r["question"]}) + "\n")
with open(OUT / "swap-owner.jsonl", "w") as f:
    for r in picked:
        f.write(json.dumps({k: v for k, v in r.items() if k != "original_question"}, ensure_ascii=False) + "\n")
with open(OUT / "gold-swap-owner.jsonl", "w") as f:
    for r in picked:
        f.write(json.dumps({"question_id": r["question_id"], "question_type": "swap-owner", "abstain": True,
                            "answer": "", "aliases": [], "evidence": []}) + "\n")
for r in picked:
    print(f"{r['original_question']!r} -> {r['question']!r}")
print(len(picked), "questions,", len(hist_ids), "histories", file=sys.stderr)
