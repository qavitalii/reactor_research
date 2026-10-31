"""Arm A subset: questions where arm B is not auto-matched correct, was rechecked, or gold is unanswerable (offline eval only)."""
import json, sys
sys.path.insert(0, "/home/alex/code/personal/memory-challenge")
from score import answer_matched
from reactor.predictions import strip_labels
D = "/home/alex/code/personal/memory-challenge/artifacts/ab-20261030/"
gold = {json.loads(l)["question_id"]: json.loads(l) for l in open(D + "gold46.jsonl")}
results = {json.loads(l)["question_id"]: json.loads(l) for l in open(D + "armB2/results.jsonl")}
rechecked = {json.loads(l)["question_id"] for l in open(D + "armB2/attempts.jsonl")
             if '"rechecked": true' in l}
pick = set()
for qid, g in gold.items():
    r = results[qid]
    ok = (g["abstain"] == r["abstained"]) and (g["abstain"] or answer_matched(strip_labels(r["answer"]), g))
    if g["abstain"] or not ok or qid in rechecked:
        pick.add(qid)
with open(D + "holdout46.jsonl") as f, open(D + "armA-subset.jsonl", "w") as out:
    for line in f:
        if json.loads(line)["question_id"] in pick:
            out.write(line)
print(f"{len(pick)} disputed questions -> armA-subset.jsonl", file=sys.stderr)
